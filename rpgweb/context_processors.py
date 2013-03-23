# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb import menus as menus_module
from rpgweb.authentication import IMPERSONATION_TARGET_POST_VARIABLE, IMPERSONATION_WRITABILITY_POST_VARIABLE # TODO USE WRITABILITY
from django.contrib.messages.api import get_messages




def rpgweb_template_context(request):
    """
    Template context manager which adds "player" to the template context.
    """

    if hasattr(request, "datamanager") and request.datamanager:

        datamanager = request.datamanager

        online_users = datamanager.get_online_users() # usernames are fine // to test: (datamanager.get_character_usernames() * 2)
        menus = menus_module.generate_filtered_menu(request)

        view_name = request.processed_view.NAME # thanks to our middleware
        if view_name in datamanager.get_help_page_names():
            help_keyword = view_name # we NECESSARILY have access permissions for this view, logically..
        else:
            help_keyword = None

        notifications = get_messages(request) # lazy 'messages' context variable.
        notifications = list(notifications)
        notification_type = "mixed" # DEFAULT
        levels = list(set(msg.tags for msg in notifications))
        if len(levels) == 1:
            notification_type = levels[0]

        possible_impersonations = datamanager.get_impersonation_targets(datamanager.user.real_username)

        return {'game_instance_id': datamanager.game_instance_id,
                'processed_view': request.processed_view,

                'user': datamanager.user,
                'game_is_started': datamanager.get_global_parameter("game_is_started"),
                'online_users': online_users,

                'menus': menus.submenus if menus else [],

                'help_keyword': help_keyword,

                'possible_impersonations': possible_impersonations,
                'impersonation_post_variable': IMPERSONATION_TARGET_POST_VARIABLE,

                # replacement of djanbgo.contrib.messages middleware
                'notification_type': notification_type,
                'notifications': notifications, }

    else:
        return {} # not in valid game instance
