

from ._test_settings import *



DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(TEST_DIR, "django.db")
    }
}
