"""
WSGI entry point of both PROD sites ("config.wsgi:application"); the site is chosen by DJANGO_SETTINGS_MODULE, taken
from the real environment or else from the untracked ".env" file (eg. "config.settings.prod_cms" or
"config.settings.prod_game"), else the legacy "pychronia_settings" module is used.
"""

from config.settings._env import configure_settings_module

configure_settings_module(default="pychronia_settings")

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
