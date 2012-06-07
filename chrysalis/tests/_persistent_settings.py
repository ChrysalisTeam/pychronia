

from ._test_settings import *

DEBUG = True

'''
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(TEST_DIR, "django.db")
    }
}
'''

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'chrysalis',
        'HOST': 'localhost',
        'USER': 'root', 
        'PASSWORD': '',
    }
}
