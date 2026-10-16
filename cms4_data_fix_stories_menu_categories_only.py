"""
One-off data fix, run once against chryscms_utf8mb4_local (and, later, against prod) after
cms4_data_fix_migrate_zinnia_to_stories.py.

djangocms-stories' StoriesConfig.menu_structure defaults to MENU_TYPE_COMPLETE ("Categories and
posts"), which adds every individual blog post as a 3rd-level menu entry under its category (eg.
News > Evenements > <34 individual post titles>). This broke the site's dropdown menu: clicking a
2nd-level category item (eg. "Evenements") opened its own flyout of posts instead of navigating to
the category page directly, requiring a confusing extra click - and visually produced a 3-level
flyout the MetalRadiance menu CSS/JS wasn't meant to need (the 3rd "tube_bronze_small.png" level
exists in CSS but was unused before djangocms-stories).

Switches menu_structure to MENU_TYPE_CATEGORIES ("Categories only"): the 2nd-level category links
remain in the menu and are clickable (navigating to the category listing page on the first click),
but individual posts no longer clutter the menu.

Run via:
PYTHONPATH=. .venv/Scripts/python.exe pychronia_cms/tests/manage.py shell -c "exec(open(r'cms4_data_fix_stories_menu_categories_only.py').read())"

After running, restart any dev server process (LocMemCache + the CMS menu pool cache are
per-process and won't pick up the DB change until restarted).
"""
from djangocms_stories.cms_appconfig import StoriesConfig
from djangocms_stories.settings import MENU_TYPE_CATEGORIES

updated = StoriesConfig.objects.exclude(menu_structure=MENU_TYPE_CATEGORIES).update(
    menu_structure=MENU_TYPE_CATEGORIES
)
print(f"Updated {updated} StoriesConfig row(s) to menu_structure={MENU_TYPE_CATEGORIES!r}")
