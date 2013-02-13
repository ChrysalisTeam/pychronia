# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from django.conf.urls.defaults import *
from .utilities import config



mobile_game_urlpatterns = patterns('rpgweb.views',

    url(r'^$', 'homepage_mobile', name="rpgweb-homepage"),
)



web_game_urlpatterns = patterns('rpgweb.views',

    # WARNING - DANGEROUS #

    url(r'^TEST_CAPTCHA/$', 'gameview_mixins.test_captcha'),
    url(r'^CHARACTERS_IDENTITIES/$', 'CHARACTERS_IDENTITIES'),
    url(r'^DATABASE_OPERATIONS/$', 'DATABASE_OPERATIONS'),
    url(r'^FAIL_TEST/$', 'FAIL_TEST'),
    url(r'^MEDIA_TEST/$', 'MEDIA_TEST'), # to check that all audio/video formats are well read by web browser!


    url(r'^$', 'homepage', name="rpgweb-homepage"),


    url(r'^opening/$', 'opening'),  # FIXME - deprecated ?
    url('^openinglogo/$', 'logo_animation'),  # FIXME - deprecated ?

    url(r'^instructions/$', 'instructions'), # FIXME - deprecated ?

    #(r'^radio_messages/$', 'personal_radio_messages_listing'),

    url(r'^view_media/$', 'view_media'),
    url(r'^personal_folder/$', 'personal_folder'),
    url(r'^encrypted_folders/(?P<folder>[^/]*)/$', 'encrypted_folder'),


    url(r'^auction_items/$', 'auction_items_slideshow'),
    url(r'^personal_items/$', 'personal_items_slideshow'),

    url(r'^item3dview/(?P<item>.*)/$', 'item_3d_view'), # Beware: slideshow URLs must not contain underscores, else 3D images are flashing !


    url(r'^webradio_popup/$', 'webradio_popup'),
    url(r'^webradio/$', 'listen_to_webradio'),
    url(r'^webradio_conf/$', 'get_radio_xml_conf'),
    url(r'^webradio_applet/$', 'listen_to_audio_messages'),

    url(r'^view_sales/$', 'view_sales'),
    url(r'^view_characters/$', 'view_characters'),

    url(r'^encyclopedia/$', 'view_encyclopedia'),
    url(r'^encyclopedia/(?P<article_id>[^/]*)/$', 'view_encyclopedia'),

    url(r'^manual/(?P<keyword>[^/]*)/$', 'view_help_page'),

    url(r'^manage_characters/$', 'manage_characters'),
    url(r'^webradio_management/$', 'webradio_management'),
    url(r'^game_events/$', 'game_events'),
    url(r'^manage_databases/$', 'manage_databases'),


    url(r'^chatroom/$', 'chatroom'),
    url(r'^ajax_chat/$', 'ajax_chat'),


    #(r'^wiretapping_management/$', 'wiretapping_management'),
    #(r'^translations_management/$', 'translations_management'),
    #(r'^scanning_management/$', 'scanning_management'),

    #(r'^mercenary_commandos/$', 'mercenary_commandos'),
    #(r'^teldorian_teleportations/$', 'teldorian_teleportations'),
    #(r'^acharith_attacks/$', 'acharith_attacks'),
    #(r'^telecom_investigation/$', 'telecom_investigation'),

#    (r'^oracle/$', 'contact_djinns'),
#    (r'^djinn/$', 'chat_with_djinn'),
#    (r'^ajax_consult_djinns/$', 'ajax_consult_djinns'),

#    (r'^ajax_domotics_security/$', 'ajax_domotics_security'), # for heavy client, if used
#    (r'^domotics_security/$', 'domotics_security'),

    url(r'^login/$', 'login'),
    url(r'^secret_question/(?P<concerned_username>[^/]*)/$', 'secret_question'),
    url(r'^profile/$', 'character_profile'),
    url(r'^friendships/$', 'friendship_management'),
    url(r'^logout/$', 'logout'),


    url(r'^messages/compose/$', 'compose_message'),
    #url(r'^messages/inbox/$', 'inbox'),
    #url(r'^messages/outbox/$', 'outbox'),
    url(r'^messages/conversation/$', 'conversation'),
    url(r'^messages/all_dispatched_messages/$', 'all_dispatched_messages'),
    url(r'^messages/all_queued_messages/$', 'all_queued_messages'),
    url(r'^messages/intercepted_messages/$', 'intercepted_messages'),
    url(r'^messages/messages_templates/$', 'messages_templates'),
    url(r'^messages/ajax_mark_msg_read/$', 'ajax_set_message_read_state'),
    url(r'^messages/ajax_force_email_sending/$', 'ajax_force_email_sending'),
    url(r'^messages/view_single_message/(?P<msg_id>\w+)/$', 'view_single_message'),

    url(r'^ajax_get_next_audio_message/$', 'ajax_get_next_audio_message'),
    url(r'^ajax_notify_audio_success/$', 'ajax_notify_audio_message_finished'),


    url(r'^ability/house_locking/$', 'house_locking'),
    url(r'^ability/runic_translation/$', 'runic_translation'),
    url(r'^ability/wiretapping_management/$', 'wiretapping_management'),
    url(r'^ability/admin_dashboard/$', 'admin_dashboard'),
    url(r'^ability/network_management/$', 'mercenaries_hiring'),
    url(r'^ability/matter_analysis/$', 'matter_analysis'),

)


support_urlpatterns = patterns('',
    
    # serving of game files is currently independent of ZODB data
    url(r'^%s(?P<hash>[^/]*)/?(?P<path>.*)$' % config.GAME_FILES_URL[1:], 'rpgweb.views.serve_game_file'), # NOT a gameview

    # USELESS - NO MEDIA ATM : (r'^%s(?P<path>.*)$' % config.MEDIA_URL[1:], 'django.views.static.serve', {'document_root': config.MEDIA_ROOT, 'show_indexes': False}),
    (r'^i18n/', include('django.conf.urls.i18n')), # to set language
    (r'^jsi18n/$', 'django.views.i18n.javascript_catalog', {'packages': ('rpgweb',)}),

)



