import logging.config



rpgweb_logging_config = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
        'instance': {
            'format': '%(asctime)s [%(levelname)s] %(name)s[%(game_instance_id)s]: %(message)s'
        },
    },
    'handlers': {
        'default': {
            'class':'logging.StreamHandler',
            'formatter': 'standard',
        },
        'instance': {
            'class':'logging.StreamHandler',
            'formatter': 'instance',
        },
    },
    'loggers': {
        '': {
            'handlers': ['default'],
            'level': 'INFO',
            'propagate': True
        },
        'rpgweb': {
            'handlers': ['instance'],
            'level': 'WARNING',
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
    }
}


logging.config.dictConfig(rpgweb_logging_config)
logging.disable(logging.WARNING) # global limit
