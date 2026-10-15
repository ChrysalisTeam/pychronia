
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
# own deprecations; these instead work around abandoned third-party packages (django-filer 1.x,
# django-blog-zinnia/cmsplugin-zinnia) that have no upstream fix for current Django versions.

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

# django-blog-zinnia 0.20 (abandoned)'s zinnia/admin/fields.py builds its MPTT choice field as
# `choices = property(_get_choices, forms.ChoiceField._set_choices)`, i.e. it needs ChoiceField
# to still expose the pre-property-rewrite `_set_choices` method. Django replaced that with a
# plain `choices` property/setter pair at some point and dropped the method name entirely, which
# Django <=4.2 tolerated (closures below for `_set_choices` were effectively unused leftovers) but
# Django 5.0 doesn't - admin autodiscovery crashes with AttributeError while importing zinnia's
# admin. No upstream fix exists; restoring just the method name here (mirroring Django 5.0's own
# setter body) is enough since zinnia never calls it directly, only passes it to `property()`.
# Must run before django.setup(), same reasoning as the patch above.
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

# django-blog-zinnia 0.20 (abandoned) ships URL patterns with a redundant bare inline
# unicode-flag group nested INSIDE a named group instead of at the pattern start, eg.
# r'^tags/(?P<tag>[^/]+(?u))/$' (zinnia/urls/tags.py, zinnia/urls/feeds.py) - the "(?u)" ends
# up at position 19, not 0. Python's re module tolerated this with a mere DeprecationWarning
# for years, but newer Python versions (3.11+) turned it into a hard re.error ("global flags
# not at the start of the expression"), which Django wraps into ImproperlyConfigured as soon
# as the pattern is first compiled (on first URL resolution / system checks, not at import
# time - hence patched here rather than needing to run before django.setup()). Moving the
# flag to the start instead of dropping it would only fix compilation, not reversal -
# django.utils.regex_helper.normalize() (used by {% url %}/reverse()) cannot parse ANY
# inline-flag group regardless of position and raises its own "Non-reversible reg-exp
# portion" ValueError. Since Python 3 str patterns are already Unicode-aware by default,
# "(?u)" is a pure no-op there, so it's safe to just strip it rather than relocate it. No
# upstream fix exists.
import re
from django.urls.resolvers import LocaleRegexDescriptor
from django.core.exceptions import ImproperlyConfigured
_original_locale_regex_compile = LocaleRegexDescriptor._compile
_bare_u_flag_re = re.compile(r"\(\?u\)")
def _patched_locale_regex_compile(self, regex):
    try:
        return _original_locale_regex_compile(self, regex)
    except ImproperlyConfigured:
        fixed_regex, count = _bare_u_flag_re.subn("", regex)
        if not count:
            raise
        return _original_locale_regex_compile(self, fixed_regex)
LocaleRegexDescriptor._compile = _patched_locale_regex_compile
LocaleRegexDescriptor._compile = _patched_locale_regex_compile

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
