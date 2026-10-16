"""
One-off data fix, run once against chryscms_utf8mb4_local (and, later, against prod).

The blog list/category/archive pages currently paginate at the djangocms_stories default
(STORIES_PAGINATION = 20, see djangocms_stories/settings.py), since StoriesConfig.paginate_by
was never set. Per product decision, the blog should show 8 posts per page instead.

StoriesConfig.paginate_by (cms_appconfig.py) feeds straight into
BaseConfigListViewMixin.get_paginate_by() (views.py: "return self.config.paginate_by or
STORIES_PAGINATION"), used by every one of PostListView / CategoryEntriesView /
PostArchiveView / TaggedListView / AuthorEntriesView - so setting it once here covers
pagination on all of those views uniformly.

Run via:
PYTHONPATH=. .venv/Scripts/python.exe pychronia_cms/tests/manage.py shell -c "exec(open(r'cms4_data_fix_stories_paginate_by_8.py').read())"

After running, restart any dev server process (LocMemCache is per-process and won't pick up
the DB change until restarted).
"""
from djangocms_stories.cms_appconfig import StoriesConfig

updated = StoriesConfig.objects.exclude(paginate_by=8).update(paginate_by=8)
print(f"Updated {updated} StoriesConfig row(s) to paginate_by=8")
