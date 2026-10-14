#!/usr/bin/env python
"""
LOCAL-ONLY launcher (do not commit) for the legacy pychronia_cms stack against the local MariaDB "chryscms_local".

Usage:  .venv\Scripts\python.exe run_local_cms.py runserver 127.0.0.1:8000
"""
import os, sys

root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, root)

import pymysql
pymysql.install_as_MySQLdb()

# PyMySQL hardcodes version_info=(1, 4, 0, ...) to advertise its mysqlclient-API compatibility level
# (unrelated to its own package version, 1.0.2). Django 4.2 raised its hard minimum check to
# mysqlclient>=1.4.3, which now rejects that hardcoded value even though PyMySQL's DB-API shim
# itself hasn't changed. Bumping the advertised tuple is the standard workaround.
pymysql.version_info = (1, 4, 3, "final", 0)

import django
if django.VERSION < (3, 0):
    # Django 2.2 expects mysqlclient's bytes "_executed", PyMySQL 1.x gives str (crashes the
    # DEBUG SQL logging); backport of the Django 3.0 implementation, which already does this
    # natively - so only needed pre-3.0. Guarded (rather than applied unconditionally like before)
    # because directly importing django.db.backends.mysql.operations here, ahead of django.setup(),
    # trips a circular import inside django.db.models on Django 5.0 (base/operations.py now imports
    # from django.db.models.expressions, which imports back into django.db.backends.base.operations).
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

# django-filer 1.x's AdminFolderFormField.__init__ calls forms.Field.__init__() directly
# (skipping ModelChoiceField.__init__, which is the only place that knows to consume a
# 'blank' kwarg). Since Django 3.1, ForeignKey.formfield() always passes 'blank' along,
# so building the folder widget crashes with "unexpected keyword argument 'blank'".
# Never fixed in the filer 1.x line (only filer 2.x's cms-plugin rewrite, which
# cmsplugin-filer 1.1.3 doesn't support, avoids this code path).
# Patched on the base Field class (not on AdminFolderFormField itself) and BEFORE
# django.setup()/setup_pychronia_env: the crash happens during admin autodiscovery,
# itself triggered deep inside django.setup() (via django_compat_patcher), too early
# for a post-setup patch to still beat it; importing filer.fields.folder this early
# would itself crash (needs the app registry + django.utils.six, neither ready yet).
# Only ModelChoiceField ever legitimately consumes 'blank', so dropping it in the
# base Field is safe framework-wide.
from django.forms.fields import Field
_original_Field_init = Field.__init__
def _patched_Field_init(self, *args, **kwargs):
    kwargs.pop("blank", None)
    _original_Field_init(self, *args, **kwargs)
Field.__init__ = _patched_Field_init

# django-blog-zinnia 0.20 (abandoned)'s zinnia/admin/fields.py builds its MPTT choice field as
# `choices = property(_get_choices, forms.ChoiceField._set_choices)`, i.e. it needs ChoiceField
# to still expose the pre-property-rewrite `_set_choices` method. Django replaced that with a
# plain `choices` property/setter pair at some point and dropped the method name entirely, which
# Django <=4.2 tolerated (closures below for `_set_choices` were effectively unused leftovers) but
# Django 5.0 doesn't - admin autodiscovery crashes with AttributeError while importing zinnia's
# admin. No upstream fix exists; restoring just the method name here (mirroring Django 5.0's own
# setter body) is enough since zinnia never calls it directly, only passes it to `property()`.
# Must run before django.setup()/setup_pychronia_env, same reasoning as the patch above.
from django.forms.fields import ChoiceField
from django.utils.choices import normalize_choices
def _set_choices(self, value):
    self._choices = self.widget.choices = normalize_choices(value)
ChoiceField._set_choices = _set_choices

# Same as pychronia_cms/tests/manage.py, but inlined so that sys.argv[0] stays this launcher,
# and the runserver autoreloader respawns it WITH the patches above
os.environ["DJANGO_SETTINGS_MODULE"] = "pychronia_cms.tests.persistent_mode_settings"
import setup_pychronia_env  # noqa: E402

from django.core.management import execute_from_command_line
execute_from_command_line(sys.argv)
