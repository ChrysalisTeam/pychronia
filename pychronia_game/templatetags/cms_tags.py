# -*- coding: utf-8 -*-

from django import template


register = template.Library()

@register.simple_tag(takes_context=False)
def cms_toolbar(*args):
    """
    DUMMY tag to replace the real cmd_toolbar from django-cms in the base "metal_radiance" template.
    """
    return ""

