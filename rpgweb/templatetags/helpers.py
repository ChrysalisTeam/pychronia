# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

import re, logging, random
from datetime import datetime

from rpgweb.utilities import mediaplayers, autolinker
from rpgweb.common import exception_swallower, game_file_url as real_game_file_url, reverse, _

import django.template
from django.templatetags.future import url as default_url_tag
from django.utils.safestring import SafeData, EscapeData, mark_safe, mark_for_escaping
from django.utils.html import escape
from django.utils.http import urlencode
from django.core.serializers import serialize
from django.db.models.query import QuerySet
from django.utils import simplejson
import urllib
from textwrap import dedent
from easy_thumbnails.templatetags.thumbnail import thumbnail_url
from easy_thumbnails.files import get_thumbnailer
from rpgweb.storage import protected_game_file_system_storage


register = django.template.Library() # IMPORTANT, module-level object used by templates !

@register.simple_tag(takes_context=False)
def random_id():
    """Tag to generate random ids in HTML tags, just to please javascript utilities."""
    return "uuid-" + str(random.randint(1000000, 1000000000))

@register.tag
def game_view_url(parser, token):
    """
    Only works if a "game_instance_id" template variable is available (use request processors for that).
    """
    #print ("PARSING IN GAMLEURL", token.contents, "\n")
    token.contents += " game_instance_id=game_instance_id" # we inject template var "game instance id"
    url_node = default_url_tag(parser, token)
    return url_node

@register.simple_tag(takes_context=False)
def game_file_url(a="", b="", c="", d="", e="", f="", thumb=None): # simple tag doesn't accept *args or **kwargs...4
    rel_path = "".join((a, b, c, d, e, f))
    full_url = real_game_file_url(rel_path)
    return full_url

@register.simple_tag(takes_context=False)
def game_file_img(a="", b="", c="", d="", e="", f="", alias=None): # simple tag doesn't accept *args or **kwargs...
    rel_path = "".join((a, b, c, d, e, f))
    if alias is not None:
        try:
            thumb = get_thumbnailer(protected_game_file_system_storage, relative_name=rel_path)[alias] # we enforce the GAME_FILES storage here!
        except Exception, e:
            print("ERROR GENERATING game_file_img ", rel_path, alias, repr(e))
            return ''
        return  thumb.url
    else:
        return real_game_file_url(rel_path) # original image




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



def _generate_encyclopedia_links(html_snippet, datamanager, excluded_link=None):

    keywords_mapping = datamanager.get_encyclopedia_keywords_mapping(excluded_link=excluded_link)

    def link_attr_generator(match):
        matched_str = match.group(0)
        # detecting here WHICH keyword triggered the match would be possible, but expensive... let's postpone that
        link = reverse("rpgweb.views.view_encyclopedia",
                       kwargs={"game_instance_id": datamanager.game_instance_id, })
        link += "?search=%s" % urllib.quote_plus(matched_str.encode("utf8"), safe=b"")
        return dict(href=link)

    regex = autolinker.join_regular_expressions_as_disjunction(keywords_mapping.keys(), as_words=True)

    res_html = autolinker.generate_links(html_snippet, regex=regex, link_attr_generator=link_attr_generator)
    return res_html





def advanced_restructuredtext(value, initial_header_level=None):
    from django import template
    from django.conf import settings
    from django.utils.encoding import smart_str, force_unicode
    try:
        from docutils.core import publish_parts
    except ImportError:
        if settings.DEBUG:
            raise template.TemplateSyntaxError("Error in 'restructuredtext' filter: The Python docutils library isn't installed.")
        return force_unicode(value)
    else:
        docutils_settings = getattr(settings, "RESTRUCTUREDTEXT_FILTER_SETTINGS", {})
        if initial_header_level is not None:
            docutils_settings.udpate(initial_header_level=initial_header_level)
        parts = publish_parts(source=smart_str(value), writer_name="html4css1", settings_overrides=docutils_settings)
        return mark_safe(force_unicode(parts["fragment"]))





def _enrich_text(datamanager, content, initial_header_level=None, excluded_link=None):
    """
    Converts RST content to HTML and adds encyclopedia links.
    """
    html = advanced_restructuredtext(content, initial_header_level=initial_header_level)
    with exception_swallower():
        return _generate_encyclopedia_links(html, datamanager, excluded_link=excluded_link) # on error
    return ""


@register.simple_tag(takes_context=True)
def rich_text(context, content, initial_header_level=None):
    """
    Converts to enriched html the restructuredtext content of the variable.
    """
    request = context.get('request')
    return _enrich_text(request.datamanager, content, initial_header_level=initial_header_level)


@register.simple_tag(takes_context=True)
def static_page(context, article_name, initial_header_level=None):
    """
    Converts to enriched html the restructuredtext content of the targeted article (or displays nothing).
    """
    assert article_name, article_name
    request = context.get('request')
    pages_table = request.datamanager.static_pages
    if pages_table.contains_item(article_name):
        content = pages_table.get_item(article_name)["content"]
    elif request.datamanager.is_master:
        content = _(dedent("""
                        .. container:: .missing-content
                        
                            Article *%s* would appear here.
                        """)) % article_name
    else:
        return "" # normal users see nothing here

    return _enrich_text(request.datamanager, content, initial_header_level=initial_header_level, excluded_link=article_name)



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
register.filter('dict_get', dict_get)


def list_filter(value, offset):
    """
    Extracts the nth elemet of each item in a list.
    """
    offset = int(offset)
    return [val[offset] for val in value]
register.filter('list_filter', list_filter)


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
        return mark_safe("<a href=" + fileurl + ">" + fileurl + "</a>")
mediaplayer.is_safe = True
register.filter('mediaplayer', mediaplayer)


def has_permission(user, permission):
    if user.has_permission(permission):
        return True
    else:
        return False
register.filter('has_permission', has_permission)


def jsonify(object):
    if isinstance(object, QuerySet):
        return serialize('json', object)
    return mark_safe(simplejson.dumps(object))
register.filter('jsonify', jsonify)

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
