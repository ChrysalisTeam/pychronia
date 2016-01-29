# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from django.conf.urls import *
from django.contrib import admin
from .utilities import config
from django.http import HttpResponse


admin.autodiscover()




inner_game_urlpatterns = patterns('pychronia_game.views',

    # WARNING - DANGEROUS #
    url(r'^TEST_CAPTCHA/$', 'gameview_mixins.test_captcha'),
    url(r'^CHARACTERS_IDENTITIES/$', 'CHARACTERS_IDENTITIES'),
    url(r'^DATABASE_OPERATIONS/$', 'DATABASE_OPERATIONS'),
    url(r'^FAIL_TEST/$', 'FAIL_TEST'),
    url(r'^MEDIA_TEST/$', 'MEDIA_TEST'), # to check that all audio/video formats are well read by web browser!

    url(r'^bug_report/$', 'bug_report_treatment'),


    url(r'^$', 'homepage', name="pychronia_game-homepage"),


    ##url(r'^opening/$', 'opening'),  # FIXME - deprecated ?
    ###url('^openinglogo/$', 'logo_animation'),  # FIXME - deprecated ?

    ##url(r'^instructions/$', 'instructions'), # FIXME - deprecated ?

    url(r'^world_map/$', 'view_world_map'),
    #(r'^radio_messages/$', 'personal_radio_messages_listing'),

    url(r'^view_media/$', 'view_media'),
    url(r'^personal_folder/$', 'personal_folder'),
    url(r'^encrypted_folders/(?P<folder>[^/]*)/$', 'encrypted_folder'),


    url(r'^auction_items/$', 'auction_items_slideshow'),
    url(r'^personal_items/$', 'personal_items_slideshow'),

    url(r'^item3dview/(?P<item>.*)/$', 'item_3d_view'), # Beware: slideshow URLs must not contain underscores, else 3D images are flashing !



    url(r'^ajax_get_next_audio_message/$', 'ajax_get_next_audio_message'),
    url(r'^ajax_notify_audio_success/$', 'ajax_notify_audio_message_finished'),

    url(r'^personal_webradio_popup/$', 'personal_webradio_popup'),
    url(r'^personal_webradio_page/$', 'personal_webradio_page'),
    url(r'^webradio_xml_conf/$', 'get_radio_xml_conf'),
    url(r'^public_webradio/$', 'public_webradio'),



    url(r'^view_sales/$', 'view_sales'),
    url(r'^view_characters/$', 'view_characters'),

    url(r'^pages/(?P<page_id>[^/]*)/$', 'view_static_page'),

    url(r'^encyclopedia/$', 'view_encyclopedia'),
    url(r'^encyclopedia/(?P<current_article_id>[^/]*)/$', 'view_encyclopedia'),

    url(r'^manual/(?P<keyword>[^/]*)/$', 'view_help_page'),

    url(r'^manage_characters/$', 'manage_characters'),
    url(r'^webradio_management/$', 'webradio_management'),
    url(r'^game_events/$', 'game_events'),
    url(r'^manage_databases/$', 'manage_databases'),
    url(r'^static_pages_management/$', 'static_pages_management'),
    url(r'^global_contacts_management/$', 'global_contacts_management'),
    url(r'^radio_spots_editing/$', 'radio_spots_editing'),
    url(r'^game_items_management/$', 'game_items_management'),
    url(r'^admin_information/$', 'admin_information'),
    url(r'^master_manual/$', 'gamemaster_manual'),

    url(r'^chatroom/$', 'chatroom'),
    url(r'^ajax_chat/$', 'ajax_chat'),


    #(r'^wiretapping_management/$', 'wiretapping_management'),
    #(r'^translations_management/$', 'translations_management'),
    #(r'^scanning_management/$', 'scanning_management'),

    #(r'^mercenary_commandos/$', 'mercenary_commandos'),
    #(r'^teldorian_teleportations/$', 'teldorian_teleportations'),
    #(r'^akarith_attacks/$', 'akarith_attacks'),
    #(r'^telecom_investigation/$', 'telecom_investigation'),

#    (r'^oracle/$', 'contact_djinns'),
#    (r'^djinn/$', 'chat_with_djinn'),
#    (r'^ajax_consult_djinns/$', 'ajax_consult_djinns'),

#    (r'^ajax_domotics_security/$', 'ajax_domotics_security'), # for heavy client, if used
#    (r'^domotics_security/$', 'domotics_security'),

    url(r'^login/$', 'login', name="pychronia_game-login"),
    url(r'^secret_question/(?P<concerned_username>[^/]*)/$', 'secret_question'),
    url(r'^profile/$', 'character_profile'),
    url(r'^friendships/$', 'friendship_management'),
    url(r'^logout/$', 'logout', name="pychronia_game-logout"),


    url(r'^messages/compose/$', 'compose_message'),
    url(r'^messages/preview_message/$', 'preview_message'),
    #url(r'^messages/inbox/$', 'inbox'),
    #url(r'^messages/outbox/$', 'outbox'),
    url(r'^messages/conversations/$', 'standard_conversations'),
    url(r'^messages/intercepted_messages/$', 'intercepted_messages'),
    url(r'^messages/all_dispatched_messages/$', 'all_dispatched_messages'),
    url(r'^messages/all_queued_messages/$', 'all_queued_messages'),
    url(r'^messages/all_archived_messages/$', 'all_archived_messages'),
    url(r'^messages/messages_templates/$', 'messages_templates'),
    url(r'^messages/ajax_set_dispatched_message_state_flags/$', 'ajax_set_dispatched_message_state_flags'),
    url(r'^messages/ajax_set_message_template_state_flags/$', 'ajax_set_message_template_state_flags'),

    url(r'^messages/ajax_force_email_sending/$', 'ajax_force_email_sending'),
    url(r'^messages/view_single_message/(?P<msg_id>\w+)/$', 'view_single_message'),
    url(r'^messages/ajax_permanently_delete_message/$', 'ajax_permanently_delete_message'),


    url(r'^ability/abilities/$', 'ability_introduction'),
    url(r'^ability/house_locking/$', 'house_locking'),
    url(r'^ability/runic_translation/$', 'runic_translation'),
    url(r'^ability/wiretapping_management/$', 'wiretapping_management'),
    url(r'^ability/admin_dashboard/$', 'admin_dashboard'),
    url(r'^ability/network_management/$', 'mercenaries_hiring'),
    url(r'^ability/matter_analysis/$', 'matter_analysis'),
    url(r'^ability/telecom_investigation/$', 'telecom_investigation'),
    url(r'^ability/world_scan/$', 'world_scan'),
    url(r'^ability/artificial_intelligence/$', 'artificial_intelligence'),
    url(r'^ability/chess_challenge/$', 'chess_challenge'),
    url(r'^ability/geoip_location/$', 'geoip_location'),
    url(r'^ability/business_escrow/$', 'business_escrow'),
    url(r'^ability/black_market/$', 'black_market'),

)


support_urlpatterns = patterns('',

    (r'^robots.txt$', lambda r: HttpResponse("User-agent: *\nDisallow: /", content_type="text/plain")),

    (r'^admin/', include(admin.site.urls)),

    (r'^i18n/', include('django.conf.urls.i18n')), # to set language
    (r'^jsi18n/$', 'django.views.i18n.javascript_catalog', {'packages': ('pychronia_game',)}),

    # serving of game files is currently independent of ZODB data
    url(r'^%s(?P<hash>[^/]+)/(?P<path>.+)$' % config.GAME_FILES_URL[1:], 'pychronia_game.views.serve_game_file'), # NOT a gameview

    ## no need to serve MEDIA_URL in this site
)


game_admin_urlpatterns = patterns('pychronia_game.meta_administration_views',
    (r'^administration/$', "manage_instances"),
    (r'^administration/create/$', "create_instance"), # to be used by non-superusers
    (r'^administration/activate/$', "activate_instance"),
    (r'^administration/edit/(?P<target_instance_id>[^/]+)/$', "edit_instance_db"), # NOT game_instance_id, else bug with middleware
)




# standard urlpatterns of pychronia_game applications, eg. in prod
urlpatterns = patterns('',
        url(r'^', include(game_admin_urlpatterns)),
        url(r'^', include(support_urlpatterns)),
        url(r'^(?P<game_instance_id>\w+)/$', 'pychronia_game.views.game_homepage_without_username'),
        url(r'^(?P<game_instance_id>[^/]+)/(?P<game_username>[^/]+)/', include(inner_game_urlpatterns)),  # beware - accept all kinds of characters here!
)



