"""
    sqlalchemy
    ~~~~~~~~~~~~~~~~

    Adds basic SQLAlchemy support to your application.

    :copyright: (c) 2014 by Armin Ronacher, Daniel Neuhäuser.
    :license: BSD, see LICENSE for more details.
"""

import functools
import os
import sys
import time
import warnings
from math import ceil
from operator import itemgetter
from threading import Lock

import sqlalchemy
from sqlalchemy import event, inspect, orm
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.declarative import DeclarativeMeta, declarative_base
from sqlalchemy.orm.exc import UnmappedClassError
from sqlalchemy.orm.session import Session as SessionBase
from anthill.framework.http import Http404

from anthill.framework.apps.builder import app
from anthill.framework.core.signals import Namespace

from .model import Model
from six import string_types
from .model import DefaultMeta
import logging

logger = logging.getLogger('anthill.application')

__version__ = '2.3.2'

_timer = time.time


def itervalues(d):
    return iter(d.values())


_signals = Namespace()
models_committed = _signals.signal('models-committed')
before_models_committed = _signals.signal('before-models-committed')


def _make_table(db):
    def _make_table(*args, **kwargs):
        if len(args) > 1 and isinstance(args[1], db.Column):
            args = (args[0], db.metadata) + args[1:]
        info = kwargs.pop('info', None) or {}
        info.setdefault('bind_key', None)
        kwargs['info'] = info
        return sqlalchemy.Table(*args, **kwargs)

    return _make_table


def _set_default_query_class(d, cls):
    if 'query_class' not in d:
        d['query_class'] = cls


def _wrap_with_default_query_class(fn, cls):
    @functools.wraps(fn)
    def newfn(*args, **kwargs):
        _set_default_query_class(kwargs, cls)
        if "backref" in kwargs:
            backref = kwargs['backref']
            if isinstance(backref, string_types):
                backref = (backref, {})
            _set_default_query_class(backref[1], cls)
        return fn(*args, **kwargs)

    return newfn


def _include_sqlalchemy(obj, cls):
    for module in sqlalchemy, sqlalchemy.orm:
        for key in module.__all__:
            if not hasattr(obj, key):
                setattr(obj, key, getattr(module, key))
    # Note: obj.Table does not attempt to be a SQLAlchemy Table class.
    obj.Table = _make_table(obj)
    obj.relationship = _wrap_with_default_query_class(obj.relationship, cls)
    obj.relation = _wrap_with_default_query_class(obj.relation, cls)
    obj.dynamic_loader = _wrap_with_default_query_class(obj.dynamic_loader, cls)
    obj.event = event


class _DebugQueryTuple(tuple):
    statement = property(itemgetter(0))
    parameters = property(itemgetter(1))
    start_time = property(itemgetter(2))
    end_time = property(itemgetter(3))
    context = property(itemgetter(4))

    @property
    def duration(self):
        return self.end_time - self.start_time

    def __repr__(self):
        return '<query statement="%s" parameters=%r duration=%.03f>' % (
            self.statement,
            self.parameters,
            self.duration
        )


def _calling_context(app_path):
    frm = sys._getframe(1)
    while frm.f_back is not None:
        name = frm.f_globals.get('__name__')
        if name and (name == app_path or name.startswith(app_path + '.')):
            funcname = frm.f_code.co_name
            return '%s:%s (%s)' % (
                frm.f_code.co_filename,
                frm.f_lineno,
                funcname
            )
        frm = frm.f_back
    return '<unknown>'


class SignallingSession(SessionBase):
    """The signalling session is the default session that SQLAlchemy
    uses. It extends the default session system with bind selection and
    modification tracking.

    If you want to use a different session you can override the
    :meth:`SQLAlchemy.create_session` function.

    .. versionadded:: 2.0

    .. versionadded:: 2.1
        The `binds` option was added, which allows a session to be joined
        to an external transaction.
    """

    def __init__(self, db, autocommit=False, autoflush=True, **options):
        #: The application that this session belongs to.
        self.app = app = db.get_app()
        track_modifications = getattr(app.config, 'SQLALCHEMY_TRACK_MODIFICATIONS')
        bind = options.pop('bind', None) or db.engine
        binds = options.pop('binds', db.get_binds(app))

        if track_modifications is None or track_modifications:
            _SessionSignalEvents.register(self)

        SessionBase.__init__(
            self, autocommit=autocommit, autoflush=autoflush,
            bind=bind, binds=binds, **options
        )

    def get_bind(self, mapper=None, clause=None):
        # mapper is None if someone tries to just get a connection
        if mapper is not None:
            info = getattr(mapper.mapped_table, 'info', {})
            bind_key = info.get('bind_key')
            if bind_key is not None:
                state = get_state(self.app)
                return state.db.get_engine(self.app, bind=bind_key)
        return SessionBase.get_bind(self, mapper, clause)


class _SessionSignalEvents:
    @classmethod
    def register(cls, session):
        if not hasattr(session, '_model_changes'):
            session._model_changes = {}

        event.listen(session, 'before_flush', cls.record_ops)
        event.listen(session, 'before_commit', cls.record_ops)
        event.listen(session, 'before_commit', cls.before_commit)
        event.listen(session, 'after_commit', cls.after_commit)
        event.listen(session, 'after_rollback', cls.after_rollback)

    @classmethod
    def unregister(cls, session):
        if hasattr(session, '_model_changes'):
            del session._model_changes

        event.remove(session, 'before_flush', cls.record_ops)
        event.remove(session, 'before_commit', cls.record_ops)
        event.remove(session, 'before_commit', cls.before_commit)
        event.remove(session, 'after_commit', cls.after_commit)
        event.remove(session, 'after_rollback', cls.after_rollback)

    @staticmethod
    def record_ops(session, flush_context=None, instances=None):
        try:
            d = session._model_changes
        except AttributeError:
            return

        for targets, operation in ((session.new, 'insert'), (session.dirty, 'update'), (session.deleted, 'delete')):
            for target in targets:
                state = inspect(target)
                key = state.identity_key if state.has_identity else id(target)
                d[key] = (target, operation)

    @staticmethod
    def before_commit(session):
        try:
            d = session._model_changes
        except AttributeError:
            return

        if d:
            before_models_committed.send(session.app, changes=list(d.values()))

    @staticmethod
    def after_commit(session):
        try:
            d = session._model_changes
        except AttributeError:
            return

        if d:
            models_committed.send(session.app, changes=list(d.values()))
            d.clear()

    @staticmethod
    def after_rollback(session):
        try:
            d = session._model_changes
        except AttributeError:
            return

        d.clear()


class Pagination:
    """
    Internal helper class returned by :meth:`BaseQuery.paginate`. You
    can also construct it from any other SQLAlchemy query object if you are
    working with other libraries. Additionally it is possible to pass `None`
    as query object in which case the :meth:`prev` and :meth:`next` will
    no longer work.
    """

    def __init__(self, query, page, per_page, total, items):
        #: the unlimited query object that was used to create this
        #: pagination object.
        self.query = query
        #: the current page number (1 indexed)
        self.page = page
        #: the number of items to be displayed on a page.
        self.per_page = per_page
        #: the total number of items matching the query
        self.total = total
        #: the items for the current page
        self.items = items

    @property
    def pages(self):
        """The total number of pages."""
        if self.per_page == 0:
            pages = 0
        else:
            pages = int(ceil(self.total / float(self.per_page)))
        return pages

    def prev(self, error_out=False):
        """Returns a :class:`Pagination` object for the previous page."""
        assert self.query is not None, 'a query object is required ' \
                                       'for this method to work'
        return self.query.paginate(self.page - 1, self.per_page, error_out)

    @property
    def prev_num(self):
        """Number of the previous page."""
        if not self.has_prev:
            return None
        return self.page - 1

    @property
    def has_prev(self):
        """True if a previous page exists."""
        return self.page > 1

    def next(self, error_out=False):
        """Returns a :class:`Pagination` object for the next page."""
        assert self.query is not None, 'a query object is required ' \
                                       'for this method to work'
        return self.query.paginate(self.page + 1, self.per_page, error_out)

    @property
    def has_next(self):
        """True if a next page exists."""
        return self.page < self.pages

    @property
    def next_num(self):
        """Number of the next page."""
        if not self.has_next:
            return None
        return self.page + 1

    def iter_pages(self, left_edge=2, left_current=2, right_current=5, right_edge=2):
        """
        Iterates over the page numbers in the pagination. The four
        parameters control the thresholds how many numbers should be produced
        from the sides. Skipped page numbers are represented as `None`.
        """
        last = 0
        for num in range(1, self.pages + 1):
            if num <= left_edge or (self.page + right_current > num > self.page - left_current - 1) \
                    or num > self.pages - right_edge:
                if last + 1 != num:
                    yield None
                yield num
                last = num


class BaseQuery(orm.Query):
    """
    SQLAlchemy :class:`~sqlalchemy.orm.query.Query` subclass
    with convenience methods for querying in a web application.

    This is the default :attr:`~Model.query` object used for models,
    and exposed as :attr:`~SQLAlchemy.Query`.
    Override the query class for an individual model by subclassing this
    and setting :attr:`~Model.query_class`.
    """

    def to_sql(self):
        """Return a literal SQL representation of the query."""
        dialect = self.session.bind.dialect
        return str(self.statement.compile(dialect=dialect))

    def get_or_404(self, ident):
        """
        Like :meth:`get` but aborts with 404 if not found instead of returning ``None``.
        """
        rv = self.get(ident)
        if rv is None:
            raise Http404
        return rv

    def first_or_404(self):
        """
        Like :meth:`first` but aborts with 404 if not found instead of returning ``None``.
        """
        rv = self.first()
        if rv is None:
            raise Http404
        return rv

    def paginate(self, request, page=None, per_page=None, error_out=True, max_per_page=None):
        """
        Returns ``per_page`` items from page ``page``.

        If ``page`` or ``per_page`` are ``None``, they will be retrieved from
        the request query. If ``max_per_page`` is specified, ``per_page`` will
        be limited to that value. If there is no request or they aren't in the
        query, they default to 1 and 20 respectively.

        When ``error_out`` is ``True`` (default), the following rules will
        cause a 404 response:

        * No items are found and ``page`` is not 1.
        * ``page`` is less than 1, or ``per_page`` is negative.
        * ``page`` or ``per_page`` are not ints.

        When ``error_out`` is ``False``, ``page`` and ``per_page`` default to
        1 and 20 respectively.

        Returns a :class:`Pagination` object.
        """

        if request:
            if page is None:
                try:
                    page = int(request.arguments.get('page', [1])[0])
                except (TypeError, ValueError, IndexError):
                    if error_out:
                        raise Http404
                    page = 1

            if per_page is None:
                try:
                    per_page = int(request.arguments.get('per_page', [20])[0])
                except (TypeError, ValueError, IndexError):
                    if error_out:
                        raise Http404
                    per_page = 20
        else:
            if page is None:
                page = 1

            if per_page is None:
                per_page = 20

        if max_per_page is not None:
            per_page = min(per_page, max_per_page)

        if page < 1:
            if error_out:
                raise Http404
            else:
                page = 1

        if per_page < 0:
            if error_out:
                raise Http404
            else:
                per_page = 20

        items = self.limit(per_page).offset((page - 1) * per_page).all()

        if not items and page != 1 and error_out:
            raise Http404

        # No need to count if we're on the first page and there are fewer
        # items than we expected.
        if page == 1 and len(items) < per_page:
            total = len(items)
        else:
            total = self.order_by(None).count()

        return Pagination(self, page, per_page, total, items)


class _QueryProperty(object):
    def __init__(self, sa):
        self.sa = sa

    def __get__(self, obj, type):
        try:
            mapper = orm.class_mapper(type)
            if mapper:
                return type.query_class(mapper, session=self.sa.session())
        except UnmappedClassError:
            return None


def _record_queries(app):
    if app.debug:
        return True
    rq = getattr(app.config, 'SQLALCHEMY_RECORD_QUERIES', None)
    if rq is not None:
        return rq
    return bool(getattr(app.config, 'TESTING', False))


class _EngineConnector(object):
    def __init__(self, sa, app, bind=None):
        self._sa = sa
        self._app = app
        self._engine = None
        self._connected_for = None
        self._bind = bind
        self._lock = Lock()

    def get_uri(self):
        if self._bind is None:
            return getattr(self._app.config, 'SQLALCHEMY_DATABASE_URI', None)
        binds = getattr(self._app.config, 'SQLALCHEMY_BINDS', None) or ()
        assert self._bind in binds, \
            'Bind %r is not specified. Set it in the SQLALCHEMY_BINDS ' \
            'configuration variable' % self._bind
        return binds[self._bind]

    def get_engine(self):
        with self._lock:
            uri = self.get_uri()
            echo = getattr(self._app.config, 'SQLALCHEMY_ECHO', False)
            if (uri, echo) == self._connected_for:
                return self._engine
            info = make_url(uri)
            options = {'convert_unicode': True}
            self._sa.apply_pool_defaults(self._app, options)
            self._sa.apply_driver_hacks(self._app, info, options)
            if echo:
                options['echo'] = echo
            self._engine = rv = sqlalchemy.create_engine(info, **options)
            if _record_queries(self._app):
                pass
            self._connected_for = (uri, echo)
            return rv


def get_state(app):
    """Gets the state for the application."""
    assert 'sqlalchemy' in app.extensions, \
        'The sqlalchemy extension was not registered to the current ' \
        'application.  Please make sure to call init_app() first.'
    return app.extensions['sqlalchemy']


class _SQLAlchemyState(object):
    """Remembers configuration for the (db, app) tuple."""

    def __init__(self, db):
        self.db = db
        self.connectors = {}


class SQLAlchemy(object):
    """
    This class is used to control the SQLAlchemy integration to one
    or more Flask applications. Depending on how you initialize the
    object it is usable right away or will attach as needed to a
    Flask application.

    There are two usage modes which work very similarly. One is binding
    the instance to a very specific Flask application::

        app = Flask(__name__)
        db = SQLAlchemy(app)

    The second possibility is to create the object once and configure the
    application later to support it::

        db = SQLAlchemy()

        def create_app():
            app = Flask(__name__)
            db.init_app(app)
            return app

    The difference between the two is that in the first case methods like
    :meth:`create_all` and :meth:`drop_all` will work all the time but in
    the second case a :meth:`flask.Flask.app_context` has to exist.

    By default Flask-SQLAlchemy will apply some backend-specific settings
    to improve your experience with them.  As of SQLAlchemy 0.6 SQLAlchemy
    will probe the library for native unicode support. If it detects
    unicode it will let the library handle that, otherwise do that itself.
    Sometimes this detection can fail in which case you might want to set
    ``use_native_unicode`` (or the ``SQLALCHEMY_NATIVE_UNICODE`` configuration
    key) to ``False``.  Note that the configuration key overrides the
    value you pass to the constructor.

    This class also provides access to all the SQLAlchemy functions and classes
    from the :mod:`sqlalchemy` and :mod:`sqlalchemy.orm` modules. So you can
    declare models like this::

        class User(db.Model):
            username = db.Column(db.String(80), unique=True)
            pw_hash = db.Column(db.String(80))

    You can still use :mod:`sqlalchemy` and :mod:`sqlalchemy.orm` directly, but
    note that Flask-SQLAlchemy customizations are available only through an
    instance of this :class:`SQLAlchemy` class.  Query classes default to
    :class:`BaseQuery` for `db.Query`, `db.Model.query_class`, and the default
    query_class for `db.relationship` and `db.backref`. If you use these
    interfaces through :mod:`sqlalchemy` and :mod:`sqlalchemy.orm` directly,
    the default query class will be that of :mod:`sqlalchemy`.

    .. admonition:: Check types carefully

       Don't perform type or `isinstance` checks against `db.Table`, which
       emulates `Table` behavior but is not a class. `db.Table` exposes the
       `Table` interface, but is a function which allows omission of metadata.

    The ``session_options`` parameter, if provided, is a dict of parameters
    to be passed to the session constructor. See :class:`~sqlalchemy.orm.session.Session`
    for the standard options.
    """

    #: Default query class used by :attr:`Model.query` and other queries.
    #: Customize this by passing ``query_class`` to :func:`SQLAlchemy`.
    #: Defaults to :class:`BaseQuery`.
    Query = None

    def __init__(self, app=None, use_native_unicode=True, session_options=None,
                 metadata=None, query_class=BaseQuery, model_class=Model):

        self.use_native_unicode = use_native_unicode
        self.Query = query_class
        self.session = self.create_scoped_session(session_options)
        self.Model = self.make_declarative_base(model_class, metadata)
        self._engine_lock = Lock()
        self.app = app

        _include_sqlalchemy(self, query_class)

        if app is not None:
            self.init_app(app)

    @property
    def metadata(self):
        """The metadata associated with ``db.Model``."""

        return self.Model.metadata

    def create_scoped_session(self, options=None):
        """
        Create a :class:`~sqlalchemy.orm.scoping.scoped_session`
        on the factory from :meth:`create_session`.

        An extra key ``'scopefunc'`` can be set on the ``options`` dict to
        specify a custom scope function.  If it's not provided, Flask's app
        context stack identity is used. This will ensure that sessions are
        created and removed with the request/response cycle, and should be fine
        in most cases.

        :param options: dict of keyword arguments passed to session class  in
        ``create_session``
        """

        if options is None:
            options = {}

        scopefunc = options.pop('scopefunc', self.get_app(app).__ident_func__)
        options.setdefault('query_cls', self.Query)
        return orm.scoped_session(self.create_session(options), scopefunc=scopefunc)

    def create_session(self, options):
        """
        Create the session factory used by :meth:`create_scoped_session`.

        The factory **must** return an object that SQLAlchemy recognizes as a session,
        or registering session events may raise an exception.

        Valid factories include a :class:`~sqlalchemy.orm.session.Session`
        class or a :class:`~sqlalchemy.orm.session.sessionmaker`.

        The default implementation creates a ``sessionmaker`` for :class:`SignallingSession`.

        :param options: dict of keyword arguments passed to session class
        """

        return orm.sessionmaker(class_=SignallingSession, db=self, **options)

    def make_declarative_base(self, model, metadata=None):
        """
        Creates the declarative base that all models will inherit from.

        :param model: base model class (or a tuple of base classes) to pass
            to :func:`~sqlalchemy.ext.declarative.declarative_base`. Or a class
            returned from ``declarative_base``, in which case a new base class
            is not created.
        :param: metadata: :class:`~sqlalchemy.MetaData` instance to use, or
            none to use SQLAlchemy's default.
        """
        if not isinstance(model, DeclarativeMeta):
            model = declarative_base(
                cls=model,
                name='Model',
                metadata=metadata,
                metaclass=DefaultMeta
            )

        # if user passed in a declarative base and a metaclass for some reason,
        # make sure the base uses the metaclass
        if metadata is not None and model.metadata is not metadata:
            model.metadata = metadata

        if not getattr(model, 'query_class', None):
            model.query_class = self.Query

        model.query = _QueryProperty(self)
        return model

    def init_app(self, app):
        """
        This callback can be used to initialize an application for the
        use with this database setup. Never use a database in the context
        of an application not initialized that way or connections will leak.
        """
        if (
                not getattr(app.config, 'SQLALCHEMY_DATABASE_URI', None) and
                not getattr(app.config, 'SQLALCHEMY_BINDS', None)
        ):
            warnings.warn(
                'Neither SQLALCHEMY_DATABASE_URI nor SQLALCHEMY_BINDS is set. '
                'Defaulting SQLALCHEMY_DATABASE_URI to "sqlite:///:memory:".'
            )

        if getattr(app.config, 'SQLALCHEMY_TRACK_MODIFICATIONS') is None:
            warnings.warn(
                'SQLALCHEMY_TRACK_MODIFICATIONS adds significant overhead and '
                'will be disabled by default in the future. Set it to True '
                'or False to suppress this warning.'
            )

        app.extensions['sqlalchemy'] = _SQLAlchemyState(self)
        logger.debug('SQLAlchemy ext installed.')

        def shutdown_session(response_or_exc):
            if getattr(app.config, 'SQLALCHEMY_COMMIT_ON_TEARDOWN', None):
                if response_or_exc is None:
                    self.session.commit()

            self.session.remove()
            return response_or_exc

    def apply_pool_defaults(self, app, options):
        def _setdefault(optionkey, configkey):
            value = getattr(app.config, configkey, None)
            if value is not None:
                options[optionkey] = value

        _setdefault('pool_size', 'SQLALCHEMY_POOL_SIZE')
        _setdefault('pool_timeout', 'SQLALCHEMY_POOL_TIMEOUT')
        _setdefault('pool_recycle', 'SQLALCHEMY_POOL_RECYCLE')
        _setdefault('max_overflow', 'SQLALCHEMY_MAX_OVERFLOW')

    def apply_driver_hacks(self, app, info, options):
        """
        This method is called before engine creation and used to inject
        driver specific hacks into the options. The `options` parameter is
        a dictionary of keyword arguments that will then be used to call
        the :func:`sqlalchemy.create_engine` function.

        The default implementation provides some saner defaults for things
        like pool sizes for MySQL and sqlite. Also it injects the setting of
        `SQLALCHEMY_NATIVE_UNICODE`.
        """
        if info.drivername.startswith('mysql'):
            info.query.setdefault('charset', 'utf8')
            if info.drivername != 'mysql+gaerdbms':
                options.setdefault('pool_size', 10)
                options.setdefault('pool_recycle', 7200)
        elif info.drivername == 'sqlite':
            pool_size = options.get('pool_size')
            detected_in_memory = False
            if info.database in (None, '', ':memory:'):
                detected_in_memory = True
                from sqlalchemy.pool import StaticPool
                options['poolclass'] = StaticPool
                if 'connect_args' not in options:
                    options['connect_args'] = {}
                options['connect_args']['check_same_thread'] = False

                # we go to memory and the pool size was explicitly set
                # to 0 which is fail.  Let the user know that
                if pool_size == 0:
                    raise RuntimeError('SQLite in memory database with an '
                                       'empty queue not possible due to data '
                                       'loss.')
            # if pool size is None or explicitly set to 0 we assume the
            # user did not want a queue for this sqlite connection and
            # hook in the null pool.
            elif not pool_size:
                from sqlalchemy.pool import NullPool
                options['poolclass'] = NullPool

            # if it's not an in memory database we make the path absolute.
            if not detected_in_memory:
                info.database = os.path.join(app.root_path, info.database)

        unu = getattr(app.config, 'SQLALCHEMY_NATIVE_UNICODE', None)
        if unu is None:
            unu = self.use_native_unicode
        if not unu:
            options['use_native_unicode'] = False

    @property
    def engine(self):
        """
        Gives access to the engine. If the database configuration is bound
        to a specific application (initialized with an application) this will
        always return a database connection. If however the current application
        is used this might raise a :exc:`RuntimeError` if no application is
        active at the moment.
        """
        return self.get_engine()

    def make_connector(self, app=None, bind=None):
        """Creates the connector for a given state and bind."""
        return _EngineConnector(self, self.get_app(app), bind)

    def get_engine(self, app=None, bind=None):
        """Returns a specific engine."""

        app = self.get_app(app)
        state = get_state(app)

        with self._engine_lock:
            connector = state.connectors.get(bind)

            if connector is None:
                connector = self.make_connector(app, bind)
                state.connectors[bind] = connector

            return connector.get_engine()

    def get_app(self, reference_app=None):
        """
        Helper method that implements the logic to look up an application.
        """

        if reference_app is not None:
            return reference_app

        if app:
            return app

        if self.app is not None:
            return self.app

        raise RuntimeError(
            'No application found. '
            'Either work inside a view function or push an application context.'
        )

    def get_tables_for_bind(self, bind=None):
        """Returns a list of all tables relevant for a bind."""
        result = []
        for table in itervalues(self.Model.metadata.tables):
            if table.info.get('bind_key') == bind:
                result.append(table)
        return result

    def get_binds(self, app=None):
        """
        Returns a dictionary with a table->engine mapping.

        This is suitable for use of sessionmaker(binds=db.get_binds(app)).
        """
        app = self.get_app(app)
        binds = [None] + list(getattr(app.config, 'SQLALCHEMY_BINDS', ()))
        retval = {}
        for bind in binds:
            engine = self.get_engine(app, bind)
            tables = self.get_tables_for_bind(bind)
            retval.update(dict((table, engine) for table in tables))
        return retval

    def _execute_for_all_tables(self, app, bind, operation, skip_tables=False):
        app = self.get_app(app)

        if bind == '__all__':
            binds = [None] + list(getattr(app.config, 'SQLALCHEMY_BINDS', ()))
        elif isinstance(bind, string_types) or bind is None:
            binds = [bind]
        else:
            binds = bind

        for bind in binds:
            extra = {}
            if not skip_tables:
                tables = self.get_tables_for_bind(bind)
                extra['tables'] = tables
            op = getattr(self.Model.metadata, operation)
            op(bind=self.get_engine(app, bind), **extra)

    def create_all(self, bind='__all__', app=None):
        """Creates all tables."""
        self._execute_for_all_tables(app, bind, 'create_all')

    def drop_all(self, bind='__all__', app=None):
        """Drops all tables."""
        self._execute_for_all_tables(app, bind, 'drop_all')

    def reflect(self, bind='__all__', app=None):
        """Reflects tables from the database."""
        self._execute_for_all_tables(app, bind, 'reflect', skip_tables=True)

    def __repr__(self):
        return '<%s engine=%r>' % (
            self.__class__.__name__,
            self.engine.url if self.app or app else None
        )
