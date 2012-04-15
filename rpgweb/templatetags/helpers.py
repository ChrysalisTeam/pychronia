# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

import re
import django.template, logging
from datetime import datetime
from django.template import defaulttags

from rpgweb.utilities import mediaplayers
from rpgweb.common import exception_swallower
from django.core.urlresolvers import reverse
register = django.template.Library() # IMPORTANT, module-level object used by templates !

from django.utils.safestring import SafeData, EscapeData, mark_safe, mark_for_escaping
from django.utils.html import escape
from django.utils.http import urlencode
from django.contrib.markup.templatetags.markup import restructuredtext


@register.tag
def gameurl(parser, token):
    """
    Only works if a "game_instance_id" template variable is available (use request processors for that).
    """
    token.contents += " game_instance_id=game_instance_id" # we inject template var "game instance id"
    url_node = defaulttags.url(parser, token) 
    return url_node



@register.simple_tag(takes_context=True)
def usercolor(context, username_or_email):
    """
    Determines if an HTML color is attached to the user/email, or returns None instead.
    """
    color = None
    with exception_swallower():
        request = context.get('request')
        if "@" in username_or_email:
            username = request.datamanager.get_character_or_none_from_email(username_or_email)
        else: 
            username = username_or_email
        color = request.datamanager.get_character_color_or_none(username)
    return color or "black" # default color



def _generate_encyclopedia_links(html, datamanager):
    """
    Beware - ATM, that system doesn't detected nested links, and will always
    replace keywords by encyclopedia links.
    """
    keywords = datamanager.get_encyclopedia_keywords()
    #print(">>>>", repr(keywords))
    base_url = reverse("rpgweb.views.view_encyclopedia", kwargs={"game_instance_id":datamanager.game_instance_id})
    for keyword, article_id in keywords.items(): 
        source= ur'(?<!=)\b(%s)\b' % re.escape(escape(keyword))
        
        #skipped_keywords_re = "(?P<preceding><a(?:(?!</a>))*)(?P<keyword>%s)" % keyword_re
        #skipped_keywords_replacement_re = "(?P=preceding)______(?P=keyword)"
        
        dest = ur'<a href="%s?%s">\1</a>' % (base_url, urlencode([("article_id", article_id)]))
        #print(source, dest)
        html = re.sub(source,
                       dest,
                       html,
                       flags=re.IGNORECASE|re.UNICODE)
    return html         
                 

@register.simple_tag(takes_context=True)
def rich_text(context, rst):
    """
    Converts a restructured
    """
    request = context.get('request')
    html = restructuredtext(rst)
    
    with exception_swallower():
        return _generate_encyclopedia_links(html, request.datamanager)
    return html  # on error


''' ???
def threefirstletters(value):
    """
    Returns the three first letters or less.
    """
    with exception_swallower():
        return value[0:3]
    return "" # value evaluating to false    
register.filter('threefirstletters',threefirstletters)
'''



def dict_get(value, arg):
    """
    Custom template tag used like so:
    {{dictionary|dict_get:var}}
    where dictionary is a dictionary and var is a variable representing
    one of it's keys
    """
    try:
        return value[arg]
    except:
        # NO ERROR, templates can just be used to test for the existence of a key, this way !
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