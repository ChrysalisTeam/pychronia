# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from pychronia_game.common import *
from pychronia_game.datamanager.abstract_game_view import register_view


@register_view(access=UserAccess.master, title=ugettext_lazy("Master Manual"))
def gamemaster_manual(request, template_name="administration/master_manual.html"):

    dm = request.datamanager

    gamemaster_manual = dm.get_gamemaster_manual_for_html()

    return render(request,
                  template_name,
                    {
                     "gamemaster_manual": gamemaster_manual
                    })
