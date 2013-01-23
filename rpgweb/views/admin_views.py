# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *
from rpgweb.datamanager.abstract_game_view import AbstractGameView, register_view
from rpgweb import forms
from django.http import Http404, HttpResponse
from rpgweb.utilities import mediaplayers

from django.core.mail import send_mail





@register_view(access=UserAccess.master)
def game_events(request, template_name='administration/game_events.html'):

    events = request.datamanager.get_game_events()  # keys : time, message, username

    trans_events = []
    for event in events:
        trans_event = event.copy()
        if trans_event["substitutions"]:
            trans_event["trans_message"] = _(trans_event["message"]) % utilities.SDICT(**trans_event["substitutions"])
        else:
            trans_event["trans_message"] = _(trans_event["message"])
        del trans_event["message"]
        del trans_event["substitutions"]
        trans_events.append(trans_event)

    trans_events = list(reversed(trans_events))  # most recent first

    return render(request,
                  template_name,
                    {
                     'page_title': _("Game events"),
                     'events': trans_events
                    })




@register_view(access=UserAccess.master)
def manage_audio_messages(request, template_name='administration/webradio_management.html'):

    user = request.datamanager.user

    if request.method == "POST":
        # manual form management, as there are hell a lot...
        if request.POST.has_key("turn_radio_off"):
            with action_failure_handler(request, _("Web Radio has been turned OFF.")):
                request.datamanager.set_radio_state(is_on=False)
        elif request.POST.has_key("turn_radio_on"):
            with action_failure_handler(request, _("Web Radio has been turned ON.")):
                request.datamanager.set_radio_state(is_on=True)
        elif request.POST.has_key("reset_playlist"):
            with action_failure_handler(request, _("Audio Playlist has been emptied.")):
                request.datamanager.reset_audio_messages()
        elif request.POST.has_key("notify_new_messages"):
            with action_failure_handler(request, _("Player notifications have been enqueued.")):
                request.datamanager.add_radio_message("intro_audio_messages")
                for (username, audio_id) in request.datamanager.get_pending_new_message_notifications().items():
                    request.datamanager.add_radio_message(audio_id)
        elif request.POST.has_key("add_audio_message"):
            with action_failure_handler(request, _("Player notifications have been enqueued.")):
                audio_id = request.POST["audio_message_added"]  # might raise KeyError
                request.datamanager.add_radio_message(audio_id)
        else:
            user.add_error(_("Unrecognized management request."))



    radio_is_on = request.datamanager.get_global_parameter("radio_is_on")

    pending_audio_messages = [(audio_id, request.datamanager.get_audio_message_properties(audio_id))
                              for audio_id in request.datamanager.get_all_next_audio_messages()]

    players_with_new_messages = request.datamanager.get_pending_new_message_notifications()

    all_audio_messages = request.datamanager.get_all_audio_messages().items()
    all_new_message_notifications = request.datamanager.get_all_new_message_notification_sounds()

    # we filter out numerous "new emails" messages, which can be summoned in batch anyway
    special_audio_messages = [msg for msg in all_audio_messages if msg[0] not in all_new_message_notifications]

    special_audio_messages.sort(key=lambda x: x[0])


    return render(request,
                  template_name,
                    {
                     'page_title': _("Web Radio Management"),
                     'radio_is_on': radio_is_on,
                     'pending_audio_messages': pending_audio_messages,
                     'players_with_new_messages': players_with_new_messages,
                     'special_audio_messages': special_audio_messages
                    })









@register_view(access=UserAccess.master)
def manage_databases(request, template_name='administration/database_management.html'):

    if request.method == "POST":
        if request.POST.has_key("switch_game_state"):
            new_state = request.POST.get("new_game_state", None) == "1"
            with action_failure_handler(request, _("Game state updated.")):
                request.datamanager.set_game_state(new_state)

        if request.POST.has_key("pack_database"):
            with action_failure_handler(request, _("ZODB file packed.")):
                request.datamanager.pack_database(days=1)  # safety measure - take at least one day of gap !

    formatted_data = request.datamanager.dump_zope_database()

    game_is_started = request.datamanager.is_game_started()  # we refresh it
    return render(request,
                  template_name,
                    {
                     'page_title': _("Database Content"),
                     'formatted_data': formatted_data,
                     'game_is_started': game_is_started
                    })


@register_view(access=UserAccess.master)
def manage_characters(request, template_name='administration/character_management.html'):

    domain_choices = request.datamanager.build_domain_select_choices()
    permissions_choices = request.datamanager.build_permission_select_choices()

    form = None
    if request.method == "POST":
        form = forms.CharacterProfileForm(data=request.POST,
                                   allegiances_choices=domain_choices,
                                   permissions_choices=permissions_choices,
                                   prefix=None)

        if form.is_valid():
            target_username = form.cleaned_data["target_username"]
            allegiances = form.cleaned_data["allegiances"]
            permissions = form.cleaned_data["permissions"]
            real_life_identity = form.cleaned_data["real_life_identity"]
            real_life_email = form.cleaned_data["real_life_email"]

            with action_failure_handler(request, _("Character %s successfully updated.") % target_username):
                request.datamanager.update_allegiances(username=target_username,
                                                       allegiances=allegiances)
                request.datamanager.update_permissions(username=target_username,
                                                       permissions=permissions)
                request.datamanager.update_real_life_data(username=target_username,
                                                            real_life_identity=real_life_identity,
                                                            real_life_email=real_life_email)
        else:
            request.datamanager.user.add_error(_("Wrong data provided (see errors below)"))

    character_forms = []

    for (username, data) in sorted(request.datamanager.get_character_sets().items()):
        # print ("AZZZZ", form["target_username"].value(), username)
        if form and form["target_username"].value() == username:
            #print (" REUSING FOR", username)
            f = form
        else:
            f = forms.CharacterProfileForm(
                                    allegiances_choices=domain_choices,
                                    permissions_choices=permissions_choices,
                                    prefix=None,
                                    initial=dict(target_username=username,
                                                 allegiances=data["domains"],
                                                 permissions=data["permissions"],
                                                 real_life_identity=data["real_life_identity"],
                                                 real_life_email=data["real_life_email"])
                                    )
        character_forms.append(f)

    return render(request,
                  template_name,
                    dict(page_title=_("Manage characters"),
                         character_forms=character_forms))






@register_view(access=UserAccess.master)
def CHARACTERS_IDENTITIES(request):

    user = request.datamanager.user

    char_sets = request.datamanager.get_character_sets().items()

    # real_life_email: flaviensoual@hotmail.com

    if user.is_master:  # FIXME
        headers = "Username;Nickname;Official Identity;IRL Identity"
        lines = [";".join([K, V["official_name"], V["real_life_identity"]]) for (K, V) in char_sets]
    else:
        headers = "Nickname;Official Identity;IRL Identity"
        lines = [";".join([V["official_name"], V["real_life_identity"]]) for (K, V) in char_sets]

    body = "\n".join([headers] + lines).encode("latin-1")

    # body = chr(0xEF) + chr(0xBB) + chr(0xBF) + body # utf8 bom ?

    response = HttpResponse(body, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename=characters.csv'

    return response




@register_view(access=UserAccess.master)
def DATABASE_OPERATIONS(request):

    if not config.DEBUG:
        raise Http404

    try:

        if request.GET.get("reset_game_data"):
            request.datamanager.reset_game_data()
            return HttpResponse("OK - Game data reset")
        else:
            return HttpResponse(_("Error - no operation specified"))

    except Exception, e:
        return Http404(_("Error : %r") % e)


@register_view(access=UserAccess.master)
def FAIL_TEST(request):

    raise IOError("Dummy error to test email sending")

    try:
        send_mail("hello", "bye", "gamemaster@prolifik.net", ["chambon.pascal@gmail.com"])
        return HttpResponse(_("Mail sent"))
    except Exception, e:
        raise
        # return HttpResponse(repr(e))



@register_view(access=UserAccess.master)
def MEDIA_TEST(request):

    return render(request,
                  "administration/media_test.html",
                    {
                     'page_title': _("Media Display Test"),
                     'audioplayer': mediaplayers.generate_audio_player([game_file_url("test_samples/music.mp3")]),
                     'videoplayers': ["<p>%s</p>" % extension +
                                      mediaplayers.generate_media_player(game_file_url("test_samples/video." + extension),
                                                                         game_file_url('test_samples/image.jpg'))
                                      for extensions in mediaplayers._media_player_templates
                                      for extension in extensions]
                    })









