from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path, re_path
from django.utils.module_loading import import_string
from django.views.i18n import JavaScriptCatalog

from .utilities import config

admin.autodiscover()


def _view(regex, view_path, *args, **kwargs):
    """
    Build a url pattern for the view at this dotted path.

    The dotted path is also used as the default URL name, so that views can still be reversed
    by dotted path (eg. reverse("pychronia_game.views.homepage") or [GAME_PAGE_LINK] tags
    stored in game data), like old Django versions allowed.
    """
    kwargs.setdefault("name", view_path)
    return re_path(regex, import_string(view_path), *args, **kwargs)


inner_game_urlpatterns = [

                                  # WARNING - DANGEROUS #
                                  _view(r'^TEST_CAPTCHA/$', "pychronia_game.views.gameview_mixins.test_captcha"),
                                  _view(r'^CHARACTERS_IDENTITIES/$', "pychronia_game.views.CHARACTERS_IDENTITIES"),
                                  _view(r'^DATABASE_OPERATIONS/$', "pychronia_game.views.DATABASE_OPERATIONS"),
                                  _view(r'^FAIL_TEST/$', "pychronia_game.views.FAIL_TEST"),
                                  _view(r'^MEDIA_TEST/$', "pychronia_game.views.MEDIA_TEST"),
                                  # to check that all audio/video formats are well read by web browser!

                                  _view(r'^bug_report/$', "pychronia_game.views.bug_report_treatment"),

                                  _view(r'^$', "pychronia_game.views.homepage"),

                                  ##url(r'^opening/$', 'opening'),  # FIXME - deprecated ?
                                  ###url('^openinglogo/$', 'logo_animation'),  # FIXME - deprecated ?

                                  ##url(r'^instructions/$', 'instructions'), # FIXME - deprecated ?

                                  _view(r'^world_map_static/$', "pychronia_game.views.view_world_map_static"),
                                  _view(r'^world_map_dynamic/$', "pychronia_game.views.view_world_map_dynamic"),
                                  #(r'^radio_messages/$', 'personal_radio_messages_listing'),

                                  _view(r'^view_media/$', "pychronia_game.views.view_media"),
                                  _view(r'^personal_folder/$', "pychronia_game.views.personal_folder"),
                                  _view(r'^encrypted_folders/(?P<folder>[^/]*)/$', "pychronia_game.views.encrypted_folder"),

                                  _view(r'^enigma_runes_puzzle/$', "pychronia_game.views.enigma_runes_puzzle"),
                                  _view(r'^enigma_runes_cards/$', "pychronia_game.views.enigma_runes_cards"),

                                  _view(r'^auction_items/$', "pychronia_game.views.auction_items_slideshow"),
                                  _view(r'^personal_items/$', "pychronia_game.views.personal_items_slideshow"),

                                  _view(r'^item3dview/(?P<item>.*)/$', "pychronia_game.views.item_3d_view"),
                                  # Beware: slideshow URLs must not contain underscores, else 3D images are flashing !



                                  _view(r'^ajax_get_next_audio_message/$', "pychronia_game.views.ajax_get_next_audio_message"),
                                  _view(r'^ajax_notify_audio_success/$', "pychronia_game.views.ajax_notify_audio_message_finished"),

                                  _view(r'^personal_webradio_popup/$', "pychronia_game.views.personal_webradio_popup"),
                                  _view(r'^personal_webradio_page/$', "pychronia_game.views.personal_webradio_page"),
                                  _view(r'^ajax_get_radio_playlist/$', "pychronia_game.views.ajax_get_radio_playlist"),
                                  _view(r'^public_webradio/$', "pychronia_game.views.public_webradio"),

                                  _view(r'^view_sales/$', "pychronia_game.views.view_sales"),
                                  _view(r'^view_characters/$', "pychronia_game.views.view_characters"),

                                  _view(r'^pages/(?P<page_id>[^/]*)/$', "pychronia_game.views.view_static_page"),

                                  _view(r'^clues/$', "pychronia_game.views.view_hidden_clue"),

                                  _view(r'^encyclopedia/$', "pychronia_game.views.view_encyclopedia"),
                                  _view(r'^encyclopedia/(?P<current_article_id>[^/]*)/$', "pychronia_game.views.view_encyclopedia"),

                                  _view(r'^manual/(?P<keyword>[^/]*)/$', "pychronia_game.views.view_help_page"),

                                  _view(r'^manage_characters/$', "pychronia_game.views.manage_characters"),
                                  _view(r'^webradio_management/$', "pychronia_game.views.webradio_management"),
                                  _view(r'^game_events/$', "pychronia_game.views.game_events"),
                                  _view(r'^manage_databases/$', "pychronia_game.views.manage_databases"),
                                  _view(r'^static_pages_management/$', "pychronia_game.views.static_pages_management"),
                                  _view(r'^global_contacts_management/$', "pychronia_game.views.global_contacts_management"),
                                  _view(r'^radio_spots_editing/$', "pychronia_game.views.radio_spots_editing"),
                                  _view(r'^game_items_management/$', "pychronia_game.views.game_items_management"),
                                  _view(r'^admin_information/$', "pychronia_game.views.admin_information"),
                                  _view(r'^master_manual/$', "pychronia_game.views.gamemaster_manual"),

                                  _view(r'^chatroom/$', "pychronia_game.views.chatroom"),
                                  _view(r'^ajax_chat/$', "pychronia_game.views.ajax_chat"),

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

                                  _view(r'^login/$', "pychronia_game.views.login"),
                                  _view(r'^secret_question/(?P<concerned_username>[^/]*)/$', "pychronia_game.views.secret_question"),
                                  _view(r'^profile/$', "pychronia_game.views.character_profile"),
                                  _view(r'^friendships/$', "pychronia_game.views.friendship_management"),
                                  _view(r'^logout/$', "pychronia_game.views.logout"),

                                  _view(r'^messages/compose/$', "pychronia_game.views.compose_message"),
                                  _view(r'^messages/preview_message/$', "pychronia_game.views.preview_message"),
                                  #url(r'^messages/inbox/$', 'inbox'),
                                  #url(r'^messages/outbox/$', 'outbox'),
                                  _view(r'^messages/conversations/$', "pychronia_game.views.standard_conversations"),
                                  _view(r'^messages/intercepted_messages/$', "pychronia_game.views.intercepted_messages"),
                                  _view(r'^messages/all_dispatched_messages/$', "pychronia_game.views.all_dispatched_messages"),
                                  _view(r'^messages/all_queued_messages/$', "pychronia_game.views.all_queued_messages"),
                                  _view(r'^messages/all_archived_messages/$', "pychronia_game.views.all_archived_messages"),
                                  _view(r'^messages/messages_templates/$', "pychronia_game.views.messages_templates"),
                                  _view(r'^messages/ajax_set_dispatched_message_state_flags/$',
                                      "pychronia_game.views.ajax_set_dispatched_message_state_flags"),
                                  _view(r'^messages/ajax_set_message_template_state_flags/$',
                                      "pychronia_game.views.ajax_set_message_template_state_flags"),

                                  _view(r'^messages/ajax_force_email_sending/$', "pychronia_game.views.ajax_force_email_sending"),
                                  _view(r'^messages/view_single_message/(?P<msg_id>\w+)/$', "pychronia_game.views.view_single_message"),
                                  _view(r'^messages/ajax_permanently_delete_message/$',
                                      "pychronia_game.views.ajax_permanently_delete_message"),

                                  _view(r'^ability/abilities/$', "pychronia_game.views.ability_introduction"),
                                  _view(r'^ability/house_locking/$', "pychronia_game.views.house_locking"),
                                  _view(r'^ability/house_reports/$', "pychronia_game.views.house_reports"),
                                  _view(r'^ability/runic_translation/$', "pychronia_game.views.runic_translation"),
                                  _view(r'^ability/my_runic_translation_open/$', "pychronia_game.views.runic_translation_open"),
                                  _view(r'^ability/wiretapping_management/$', "pychronia_game.views.wiretapping_management"),
                                  _view(r'^ability/admin_dashboard/$', "pychronia_game.views.admin_dashboard"),
                                  _view(r'^ability/network_management/$', "pychronia_game.views.mercenaries_hiring"),
                                  _view(r'^ability/matter_analysis/$', "pychronia_game.views.matter_analysis"),
                                  _view(r'^ability/telecom_investigation/$', "pychronia_game.views.telecom_investigation"),
                                  _view(r'^ability/world_scan/$', "pychronia_game.views.world_scan"),
                                  _view(r'^ability/artificial_intelligence/$', "pychronia_game.views.artificial_intelligence"),
                                  _view(r'^ability/chess_challenge/$', "pychronia_game.views.chess_challenge"),
                                  _view(r'^ability/geoip_location/$', "pychronia_game.views.geoip_location"),
                                  _view(r'^ability/business_escrow/$', "pychronia_game.views.business_escrow"),
                                  _view(r'^ability/black_market/$', "pychronia_game.views.black_market"),

                                  ]

support_urlpatterns = [

    re_path(r'^$',
            lambda r: HttpResponse("Access to the root of this domain is not allowed, please check your url.", content_type="text/plain")),

    re_path(r'^robots.txt$',
            lambda r: HttpResponse("User-agent: *\nDisallow: /", content_type="text/plain")),

    re_path(r'^admin/', admin.site.urls),

    re_path(r'^i18n/', include('django.conf.urls.i18n')),  # to set language
    _view(r'^set_interface_language/$', 'pychronia_game.views.set_interface_language',
          name="pychronia_game-set_interface_language"),
    re_path(r'^jsi18n/$', JavaScriptCatalog.as_view(packages=['pychronia_game'])),

    # serving of game files is currently independent of ZODB data
    _view(r'^%s(?P<hash>[^/]+)/(?P<path>.+)$' % config.GAME_FILES_URL[1:],
          'pychronia_game.views.serve_game_file'),  # NOT a gameview

    ## no need to serve MEDIA_URL in this site
]

game_admin_urlpatterns = [
    _view(r'^administration/$', "pychronia_game.meta_administration_views.manage_instances"),
    _view(r'^administration/create/$', "pychronia_game.meta_administration_views.create_instance"),  # to be used by non-superusers
    _view(r'^administration/activate/$', "pychronia_game.meta_administration_views.activate_instance"),
    _view(r'^administration/edit/(?P<target_instance_id>[^/]+)/$', "pychronia_game.meta_administration_views.edit_instance_db"),
    # NOT game_instance_id, else bug with middleware
]

# standard urlpatterns of pychronia_game applications, eg. in prod
urlpatterns = [
    re_path(r'^', include(game_admin_urlpatterns)),
    re_path(r'^', include(support_urlpatterns)),
    _view(r'^(?P<game_instance_id>\w+)/$', 'pychronia_game.views.game_homepage_without_username'),
    re_path(r'^(?P<game_instance_id>[^/]+)/(?P<game_username>[^/]+)/', include(inner_game_urlpatterns)),
    # beware - accept all kinds of characters here!
]


# Django Debug Toolbar

urlpatterns += [
    path('__debug__/', include('debug_toolbar.urls')),
]
