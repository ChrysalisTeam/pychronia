import django.template, logging
from datetime import datetime
from django.template import defaulttags

from rpgweb.utilities import mediaplayers

register = django.template.Library() # IMPORTANT, module-level object used by templates !

from django.utils.safestring import SafeData, EscapeData, mark_safe, mark_for_escaping
from django.utils.html import escape


@register.tag
def gameurl(parser, token):
    """
    Only works if a "game_instance_id" template variable is available (use request processors for that).
    """
    token.contents += " game_instance_id=game_instance_id" # we inject template var "game instance id"
    url_node = defaulttags.url(parser, token) 
    return url_node
    

def threefirstletters(value):
    #custom template tag used like so:
    #{{dictionary|dict_get:var}}
    #where dictionary is a dictionary and var is a variable representing
    #one of it's keys
    try :
        return value[0:3]
    except:
        logging.error("threefirstletters filter failed", exc_info=True)
        return "" # value evaluating to false    
register.filter('threefirstletters',threefirstletters)


# dynamic dictionary key in templates
def dict_get(value, arg):
    #custom template tag used like so:
    #{{dictionary|dict_get:var}}
    #where dictionary is a dictionary and var is a variable representing
    #one of it's keys
    try :
        return value[arg]
    except:
        #logging.error("dict_get filter failed", exc_info=True) - NO, templates can just be used to test for the existence of a key, this way !
        return "" # value evaluating to false    
register.filter('dict_get',dict_get)


def utctolocal(value, arg=None):
    # poor man's timezone system, base on current time offset
    # all we want is to avoid dealing with the nightmare of TZ and DST...
    try:    
        timedelta = datetime.now() - datetime.utcnow()
        return value + timedelta
    except:
        logging.error("utctolocal filter failed", exc_info=True)
        return value
register.filter('utctolocal', utctolocal)


def mediaplayer(fileurl, autostart):
    try:
        res = mediaplayers.build_proper_viewer(fileurl, autostart=(autostart == "true"))
        return mark_safe(res)
    except:
        logging.error("mediaplayer filter failed", exc_info=True)
        return mark_safe("<a href="+fileurl+">"+fileurl+"</a>")
mediaplayer.is_safe = True
register.filter('mediaplayer', mediaplayer)


def has_permission(user, permission):
    if user.has_permission(permission):
        return True
    else:
        return False
register.filter('has_permission', has_permission)


def game_color(username):
    return "black"
register.filter('game_color', game_color)


"""
def preformat(value):
    "
    Escapes a string's HTML. This returns a new string containing the escaped
    characters (as opposed to "escape", which marks the content for later
    possible escaping).
    "
    from django.utils.html import escape
    from django.utils.safestring import mark_safe
    return mark_safe(escape(value))
force_escape = stringfilter(force_escape)
force_escape.is_safe = True
register.filter('has_permission', has_permission)
"""