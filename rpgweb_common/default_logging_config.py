import logging.config



rpgweb_logging_config = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
        'game_instance': {
            'format': '%(asctime)s [%(levelname)s] %(name)s[%(game_instance_id)s]: %(message)s'
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
        'rpgweb': {
            'handlers': ['game_instance'],
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
        ## django.request is auto-configured to send admin emails when DEBUG=False ##
    }
}


logging.config.dictConfig(rpgweb_logging_config)
logging.disable(logging.WARNING) # global limit
