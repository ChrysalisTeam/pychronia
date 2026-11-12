
import os, sys

root = os.path.dirname(os.path.realpath(__file__))
if root not in sys.path:
    sys.path.insert(0, root)

dependencies = os.path.join(root, "dependencies")
if dependencies not in sys.path:
    sys.path.insert(0, dependencies)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pychronia_settings")  # not erased if already set, eg. for tests

#warnings.resetwarnings() # UNCOMMENT TO SHOW ALL WARNINGS (even deprecation stuffs)

# The patches below must run before django.setup() (triggered a few lines down by
# django_compat_patcher.patch()), since they fix crashes that happen during app loading /
# admin autodiscovery / model preparation themselves. django_compat_patcher covers Django's
# own deprecations; these instead work around abandoned third-party packages (django-filer 1.x)
# that have no upstream fix for current Django versions.

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

# django-cms 3.6 apphook resolvers use a dummy 'app_resolver' urlconf, which the Django 2.2 system
# checks (run by runserver, not by WSGI in prod) try to import, by recursing into every
# URLResolver.check() -> URLResolver._check_custom_error_handlers(). Django 5.1 pulled the
# custom-handler check out of URLResolver entirely into a standalone
# django.core.checks.urls.check_custom_error_handlers() that only resolves handlers off
# settings.ROOT_URLCONF directly - it no longer recurses into included sub-resolvers at all, so
# the apphook's dummy urlconf is never touched and this patch has nothing left to guard against.
if django.VERSION < (5, 1):
    from django.urls.resolvers import URLResolver
    _original_check_custom_error_handlers = URLResolver._check_custom_error_handlers
    URLResolver._check_custom_error_handlers = \
        lambda self: [] if self.urlconf_name == "app_resolver" else _original_check_custom_error_handlers(self)

import django_compat_patcher
from django_compat_patcher import default_settings as dcp_default_settings
dcp_settings = dict(DCP_ENABLE_WARNINGS=False,
                    DCP_LOGGING_LEVEL="WARNING",
                    # callable User.is_authenticated/is_anonymous trigger CRITICAL system checks in recent Django versions
                    DCP_EXCLUDE_FIXER_IDS=dcp_default_settings.DCP_EXCLUDE_FIXER_IDS + [
                        "fix_behaviour_contrib_auth_user_is_anonymous_is_authenticated_callability"])
django_compat_patcher.patch(dcp_settings)

import django
django.setup()
