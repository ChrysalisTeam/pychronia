"""
One-off data fix, run once against chryscms_utf8mb4_local (and, later, against prod), after
cms4_data_fix_stories_menu_categories_only.py.

The "News" top-level menu item currently opens a flyout submenu with the 3 blog categories
(Evènements, Média, Mises à jour), because an earlier fix set
StoriesConfig.menu_structure = MENU_TYPE_CATEGORIES to avoid a broken 3-level flyout. The
requirement is now stricter: "News" must have no submenu at all, and clicking it must go
straight to the blog root page (/fr/cms/blog/).

djangocms-stories' PostCategoryMenu.get_nodes() only appends extra child nodes under the
apphook page's own menu node when menu_structure is MENU_TYPE_COMPLETE/MENU_TYPE_CATEGORIES/
MENU_TYPE_POSTS; with MENU_TYPE_NONE it appends nothing. The "News" label and its URL come
from the apphook page's own PageContent.title/Page.get_absolute_url() (standard django-cms
page menu), which is unaffected by menu_structure - so switching to MENU_TYPE_NONE removes
the submenu while leaving "News" itself a normal, directly-clickable link to /fr/cms/blog/.

Run via:
PYTHONPATH=. .venv/Scripts/python.exe pychronia_cms/tests/manage.py shell -c "exec(open(r'cms4_data_fix_stories_menu_no_submenu.py').read())"

After running, restart any dev server process (LocMemCache + the CMS menu pool cache are
per-process and won't pick up the DB change until restarted).
"""
from djangocms_stories.cms_appconfig import StoriesConfig
from djangocms_stories.settings import MENU_TYPE_NONE

updated = StoriesConfig.objects.exclude(menu_structure=MENU_TYPE_NONE).update(menu_structure=MENU_TYPE_NONE)
print(f"Updated {updated} StoriesConfig row(s) to menu_structure={MENU_TYPE_NONE!r}")
