# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from pychronia_game.common import reverse, config, NBSP, _
from pychronia_game import menus as menus_module, utilities
from pychronia_game.authentication import IMPERSONATION_TARGET_POST_VARIABLE, IMPERSONATION_WRITABILITY_POST_VARIABLE # TODO USE WRITABILITY
from django.contrib.messages.api import get_messages
from pychronia_game.views.admin_views.webradio_management_mod import WebradioManagement
from django.core.urlresolvers import reverse




def pychronia_template_context(request):
    """
    Template context manager which adds all necessary game data to all pages.
    """

    res = {

            'use_parallax': False, # might be enabled only for some browsers..

            'bug_report_email': config.BUG_REPORT_EMAIL, # might be None

            # useful constants
            'None': None,
            'True': True,
            'False': False,

            'COLON': _(":").replace(" ", NBSP), # different spacing when english or french...
            'SITE_DOMAIN': config.SITE_DOMAIN,
          }



    if hasattr(request, "datamanager") and request.datamanager and getattr(request, "processed_view", None):

        dm = request.datamanager

        ### dm.user.add_warning("THIS IZ A TEST")
        display_admin_tips = dm.should_display_admin_tips()

        # WARNING - must be BEFORE messages retrieval!
        writability_data = dm.determine_actual_game_writability()
        if writability_data["reason"] and not request.is_ajax():
            dm.user.add_warning(writability_data["reason"]) # a reason for no-writability most probably
        elif not dm.is_game_started() and display_admin_tips:
            dm.user.add_warning(_("Game is currently paused for players."))

        online_users = dm.get_online_users() # usernames are fine // to test: (dm.get_character_usernames() * 2)
        menus = menus_module.generate_filtered_menu(request) # might be None

        view_name = request.processed_view.NAME # set thanks to game view __call__()

        impersonation_capabilities = dm.get_current_user_impersonation_capabilities()
        impersonation_capabilities.update(impersonation_target_post_variable=IMPERSONATION_TARGET_POST_VARIABLE,
                                          impersonation_writability_post_variable=IMPERSONATION_WRITABILITY_POST_VARIABLE)

        notifications = get_messages(request) # lazy 'messages' context variable.
        notifications = utilities.remove_duplicates(notifications) # order doesn't matter, and we don't want duplicates!
        notification_type = "mixed" # DEFAULT
        levels = list(set(msg.tags for msg in notifications))
        if len(levels) == 1:
            notification_type = levels[0]

        # TEST of notifications:
        #notification_type = "success"  # or info/warning/error
        #notifications = ["heelqsdqsdqsdq sdqdqsdq rle \n qsdqsdqsd dfgdfgdfg dfgdfg dfgdfg dfg  sdfsdfsdf sdfsdfsdf ",
        #                 "sdfqjidqksd sdqkj qsdkqsdjk qsd \n qsdqsdqsd",
        #                 "sdfs sdf ghhgh fgh fghfgh fghfg fghgh fghfghfgh fghfgh "]

        action_explanations = request.processed_view.get_game_actions_explanations()

        # we only check the 2 first levels of menu for "novelty" menu entries
        signal_new_menu_entries = False
        if menus:
            for entry in menus.submenus:
                if entry.is_novelty:
                    signal_new_menu_entries = True
                for subentry in entry.submenus:
                    if subentry.is_novelty:
                        signal_new_menu_entries = True

        help_page_key = "help-" + view_name
        signal_new_help_page = not dm.has_user_accessed_static_page(help_page_key)

        signal_new_radio_messages = not dm.has_read_current_playlist() if not isinstance(request.processed_view, WebradioManagement) else False
        signal_new_text_messages = dm.is_character() and dm.has_new_message_notification() # only for characters atm

        message_sent = (request.GET.get("message_sent") == "1")  # useful to purge localstorage backups

        if request.processed_view.DISPLAY_STATIC_CONTENT:
            content_blocks = dict(help_page=dict(name=help_page_key,
                                                      data=dm.get_categorized_static_page(dm.HELP_CATEGORY, help_page_key)),
                                   top_content=dict(name="top-" + view_name,
                                                   data=dm.get_categorized_static_page(dm.CONTENT_CATEGORY, "top-" + view_name)),
                                   bottom_content=dict(name="bottom-" + view_name,
                                                       data=dm.get_categorized_static_page(dm.CONTENT_CATEGORY, "bottom-" + view_name)))
        else:
            content_blocks = {}

        res.update({
                'game_instance_id': dm.game_instance_id,
                'game_real_username': dm.user.real_username,  # really logged-in user
                'game_username': dm.user.username,  # might be impersonated
                'fallback_title': request.processed_view.relevant_title(dm),

                'user': dm.user,
                'impersonation_capabilities': impersonation_capabilities,
                'game_is_writable': writability_data["writable"],
                'disable_widgets': not writability_data["writable"] and not request.processed_view.ALWAYS_ALLOW_POST,
                'display_admin_tips': display_admin_tips,
                'menus': menus.submenus if menus else [], # we ignore root entry

                'online_users': online_users,
                'signal_chatting_users': bool(dm.get_chatting_users()),
                'signal_new_menu_entries': signal_new_menu_entries,
                'signal_new_help_page': signal_new_help_page,
                'signal_new_radio_messages': signal_new_radio_messages,
                'signal_new_text_messages': signal_new_text_messages,

                'message_sent': message_sent,

                # replacement of django.contrib.messages middleware
                'notification_type': notification_type,
                'notifications': notifications,

                'content_blocks': content_blocks,
                'action_explanations': action_explanations,
                'default_contact_avatar': dm.get_global_parameter("default_contact_avatar"),

            })

    else:
        pass # not in valid game instance

    return res
