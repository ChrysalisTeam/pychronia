# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from . import menus as menus_module
from rpgweb.authentication import IMPERSONATION_POST_VARIABLE


def rpgweb_template_context(request):
    """
    Template context manager which adds "player" to the template context.
    """

    if hasattr(request, "datamanager") and request.datamanager:
        
        datamanager = request.datamanager
        
        online_users = [datamanager.get_official_name_from_username(username)
                        for username in datamanager.get_online_users()]
        menus = menus_module.generate_filtered_menu(request)
        
        view_name = request.processed_view.NAME # thanks to our middleware
        if view_name in datamanager.get_help_page_names():
            help_keyword = view_name # we NECESSARILY have access permissions for this view, logically..
        else:
            help_keyword = None
            
        possible_impersonations = [_username for _username in datamanager.get_available_logins()
                                   if datamanager.can_impersonate(datamanager.user.real_username, _username)
                                   and _username != datamanager.user.real_username]
        if datamanager.user.is_impersonation:
            possible_impersonations.append(datamanager.user.real_username) # way of stopping impersonation, actually
        
        return {'game_instance_id': datamanager.game_instance_id,
                'user': datamanager.user,
                'game_is_started': datamanager.get_global_parameter("game_is_started"),
                'online_users': online_users,
                'menus': menus.submenus if menus else [],
                'help_keyword': help_keyword,
                'possible_impersonations': possible_impersonations,
                'impersonation_post_variable': IMPERSONATION_POST_VARIABLE}
        
    else:
        return {} # not in valid game instance
    