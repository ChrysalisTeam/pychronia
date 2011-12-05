# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *

from django.utils.http import urlencode

_media_player_templates = \
{
    ("flv", "mp3"): """
    <object  type="application/x-shockwave-flash" class="mediaplayer" style="width:%(width)spx;height:%(height)spx;" data="%(media_full_url)svideoplayers/mediaplayer/player.swf" title="%(title)s">
        <param name="movie" value="%(media_full_url)svideoplayers/mediaplayer/player.swf" />
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

    ("swf",): """
    <object type="application/x-shockwave-flash" class="mediaplayer" style="width:%(width)spx;height:%(height)spx;" data="%(fileurl)s" title="%(title)s>
        <param name="movie" value="%(fileurl)s" />
        <param name="quality" value="high" />
        <param name="wmode" value="%(transparency)s" />
        <param name="bgcolor" value="%(background)s" />
        <param name="autoplay" value="%(autoplay)s" />
        <param name="scale" value="showall" />
    </object>
    """,

    # uses silverlight/moonlight - badly supported, preferably not used
    ("wmv", "wma",): """
    <span id="avID_%(id)s" class="mediaplayer" style="width:%(width)spx;height:%(height)spx;" title="%(title)s"></span>
    <script type="text/javascript">
    
    var cnt = document.getElementById('avID_%(id)s');
    var src = '%(media_full_url)svideoplayers/wmvplayer/wmvplayer.xaml';
    var cfg = {
        file:'%(fileurl)s',
        width:'%(width)s',
        height:'%(height)s',
        autostart:'%(autoplay)s',
        image:'%(image)s'
    };
    var ply = new jeroenwijering.Player(cnt,src,cfg);
    </script>
    """,

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
        <param name="autoPlay" value="%(autoplay)s" />
        <param name="minVersion" value="1.0.0" />
        <param name="custommode" value="none" />
        <p>No video? Get the DivX browser plug-in for <a href="http://download.divx.com/player/DivXWebPlayerInstaller.exe">Windows</a> or <a href="http://download.divx.com/player/DivXWebPlayer.dmg">Mac</a></p>
    </object>
    """,


    # warning - quicktime videos have their controller right under the image, 
    # not at the bottom of the <object> area, so it's better to specify width/height 
    # with the right ratio...
    ("mov", "mp4", "3gp", "mpg", "mpeg"): """
    <span id="qtID_%(id)s" class="mediaplayer" style="width:%(width)spx;height:%(height)spx;" title="%(title)s"></span>
    <script type="text/javascript">
        html = QT_Generate_XHTML('%(fileurl)s', '%(width)s', '%(height)s', '', 'autoplay', '%(autoplay)s', 
        'bgcolor', '%(backgroundqt)s', 'scale', 'aspect', 'class', 'mediaplayer', 'title', '%(title)s');
        document.getElementById("qtID_%(id)s").innerHTML = html;
    </script>
    """,

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

def generate_media_player(fileurl, image="", autostart=False, **kwargs):
    # Warning - fileurl had better be an ABSOLUTE url, else some media players won't find the file !

    md5 = hashlib.md5()
    md5.update(fileurl.encode('ascii', 'ignore'))
    myhash = md5.hexdigest()[0:8]

    options = \
    {
        "title": "Video Viewer",
        "id": myhash, # risks of collision are ultra weak...
        "media_full_url": config.MEDIA_URL,
        "autoplay": "true" if autostart else "false",
        "allowfullscreen": "true",
        "transparency": "opaque", # transparent, window
        "background": "#000000",
        "backgroundqt": "black",
        "fileurl": fileurl,
        "image": image, # warning - gif images aren't supported by all players !
        "width": 450,
        "height": 350,
        "additional_flash_vars": "" # must begin with '&' if present
    }
    options.update(kwargs)


    extension = os.path.splitext(fileurl)[1][1:].lower() # we remove the dot and lower-case the extension

    for extensions in _media_player_templates.keys():
        if extension in extensions:
            template = _media_player_templates[extensions]
            return template % options

    raise ValueError("Unsupported media type")






# We could use the JS script to load this SWF in a safer way, but well...
# <!--script language="JavaScript" src="{{ media_full_url }}audioplayer/audio-player.js"></script-->
_mp3_template = """
    <object width="300px" height="24px" type="application/x-shockwave-flash" data="%(media_full_url)saudioplayer/player.swf" class="audioplayer">
        <param name="movie" value="%(media_full_url)saudioplayer/player.swf" />
        <param name="FlashVars" value="%(audiosettings)s" /> <!-- additional value: &playerID=id-of-script-tag -->
        <param name="quality" value="high" />
        <param name="scale" value="showall" />
        <param name="menu" value="true" />  <!-- add or not additional right-click menu entries -->
        <param name="wmode" value="transparent" /> <!--  opacity of background in shrinked mode - alternatives : opaque, window -->
        <p>Error - Your browser doesn't seem to support Flash, please install it from <a target="_blank" href="http://get.adobe.com/flashplayer/">the Adobe site</a>.</p>
    </object> 
"""

def generate_audio_player(files, titles=None, artists=None, autostart=False):

    audiosettings = (# one long string of '&' separated options
                    "bg=0xEFDCC2&" +
                    "leftbg=0xDFBD99&" +
                    "lefticon=0x6F5129&" +
                    "voltrack=0xEFDCC2&" +
                    "volslider=0x6F5129&" +
                    "rightbg=0xDFBD99&" +
                    "rightbghover=0xCFAD89&" +
                    "righticon=0x6F5129&" +
                    "righticonhover=0xffffff&" +
                    "text=0x6F5129&" +
                    "track=0xEFDCC2&" +
                    "tracker=0xDFBD99&" +
                    "border=0x6F5129&" +
                    "loader=0xDFBD99&" +
                    "skip=0x6F5129&" +
                    "loop=no&" +
                    "autostart=" + ("yes" if autostart else "no") + "&" +
                    "animation=no&" + # shrinking/etending of the player
                    "initialvolume=60&" +
                    #"soundFile=" + ",".join(files) +
                    urlencode({"soundFile": ",".join(files)}) +
                    ("&" + urlencode({"titles": ",".join(titles)}) if titles else "") +
                    ("&" + urlencode({"artists": ",".join(artists)}) if artists else "")

                    # Options visibly not working without instantiating SWF through javascript...
                    #"width=50%&" +
                    #"transparentpagebg=0x00FF00&" +
                    #"pagebg=0xFF0000&" +
                    )

    options = {
                "media_full_url": config.MEDIA_URL,
                "audiosettings": audiosettings
              }

    return _mp3_template % options



def generate_image_viewer(imageurl, **kwargs):

    md5 = hashlib.md5()
    md5.update(imageurl.encode('ascii', 'ignore'))
    myhash = md5.hexdigest()[0:8]

    options = \
    {
        "title": "Image Viewer",
        "id": myhash,
        "imageurl": imageurl,
        "width": 450,
        "height": 350,
    }

    template = ("""<a href="%(imageurl)s"><img class="imageviewer" src="%(imageurl)s" title="%(title)s"id="%(id)s" """ +
               """style="max-width: %(width)spx; max-height:%(height)spx"/></a>""")

    return template % options




def build_proper_viewer(fileurl, **kwargs): # interesting kwarg : "autostart"

    # we try to provide the best player for this media type

    if not fileurl:
        return ""

    extension = os.path.splitext(fileurl)[1][1:].lower() # no starting dot

    if extension == "mp3": # fileurl may be a string of comma-separated mp3 urls - it works
        return generate_audio_player([fileurl], **kwargs)
    elif extension in ["jpg", "jpeg", "gif", "bmp", "png", "tif"]:
        return generate_image_viewer(fileurl, **kwargs)
    else:
        try:
            return generate_media_player(fileurl, **kwargs) # warning - this media player also supports mp3, so put it after the audio player !
        except ValueError:
            name = os.path.basename(fileurl)
            return '<div class="medialink">' + _("Access file") + ' <a target="_blank" href="%s">%s</a></div>' % (fileurl, name if name else _("here")) # last solution - giving a simple link

