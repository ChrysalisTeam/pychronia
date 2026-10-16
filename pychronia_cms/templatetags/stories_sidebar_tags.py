"""
Sidebar widgets for the djangocms-stories blog, mirroring the "Categories" and "Archives"
widgets the old zinnia-based blog rendered via its own {% get_categories %} /
{% get_archives_entries_tree %} template tags (see pychronia_cms/templates/djangocms_stories/
base.html for how these are plugged into the page layout).

djangocms-stories itself only exposes this data through CMS plugins
(djangocms_stories.cms_plugins.BlogCategoryPlugin / BlogArchivePlugin), which require an
editor to drop them into a placeholder. These tags reuse the exact same queries directly,
so the widgets always render automatically on every blog page, with no CMS placeholder setup
needed - mirroring how the old zinnia tags worked.

Unlike the stock BlogArchivePlugin (which groups by year+month), the archive widget here
only goes down to year granularity, per product decision - djangocms-stories has no month/day
URL below the year/month archive routes, and the project no longer wants day-level navigation.
"""
from django.contrib.sites.shortcuts import get_current_site
from django.db.models import Q
from django.template import Library
from django.utils.translation import get_language

from djangocms_stories.cms_appconfig import get_app_instance
from djangocms_stories.models import Post, PostCategory

register = Library()


@register.inclusion_tag("djangocms_stories/includes/categories_widget.html", takes_context=True)
def stories_categories_widget(context):
    request = context["request"]
    _, config = get_app_instance(request)
    qs = PostCategory.objects.active_translations(get_language())
    if config:
        qs = qs.filter(app_config__namespace=config.namespace)
    site = get_current_site(request)
    qs = qs.filter(Q(posts__sites__isnull=True) | Q(posts__sites=site.pk))
    if not config or not config.menu_empty_categories:
        qs = qs.filter(posts__isnull=False)
    categories = qs.distinct().order_by("translations__name")
    return {"categories": categories}


@register.inclusion_tag("djangocms_stories/includes/archive_years_widget.html", takes_context=True)
def stories_archive_years_widget(context):
    request = context["request"]
    _, config = get_app_instance(request)
    site = get_current_site(request)
    qs = Post.objects.on_site(site)
    if config:
        qs = qs.filter(app_config=config)
    years = {}
    for month in Post.objects.get_months(queryset=qs):
        years[month["date"].year] = years.get(month["date"].year, 0) + month["count"]
    years_list = sorted(years.items(), reverse=True)
    return {"years": years_list, "namespace": config.namespace if config else "djangocms_stories"}
