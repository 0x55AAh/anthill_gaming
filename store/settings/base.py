import os
from anthill.platform.conf.settings import *

# Build paths inside the application like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'gu@uycmwi44&amp;e%(#0(%jfcck71gn^v2%d^7789*!b74fi9(^dd'

DEBUG = False

ADMINS = (
    ('Lysenko Vladimir', 'wofkin@gmail.com'),
)

# Database uri example:
SQLALCHEMY_DATABASE_URI = 'postgres://anthill_store@/anthill_store'

LOCATION = 'http://localhost:9513'
BROKER = 'amqp://guest:guest@localhost:5672'

# ROUTES_CONF = 'store.routes'

UI_THEME = 'limitless'

STATIC_PATH = os.path.join(BASE_DIR, 'ui', 'themes', UI_THEME, 'static')
TEMPLATE_PATH = os.path.join(BASE_DIR, 'ui', 'themes', UI_THEME, 'templates')

# APPLICATION_CLASS = 'store.apps.AnthillApplication'
APPLICATION_NAME = 'store'
APPLICATION_VERBOSE_NAME = 'Store'
APPLICATION_DESCRIPTION = 'In-App Purchasing, with server validation'
APPLICATION_ICON_CLASS = 'icon-cart'
APPLICATION_COLOR = 'primary'

# SERVICE_CLASS = 'store.services.Service'

STATIC_URL = '/static/'

# UI_MODULE = 'store.ui'

CONTEXT_PROCESSORS = [

]

EMAIL_SUBJECT_PREFIX = '[Anthill: store] '

CACHES["default"]["LOCATION"] = "redis://localhost:6379/13"

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'anthill.framework.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'anthill.framework.utils.log.RequireDebugTrue',
        },
    },
    'formatters': {
        'anthill.server': {
            '()': 'anthill.framework.utils.log.ServerFormatter',
            'fmt': '%(color)s[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d]%(end_color)s %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S',
            'color': False,
        }
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'filters': ['require_debug_true'],
            'class': 'logging.StreamHandler',
            'formatter': 'anthill.server',
        },
        'anthill.server': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/anthill/store.log',
            'formatter': 'anthill.server',
            'maxBytes': 100 * 1000 * 1000,
            'backupCount': 10
        },
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'anthill.framework.utils.log.AdminEmailHandler'
        }
    },
    'loggers': {
        'anthill': {
            'handlers': ['console', 'mail_admins'],
            'level': 'INFO',
        },
        'anthill.application': {
            'handlers': ['anthill.server'],
            'level': 'INFO',
            'propagate': False
        },
        'tornado.access': {
            'handlers': ['anthill.server'],
            'level': 'INFO',
            'propagate': False
        },
        'tornado.application': {
            'handlers': ['anthill.server'],
            'level': 'INFO',
            'propagate': False
        },
        'tornado.general': {
            'handlers': ['anthill.server'],
            'level': 'INFO',
            'propagate': False
        },
        'celery': {
            'handlers': ['anthill.server'],
            'level': 'INFO',
            'propagate': False
        },
        'celery.worker': {
            'handlers': ['anthill.server'],
            'level': 'INFO',
            'propagate': False
        },
        'celery.task': {
            'handlers': ['anthill.server'],
            'level': 'INFO',
            'propagate': False
        },
        'celery.redirected': {
            'handlers': ['anthill.server'],
            'level': 'INFO',
            'propagate': False
        },
        'asyncio': {
            'handlers': ['anthill.server'],
            'level': 'INFO',
            'propagate': False
        },
    }
}


#########
# GEOIP #
#########

GEOIP_PATH = os.path.join(BASE_DIR, '../')

#########
# HTTPS #
#########

# HTTPS = {
#     'key_file': os.path.join(BASE_DIR, '../server.key'),
#     'crt_file': os.path.join(BASE_DIR, '../server.crt'),
# }
HTTPS = None


############
# GRAPHENE #
############

GRAPHENE = {
    'SCHEMA': 'store.api.v1.public.schema',
    'MIDDLEWARE': ()
}