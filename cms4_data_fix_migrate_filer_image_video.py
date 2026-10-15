"""
One-off data fix, run once against chryscms_local after djangocms-picture/djangocms-video were
added alongside cmsplugin-filer (which is abandoned, has no cms4+ release, and must eventually be
removed from INSTALLED_APPS/requirements.txt).

Converts every live cmsplugin_filer_image.FilerImage / cmsplugin_filer_video.FilerVideo plugin
instance into the equivalent djangocms_picture.Picture / djangocms_video.VideoPlayer instance,
IN PLACE: the underlying cms_cmsplugin row (placeholder, position, parent, treebeard path/depth)
is kept and only has its plugin_type field repointed, so page structure/ordering is untouched.
Only the old subclass table row is replaced by a new one for the new plugin type, re-using the
same pk (= cmsplugin_ptr_id).

Field mapping decided from inspecting the live data (53 FilerImagePlugin + 1 FilerVideoPlugin
rows, after the draft/public page dedup in cms4_data_fix_merge_draft_public_pages.py):
  - style: always '' or 'default' (no real CSS variation) -> dropped.
  - alignment: only ever 'center' -> copied directly (djangocms_picture.Picture.alignment has a
    'center' choice).
  - image/caption_text/width/height -> copied directly.
  - crop/upscale/use_autoscale -> use_crop/use_upscale/use_automatic_scaling.
  - use_original_image -> use_no_cropping.
  - alt_text -> attributes={'alt': ...} (djangocms_picture's AttributesField excludes src/
    width/height but not alt).
  - free_link/target_blank -> link_url/link_target ('_blank' if target_blank else '').
  - original_link=True (15 rows, no direct djangocms-picture equivalent): best-effort mapped to
    link_url = the image's own file URL (i.e. "click the picture to open the full-size image"),
    which is what original_link meant under cmsplugin-filer.
  - page_link/file_link/image_url/description/thumbnail_option: 0 live rows -> dropped.

The one live FilerVideoPlugin row has no movie file, no image, no movie_url set (only
fullscreen=True, which has no djangocms-video equivalent) - i.e. it is already-orphaned/empty
content under the old plugin too, so it is migrated to an empty VideoPlayer row for structural
parity (same placeholder/position) rather than silently dropped.

Run via: run_local_cms.py shell -c "exec(open(r'cms4_data_fix_migrate_filer_image_video.py').read())"
"""
from django.db import connection
from cms.models import CMSPlugin
from cmsplugin_filer_image.models import FilerImage
from cmsplugin_filer_video.models import FilerVideo
from djangocms_picture.models import Picture
from djangocms_video.models import VideoPlayer

cur = connection.cursor()

migrated_images = 0
for fi in FilerImage.objects.all():
    attributes = {"alt": fi.alt_text} if fi.alt_text else {}
    link_url = fi.free_link or ""
    if not link_url and fi.original_link and fi.image_id:
        link_url = fi.image.url

    picture = Picture(
        cmsplugin_ptr_id=fi.pk,
        picture_id=fi.image_id,
        width=fi.width,
        height=fi.height,
        alignment=fi.alignment or "",
        caption_text=fi.caption_text or "",
        attributes=attributes,
        link_url=link_url,
        link_target="_blank" if fi.target_blank else "",
        use_automatic_scaling=fi.use_autoscale,
        use_no_cropping=fi.use_original_image,
        use_crop=fi.crop,
        use_upscale=fi.upscale,
    )
    picture.save_base(raw=True)
    migrated_images += 1

image_ids = list(FilerImage.objects.values_list("pk", flat=True))
if image_ids:
    fmt = ",".join(["%s"] * len(image_ids))
    cur.execute(f"DELETE FROM cmsplugin_filer_image_filerimage WHERE cmsplugin_ptr_id IN ({fmt})", image_ids)
    CMSPlugin.objects.filter(pk__in=image_ids).update(plugin_type="PicturePlugin")

print("migrated FilerImagePlugin -> PicturePlugin:", migrated_images)

migrated_videos = 0
for fv in FilerVideo.objects.all():
    video = VideoPlayer(cmsplugin_ptr_id=fv.pk, template="default", label="", embed_link="")
    video.save_base(raw=True)
    migrated_videos += 1

video_ids = list(FilerVideo.objects.values_list("pk", flat=True))
if video_ids:
    fmt = ",".join(["%s"] * len(video_ids))
    cur.execute(f"DELETE FROM cmsplugin_filer_video_filervideo WHERE cmsplugin_ptr_id IN ({fmt})", video_ids)
    CMSPlugin.objects.filter(pk__in=video_ids).update(plugin_type="VideoPlayerPlugin")

print("migrated FilerVideoPlugin -> VideoPlayerPlugin:", migrated_videos)

print("remaining FilerImage rows:", FilerImage.objects.count())
print("remaining FilerVideo rows:", FilerVideo.objects.count())
print("Picture rows:", Picture.objects.count())
print("VideoPlayer rows:", VideoPlayer.objects.count())
