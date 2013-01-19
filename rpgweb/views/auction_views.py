# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *
from rpgweb.views._abstract_game_view import register_view
from rpgweb import forms

@register_view(access=UserAccess.anonymous, always_available=True)
def homepage(request, template_name='auction/homepage.html'):

    return render(request,
                  template_name,
                    {
                     'page_title': _("Welcome to Anthropia, %s") % request.datamanager.username,
                    })


@register_view(access=UserAccess.anonymous, always_available=True)
def opening(request, template_name='auction/opening.html'): # NEEDS FIXING !!!!

    return render(request,
                  template_name,
                    {
                     'page_title': None,
                    })
