"""
HTML5 media players (audio/video), enhanced client-side by Plyr (see static
MetalRadiance/pychronia_media.js), plus the image thumbnail viewer.

Each generated snippet is self-sufficient: it carries a tiny inline script which
initializes Plyr on it, so that snippets inserted via ajax (eg. the personal folder's
media viewer) work too. Without javascript, the native browser controls remain.
"""

from pychronia_game.common import *

from django.utils import translation
from django.utils.html import escape, format_html, format_html_join
from django.utils.safestring import mark_safe
from django.utils.translation import get_language_info
from pychronia_game.storage import get_game_thumbnailer

AUDIO_MIMETYPES = {
    "mp3": "audio/mpeg",
    "ogg": "audio/ogg",
    "oga": "audio/ogg",
    "opus": "audio/ogg",
    "wav": "audio/wav",
    "m4a": "audio/mp4",
    "aac": "audio/aac",
    "flac": "audio/flac",
    "weba": "audio/webm",
}

VIDEO_MIMETYPES = {
    "mp4": "video/mp4",
    "m4v": "video/mp4",
    "webm": "video/webm",
    "ogv": "video/ogg",
}

# Formats that no browser can play anymore (Flash video, DivX...): such game files
# must be converted to H.264/AAC ".mp4" files, with the same base name, which are then
# used transparently (so that old URLs, eg. in existing game databases, keep working).
LEGACY_VIDEO_EXTENSIONS = ("flv", "avi", "divx")

IMAGE_EXTENSIONS = ("jpg", "jpeg", "gif", "bmp", "png", "tif", "webp")

_INIT_SCRIPT = mark_safe(
    '<script type="text/javascript">if (window.PychroniaMedia) { PychroniaMedia.init(); }</script>'
)


def _get_extension(fileurl):
    """Returns the lowercased extension of the url path (without dot), maybe an empty string."""
    path = urlparse(fileurl).path
    return os.path.splitext(path)[1][1:].lower()


def _localize_url(fileurl):
    """
    Turns absolute urls pointing to our own site into root-relative urls, so that
    media files are always loaded from the current origin (no http/https mixed content,
    no dependency on the exactness of SITE_DOMAIN).
    """
    site_domain = config.SITE_DOMAIN
    if site_domain and fileurl.startswith(site_domain + "/"):
        return fileurl[len(site_domain) :]
    return fileurl


def _get_game_file_abspath(rel_path):
    return os.path.join(config.GAME_FILES_ROOT, rel_path)


def _css_length(value):
    """Normalizes a width option ("450", "450px", "80%"...) into a CSS length, or None if invalid."""
    if value is None:
        return None
    value = str(value).strip()
    if re.match(r"^\d+(\.\d+)?$", value):
        return value + "px"
    if re.match(r"^\d+(\.\d+)?(px|%|em|rem|vw)$", value):
        return value
    return None


def _resolve_legacy_video_url(fileurl):
    """
    Returns the url of the ".mp4" counterpart of a legacy video game file, or None if there
    is none (or if the url is external, since we can't check anything then).
    """
    rel_path = checked_game_file_path(fileurl)
    if not rel_path:
        return None
    mp4_rel_path = os.path.splitext(rel_path)[0] + ".mp4"
    if not os.path.exists(_get_game_file_abspath(mp4_rel_path)):
        logging.warning("No .mp4 conversion found for legacy video game file %s", rel_path)
        return None
    return game_file_url(mp4_rel_path)  # new security hash, since the path changed


def _find_subtitle_tracks(fileurl):
    """
    Finds WebVTT subtitles stored alongside a video game file, as "<basename>.<lang>.vtt"
    (or "<basename>.vtt", then considered to be in the current language).
    """
    rel_path = checked_game_file_path(fileurl)
    if not rel_path:
        return []

    base_rel_path = os.path.splitext(rel_path)[0]
    abs_base_path = _get_game_file_abspath(base_rel_path)

    tracks = []
    for abs_vtt_path in sorted(glob.glob(glob.escape(abs_base_path) + "*.vtt")):
        suffix = abs_vtt_path[len(abs_base_path) : -len(".vtt")]  # eg. "" or ".fr"
        if suffix and not re.match(r"^\.[a-zA-Z]{2,3}(-[a-zA-Z0-9]{2,8})?$", suffix):
            continue  # unrelated file, like "<basename>_other.vtt"
        lang = suffix[1:] or translation.get_language() or "en"
        try:
            label = get_language_info(lang)["name_local"]
        except KeyError:
            label = lang
        tracks.append(dict(url=game_file_url(base_rel_path + suffix + ".vtt"), lang=lang, label=label))
    return tracks


def _render_fallback_link(fileurl):
    name = os.path.basename(urlparse(fileurl).path)
    return format_html(
        '<div class="medialink">{} <a target="_blank" href="{}">{}</a></div>',
        _("Access file"),
        fileurl,
        name if name else _("here"),
    )


def generate_media_player(fileurl, image="", autostart=False, width=None, height=None, title="", **kwargs):
    """
    Returns an HTML5 video player for the given file url (or an audio player, for audio files).

    Height is ignored, since the player keeps the aspect ratio of the video.

    Returns a simple HTML link,  if file format is not supported.
    """
    del height, kwargs  # unused, the player keeps the aspect ratio of the video

    # NOT ALWAYS ABSOLUTE URLS, eg. for personal documents these are "/my/file.mp4" URLs -
    assert fileurl.startswith("http") or fileurl.startswith("/"), fileurl

    extension = _get_extension(fileurl)

    if extension in AUDIO_MIMETYPES:
        return generate_audio_player([fileurl], titles=[title] if title else None, autostart=autostart)

    if extension in LEGACY_VIDEO_EXTENSIONS:
        converted_url = _resolve_legacy_video_url(fileurl)
        if not converted_url:
            return _render_fallback_link(_localize_url(fileurl))
        fileurl = converted_url
        extension = "mp4"

    if extension not in VIDEO_MIMETYPES:
        return _render_fallback_link(_localize_url(fileurl))

    tracks = _find_subtitle_tracks(fileurl)
    fileurl = _localize_url(fileurl)

    max_width = _css_length(width)
    tracks_html = format_html_join(
        "",
        '<track kind="subtitles" src="{}" srclang="{}" label="{}" />',
        ((track["url"], track["lang"], track["label"]) for track in tracks),
    )

    return format_html(
        '<div class="pychronia-media pychronia-video"{style}>'
        '<video class="pychronia-media-element" controls playsinline preload="metadata"'
        '{poster}{autostart} title="{title}">'
        '<source src="{src}" type="{mimetype}" />'
        "{tracks}"
        '<a target="_blank" href="{src}">{link_label}</a>'
        "</video>"
        "</div>"
        "{init_script}",
        style=format_html(' style="max-width: {}"', max_width) if max_width else "",
        poster=format_html(' poster="{}"', _localize_url(image)) if image else "",
        autostart=mark_safe(' data-autostart="true"') if autostart else "",
        title=title,
        src=fileurl,
        mimetype=VIDEO_MIMETYPES[extension],
        tracks=tracks_html,
        link_label=_("Download the video"),
        init_script=_INIT_SCRIPT,
    )


def generate_audio_player(files, titles=None, artists=None, autostart=False, **kwargs):
    """
    Returns one HTML5 audio player per file url, with its (optional) title displayed above.
    """
    del kwargs  # eg. width/height options, irrelevant here
    assert files

    players = []
    for index, fileurl in enumerate(files):
        title = titles[index] if titles and index < len(titles) else ""
        artist = artists[index] if artists and index < len(artists) else ""
        full_title = " - ".join(x for x in (artist, title) if x)

        extension = _get_extension(fileurl)
        mimetype = AUDIO_MIMETYPES.get(extension)
        fileurl = _localize_url(fileurl)

        players.append(
            format_html(
                '<div class="pychronia-media pychronia-audio">'
                "{title_html}"
                '<audio class="pychronia-media-element" controls preload="none"{autostart} title="{title}">'
                '<source src="{src}"{type_attr} />'
                '<a target="_blank" href="{src}">{link_label}</a>'
                "</audio>"
                "</div>",
                title_html=format_html('<div class="pychronia-media-title">{}</div>', full_title) if full_title else "",
                autostart=mark_safe(' data-autostart="true"') if autostart else "",
                title=full_title,
                src=fileurl,
                type_attr=format_html(' type="{}"', mimetype) if mimetype else "",
                link_label=_("Download the audio file"),
            )
        )

    return mark_safe("".join(players) + _INIT_SCRIPT)


def generate_image_viewer(imageurl, width=500, height=400, preset=None, align="", **kwargs):
    """
    Generates an image thumbnail linking to the original image.

    Align, if not empty, can be center/left/right.
    """

    md5 = hashlib.md5()
    md5.update(imageurl.encode("ascii", "ignore"))
    myhash = md5.hexdigest()[0:8]

    thumb = None

    rel_path = checked_game_file_path(imageurl)
    if not rel_path:
        thumburl = imageurl  # this might just not be an internal, secure, image
    else:
        try:
            # this url is actually a local game file
            thumbnailer = get_game_thumbnailer(rel_path)
            if preset:
                try:
                    thumb = thumbnailer[preset]
                except Exception:  # eg. if preset name is unexisting
                    logging.critical(
                        "generate_image_viewer preset selection failed for %s/%s", imageurl, preset, exc_info=True
                    )
                    pass
            if not thumb:  # we fallback to default options
                options = {
                    "autocrop": False,  # remove useless whitespace
                    "crop": False,  # no cropping at all,thumb must fit in both W and H
                    "size": (width, height),  # one of these can be 0
                }
                thumb = thumbnailer.get_thumbnail(options)
            thumburl = thumb.url
        except Exception:
            logging.critical(
                "generate_image_viewer thumbnail generation failed %s - %s", imageurl, preset, exc_info=True
            )
            thumburl = imageurl  # we give up thumbnailing...

    options = {
        "title": "",  # no title for now
        "id": myhash,
        "imageurl": escape(imageurl),
        "thumburl": escape(thumburl),
        "width": escape(thumb.width if thumb else width),
        "height": escape(thumb.height if thumb else height),
        "classes": "align-%s" % align if align else "",
    }

    template = (
        """<a href="%(imageurl)s"><img class="imageviewer %(classes)s" src="%(thumburl)s" title="%(title)s" id="%(id)s" """
        + """style="max-width: %(width)spx; max-height:%(height)spx"/></a>"""
    )

    return template % options


def get_medium_title_from_url(file_url):
    basename = os.path.basename(file_url)
    return os.path.splitext(basename)[0]


def build_proper_viewer(fileurl, **kwargs):  # interesting kwarg : "autostart"

    # we try to provide the best player for this media type

    if not fileurl:
        message = _("No media file available")
        return """<span class="mediaplayer_fallback">{%s}<i></i></span>""" % escape(message)

    title = kwargs.pop("title", "") or get_medium_title_from_url(fileurl)
    extension = _get_extension(fileurl)

    if extension in AUDIO_MIMETYPES:
        return generate_audio_player([fileurl], [title], **kwargs)
    elif extension in IMAGE_EXTENSIONS:
        kwargs.pop("autostart", None)
        return generate_image_viewer(fileurl, **kwargs)
    else:
        return generate_media_player(fileurl, title=title, **kwargs)
