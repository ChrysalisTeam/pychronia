"""
One-off data fix, run once against chryscms_utf8mb4_local (and, later, against prod).

Same root cause as cms4_data_fix_special_abilities_thumbnail_crop.py (pk=54), found to affect
several more images: djangocms_picture.Picture rows migrated from the old cmsplugin-filer plugin
(cms4_data_fix_migrate_filer_image_video.py) kept crop=True with no explicit height, so
Picture.get_size() falls back to a golden-ratio height (width / 1.618). For images whose natural
aspect ratio is far from golden ratio, this crops away a large share of the image.

Scans every Picture row with use_crop=True and height=None, and for any whose natural aspect
ratio deviates from golden ratio (1.618) by more than 30%, sets an explicit height matching the
image's own natural aspect ratio (crop becomes a no-op, full image renders). Rows closer to golden
ratio (typical photos) are left untouched, since a mild crop there is an unobjectionable/likely
intentional thumbnail style, not a visible bug.

Run via:
PYTHONPATH=. .venv/Scripts/python.exe pychronia_cms/tests/manage.py shell -c "exec(open(r'cms4_data_fix_thumbnail_golden_ratio_crop_mismatches.py').read())"
"""
from djangocms_picture.models import Picture

GOLDEN_RATIO = 1.618
DEVIATION_THRESHOLD = 0.3

fixed = []
for p in Picture.objects.select_related("picture").filter(height__isnull=True, use_crop=True):
    img = p.picture
    if not img or not img.width or not img.height or not p.width:
        continue
    natural_ratio = img.width / img.height
    deviation = abs(natural_ratio - GOLDEN_RATIO) / GOLDEN_RATIO
    if deviation <= DEVIATION_THRESHOLD:
        continue
    new_height = round(p.width * img.height / img.width)
    p.height = new_height
    p.save()
    fixed.append((p.pk, img.original_filename, p.width, new_height, round(natural_ratio, 2)))

for row in fixed:
    print(f"Picture pk={row[0]} file={row[1]!r}: height set to {row[3]} (width={row[2]}, natural_ratio={row[4]})")
print(f"Fixed {len(fixed)} row(s)")
