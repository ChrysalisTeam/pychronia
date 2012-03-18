# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from . import menus as menus_module


def rpgweb_template_context(request):
    """
    Template context manager which adds "player" to the template context.
    """

    if hasattr(request, "datamanager") and request.datamanager:
        
        online_users = [request.datamanager.get_official_name_from_username(username)
                        for username in request.datamanager.get_online_users()]
        menus = menus_module.generate_filtered_menu(request)
        
        view_name = request.processed_view.NAME # thanks to our middleware
        if view_name in request.datamanager.get_help_page_names():
            help_keyword = view_name
        else:
            help_keyword = None

        return {'game_instance_id': request.datamanager.game_instance_id,
                'user': request.datamanager.user,
                'game_is_started': request.datamanager.get_global_parameter("game_is_started"),
                'online_users': online_users,
                'menus': menus.submenus if menus else [],
                'help_keyword': help_keyword}
    else:
        return {} # not in valid game instance
    