"""
One-off data fix, run once against chryscms_local right after the django-cms 3.11.11 -> 5.0.13
`migrate` completed (which includes djangocms_versioning's own migrations).

cms core's migrations rename Title -> PageContent and create PageUrl etc., but they do NOT
create any djangocms_versioning.Version rows for pre-existing PageContent - that app's own
migrations only handle apps that already had their own versioning/grouper split (e.g.
djangocms_snippet). Since PageContent.objects (the manager every public view uses) filters to
"the published row per language" once djangocms_versioning is installed, having zero Version
rows means every page becomes invisible on the public site (requests get redirected into
/admin/cms/pagecontent/ -> /admin/login/ instead of rendering) even though the page data itself
migrated fine.

Fix: every surviving PageContent row (one per page+language, after the draft/public merge in
cms4_data_fix_merge_draft_public_pages.py) was - in the old cms3 schema - exactly the page's
live, served content, so backfill one Version row per PageContent marked PUBLISHED.

Run via: run_local_cms.py shell -c "exec(open(r'cms4_data_fix_backfill_published_versions.py').read())"
"""
from djangocms_versioning.models import Version
from djangocms_versioning.constants import PUBLISHED
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from cms.models import PageContent
from django.utils import timezone

admin = get_user_model().objects.get(username="admin")
ct = ContentType.objects.get_for_model(PageContent)
existing = set(Version.objects.filter(content_type=ct).values_list("object_id", flat=True))
now = timezone.now()
to_create = [
    Version(content_type=ct, object_id=pc.id, state=PUBLISHED, created_by=admin, number="1", created=now, modified=now)
    for pc in PageContent._base_manager.all()
    if pc.id not in existing
]
Version.objects.bulk_create(to_create)
print("created", len(to_create), "version rows")
print("total PageContent:", PageContent._base_manager.count())
print("total Version(pagecontent):", Version.objects.filter(content_type=ct).count())
