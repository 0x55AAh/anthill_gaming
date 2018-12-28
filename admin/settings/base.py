from anthill.framework.utils.translation import translate_lazy as _
from anthill.platform.conf.settings import *
import os

# Build paths inside the application like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'dsuy#yg2#h+0msm)lja9sz(xtb)*a81215z#uyj3$im0^d1m$t'

DEBUG = False

ADMINS = (
    ('Lysenko Vladimir', 'wofkin@gmail.com'),
)

SQLALCHEMY_DATABASE_URI = 'postgres://anthill_admin@/anthill_admin'

# ROUTES_CONF = 'admin.routes'

LOCATION = 'http://localhost:9600'
BROKER = 'amqp://guest:guest@localhost:5672'

# APPLICATION_CLASS = 'admin.apps.AnthillApplication'
APPLICATION_NAME = 'admin'
APPLICATION_VERBOSE_NAME = _('Admin')

DEFAULT_HANDLER_CLASS = 'anthill.framework.handlers.Handler404'

# SERVICE_CLASS = 'admin.services.Service'

UI_THEME = 'limitless'

EMAIL_SUBJECT_PREFIX = '[Anthill: admin] '

STATIC_PATH = os.path.join(BASE_DIR, 'ui', 'themes', UI_THEME, 'static')
TEMPLATE_PATH = os.path.join(BASE_DIR, 'ui', 'themes', UI_THEME, 'templates')

LOCALE_PATH = os.path.join(BASE_DIR, 'locale')

STATIC_URL = '/static/'

# UI_MODULE = 'admin.ui'

CONTEXT_PROCESSORS = [
    'anthill.framework.context_processors.datetime',
    'admin.context_processors.main_sidebar',
    'admin.context_processors.metadata',
]

CACHES["default"]["LOCATION"] = "redis://localhost:6379/10"
CACHES["default"]["KEY_PREFIX"] = "anthill:admin"


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
            'formatter': 'anthill.server'
        },
        'anthill.server': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOGGING_ROOT_DIR, 'admin.log'),
            'formatter': 'anthill.server',
            'maxBytes': 100 * 1024 * 1024,  # 100 MiB
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


PUBLIC_API_URL = '/api/'


############
# GRAPHENE #
############

GRAPHENE = {
    'SCHEMA': 'admin.api.v1.public.schema',
    'MIDDLEWARE': ()
}


LOGIN_REDIRECT_URL = 'index'
