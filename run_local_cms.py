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

# django-cms 3.6 apphook resolvers use a dummy 'app_resolver' urlconf, which the Django 2.2 system
# checks (run by runserver, not by WSGI in prod) try to import, by recursing into every
# URLResolver.check() -> URLResolver._check_custom_error_handlers(). Django 5.1 pulled the
# custom-handler check out of URLResolver entirely into a standalone
# django.core.checks.urls.check_custom_error_handlers() that only resolves handlers off
# settings.ROOT_URLCONF directly - it no longer recurses into included sub-resolvers at all, so
# the apphook's dummy urlconf is never touched and this patch has nothing left to guard against.
import django
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

# django-blog-zinnia 0.20's zinnia/models_bases/entry.py declares
# `index_together = [['slug', 'publication_date'], ...]` - a list of lists, not Django's
# expected tuple of tuples. Options.contribute_to_class() only runs normalize_together() on
# unique_together, never on index_together, so this raw list is stored verbatim in
# _meta.original_attrs and copied as-is into migration state. `migrate`'s autodetector used to
# tolerate that, but Django 5.1 does `new_value = set(new_value)` on it directly in
# _get_altered_foo_together_operations(), and lists aren't hashable -> TypeError. No upstream
# fix exists. Patched by normalizing index_together into tuples right after ModelState captures
# it off the live model, which is the only place this raw value flows through unmodified.
from django.db.migrations.state import ModelState
_original_from_model = ModelState.from_model.__func__
def _patched_from_model(cls, model, exclude_rels=False):
    state = _original_from_model(cls, model, exclude_rels=exclude_rels)
    it = state.options.get("index_together")
    if it:
        state.options["index_together"] = tuple(tuple(entry) for entry in it)
    return state
ModelState.from_model = classmethod(_patched_from_model)

# Same as pychronia_cms/tests/manage.py, but inlined so that sys.argv[0] stays this launcher,
# and the runserver autoreloader respawns it WITH the patches above
os.environ["DJANGO_SETTINGS_MODULE"] = "pychronia_cms.tests.persistent_mode_settings"
import setup_pychronia_env  # noqa: E402

from django.core.management import execute_from_command_line
execute_from_command_line(sys.argv)
