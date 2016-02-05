# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from pychronia_game.common import *

from django.utils.http import urlencode
from django.utils.html import escape
from pychronia_game.storage import get_game_thumbnailer
import json

LIB_DIR = config.STATIC_URL + "libs/"

_media_player_templates = \
{
    ("flv", "mp3"): """
    <object type="application/x-shockwave-flash" class="mediaplayer" style="width:%(width)spx;height:%(height)spx;" data="%(lib_dir)svideoplayers/mediaplayer/simple_video_player.swf" title="%(title)s">
        <param name="movie" value="%(lib_dir)svideoplayers/mediaplayer/simple_video_player.swf" />
        <param name="quality" value="high" />
        <param name="wmode" value="%(transparency)s" />
        <param name="bgcolor" value="%(background)s" />
        <param name="autoplay" value="%(autoplay)s" />
        <param name="allowfullscreen" value="%(allowfullscreen)s" />
        <param name="allowscriptaccess" value="always" />
        <param name="scale" value="showall" />
        <param name="flashvars" value="file=%(fileurl)s&image=%(image)s&autostart=%(autoplay)s&fullscreen=%(allowfullscreen)s%(additional_flash_vars)s" />
    </object>
    """,

#    ("swf",): """ NOT WORKING DUNNO WHY
#    <object type="application/x-shockwave-flash" class="mediaplayer" style="width:%(width)spx;height:%(height)spx;" data="%(fileurl)s" title="%(title)s>
#        <param name="movie" value="%(fileurl)s" />
#        <param name="quality" value="high" />
#        <param name="wmode" value="%(transparency)s" />
#        <param name="bgcolor" value="%(background)s" />
#        <param name="autoplay" value="%(autoplay)s" />
#        <param name="scale" value="showall" />
#    </object>
#    """,

#    UNUSABLE, NEEDS JS ESCAPING AND NOT HTML ESCAPING
#    # uses silverlight/moonlight - badly supported, preferably not used
#    ("wmv", "wma",): """
#    <span id="avID_%(id)s" class="mediaplayer" style="width:%(width)spx;height:%(height)spx;" title="%(title)s"></span>
#    <script type="text/javascript">
#
#    var cnt = document.getElementById('avID_%(id)s');
#    var src = '%(lib_dir)svideoplayers/wmvplayer/wmvplayer.xaml';
#    var cfg = {
#        file:'%(fileurl)s',
#        width:'%(width)s',
#        height:'%(height)s',
#        autostart:'%(autoplay)s',
#        image:'%(image)s'
#    };
#    var ply = new jeroenwijering.Player(cnt,src,cfg);
#    </script>
#    """,


    ("avi", "divx"): """
    <object type="video/divx" data="%(fileurl)s" class="mediaplayer" style="width:%(width)spx;height:%(height)spx;" title="%(title)s">
        <param name="type" value="video/divx" />
        <param name="src" value="%(fileurl)s" />
        <param name="data" value="%(fileurl)s" />
        <param name="codebase" value="%(fileurl)s" />
        <param name="url" value="%(fileurl)s" />
        <param name="mode" value="full" />
        <param name="pluginspage" value="http://go.divx.com/plugin/download/" />
        <param name="allowContextMenu" value="true" />
        <param name="previewImage" value="%(image)s" />
        <param name="autoplay" value="%(autoplay)s" />
        <param name="minVersion" value="1.0.0" />
        <param name="custommode" value="none" />
        <p>No video? Get the DivX browser plug-in for <a href="http://download.divx.com/player/DivXWebPlayerInstaller.exe">Windows</a> or <a href="http://download.divx.com/player/DivXWebPlayer.dmg">Mac</a></p>
    </object>
    """,

#    UNUSED BECAUSE NEEDS JS ESCAPING FOR PARAMS, NOT HTML ENTITIES
#    # warning - quicktime videos have their controller right under the image,
#    # not at the bottom of the <object> area, so it's better to specify width/height
#    # with the right ratio...
#    ("mov", "mp4", "3gp", "mpg", "mpeg"): """
#    <span id="qtID_%(id)s" class="mediaplayer" style="width:%(width)spx;height:%(height)spx;" title="%(title)s"></span>
#    <script type="text/javascript">
#        html = QT_Generate_XHTML('%(fileurl)s', '%(width)s', '%(height)s', '', 'autoplay', '%(autoplay)s',
#        'bgcolor', '%(backgroundqt)s', 'scale', 'aspect', 'class', 'mediaplayer', 'title', '%(title)s');
#        document.getElementById("qtID_%(id)s").innerHTML = html;
#    </script>
#    """,

#    # Might be useful if silverlight isn't portable enough for avi/divx files...
#
#    ("divx", "avi"): """
#    <object type="video/divx" data="%(fileurl)s" style="width:%(width)spx;height:%(height)spx;" title="%(title)s">
#        <param name="type" value="video/divx" />
#        <param name="src" value="%(fileurl)s" />
#        <param name="data" value="%(fileurl)s" />
#        <param name="codebase" value="%(fileurl)s" />
#        <param name="url" value="%(fileurl)s" />
#        <param name="mode" value="full" />
#        <param name="pluginspage" value="http://go.divx.com/plugin/download/" />
#        <param name="allowContextMenu" value="true" />
#        <param name="previewImage" value="%(image)s" />
#        <param name="autoPlay" value="%(autoplay)s" />
#        <param name="minVersion" value="1.0.0" />
#        <param name="custommode" value="none" />
#        <p>No video? Get the DivX browser plug-in for <a href="http://download.divx.com/player/DivXWebPlayerInstaller.exe">Windows</a> or <a href="http://download.divx.com/player/DivXWebPlayer.dmg">Mac</a></p>
#    </object>
#    """
}

def generate_media_player(fileurl, image="", autostart=False, width=450, height=350, **kwargs):
    """
    Warning - fileurl had better be an ABSOLUTE url, else some media players won't find the file !
    
    Returns a simple HTML link,  if file format is not supported
    """

    # NOT ALWAYS ABSOLUTE URLS, eg. for personal documents these are "/my/file.mp4" URLs - 
    assert fileurl.startswith("http") or fileurl.startswith("/"), fileurl

    md5 = hashlib.md5()
    md5.update(fileurl.encode('ascii', 'ignore'))
    myhash = md5.hexdigest()[0:8]

    options = \
    {
        "title": "Video Viewer",
        "id": myhash, # risks of collision are ultra weak...
        "lib_dir": escape(LIB_DIR),
        "autoplay": "true" if autostart else "false",
        "allowfullscreen": "true",
        "transparency": "opaque", # transparent, window
        "background": "#000000",
        "backgroundqt": "black",
        "fileurl": escape(fileurl), # warning, sometimes would need urlencoding actually!
        "image": escape(image), # warning - gif images aren't supported by all players !
        "width": escape(width),
        "height": escape(height),
        "additional_flash_vars": "" # must begin with '&' if present, and be escaped/urlencoded properly
    }
    options.update(kwargs)


    extension = os.path.splitext(fileurl)[1][1:].lower() # we remove the dot and lower-case the extension -> might result in an empty string

    for extensions in _media_player_templates.keys():
        if extension in extensions:
            template = _media_player_templates[extensions]
            return template % options

    # if no extension matched, we fallback to a simple link...
    name = os.path.basename(fileurl)
    return '<div class="medialink">' + _("Access file") + ' <a target="_blank" href="%s">%s</a></div>' % \
            (escape(fileurl), escape(name if name else _("here")))







# We could use the JS script to load this SWF in a safer way, but well...
# <!--script language="JavaScript" src="{{ lib_dir }}audioplayer/audio-player.js"></script-->
_mp3_template = """
<p id="%(unikid)s">MP3 Flayer should appear here</p>
<script type="text/javascript">  
AudioPlayer.embed("%(unikid)s", %(options)s);  
</script>  
"""
def generate_audio_player(files, titles=None, artists=None, autostart=False):
    assert files

    unikid = str(random.randint(100000, 100000000000))

    options = {
        "soundFile": ",".join(files),
        "titles": ",".join(titles) if titles else "",
        "artists": ",".join(artists) if artists else "",
        "autostart": "yes" if autostart else "no",
        "width": "70%"
    }

    return _mp3_template % dict(options=json.dumps(options), unikid=unikid)



def generate_image_viewer(imageurl, width=500, height=400, preset=None, align="", **kwargs):
    """
    Generates an image thumbnail linking to the original image.
    
    Align, if not empty, can be center/left/right.
    """

    md5 = hashlib.md5()
    md5.update(imageurl.encode('ascii', 'ignore'))
    myhash = md5.hexdigest()[0:8]

    thumb = None

    rel_path = checked_game_file_path(imageurl)
    if not rel_path:
        thumburl = imageurl  # this might just not be an internal, secure, image
    else:
        try:
            # this url is actually a local game file
            thumbnailer = get_game_thumbnailer(rel_path)
            thumb = None
            if preset:
                try:
                    thumb = thumbnailer[preset]
                except Exception, e:  # eg. if preset name is unexisting
                    logging.critical("generate_image_viewer preset selection failed for %s/%s", imageurl, preset, exc_info=True)
                    pass
            if not thumb:  #we fallback to default options
                options = {
                           'autocrop': False, # remove useless whitespace
                           'crop': False, # no cropping at all,thumb must fit in both W and H
                           'size': (width, height), # one of these can be 0
                           }
                thumb = thumbnailer.get_thumbnail(options)
            thumburl = thumb.url
        except Exception, e:
            logging.critical("generate_image_viewer thumbnail generation failed %s - %s", imageurl, preset, exc_info=True)
            thumburl = imageurl # we give up thumbnailing...

    options = \
    {
        "title": "Image Viewer",
        "id": myhash,
        "imageurl": escape(imageurl),
        "thumburl": escape(thumburl),
        "width": escape(thumb.width if thumb else width),
        "height": escape(thumb.height if thumb else height),
        "classes": "align-%s" % align if align else "",
    }

    template = ("""<a href="%(imageurl)s"><img class="imageviewer %(classes)s" src="%(thumburl)s" title="%(title)s"id="%(id)s" """ +
               """style="max-width: %(width)spx; max-height:%(height)spx"/></a>""")

    return template % options



def build_proper_viewer(fileurl, **kwargs): # interesting kwarg : "autostart"

    # we try to provide the best player for this media type

    if not fileurl:
        return ""

    title = kwargs.pop("title", "")
    extension = os.path.splitext(fileurl)[1][1:].lower() # no starting dot

    if extension == "mp3": # fileurl may be a string of comma-separated mp3 urls - it works
        return generate_audio_player([fileurl], [title], **kwargs)
    elif extension in ["jpg", "jpeg", "gif", "bmp", "png", "tif"]:
        return generate_image_viewer(fileurl, **kwargs)
    else:
        # warning - this media player also supports mp3, so put it after the audio player !
        return generate_media_player(fileurl, **kwargs)


