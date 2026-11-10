"""
Per-language URLs of the page being viewed, for the language switcher and the <link rel="alternate"
hreflang> / canonical tags of cms_base.html.

CMS pages and blog posts are handled by django-cms's own language changer (the one behind
{% page_language_url %}: page slugs per language, toolbar object for posts). djangocms-stories'
category pages register no toolbar object, so cms would just swap the language prefix and keep
the current-language category slug (a 404, or a duplicate page served via the parler fallback):
they are mapped here through the category's own per-language slug instead.
"""
from django.conf import settings
from django.template import Library
from django.urls import NoReverseMatch
from django.utils.translation import get_language, get_language_info

from cms.utils import get_current_site
from cms.utils.i18n import force_language, get_public_languages
from djangocms_stories.models import PostCategory
from menus.utils import DefaultLanguageChanger

register = Library()

# only query param worth keeping across languages (blog list pagination), others are toolbar/editing noise
_KEPT_QUERY_PARAMS = ("page",)


def _get_path_in_language(context, lang):
    """Path of the current page in `lang`, or None if it has no version in that language."""
    request = context["request"]
    category = context.get("category")
    if isinstance(category, PostCategory):
        if not category.has_translation(lang):
            return None
        with force_language(lang):
            path = category.get_absolute_url(lang)
    else:
        language_changer = getattr(request, "_language_changer", None) or DefaultLanguageChanger(request)
        try:
            path = language_changer(lang)
        except NoReverseMatch:
            path = DefaultLanguageChanger(request)(lang)
    # cms falls back to another language's url (or to the bare /<lang>/ root) for untranslated pages
    if not path or not path.startswith("/%s/" % lang) or path == "/%s/" % lang:
        return None
    query = request.GET.copy()
    for key in list(query):
        if key not in _KEPT_QUERY_PARAMS:
            del query[key]
    if query:
        path += "?" + query.urlencode()
    return path


@register.simple_tag(takes_context=True)
def language_alternates(context):
    """
    One dict per public CMS language the current page exists in: code, (capitalized native) name,
    absolute url, is_current, and is_default (LANGUAGE_CODE, i.e. the hreflang "x-default" one).
    Empty list outside of a request (e.g. error pages).
    """
    request = context.get("request")
    if request is None:
        return []
    current_language = get_language()
    alternates = []
    for lang in get_public_languages(site_id=get_current_site(request).pk):
        path = _get_path_in_language(context, lang)
        if path is None:
            continue
        alternates.append({
            "code": lang,
            "name": get_language_info(lang)["name_local"].capitalize(),
            "url": request.build_absolute_uri(path),
            "is_current": lang == current_language,
            "is_default": lang == settings.LANGUAGE_CODE,
        })
    return alternates
