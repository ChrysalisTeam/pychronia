"""
One-off data fix, run once against chryscms_utf8mb4_local (and, later, against prod).

The djangocms_picture.Picture row for special_abilities.png (pk=54, used on the "Le concept
Leet'RPG" page) was migrated from the old cmsplugin-filer FilerImage plugin by
cms4_data_fix_migrate_filer_image_video.py, which faithfully copied crop=True/height=None from
the old plugin instance. djangocms-picture's Picture.get_size() falls back to a golden-ratio
height (width / 1.618) whenever crop is enabled and no explicit height is set - but the real
image is a wide 3-panel strip (521x166, ratio ~3.14), so the golden-ratio crop chopped off most
of the left and right panels, leaving only a sliver of each
(see media/filer_public_thumbnails/.../special_abilities.png__500x309_crop_subsampling-2_upscale.png).

Sets an explicit height on that one Picture row matching the image's own natural aspect ratio, so
the "crop" becomes a no-op and the full 3-panel strip renders.

Run via:
PYTHONPATH=. .venv/Scripts/python.exe pychronia_cms/tests/manage.py shell -c "exec(open(r'cms4_data_fix_special_abilities_thumbnail_crop.py').read())"
"""
from djangocms_picture.models import Picture

p = Picture.objects.select_related("picture").get(pk=54, picture__original_filename="special_abilities.png")
img = p.picture
new_height = round(p.width * img.height / img.width)
p.height = new_height
p.save()
print(f"Picture pk={p.pk}: height set to {new_height} (width={p.width}, natural={img.width}x{img.height})")
