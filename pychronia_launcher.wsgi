# LEGACY WSGI file, for servers not yet using "config.wsgi:application" (equivalent, but needs the project to be installed via "uv sync")
import setup_pychronia_env

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()

