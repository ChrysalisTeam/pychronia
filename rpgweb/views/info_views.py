# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *
from rpgweb.datamanager.abstract_game_view import AbstractGameView, register_view
from rpgweb import forms
from django.http import Http404, HttpResponseRedirect





@register_view(access=UserAccess.anonymous, always_available=True)
def view_encyclopedia(request, article_id=None, template_name='info/encyclopedia.html'):

    dm = request.datamanager

    article_ids = None  # index of encyclopedia
    entry = None  # current article
    search_results = None  # list of matching article ids

    if article_id:
        entry = dm.get_encyclopedia_entry(article_id)
        if not entry:
            dm.user.add_error(_("Sorry, no encyclopedia article has been found for id '%s'") % article_id)
    else:
        search_string = request.REQUEST.get("search")  # needn't appear in browser history, but GET needed for encyclopedia links
        if search_string:
            if not dm.is_game_started():
                dm.user.add_error(_("Sorry, the search engine of the encyclopedia is currently under repair"))
            else:
                search_results = dm.get_encyclopedia_matches(search_string)
                if not search_results:
                    dm.user.add_error(_("Sorry, no matching encyclopedia article has been found for '%s'") % search_string)
                else:
                    if dm.is_character():  # not for master or anonymous!!
                        dm.update_character_known_article_ids(search_results)
                    if len(search_results) == 1:
                        dm.user.add_message(_("Your search has led to a single article, below."))
                        return HttpResponseRedirect(redirect_to=reverse(view_encyclopedia, kwargs=dict(game_instance_id=request.datamanager.game_instance_id,
                                                                                                  article_id=search_results[0])))

    # NOW only retrieve article ids, since known article ids have been updated if necessary
    if request.datamanager.is_encyclopedia_index_visible() or dm.is_master():
        article_ids = request.datamanager.get_encyclopedia_article_ids()
    elif dm.is_character():
        article_ids = dm.get_character_known_article_ids()
    else:
        assert dm.is_anonymous()  # we leave article_ids to None

    return render(request,
                  template_name,
                    {
                     'page_title': _("Pangea Encyclopedia"),
                     'article_ids': article_ids,
                     'entry': entry,
                     'search_results': search_results
                    })
