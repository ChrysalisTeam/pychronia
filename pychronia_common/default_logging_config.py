# -*- coding: utf-8 -*-
import logging.config


pychronia_logging_config = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
        'game_instance': {
            'format': '%(asctime)s [%(levelname)s] %(name)s[%(game_instance_id)s:%(real_username)s]: %(message)s'
        },
    },
    'handlers': {
        'default': {
            'class':'logging.StreamHandler',
            'formatter': 'standard',
        },
        'game_instance': {
            'class':'logging.StreamHandler',
            'formatter': 'game_instance',
        },
    },
    'loggers': {
        '': {
            'handlers': ['default'],
            'level': 'INFO',
            'propagate': True
        },
        'pychronia_game': {
            'handlers': ['game_instance'],
            'level': 'INFO',
            'propagate': False
        },
        'django.db.backends': {
            'handlers': [],
            'level': 'WARNING',
            'propagate': False
        },
        'txn': { # ZODB transactions
            'handlers': [],
            'level': 'WARNING',
            'propagate': False
        },
        ## django.request is auto-configured to send admin emails when DEBUG=False ##
    }
}


logging.config.dictConfig(pychronia_logging_config)
logging.disable(logging.DEBUG) # global limit

'''
DEFAULT_LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'filters': ['require_debug_true'],
            'class': 'logging.StreamHandler',
        },
        'null': {
            'class': 'logging.NullHandler',
        },
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler'
        }
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
        },
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': False,
        },
        'py.warnings': {
            'handlers': ['console'],
        },
    }
}
'''
