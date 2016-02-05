# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

import sys, re, logging, random, logging, json
from datetime import datetime

from pychronia_game.utilities import (mediaplayers, autolinker,
                                      rst_directives, is_absolute_url) # important to register RST extensions
from pychronia_game.common import exception_swallower, game_file_url as real_game_file_url, determine_asset_url, reverse, game_view_url, _

import django.template
from django.templatetags.future import url as default_url_tag
from django.utils.safestring import SafeData, EscapeData, mark_safe, mark_for_escaping
from django.utils.html import escape
from django.utils.http import urlencode
from django.core.serializers import serialize
from django.db.models.query import QuerySet
from django.template.defaultfilters import stringfilter
from django.template.defaultfilters import linebreaks

import urllib
from textwrap import dedent
from easy_thumbnails.templatetags.thumbnail import thumbnail_url
from easy_thumbnails.files import get_thumbnailer
from pychronia_game.storage import protected_game_file_system_storage, \
    get_game_thumbnailer
from pychronia_game.common import config, utctolocal
from django.template.loader import render_to_string

register = django.template.Library() # IMPORTANT, module-level object used by templates !


GAME_LOCAL_TZ = config.GAME_LOCAL_TZ # real timezone object


def _try_generating_thumbnail_url(rel_path, alias=None):
    """
    Falls back to original fail url if thumbnail generation fails, or if no alias is provided.
    """
    if alias:
        try:
            thumb = get_game_thumbnailer(rel_path)[alias] # we enforce the GAME_FILES storage here!
            return thumb.url
        except Exception, e:
            logging.warning("Error generating game_file_img %s (alias=%s): %r", rel_path, alias, e)
            pass # fallback to plain file

    return real_game_file_url(rel_path) # original image



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

@register.tag(name="game_view_url")
def game_view_url_tag(parser, token):
    """
    Only works if a "game_instance_id" and "game_username" template variables are available (use request processors for that).
    """
    #print ("PARSING IN GAMLEURL", token.contents, "\n")
    redirector = False
    content = token.contents

    if " redirector" in content:
        redirector = True
        content = content.replace(" redirector", "")

    sep = " as "
    parts = content.rsplit(sep, 1) # beware of alternate form of url tag
    from pychronia_game.authentication import TEMP_URL_USERNAME  # FIXME - move that to a better place
    new_content = parts[0] + " game_instance_id=game_instance_id game_username=%s" % ("game_username" if not redirector else "'%s'" % TEMP_URL_USERNAME)
    if len(parts) > 1:
        assert len(parts) == 2
        new_content += sep + parts[1]

    token.contents = new_content # we thus injected template vars "game instance id" and "game username"
    url_node = default_url_tag(parser, token)
    return url_node


@register.simple_tag(takes_context=True, name="game_file_url")
def game_file_url_tag(context, a="", b="", c="", d="", e="", f="", varname=None):
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
    if is_absolute_url(rel_path):
        return rel_path  # might be an external URL, it can't be resized then...
    return _try_generating_thumbnail_url(rel_path=rel_path, alias=alias)



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
    """
    Generates file urls ; tag must be in the form [ GAME_FILE_URL "images/emblems/auction_logo_rounded.png" ]
    """
    if __debug__: datamanager.notify_event("GENERATE_GAME_FILE_LINKS")
    regex = r"""\[\s*GAME_FILE_URL\s*('|")?(?P<path>.+?)('|")?\s*]"""
    def _replacer(match_obj):
        rel_path = match_obj.group("path")
        fullpath = real_game_file_url(rel_path)
        return fullpath
    return re.sub(regex, _replacer, rst_content)


def _generate_game_image_thumbnails(rst_content, datamanager):
    """
    Generates urls of thumbnails ; tag must be in the form [ GAME_IMAGE_URL "images/emblems/auction_logo_rounded.png" "default" ]
    """
    if __debug__: datamanager.notify_event("GENERATE_GAME_IMAGE_THUMBNAILS")
    regex = r"""\[\s*GAME_IMAGE_URL\s*('|")(?P<path>.+?)('|")\s*('|")(?P<alias>.+)('|")\s*]"""
    def _replacer(match_obj):
        rel_path = match_obj.group("path")
        alias = match_obj.group("alias")
        fullpath = _try_generating_thumbnail_url(rel_path=rel_path, alias=alias)
        return fullpath
    return re.sub(regex, _replacer, rst_content)


def _generate_encyclopedia_links(html_snippet, datamanager, excluded_link=None):
    """
    Replaces identified keywords by links to corresponding encyclopedia pages.
    """
    if __debug__: datamanager.notify_event("GENERATE_ENCYCLOPEDIA_LINKS")
    keywords_mapping = datamanager.get_encyclopedia_keywords_mapping(excluded_link=excluded_link, only_primary_keywords=True)

    def encyclopedia_link_attr_generator(match):
        matched_str = match.group(0)
        assert matched_str
        # detecting here WHICH keyword triggered the match would be possible, but expensive... let's postpone that
        link = game_view_url("pychronia_game.views.view_encyclopedia", datamanager=datamanager)
        link += "?search=%s" % urllib.quote_plus(matched_str.encode("utf8"), safe=b"")
        return dict(href=link)
    regex = autolinker.join_regular_expressions_as_disjunction(keywords_mapping.keys(), as_words=True)
    ##print (">>>>>>>> REGEX", repr(regex))
    if regex:
        html_res = autolinker.generate_links(html_snippet, regex=regex, link_attr_generator=encyclopedia_link_attr_generator)
    else:
        html_res = html_snippet # no changes
    return html_res


def _generate_messaging_links(html_snippet, datamanager):
    """
    Generates "new message" links for emails identified, provided they have had their @ escapes with a backslash
    (else they end up as standard mailto links because of docutils systems).
    
    ATM we also generate links for current user, but it's not a problem.
    """
    if __debug__: datamanager.notify_event("GENERATE_MESSAGING_LINKS")
    def email_link_attr_generator(match):
        matched_str = match.group(0)
        link = game_view_url("pychronia_game.views.compose_message", datamanager=datamanager)
        link += "?recipient=%s" % urllib.quote_plus(matched_str.encode("utf8"), safe=b"")
        return dict(href=link)
    regex = r"\b[-_\w.]+@\w+\.\w+\b"
    html_res = autolinker.generate_links(html_snippet, regex=regex, link_attr_generator=email_link_attr_generator)
    return html_res


def _generate_site_links(html_snippet, datamanager):
    """
    Generates a site link, similarly to django's URL tag ; tag must be in the form [ GAME_PAGE_LINK "click here" "pychronia.views.homepage" ]
    Rg, in rst-generated text.
    """
    if __debug__: datamanager.notify_event("GENERATE_SITE_LINKS")
    def site_link_attr_generator(match):
        matched_str = match.group("view")
        if "." not in matched_str:
            matched_str = "pychronia_game.views." + matched_str
        try:
            link = game_view_url(matched_str, datamanager=datamanager)
            return dict(href=link)
        except Exception:
            logging.warning("Error in generate_site_links for match %r", matched_str, exc_info=True)
            return None # abort link creation
    regex = r"""\[\s*GAME_PAGE_LINK\s*('|")(?P<content>[^"]+)('|")\s*('|")(?P<view>[.\w]+)('|")\s*]""" # content will be the text used as link
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





def format_enriched_text(datamanager, content, initial_header_level=None, report_level=None, excluded_link=None, text_format=None):
    """
    Converts RST content to HTML and adds encyclopedia links.
    
    *excluded_link* is the ENCYCLOPEDIA article_id in which we currently are, if any.
    """
    assert isinstance(content, basestring)

    #print(">>>format_enriched_text", content[:30], "----", excluded_link)

    # we leave RestructuredRext as the DEFAULT format for game contents
    text_format = text_format or datamanager.AVAILABLE_TEXT_FORMATS.rst

    content = content.replace("[INSTANCE_ID]", datamanager.game_instance_id) # handy to build URLs manually

    with exception_swallower():
        content = _generate_game_file_links(content, datamanager) # BEFORE html
    with exception_swallower():
        content = _generate_game_image_thumbnails(content, datamanager) # BEFORE html

    if text_format == datamanager.AVAILABLE_TEXT_FORMATS.rst:
        html = advanced_restructuredtext(content, initial_header_level=initial_header_level, report_level=report_level)
    else:
        assert text_format in (None, datamanager.AVAILABLE_TEXT_FORMATS.raw)
        html = linebreaks(content)  # only adds <p> and <br> tags

    #print(">>>format_enriched_text>>>>>", html)
    with exception_swallower():
        html = _generate_encyclopedia_links(html, datamanager, excluded_link=excluded_link)
    with exception_swallower():
        html = _generate_messaging_links(html, datamanager)
    with exception_swallower():
        html = _generate_site_links(html, datamanager) # o

    html = html.replace("[BR]", "<br />") # line breaks, handy for vertical spacing
    html = html.replace("[NBSP]", unichr(160)) # non-breaking spaces, handy for punctuation mainly

    return html


@register.simple_tag(takes_context=True)
def rich_text(context, content, initial_header_level=None, report_level=None, excluded_link=None, text_format=None):
    """
    Converts to enriched html the restructuredtext content of the variable.
    """
    request = context.get('request')
    report_level = report_level if report_level is not None else 5 # FIXME - by default we DO NOT display RST syntax errors!
    result = format_enriched_text(request.datamanager, content, initial_header_level=initial_header_level,
                                  report_level=report_level, excluded_link=excluded_link,
                                  text_format=text_format)

    content_id = str(random.randint(1, 10000000000))
    html = render_to_string('utilities/rich_text.html', {'content_id':content_id,
                                                         'source': content,
                                                         'result': result,
                                                         'display_admin_tips': request.datamanager.should_display_admin_tips()})
    return html




@register.simple_tag
def fontawesome_icon(icon, large=True, fixed=False, spin=False, li=False,
    rotate=False, border=False, color=False):

    return '<i class="{prefix} {prefix}-{icon}{large}{fixed}{spin}{li}{rotate}{border}"{color}></i>'.format(
        prefix='fa',
        icon=icon,
        large=' fa-lg' if large is True else '',
        fixed=' fa-fw' if fixed else '',
        spin=' fa-spin' if spin else '',
        li=' fa-li' if li else '',
        rotate=' fa-rotate-%s' % str(rotate) if rotate else '',
        border=' fa-border' if border else '',
        color='style="color:%s;"' % color if color else ''
    )


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

    returnformat_enriched_text(request.datamanager, content, initial_header_level=initial_header_level, excluded_link=article_name)
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

def list_sum(value):
    """
    Simple sum (or concatenate) all items in list.
    """
    if not value:
        return None
    return sum(value, value[0].__class__())
register.filter('list_sum', list_sum)


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


def matrix_extract_column(value, offset):
    """
    Extracts the nth element of each item in a list.
    """
    offset = int(offset)
    return [val[offset] for val in value]
register.filter('matrix_extract_column', matrix_extract_column)


def list_append_to_each(value, suffix):
    """
    Appends a suffix to each value of the strings list.
    """
    return [unicode(val) + suffix for val in value]
register.filter('list_append_to_each', list_append_to_each)


register.filter('utctolocal', utctolocal)


def _determine_asset_url(properties):
    return determine_asset_url(properties)
register.filter('determine_asset_url', _determine_asset_url)


def mediaplayer(properties, autostart="false"):

    fileurl = determine_asset_url(properties)
    title = properties.get("title") if hasattr(properties, "get") else properties  # might even be None

    try:
        res = mediaplayers.build_proper_viewer(fileurl, title=title, autostart=(autostart == "true"))
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

def split(var, sep):
    return var.split(sep)
register.filter('split', split)

def jsonify(object):
    if isinstance(object, QuerySet):
        return serialize('json', object)
    return mark_safe(json.dumps(object))
register.filter('jsonify', jsonify)

def has_unread_msg(ctx_msgs_list):
    res = False
    for ctx, msg in ctx_msgs_list:
        if not ctx["has_read"]:
            res = True
            break
    return res
register.filter('has_unread_msg', has_unread_msg)

def has_starred_msg(ctx_msgs_list):
    res = False
    for ctx, msg in ctx_msgs_list:
        if ctx["has_starred"]:
            res = True
            break
    return res
register.filter('has_starred_msg', has_starred_msg)




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
