import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pychronia_settings')

import django_compat_patcher
django_compat_patcher.patch()

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()

