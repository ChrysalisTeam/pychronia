# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb import menus as menus_module
from rpgweb.authentication import IMPERSONATION_TARGET_POST_VARIABLE, IMPERSONATION_WRITABILITY_POST_VARIABLE # TODO USE WRITABILITY
from django.contrib.messages.api import get_messages




def rpgweb_template_context(request):
    """
    Template context manager which adds all necessary game data to all pages.
    """

    if hasattr(request, "datamanager") and request.datamanager:

        datamanager = request.datamanager

        ### datamanager.user.add_warning("THIS IZ A TEST")

        # WARNING - must be BEFORE messages retrieval!
        writability_data = datamanager.determine_actual_game_writability()
        if writability_data["reason"]:
            datamanager.user.add_warning(writability_data["reason"]) # a reason for no-writability most probably

        online_users = datamanager.get_online_users() # usernames are fine // to test: (datamanager.get_character_usernames() * 2)
        menus = menus_module.generate_filtered_menu(request)

        view_name = request.processed_view.NAME # thanks to our middleware
        help_keyword = None ## FIXME
        ##if datamanager.get_help_page(view_name):
        ##    help_keyword = view_name

        impersonation_capabilities = datamanager.get_current_user_impersonation_capabilities()
        impersonation_capabilities.update(impersonation_target_post_variable=IMPERSONATION_TARGET_POST_VARIABLE,
                                          impersonation_writability_post_variable=IMPERSONATION_WRITABILITY_POST_VARIABLE)

        notifications = get_messages(request) # lazy 'messages' context variable.
        notifications = list(set(notifications)) # order doesn't matter, and we don't want duplicates!
        notification_type = "mixed" # DEFAULT
        levels = list(set(msg.tags for msg in notifications))
        if len(levels) == 1:
            notification_type = levels[0]


        # auto information
        ## FIXME action_explanations = request.processed_view.klass(request.datamanager).get_game_actions_explanations() # we're forced to reinstantiate the view...

        return {'game_instance_id': datamanager.game_instance_id,
                
                'fallback_title': request.processed_view.TITLE,

                'user': datamanager.user,
                'game_is_writable': writability_data["writable"],
                'is_mobile_page': request.is_mobile,

                'online_users': online_users,

                'menus': menus.submenus if menus else [],

                'help_keyword': help_keyword,

                'impersonation_capabilities': impersonation_capabilities,

                # replacement of django.contrib.messages middleware
                'notification_type': notification_type,
                'notifications': notifications,

                # useful constants
                'None': None,
                'True': True,
                'False': False,
                }

    else:
        return {} # not in valid game instance
