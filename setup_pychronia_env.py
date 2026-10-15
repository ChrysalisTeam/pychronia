
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

# django-filer 1.x's AdminFolderFormField.__init__ calls forms.Field.__init__() directly
# (skipping ModelChoiceField.__init__, which is the only place that knows to consume a
# 'blank' kwarg). Since Django 3.1, ForeignKey.formfield() always passes 'blank' along,
# so building the folder widget crashes with "unexpected keyword argument 'blank'".
# Never fixed in the filer 1.x line (only filer 2.x's cms-plugin rewrite, which
# cmsplugin-filer 1.1.3 doesn't support, avoids this code path).
# Patched on the base Field class (not on AdminFolderFormField itself) and BEFORE
# django.setup(): the crash happens during admin autodiscovery, itself triggered deep inside
# django.setup() (via django_compat_patcher), too early for a post-setup patch to still beat
# it; importing filer.fields.folder this early would itself crash (needs the app registry +
# django.utils.six, neither ready yet).
# Only ModelChoiceField ever legitimately consumes 'blank', so dropping it in the
# base Field is safe framework-wide.
from django.forms.fields import Field
_original_Field_init = Field.__init__
def _patched_Field_init(self, *args, **kwargs):
    kwargs.pop("blank", None)
    _original_Field_init(self, *args, **kwargs)
Field.__init__ = _patched_Field_init

# django-filer 1.5.0's Folder/File models declare their MPTT fields (level/lft/rght)
# explicitly but still rely on the old imperative `mptt.register(Folder)` (called at module
# level, AFTER the class body closes) to add the remaining ones, 'tree_id' among them - so
# 'tree_id' doesn't exist yet when the class itself is being prepared. That used to be fine
# because Meta.index_together's entries were resolved into named Index objects lazily; Django
# 5.1 made Index.set_name_with_model() resolve its fields eagerly during Model._prepare(),
# so building the `index_together = (('tree_id', 'lft'),)` index on Folder/File now crashes
# with FieldDoesNotExist before mptt.register() ever runs. No upstream fix exists (filer 1.x is
# abandoned). Patched narrowly: when a field named in an index isn't resolvable yet, fall back
# to using its bare name as the column name (true here - 'tree_id' has no custom db_column) so
# naming can proceed; this only affects the auto-generated index *name*, not the schema itself.
from django.db.models.indexes import Index
from django.core.exceptions import FieldDoesNotExist
_original_set_name_with_model = Index.set_name_with_model
def _patched_set_name_with_model(self, model):
    try:
        for field_name, _order in self.fields_orders:
            model._meta.get_field(field_name)
    except FieldDoesNotExist:
        from django.db.backends.utils import names_digest, split_identifier
        _, table_name = split_identifier(model._meta.db_table)
        column_names = [field_name for field_name, _order in self.fields_orders]
        hash_data = [table_name] + column_names + [self.suffix]
        self.name = "%s_%s_%s" % (
            table_name[:11],
            column_names[0][:7],
            "%s_%s" % (names_digest(*hash_data, length=6), self.suffix),
        )
        if self.name[0] == "_" or self.name[0].isdigit():
            self.name = "D%s" % self.name[1:]
        return
    _original_set_name_with_model(self, model)
Index.set_name_with_model = _patched_set_name_with_model

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
