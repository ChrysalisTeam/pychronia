# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from pychronia_game.common import *
from pychronia_game.datamanager.abstract_game_view import register_view


@register_view(access=UserAccess.master, title=ugettext_lazy("Master Manual"))
def gamemaster_manual(request, template_name="administration/master_manual.html"):

    datas = render_rst_template("hellllllooo", request.datamanager)

    return render(request,
                  template_name,
                    {
                     "datas": datas

                    })
