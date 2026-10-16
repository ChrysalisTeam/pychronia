"""
One-off data fix, run once against chryscms_utf8mb4_local (and, later, against prod).

Same root cause as cms4_data_fix_thumbnail_golden_ratio_crop_mismatches.py, but the mirror
case: djangocms_picture.Picture.get_size() also falls back to a golden-ratio WIDTH
(height * 1.618, or height / 1.618 depending on orientation) whenever crop is enabled and
WIDTH is unset (height is set) - the previous fix script only scanned rows with height=None,
missing rows where width=None instead. Found one such row sitewide: pk=2082
(cromlech_game_booklet_preview.png, used on the "Nouveaux jeux en vrac !" blog post), whose
natural aspect ratio (663x739, ~1.12) is far from golden ratio, so the golden-ratio-width
fallback (278px) cropped away a large share of the portrait photo's left/right edges.

Scans every Picture row with use_crop=True and width=None, and for any whose natural aspect
ratio deviates from golden ratio (1.618) by more than 30%, sets an explicit width matching the
image's own natural aspect ratio (crop becomes a no-op, full image renders). Rows closer to
golden ratio are left untouched, since a mild crop there is an unobjectionable/likely
intentional thumbnail style, not a visible bug.

Run via:
PYTHONPATH=. .venv/Scripts/python.exe pychronia_cms/tests/manage.py shell -c "exec(open(r'cms4_data_fix_thumbnail_golden_ratio_crop_mismatches_missing_width.py').read())"
"""
from djangocms_picture.models import Picture

GOLDEN_RATIO = 1.618
DEVIATION_THRESHOLD = 0.3

fixed = []
for p in Picture.objects.select_related("picture").filter(width__isnull=True, use_crop=True):
    img = p.picture
    if not img or not img.width or not img.height or not p.height:
        continue
    natural_ratio = max(img.width, img.height) / min(img.width, img.height)
    deviation = abs(natural_ratio - GOLDEN_RATIO) / GOLDEN_RATIO
    if deviation <= DEVIATION_THRESHOLD:
        continue
    new_width = round(p.height * img.width / img.height)
    p.width = new_width
    p.save()
    fixed.append((p.pk, img.original_filename, new_width, p.height, round(natural_ratio, 2)))

for row in fixed:
    print(f"Picture pk={row[0]} file={row[1]!r}: width set to {row[2]} (height={row[3]}, natural_ratio={row[4]})")
print(f"Fixed {len(fixed)} row(s)")
