# -*- coding: utf-8 -*-
import logging.config

pychronia_logging_config = {
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
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
        },
        'game_instance': {
            'class': 'logging.StreamHandler',
            'formatter': 'game_instance',
        },
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler'
        }
    },
    'loggers': {
        '': {
            'handlers': ['default'],
            'level': 'INFO',
            'propagate': True
        },

        'py.warnings': {
            'handlers': [],
            'level': 'ERROR',  # this SILENCES warnings!
            'propagate': True
        },

        'pychronia_game': {
            'handlers': ['game_instance'],
            'level': 'INFO',
            'propagate': False
        },

        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },
        'django.security': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },
        'django.db.backends': {
            'handlers': [],
            'level': 'WARNING',
            'propagate': False
        },

        'txn': {  # ZODB transactions
            'handlers': [],
            'level': 'WARNING',
            'propagate': False
        },
        ## django.request is auto-configured to send admin emails when DEBUG=False ##
    }
}

logging.config.dictConfig(pychronia_logging_config)
logging.disable(logging.DEBUG)  # global limit
