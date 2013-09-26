# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from pychronia_game.common import *
from pychronia_game.datamanager.abstract_game_view import AbstractGameView, register_view
from pychronia_game import forms
from django.http import Http404, HttpResponseRedirect, HttpResponse

from .info_views import view_encyclopedia

@register_view(access=UserAccess.anonymous, requires_global_permission=False, title=_lazy("Homepage"))
def homepage_mobile(request, template_name="mobile/homepage.html"):
    from django.core import urlresolvers

    return render(request,
                  template_name,
                    {

                    })

 # HttpResponse("<html><body>It works, mobile client - %r</body></html>" % urlresolvers.get_urlconf())



''' LATER ON
@register_view(access=UserAccess.anonymous, requires_global_permission=False, title=_lazy("Encyclopedia"))
def encyclopedia_mobile(request, article_id=None, template_name='mobile/encyclopedia.html'):
    # FIXME THIS IS USELESS, JUST OVERRIDE template_name ARG!!
    template_response = view_encyclopedia(request, article_id=article_id)
    assert template_response.template_name and not template_response.is_rendered
    template_response.template_name = template_name
    return template_response
'''
