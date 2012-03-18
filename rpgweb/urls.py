# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from django.conf.urls.defaults import *


view_urlpatterns = patterns('rpgweb.views',

    # WARNING - DANGEROUS #

    (r'^CHARACTERS_IDENTITIES/$', 'CHARACTERS_IDENTITIES'),
    (r'^DATABASE_OPERATIONS/$', 'DATABASE_OPERATIONS'),
    (r'^FAIL_TEST/$', 'FAIL_TEST'),
    (r'^MEDIA_TEST/$', 'MEDIA_TEST'), # to check that all audio/video formats are well read by web browser!


    (r'^$', 'homepage'),


    (r'^opening/$', 'opening'),
    ('^openinglogo/$', 'logo_animation'),

    (r'^instructions/$', 'instructions'),

    #(r'^radio_messages/$', 'personal_radio_messages_listing'),

    (r'^view_media/$', 'view_media'),
    (r'^personal_folder/$', 'personal_folder'),
    (r'^encrypted_folders/(?P<folder>[^/]*)/$', 'encrypted_folder'),


    (r'^slideshow/$', 'items_slideshow'),            # Beware: slideshow URLs must not contain underscores,
    (r'^item3dview/(?P<item>.*)/$', 'item_3d_view'), # else 3D images are flashing !

    (r'^webradio_applet/$', 'listen_to_audio_messages'),

    (r'^view_sales/$', 'view_sales'),
    (r'^view_characters/$', 'view_characters'),
    
    (r'^encyclopedia/$', 'view_encyclopedia'),
    (r'^manual/(?P<keyword>[^/]*)/$', 'view_help_page'),
    
    (r'^manage_characters/$', 'manage_characters'),
    (r'^webradio_management/$', 'manage_audio_messages'),
    (r'^game_events/$', 'game_events'),
    (r'^manage_databases/$', 'manage_databases'),




    (r'^chatroom/$', 'chatroom'),
    (r'^ajax_chat/$', 'ajax_chat'),


    #(r'^wiretapping_management/$', 'wiretapping_management'),
    #(r'^network_management/$', 'network_management'),
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
        
    (r'^login/$', 'login'),
    (r'^secret_question/$', 'secret_question'),
    (r'^logout/$', 'logout'),


    (r'^messages/compose/$', 'compose_message'),
    (r'^messages/inbox/$', 'inbox'),
    (r'^messages/outbox/$', 'outbox'),
    (r'^messages/all_sent_messages/$', 'all_sent_messages'),
    (r'^messages/all_queued_messages/$', 'all_queued_messages'),
    (r'^messages/intercepted_messages/$', 'intercepted_messages'),
    (r'^messages/messages_templates/$', 'messages_templates'),
    (r'^messages/ajax_mark_msg_read/$', 'ajax_set_message_read_state'),
    (r'^messages/ajax_force_email_sending/$', 'ajax_force_email_sending'),

    (r'^messages/view_single_message/(?P<msg_id>\w+)/$', 'view_single_message'),


    (r'^ajax_get_next_audio_message/$', 'ajax_get_next_audio_message'),
    (r'^ajax_notify_audio_success/$', 'ajax_notify_audio_message_finished'),

)


ability_urlpatterns = patterns("rpgweb.abilities",

    (r'^ability/house_locking/$', 'house_locking'),
    (r'^ability/runic_translation/$', 'runic_translation'),
    (r'^ability/wiretapping_management/$', 'wiretapping_management'),

)


final_urlpatterns = view_urlpatterns + ability_urlpatterns

# root urlpatterns of rpgweb application
urlpatterns = patterns('',
                    (r'^(?P<game_instance_id>\w+)/', include(final_urlpatterns)),
                    (r'^', include(final_urlpatterns), {"game_instance_id": "DEMO"}), # default game instance, just as a demo
)




