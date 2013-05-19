# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

import sys, re, logging, random, logging
from datetime import datetime

from rpgweb.utilities import (mediaplayers, autolinker,
                             rst_directives) # important to register RST extensions
from rpgweb.common import exception_swallower, game_file_url as real_game_file_url, determine_asset_url, reverse, _

import django.template
from django.templatetags.future import url as default_url_tag
from django.utils.safestring import SafeData, EscapeData, mark_safe, mark_for_escaping
from django.utils.html import escape
from django.utils.http import urlencode
from django.core.serializers import serialize
from django.db.models.query import QuerySet
from django.utils import simplejson
from django.template.defaultfilters import stringfilter

import urllib
from textwrap import dedent
from easy_thumbnails.templatetags.thumbnail import thumbnail_url
from easy_thumbnails.files import get_thumbnailer
from rpgweb.storage import protected_game_file_system_storage, \
    get_game_thumbnailer

register = django.template.Library() # IMPORTANT, module-level object used by templates !


@register.simple_tag(takes_context=False)
def first_non_empty(*args):
    for arg in args:
        if arg:
            return arg
    return ""


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
    sep = " as "
    parts = token.contents.split(sep) # beware of alternate form of url tag
    if len(parts) > 1:
        new_content = " as ".join(parts[:-1]) + " game_instance_id=game_instance_id" + sep + parts[-1]
    else:
        new_content = parts[0] + " game_instance_id=game_instance_id"

    token.contents = new_content # we thus injected template var "game instance id"
    url_node = default_url_tag(parser, token)
    return url_node

@register.simple_tag(takes_context=True)
def game_file_url(context, a="", b="", c="", d="", e="", f="", varname=None):
    """
    Here "varname" is the varuiable under which to store the result, if any.
    """
    assert not isinstance(context, basestring)
    rel_path = "".join((a, b, c, d, e, f))
    full_url = real_game_file_url(rel_path)
    if varname is not None:
        assert varname, "wrong game_file_url varname %s" % varname
        context[varname] = full_url
        return ""
    else:
        return full_url

@register.simple_tag(takes_context=False)
def game_file_img(a="", b="", c="", d="", e="", f="", alias=None):
    rel_path = "".join((a, b, c, d, e, f))
    if alias is not None:
        try:
            thumb = get_game_thumbnailer(rel_path)[alias] # we enforce the GAME_FILES storage here!
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



def _generate_game_file_links(rst_content, datamanager):
    if __debug__: datamanager.notify_event("GENERATE_GAME_FILE_LINKS")
    regex = r"""\[\s*GAME_FILE_URL\s*('|")?(?P<path>.+?)('|")?\s*]"""
    def _replacer(match_obj):
        relpath = match_obj.group("path")
        fullpath = real_game_file_url(relpath)
        return fullpath
    return re.sub(regex, _replacer, rst_content)


def _generate_encyclopedia_links(html_snippet, datamanager, excluded_link=None):
    if __debug__: datamanager.notify_event("GENERATE_ENCYCLOPEDIA_LINKS")
    keywords_mapping = datamanager.get_encyclopedia_keywords_mapping(excluded_link=excluded_link)

    def encyclopedia_link_attr_generator(match):
        matched_str = match.group(0)
        # detecting here WHICH keyword triggered the match would be possible, but expensive... let's postpone that
        link = reverse("rpgweb.views.view_encyclopedia",
                       kwargs={"game_instance_id": datamanager.game_instance_id})
        link += "?search=%s" % urllib.quote_plus(matched_str.encode("utf8"), safe=b"")
        return dict(href=link)
    regex = autolinker.join_regular_expressions_as_disjunction(keywords_mapping.keys(), as_words=True)
    html_res = autolinker.generate_links(html_snippet, regex=regex, link_attr_generator=encyclopedia_link_attr_generator)
    return html_res


def _generate_messaging_links(html_snippet, datamanager):
    """
    ATM we also generate links for current user, but it's not a problem.
    """
    if __debug__: datamanager.notify_event("GENERATE_MESSAGING_LINKS")
    def email_link_attr_generator(match):
        matched_str = match.group(0)
        link = reverse("rpgweb.views.compose_message",
                       kwargs={"game_instance_id": datamanager.game_instance_id})
        link += "?recipient=%s" % urllib.quote_plus(matched_str.encode("utf8"), safe=b"")
        return dict(href=link)
    regex = r"\b\w+@\w+\.\w+\b"
    html_res = autolinker.generate_links(html_snippet, regex=regex, link_attr_generator=email_link_attr_generator)
    return html_res


def _generate_site_links(html_snippet, datamanager):
    """
    Replacement for django's url template tag, in rst-generated text.
    """
    if __debug__: datamanager.notify_event("GENERATE_SITE_LINKS")
    def site_link_attr_generator(match):
        matched_str = match.group("view")
        if "." not in matched_str:
            matched_str = "rpgweb.views." + matched_str
        try:
            link = reverse(matched_str, kwargs={"game_instance_id": datamanager.game_instance_id})
            return dict(href=link)
        except Exception:
            logging.warning("Error in generate_site_links for match %r", matched_str, exc_info=True)
            return None # abort link creation
    regex = r"""\{% "(?P<content>[^"]+)" "(?P<view>[.\w]+)" %\}"""
    html_res = autolinker.generate_links(html_snippet, regex=regex, link_attr_generator=site_link_attr_generator)
    return html_res



def advanced_restructuredtext(value,
                              initial_header_level=None,
                              report_level=None): # report
    '''
    *value* is the text to parse as restructuredtext.
    
    initial-header-level
        Specify the initial header level.  Default is 1 for
        "<h1>".  Does not affect document title & subtitle
        (see --no-doc-title).
                        
    report_level
        Report system messages at or higher than <level> - 
        "info" or "1", "warning"/"2" (default), "error"/"3",
        "severe"/"4", "none"/"5" (ONLY INTEGERS WORK ATM).
    '''
    from django import template
    from django.conf import settings
    from django.utils.encoding import smart_str, force_unicode
    assert initial_header_level is None or isinstance(initial_header_level, (int, long))
    assert report_level is None or isinstance(report_level, (int, long)) ### NO, TOO RECENT or report_level in "info warning error severe none".split()
    try:
        from docutils.core import publish_parts
    except ImportError:
        if settings.DEBUG:
            raise template.TemplateSyntaxError("Error in 'restructuredtext' filter: The Python docutils library isn't installed.")
        return force_unicode(value)
    else:
        docutils_settings = getattr(settings, "RESTRUCTUREDTEXT_FILTER_SETTINGS", {}).copy() # VERY IMPORTANT - copy it!!!
        if initial_header_level is not None:
            docutils_settings.update(initial_header_level=initial_header_level)
        if report_level is not None:
            docutils_settings.update(report_level=report_level)
        #print(">><<", docutils_settings, file=sys.stderr)
        parts = publish_parts(source=smart_str(value), writer_name="html4css1", settings_overrides=docutils_settings)
        return mark_safe(force_unicode(parts["fragment"]))





def _enriched_text(datamanager, content, initial_header_level=None, report_level=None, excluded_link=None):
    """
    Converts RST content to HTML and adds encyclopedia links.
    
    *excluded_link* is the ENCYCLOPEDIA article_id in which we currently are, if any.
    """

    content = content.replace("[INSTANCE_ID]", datamanager.game_instance_id) # handy to build URLs manually

    with exception_swallower():
        content = _generate_game_file_links(content, datamanager) # BEFORE html

    html = advanced_restructuredtext(content, initial_header_level=initial_header_level, report_level=report_level)

    with exception_swallower():
        html = _generate_encyclopedia_links(html, datamanager, excluded_link=excluded_link)
    with exception_swallower():
        html = _generate_messaging_links(html, datamanager)
    with exception_swallower():
        html = _generate_site_links(html, datamanager) # o

    html = html.replace("[BR]", "<br />") # handy for vertical spacing

    return html


@register.simple_tag(takes_context=True)
def rich_text(context, content, initial_header_level=None, report_level=None, excluded_link=None):
    """
    Converts to enriched html the restructuredtext content of the variable.
    """
    request = context.get('request')
    report_level = report_level if report_level is not None else 5 # by default we DO NOT display RST syntax errors!
    return _enriched_text(request.datamanager, content, initial_header_level=initial_header_level, report_level=report_level, excluded_link=excluded_link)


'''
@register.simple_tag(takes_context=True)
def static_page(context, article_name, initial_header_level=None):
    """
    Converts to enriched html the restructuredtext content of the targeted article (or displays nothing).
    """
    assert article_name, article_name
    request = context.get('request')
    pages_table = request.datamanager.static_pages
    if article_name in pages_table:
        content = pages_table[article_name]["content"]
    elif request.datamanager.is_master:
        content = _(dedent("""
                        .. container:: .missing-content
                        
                            Article *%s* would appear here.
                        """)) % article_name
    else:
        return "" # normal users see nothing here

    return _enriched_text(request.datamanager, content, initial_header_level=initial_header_level, excluded_link=article_name)
'''



def _do_corrupt_string(value):
    return ''.join(['&#%s;<span class="obfusk">%s</span>' % (ord(char), random.randint(10, 100)) for char in value]) # html entities
@stringfilter
def corrupt_string(value):
    return mark_safe(_do_corrupt_string(value))
register.filter('corrupt_string', corrupt_string)

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


def utctolocal(value, arg=None): # FIXME - BUGGY CALLS
    # poor man's timezone system, base on current time offset
    # all we want ATM is to avoid dealing with the nightmare of TZ and DST...
    try:
        timedelta = datetime.now() - datetime.utcnow() # both NAIVE datetimes
        return value + timedelta
    except:
        logging.critical("utctolocal filter failed", exc_info=True)
        return value
register.filter('utctolocal', utctolocal)


def mediaplayer(properties, autostart=False):

    fileurl = determine_asset_url(properties)

    try:
        res = mediaplayers.build_proper_viewer(fileurl, autostart=(autostart == "true"))
        return mark_safe(res)
    except:
        logging.error("mediaplayer filter failed", exc_info=True)
        return mark_safe("<a href=" + fileurl + ">" + fileurl + "</a>")
mediaplayer.is_safe = True
register.filter('mediaplayer', mediaplayer)


def has_permission(user, permission):
    if user.has_permission(permission=permission):
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
register.filter('ddd', ddd)
"""
