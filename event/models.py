# For more details, see
# http://docs.sqlalchemy.org/en/latest/orm/tutorial.html#declare-a-mapping
from anthill.framework.db import db, ma
from anthill.framework.utils import timezone
from anthill.framework.utils.asynchronous import as_future
from anthill.framework.utils.translation import translate as _
from anthill.platform.api.internal import InternalAPIMixin
from anthill.platform.core.celery import app as celery_app
from sqlalchemy_utils.types import JSONType, UUIDType, ChoiceType
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.event import listens_for
from sqlalchemy.types import TypeDecorator, VARCHAR
from celery.worker.control import revoke
from celery.schedules import crontab
from celery.beat import Scheduler
from tornado.ioloop import IOLoop
from typing import Optional
from datetime import timedelta
import enum
import logging
import json
import re
import random


logger = logging.getLogger('anthill.application')


EVENT_PARTICIPATION_STATUS_CHANGED = 'EVENT_PARTICIPATION_STATUS_CHANGED'


@enum.unique
class EventStatus(enum.Enum):
    STARTED = 0
    FINISHED = 1


class EventCategory(db.Model):
    __tablename__ = 'event_categories'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.String(512), nullable=False)
    payload = db.Column(JSONType, nullable=False, default={})
    events = db.relationship('Event', backref='category')
    generators = db.relationship('EventGenerator', backref='category')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.Schema = self.get_schema_class()

    @classmethod
    def get_schema_class(cls):
        class _Schema(ma.Schema):
            class Meta:
                model = cls
                fields = ('id', 'name', 'description', 'payload')

        return _Schema


class Event(db.Model):
    __tablename__ = 'events'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    category_id = db.Column(db.Integer, db.ForeignKey('event_categories.id'))
    generator_id = db.Column(db.Integer, db.ForeignKey('event_generators.id'))
    created_at = db.Column(db.DateTime, nullable=False, default=timezone.now)
    start_at = db.Column(db.DateTime, nullable=False)
    finish_at = db.Column(db.DateTime, nullable=False)
    payload = db.Column(JSONType, nullable=False, default={})
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    on_start_task_id = db.Column(UUIDType(binary=False))
    on_finish_task_id = db.Column(UUIDType(binary=False))

    participations = db.relationship('EventParticipation', backref='event')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.Schema = self.get_schema_class()

    @classmethod
    def get_schema_class(cls):
        class _Schema(ma.Schema):
            class Meta:
                model = cls
                fields = ('id', 'start_at', 'finish_at', 'payload', 'category')

        return _Schema

    def dumps(self) -> dict:
        return self.Schema().dump(self).data

    @hybrid_property
    def active(self) -> bool:
        return self.finish_at > timezone.now() >= self.on_start() and self.is_active

    @hybrid_property
    def started(self) -> bool:
        return self.start_at >= timezone.now()

    @hybrid_property
    def finished(self) -> bool:
        return self.finish_at < timezone.now()

    @hybrid_property
    def start_in(self) -> Optional[timedelta]:
        if self.start_at >= timezone.now():
            return self.start_at - timezone.now()

    @hybrid_property
    def finish_in(self) -> Optional[timedelta]:
        if self.finish_at >= timezone.now():
            return self.finish_at - timezone.now()

    async def on_start(self) -> None:
        # TODO: bulk get_users request
        for p in self.participations:
            user = await p.get_user()
            msg = {
                'type': EventStatus.STARTED.name,
                'data': self.dumps()
            }
            await user.send_message(message=json.dumps(msg),
                                    content_type='application/json')

    async def on_finish(self) -> None:
        # TODO: bulk get_users request
        for p in self.participations:
            user = await p.get_user()
            msg = {
                'type': EventStatus.FINISHED.name,
                'data': self.dumps()
            }
            await user.send_message(message=json.dumps(msg),
                                    content_type='application/json')

    @as_future
    def join(self, user_id: str) -> None:
        EventParticipation.create(user_id=user_id, event_id=self.id, status='joined')

    @as_future
    def leave(self, user_id: str) -> None:
        kwargs = dict(user_id=user_id, event_id=self.id, status='joined')
        p = EventParticipation.query.filter_by(**kwargs).first()
        if p is not None:
            p.status = 'leaved'
            p.save()
        else:
            logger.warning('User (%s) is not joined to event (%s), '
                           'so cannot leave.' % (user_id, self.id))


@listens_for(Event, 'after_insert')
def on_event_create(mapper, connection, target):
    from event import tasks

    if not target.is_active:
        return

    if target.start_in:
        task = tasks.on_event_start.apply_async(
            (target.id,), countdown=target.start_in.seconds)
        target.on_start_task_id = task.id

    if target.finish_in:
        task = tasks.on_event_finish.apply_async(
            (target.id,), countdown=target.finish_in.seconds)
        target.on_finish_task_id = task.id


@listens_for(Event, 'after_update')
def on_event_update(mapper, connection, target):
    from event import tasks

    if target.on_start_task_id:
        revoke(celery_app, target.on_start_task_id)
    if target.on_finish_task_id:
        revoke(celery_app, target.on_finish_task_id)

    if not target.is_active:
        return

    if target.start_in:
        task = tasks.on_event_start.apply_async(
            (target.id,), countdown=target.start_in.seconds)
        target.on_start_task_id = task.id

    if target.finish_in:
        task = tasks.on_event_finish.apply_async(
            (target.id,), countdown=target.finish_in.seconds)
        target.on_finish_task_id = task.id


@listens_for(Event, 'after_delete')
def on_event_delete(mapper, connection, target):
    if target.on_start_task_id:
        revoke(celery_app, target.on_start_task_id)
    if target.on_finish_task_id:
        revoke(celery_app, target.on_finish_task_id)


class EventParticipation(InternalAPIMixin, db.Model):
    __tablename__ = 'event_participations'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'event_id'),
    )

    STATUSES = (
        ('joined', _('Joined')),
        ('leaved', _('Leaved'))
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    created_at = db.Column(db.DateTime, nullable=False, default=timezone.now)
    status = db.Column(ChoiceType(STATUSES))
    payload = db.Column(JSONType, nullable=False, default={})
    user_id = db.Column(db.Integer, nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.Schema = self.get_schema_class()

    @classmethod
    def get_schema_class(cls):
        class _Schema(ma.Schema):
            class Meta:
                model = self.__class__
                fields = ('payload', 'created_at', 'status', 'event')

        return _Schema

    def dumps(self) -> dict:
        return self.Schema().dump(self).data

    async def on_status_changed(self) -> None:
        user = await self.get_user()
        msg = {
            'type': EVENT_PARTICIPATION_STATUS_CHANGED,
            'data': self.dumps()
        }
        await user.send_message(message=json.dumps(msg),
                                content_type='application/json')

    async def get_user(self):
        return await self.internal_request('login', 'get_user', user_id=self.user_id)


@listens_for(EventParticipation.status, 'set', active_history=True)
def on_event_participation_status_changed(target, value, oldvalue, initiator):
    if value != oldvalue:
        IOLoop.current().add_callback(target.on_status_changed)


class CrontabField(TypeDecorator):
    impl = VARCHAR(128)

    def process_literal_param(self, value, dialect):
        pass

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = re.split(r'\s+', value)
            if len(value) != 5:
                raise ValueError('Illegal crontab field value: %s' % value)
            return value

    def process_result_value(self, value, dialect):
        if value is not None:
            if len(value) != 5:
                raise ValueError('Illegal crontab field value: %s' % value)
            return ' '.join(value)

    @property
    def python_type(self):
        return self.impl.type.python_type


class EventGenerator(db.Model):
    __tablename__ = 'event_generators'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    pool_id = db.Column(db.Integer, db.ForeignKey('event_generator_pools.id'))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    last_run_at = db.Column(db.DateTime)
    total_run_count = db.Column(db.Integer, nullable=False, default=0)
    generator_plan = db.Column(CrontabField)

    # Event parameters
    category_id = db.Column(db.Integer, db.ForeignKey('event_categories.id'))
    start_at = db.Column(db.DateTime, nullable=False)
    finish_at = db.Column(db.DateTime, nullable=False)
    payload = db.Column(JSONType, nullable=False, default={})

    events = db.relationship('Event', backref='generator')

    @as_future
    def next(self, is_active=True) -> Event:
        self.last_run_at = timezone.now()
        self.total_run_count += 1
        self.save()
        kwargs = {
            'category_id': self.category_id,
            'start_at': self.start_at,
            'finish_at': self.finish_at,
            'payload': self.payload,
            'is_active': is_active,
            'generator_id': self.id,
        }
        return Event.create(**kwargs)

    @hybrid_property
    def plan(self):
        if self.pool_id is not None:
            return self.pool.plan or self.generator_plan
        return self.generator_plan

    @hybrid_property
    def active(self) -> bool:
        if self.pool_id is not None:
            return self.pool.is_active
        return self.is_active


class EventGeneratorPool(db.Model):
    __tablename__ = 'event_generator_pools'

    RUN_SCHEMES = (
        ('all', _('All')),
        ('any', _('Any')),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(128), nullable=False, unique=True)
    description = db.Column(db.String(512), nullable=False)
    generators = db.relationship('EventGenerator', backref='pool')
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_follow_generator_plan = db.Column(db.Boolean, nullable=False, default=False)
    run_scheme = db.Column(ChoiceType(RUN_SCHEMES), default='any')
    last_run_at = db.Column(db.DateTime)
    total_run_count = db.Column(db.Integer, nullable=False, default=0)
    pool_plan = db.Column(CrontabField)

    async def run(self) -> None:
        self.last_run_at = timezone.now()
        self.total_run_count += 1
        generators = await self.prepare_generators()
        await self._run(generators)

    @as_future
    def _run(self, generators, is_active=True) -> None:
        now = timezone.now()
        events = []

        for gen in generators:
            gen.last_run_at = now
            gen.total_run_count += 1
            kwargs = {
                'category_id': gen.category_id,
                'start_at': gen.start_at,
                'finish_at': gen.finish_at,
                'payload': gen.payload,
                'is_active': is_active,
                'generator_id': gen.id
            }
            events.append(Event(**kwargs))

        db.session.bulk_save_objects(events)
        db.session.commit()

    @as_future
    def prepare_generators(self) -> list:
        generators = self.generators.query.filter_by(active=True).all()
        if self.run_scheme is 'any':
            return [random.choice(generators)]
        elif self.run_scheme is 'all':
            return generators
        return []

    @hybrid_property
    def plan(self):
        if not self.is_follow_generator_plan:
            return self.pool_plan


class EventGeneratorSheduler(Scheduler):
    pass


class EventGeneratorPoolSheduler(Scheduler):
    pass
