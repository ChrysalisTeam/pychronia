#!/usr/bin/env python
"""
LOCAL-ONLY launcher (do not commit) for the legacy pychronia_cms stack against the local MariaDB "chryscms_local".

Usage:  .venv\Scripts\python.exe run_local_cms.py runserver 127.0.0.1:8000
"""
import os, sys

root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, root)

# Django 2.2 expects mysqlclient's bytes "_executed", PyMySQL 1.x gives str (crashes the DEBUG SQL logging);
# backport of the Django 3.0 implementation.
import pymysql
pymysql.install_as_MySQLdb()
from django.db.backends.mysql.operations import DatabaseOperations
from django.utils.encoding import force_str
DatabaseOperations.last_executed_query = \
    lambda self, cursor, sql, params: force_str(getattr(cursor, "_executed", None), errors="replace")

# django-cms 3.6 apphook resolvers use a dummy 'app_resolver' urlconf, which the Django 2.2 system checks
# (run by runserver, not by WSGI in prod) try to import.
from django.urls.resolvers import URLResolver
_original_check_custom_error_handlers = URLResolver._check_custom_error_handlers
URLResolver._check_custom_error_handlers = \
    lambda self: [] if self.urlconf_name == "app_resolver" else _original_check_custom_error_handlers(self)

# Same as pychronia_cms/tests/manage.py, but inlined so that sys.argv[0] stays this launcher,
# and the runserver autoreloader respawns it WITH the patches above
os.environ["DJANGO_SETTINGS_MODULE"] = "pychronia_cms.tests.persistent_mode_settings"
import setup_pychronia_env
from django.core.management import execute_from_command_line
execute_from_command_line(sys.argv)
