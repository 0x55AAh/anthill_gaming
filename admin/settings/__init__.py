import os

# Build paths inside the application like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'ADMIN_SERVICE_SECRET_KEY'

DEBUG = False

DATABASES = {
    'default': {
        'url': 'postgres://user:pass@localhost/ah_admin',
        'encoding': 'utf-8'
    }
}

ROUTES_CONF = 'admin.routes'

LOCATION = 'http://localhost:9500'
BROKER = 'amqp://guest:guest@localhost:5672'

APPLICATION_CLASS = 'admin.apps.AnthillApplication'
APPLICATION_NAME = 'admin'
APPLICATION_VERBOSE_NAME = 'Admin'
APPLICATION_DESCRIPTION = None
APPLICATION_ICON_CLASS = None

SERVICE_CLASS = 'admin.services.Service'

try:
    from anthill_platform.settings import *
except ImportError:
    pass

try:
    from .local import *
except ImportError:
    pass
