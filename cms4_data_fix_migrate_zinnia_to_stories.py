"""
One-off data fix, run once against chryscms_utf8mb4_local (and, later, against prod) after
djangocms_stories' own migrations have been applied (see commit wiring djangocms_stories into
INSTALLED_APPS alongside zinnia/cmsplugin_zinnia).

Requires zinnia/cmsplugin_zinnia to still be installed and in INSTALLED_APPS at the time this
script runs (it reads straight from zinnia's own models) - run this BEFORE the follow-up commit
that drops zinnia/cmsplugin_zinnia from pyproject.toml/INSTALLED_APPS, not after.

Migrates the 34 zinnia_entry rows into djangocms_stories' Post/PostContent models:
- All 34 entries are status=PUBLISHED (zinnia.managers.PUBLISHED == 2), single author "admin",
  3 flat (non-hierarchical) categories, no tags in use, no main_image/lead in use.
- Each entry's real body content lives in a CMS placeholder (zinnia_entry.content_placeholder_id
  -> cms_placeholder.id, slot='content') holding real plugin rows (RstPlugin/PicturePlugin/
  TextPlugin) - NOT in zinnia_entry.content (a legacy/unused duplicate column for some rows).
  cmsplugin_zinnia's EntryPlaceholder never set cms_placeholder.content_type_id/object_id (its
  FK runs the other way, from Entry to Placeholder directly), so those columns are free to set
  for djangocms_stories' PlaceholderRelationField (a GenericRelation) without touching any
  existing plugin row - this re-parents the placeholder (and all its plugins, untouched) onto
  the new PostContent instead of copying/recreating plugin content.

Creates one StoriesConfig (namespace "blog") and re-points the pre-existing zinnia apphook page
(application_urls="ZinniaApphook") onto the new StoriesApp apphook in place, preserving its real
slug/URL ("blog", not "weblog" - zinnia's own URLs were year/month/day/slug-based, matching
djangocms_stories' default "full_date" permalink style, so no URL-pattern change is needed
either). If no such page exists (e.g. a from-scratch install), falls back to creating a new one
at slug "weblog".

Run via:
PYTHONPATH=. .venv/Scripts/python.exe pychronia_cms/tests/manage.py shell -c "exec(open(r'cms4_data_fix_migrate_zinnia_to_stories.py').read())"
"""
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.db import connection
from django.utils import timezone

from cms.api import create_page
from djangocms_stories.cms_appconfig import StoriesConfig, config_defaults
from djangocms_stories.models import Post, PostCategory, PostContent
from djangocms_versioning.constants import PUBLISHED
from djangocms_versioning.models import Version

from zinnia.models import Entry as ZinniaEntry
from zinnia.models import Category as ZinniaCategory

LANGUAGE = "fr"  # pychronia_cms.common_settings.LANGUAGE_CODE: "CMS content is french only"

admin = get_user_model().objects.get(username="admin")
site = Site.objects.get(pk=1)

# --- 1. StoriesConfig + apphook page (idempotent: skip if already run) ---
# config_defaults only backs the admin form's initial values, not actual model field
# defaults - most of its keys (set_author, url_patterns, ...) are NOT NULL fields with no
# default= kwarg, so a plain .create() without them fails; pass them through explicitly.
config, config_created = StoriesConfig.objects.get_or_create(
    namespace="blog",
    defaults=dict(type="djangocms_stories.cms_appconfig.StoriesConfig", **config_defaults),
)
if config_created:
    config.set_current_language(LANGUAGE)
    config.app_title = "Blog"
    config.object_name = "Article"
    config.save()
print("StoriesConfig:", config, "(created)" if config_created else "(existing)")

from cms.models import Page, PageContent

existing_blog_page = Page.objects.filter(application_namespace="blog").first()
legacy_zinnia_page = Page.objects.filter(application_urls="ZinniaApphook").first()

if existing_blog_page:
    blog_page = existing_blog_page
    print("Blog apphook page already exists:", blog_page)
elif legacy_zinnia_page:
    # Re-point the pre-existing zinnia apphook page in place, instead of creating a new one,
    # so its real slug/URL ("blog") is preserved rather than switching to a different slug.
    blog_page = legacy_zinnia_page
    blog_page.application_urls = "StoriesApp"
    blog_page.application_namespace = "blog"
    blog_page.save()
    print("Re-pointed legacy zinnia apphook page onto StoriesApp:", blog_page)
else:
    # Note: `published=True` is a no-op here (recent cms versions warn and ignore it) and
    # `created_by="admin"` as a bare username (rather than the User instance) means create_page
    # can't attach a Version either - so backfill one PUBLISHED Version row for the new
    # PageContent explicitly below, same "one Version row per surviving PageContent" pattern
    # used for the cms3->cms4 upgrade itself (see DJANGO_CMS_UPGRADE_REPORT.md).
    blog_page = create_page(
        title="Weblog",
        template="INHERIT",
        language=LANGUAGE,
        slug="weblog",
        created_by="admin",
        apphook="StoriesApp",
        apphook_namespace="blog",
    )
    print("Created blog apphook page:", blog_page)

pagecontent_ct = ContentType.objects.get_for_model(PageContent)
blog_page_contents = PageContent._base_manager.filter(page=blog_page)
existing_page_versions = set(
    Version.objects.filter(content_type=pagecontent_ct, object_id__in=blog_page_contents.values_list("pk", flat=True))
    .values_list("object_id", flat=True)
)
for pc in blog_page_contents:
    if pc.pk in existing_page_versions:
        continue
    Version.objects.create(
        content_type=pagecontent_ct, object_id=pc.pk, state=PUBLISHED, created_by=admin, number="1",
    )
    print("backfilled PUBLISHED Version for blog PageContent", pc.pk)

# --- 2. Categories ---
category_map = {}  # zinnia_category.id -> PostCategory
for zcat in ZinniaCategory.objects.all():
    created = False
    pcat = PostCategory.objects.translated(LANGUAGE, slug=zcat.slug).filter(app_config=config).first()
    if pcat is None:
        pcat = PostCategory.objects.create(app_config=config)
        pcat.set_current_language(LANGUAGE)
        pcat.name = zcat.title
        pcat.slug = zcat.slug
        pcat.save()
        created = True
    category_map[zcat.id] = pcat
    print("category", zcat.id, zcat.title, "->", pcat.pk, "(created)" if created else "(existing)")

# --- 3. Posts ---
postcontent_ct = ContentType.objects.get_for_model(PostContent)
existing_entry_ids = set(
    Post.objects.filter(postcontent__meta_keywords__startswith="zinnia_entry_id:")
    .values_list("postcontent__meta_keywords", flat=True)
)
existing_migrated_ids = {int(v.split(":", 1)[1]) for v in existing_entry_ids if v.split(":", 1)[1].isdigit()}

created_count = 0
skipped_count = 0
reparented_count = 0

for entry in ZinniaEntry.objects.all().order_by("id"):
    if entry.id in existing_migrated_ids:
        skipped_count += 1
        continue

    post = Post.objects.create(author=admin, app_config=config, include_in_rss=True)
    Post.objects.filter(pk=post.pk).update(
        date_created=entry.creation_date,
        date_modified=entry.last_update,
        date_published=entry.publication_date,
    )

    for zcat in entry.categories.all():
        post.categories.add(category_map[zcat.id])

    post_content = PostContent.objects.create(
        post=post,
        language=LANGUAGE,
        title=entry.title,
        slug=entry.slug,
        abstract=entry.excerpt or "",
        # Tag this row with the source zinnia_entry id, both for traceability and so this
        # script can be re-run safely (skips already-migrated entries, see existing_migrated_ids).
        meta_keywords=f"zinnia_entry_id:{entry.id}",
    )

    Version.objects.create(
        content_type=postcontent_ct,
        object_id=post_content.pk,
        state=PUBLISHED,
        created_by=admin,
        number="1",
        created=entry.creation_date,
        modified=entry.last_update,
    )

    # Re-parent the entry's real CMS placeholder (with its live plugin rows, untouched) onto
    # the new PostContent via the generic relation columns cmsplugin_zinnia's EntryPlaceholder
    # never populated.
    if entry.content_placeholder_id:
        with connection.cursor() as cur:
            cur.execute(
                "UPDATE cms_placeholder SET content_type_id = %s, object_id = %s WHERE id = %s",
                [postcontent_ct.pk, post_content.pk, entry.content_placeholder_id],
            )
        reparented_count += 1

    created_count += 1

print("posts created:", created_count, "skipped (already migrated):", skipped_count,
      "placeholders reparented:", reparented_count)
print("total zinnia_entry:", ZinniaEntry.objects.count())
print("total djangocms_stories Post:", Post.objects.count())
print("total djangocms_stories PostContent:", PostContent.objects.count())
print("total Version(postcontent, published):",
      Version.objects.filter(content_type=postcontent_ct, state=PUBLISHED).count())
