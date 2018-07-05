from anthill.framework.auth.hashers import make_password, check_password
from anthill.framework.db import db
from anthill.framework.utils import timezone
from anthill.framework.utils.crypto import salted_hmac
from anthill.framework.auth import password_validation


class AbstractUser(db.Model):
    __abstract__ = True

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    created = db.Column(db.DateTime, nullable=False, default=timezone.now)
    last_login = db.Column(db.DateTime, nullable=True, default=None)
    password = db.Column(db.String)

    # Stores the raw password if set_password() is called so that it can
    # be passed to password_changed() after the model is saved.
    _password = None

    def get_username(self):
        """Return the identifying username for this User."""
        return getattr(self, self.USERNAME_FIELD)

    def __str__(self):
        return self.get_username()

    @property
    def is_active(self):
        return True

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def set_password(self, raw_password):
        self.password = make_password(raw_password)
        self._password = raw_password

    def check_password(self, raw_password):
        """
        Return a boolean of whether the raw_password was correct.
        Handles hashing formats behind the scenes.
        """
        def setter(raw_password):
            self.set_password(raw_password)
            # Password hash upgrades shouldn't be considered password changes.
            self._password = None
            self.save()
        return check_password(raw_password, self.password, setter=setter)

    def save(self, *args, **kwargs):
        super(AbstractUser, self).save(*args, **kwargs)
        if self._password is not None:
            password_validation.password_changed(self._password, self)
            self._password = None

    def get_session_auth_hash(self):
        """Return an HMAC of the password field."""
        key_salt = "anthill.framework.auth.models.AbstractUser.get_session_auth_hash"
        return salted_hmac(key_salt, self.password).hexdigest()


class User(AbstractUser):
    """Default User model."""

    __tablename__ = 'users'

    username = db.Column(db.String(128), nullable=False, unique=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    USERNAME_FIELD = 'username'

    def __init__(self, username):
        self.username = username

    @classmethod
    def __declare_last__(cls):
        """Validation must be here."""

    @property
    def is_authenticated(self):
        return True


class Profile(db.Model):
    """Extra fields for User model."""

    __tablename__ = 'profiles'

    id = db.Column(db.Integer, primary_key=True)
    user = db.relationship(
        'User',
        backref=db.backref('profile', lazy='joined'),
        uselist=False
    )

    @classmethod
    def __declare_last__(cls):
        """Validation must be here."""


class AnonymousUser:
    id = None
    is_active = False
    username = ''

    def __str__(self):
        return 'AnonymousUser'

    def __eq__(self, other):
        return isinstance(other, self.__class__)

    def __hash__(self):
        return 1  # instances always return the same hash value

    @property
    def is_anonymous(self):
        return True

    @property
    def is_authenticated(self):
        return False

    def save(self):
        raise NotImplementedError("Anthill doesn't provide a DB representation for AnonymousUser.")

    def delete(self):
        raise NotImplementedError("Anthill doesn't provide a DB representation for AnonymousUser.")

    def set_password(self, raw_password):
        raise NotImplementedError("Anthill doesn't provide a DB representation for AnonymousUser.")

    def check_password(self, raw_password):
        raise NotImplementedError("Anthill doesn't provide a DB representation for AnonymousUser.")

    def get_username(self):
        return self.username
