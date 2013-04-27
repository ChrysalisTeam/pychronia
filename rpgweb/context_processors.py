# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb import menus as menus_module
from rpgweb.authentication import IMPERSONATION_TARGET_POST_VARIABLE, IMPERSONATION_WRITABILITY_POST_VARIABLE # TODO USE WRITABILITY
from django.contrib.messages.api import get_messages
from rpgweb.views.admin_views.webradio_management_mod import WebradioManagement




def rpgweb_template_context(request):
    """
    Template context manager which adds all necessary game data to all pages.
    """

    if hasattr(request, "datamanager") and request.datamanager:

        dm = request.datamanager

        ### dm.user.add_warning("THIS IZ A TEST")

        # WARNING - must be BEFORE messages retrieval!
        writability_data = dm.determine_actual_game_writability()
        if writability_data["reason"]:
            dm.user.add_warning(writability_data["reason"]) # a reason for no-writability most probably

        online_users = dm.get_online_users() # usernames are fine // to test: (dm.get_character_usernames() * 2)
        menus = menus_module.generate_filtered_menu(request)

        view_name = request.processed_view.NAME # set thanks to game view __call__()

        impersonation_capabilities = dm.get_current_user_impersonation_capabilities()
        impersonation_capabilities.update(impersonation_target_post_variable=IMPERSONATION_TARGET_POST_VARIABLE,
                                          impersonation_writability_post_variable=IMPERSONATION_WRITABILITY_POST_VARIABLE)

        notifications = get_messages(request) # lazy 'messages' context variable.
        notifications = list(set(notifications)) # order doesn't matter, and we don't want duplicates!
        notification_type = "mixed" # DEFAULT
        levels = list(set(msg.tags for msg in notifications))
        if len(levels) == 1:
            notification_type = levels[0]


        # we only check the 2 first levels of menu for "novelty" menu entries
        signal_new_menu_entries = False
        for entry in menus.submenus:
            if entry.is_novelty:
                signal_new_menu_entries = True
            for subentry in entry.submenus:
                if subentry.is_novelty:
                    signal_new_menu_entries = True


        action_explanations = request.processed_view.get_game_actions_explanations()

        help_page_key = "help-" + view_name
        signal_new_help_page = not dm.has_user_accessed_static_page(help_page_key)

        return {'game_instance_id': dm.game_instance_id,

                'fallback_title': request.processed_view.TITLE,

                'user': dm.user,
                'game_is_writable': writability_data["writable"],
                'display_admin_tips': dm.user.is_superuser or dm.is_master(dm.user.real_username), # tops also visible when impersonation!
                
                'impersonation_capabilities': impersonation_capabilities,

                'menus': menus.submenus if menus else [], # we ignore root entry
                'signal_new_menu_entries': signal_new_menu_entries,

                'is_mobile_page': request.is_mobile,

                'online_users': online_users,
                'signal_new_radio_messages': not dm.has_read_current_playlist() if not isinstance(request.processed_view, WebradioManagement) else False,

                # replacement of django.contrib.messages middleware
                'notification_type': notification_type,
                'notifications': notifications,

                'content_blocks': dict(help_page=dict(name=help_page_key,
                                                      data=dm.get_categorized_static_page(dm.HELP_CATEGORY, help_page_key)),
                                       top_content=dict(name="top-" + view_name,
                                                       data=dm.get_categorized_static_page(dm.CONTENT_CATEGORY, "top-" + view_name)),
                                       bottom_content=dict(name="bottom-" + view_name,
                                                           data=dm.get_categorized_static_page(dm.CONTENT_CATEGORY, "bottom-" + view_name))),
                'signal_new_help_page': signal_new_help_page,

                'action_explanations': action_explanations,

                # useful constants
                'None': None,
                'True': True,
                'False': False,
                }

    else:
        return {} # not in valid game instance
