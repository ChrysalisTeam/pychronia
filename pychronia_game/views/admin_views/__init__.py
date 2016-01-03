# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from pychronia_game.common import *
from pychronia_game.datamanager.abstract_game_view import AbstractGameView, register_view, readonly_method
from pychronia_game import forms
from django.http import Http404, HttpResponse
from pychronia_game.utilities import mediaplayers
from django.core.mail import send_mail


from .admin_dashboard_mod import AdminDashboardAbility

admin_dashboard = AdminDashboardAbility.as_view

from .webradio_management_mod import WebradioManagement
webradio_management = WebradioManagement.as_view

from .static_pages_management_mod import StaticPagesManagement
static_pages_management = StaticPagesManagement.as_view

from .global_contacts_management_mod import GlobalContactsManagement
global_contacts_management = GlobalContactsManagement.as_view

from .game_items_management_mod import GameItemsManagement
game_items_management = GameItemsManagement.as_view

from .radio_spots_editing_mod import RadioSpotsEditing
radio_spots_editing = RadioSpotsEditing.as_view

from .admin_information_mod import AdminInformation
admin_information = AdminInformation.as_view

from .gamemaster_manual_mod import gamemaster_manual


@register_view(access=UserAccess.master, title=ugettext_lazy("View Database"))
def manage_databases(request, template_name='administration/database_management.html'):

    ''' OBSOLETE
    if request.method == "POST":
        if request.POST.has_key("pack_database"):
            with action_failure_handler(request, _("ZODB file packed.")):
                request.datamanager.pack_database(days=1)  # safety measure - take at least one day of gap !
    '''

    formatted_data = request.datamanager.dump_zope_database(width=100)

    return render(request,
                  template_name,
                    {
                     'formatted_data': formatted_data,
                    })


@register_view(access=UserAccess.master, title=ugettext_lazy("Manage Characters"))
def manage_characters(request, template_name='administration/character_management.html'):

    dm = request.datamanager

    characters_items = sorted(dm.get_character_sets().items(), key=lambda x: (x[1]["is_npc"], x[0]))

    character_forms = []

    def _prefix(idx):
        return "form%s" % idx

    form_validation_failed = None  # TERNARY

    if request.method == "POST":

        form_validation_failed = False

        for idx, (username, __character_data) in enumerate(characters_items):

            form = forms.CharacterProfileForm(datamanager=dm,
                                              data=request.POST,
                                              prefix=_prefix(idx))

            if form.is_valid():
                target_username = form.cleaned_data["target_username"]
                is_npc = form.cleaned_data["is_npc"]
                official_name = form.cleaned_data["official_name"]
                official_role = form.cleaned_data["official_role"]
                allegiances = form.cleaned_data["allegiances"]
                permissions = form.cleaned_data["permissions"]
                real_life_identity = form.cleaned_data["real_life_identity"].strip() or None
                real_life_email = form.cleaned_data["real_life_email"].strip() or None
                gamemaster_hints = form.cleaned_data["gamemaster_hints"].strip() # may be an empty string !
                extra_goods = form.cleaned_data["extra_goods"]

                assert official_name == official_name.strip() # auto-stripping
                assert official_role == official_role.strip()

                with action_failure_handler(request, success_message=None):

                    assert not dm.is_in_writing_transaction() # each call below will be separately atomic

                    previous_data = copy.deepcopy(dm.get_character_properties(username=target_username))

                    dm.update_official_character_data(username=target_username,
                                                        official_name=official_name,
                                                        official_role=official_role,
                                                        gamemaster_hints=gamemaster_hints,
                                                        extra_goods=extra_goods,
                                                        is_npc=is_npc)

                    dm.update_allegiances(username=target_username,
                                          allegiances=allegiances)

                    dm.update_permissions(username=target_username,
                                          permissions=permissions)
                    dm.update_real_life_data(username=target_username,
                                            real_life_identity=real_life_identity,
                                            real_life_email=real_life_email)

                    new_data = dm.get_character_properties(username=target_username)

                    utilities.assert_sets_equal(previous_data.keys(), new_data.keys())

                    with exception_swallower():  # we don't want this advanced logging to mess with the game

                        def _is_equivalent(a, b):
                            if isinstance(a, (list, PersistentList, tuple)):
                                return sorted(a) == sorted(b)  # handle damn allegiances, permissions etc.
                            return a == b
                        # we create a list of tuples (key, old_value, new_value) ONLY for modified fields
                        all_changes = [(k, previous_data[k], new_data[k])
                                       for k in sorted(new_data.keys()) if not _is_equivalent(previous_data[k], new_data[k])]

                        if all_changes:

                            message = ugettext_noop("""Attributes of user "%(username)s" have been modified:""")

                            additional_details = ""
                            for change_triplet in all_changes:
                                additional_details += """~ %s: "%s" => "%s"\n""" % change_triplet
                            additional_details = re.sub(r"\bu'", "'", additional_details)  # WORKAROUND for ugly "unicode" prefixes of python2
                            additional_details = additional_details.replace("%", "%%") # security against rogue placeholders

                            dm.log_game_event(message,
                                              substitutions=PersistentMapping(username=target_username),
                                              additional_details=additional_details,
                                              url=None,
                                              visible_by=None) # only for game master

            else:
                form_validation_failed = True

            character_forms.append(form)


    if not form_validation_failed:  # i.e if None or False

        character_forms = []

        for idx, (username, character_data) in enumerate(characters_items):
            f = forms.CharacterProfileForm(
                                    datamanager=dm,
                                    prefix=_prefix(idx),
                                    initial=dict(target_username=username,
                                                 official_name=character_data["official_name"],
                                                 official_role=character_data["official_role"],
                                                 allegiances=character_data["domains"],
                                                 permissions=character_data["permissions"],
                                                 real_life_identity=character_data["real_life_identity"],
                                                 real_life_email=character_data["real_life_email"],
                                                 gamemaster_hints=character_data["gamemaster_hints"],
                                                 is_npc=character_data["is_npc"],
                                                 extra_goods=character_data["extra_goods"])
                                    )
            character_forms.append(f)

    assert len(character_forms) == len(characters_items), [character_forms, characters_items]

    if form_validation_failed == True :
        dm.user.add_error(_("Some character updates failed (see below)."))
    elif form_validation_failed == False:
        dm.user.add_message(_("Characters were properly updated."))
    else:
        assert form_validation_failed is None
        pass

    friendship_data = dm.get_full_friendship_data()
    sealed_friendships = sorted(friendship_data["sealed"].items())
    proposed_friendships = sorted(friendship_data["proposed"].items())
    del friendship_data

    characters_emails = [x["real_life_email"] for (_username, x) in characters_items if x["real_life_email"]]

    return render(request,
                  template_name,
                    dict(
                         character_forms=character_forms,
                         sealed_friendships=sealed_friendships,
                         proposed_friendships=proposed_friendships,
                         characters_emails=characters_emails,
                         ))






@register_view(access=UserAccess.master, title=ugettext_lazy("Character Identities"))
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




@register_view(access=UserAccess.master, title=ugettext_lazy("Database Operations"))
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


@register_view(access=UserAccess.master, title=ugettext_lazy("Fail Test"))
def FAIL_TEST(request):

    raise IOError("Dummy error to test email sending")

    try:
        send_mail("hello", "bye", "gamemaster@prolifik.net", ["chambon.pascal@gmail.com"])
        return HttpResponse(_("Mail sent"))
    except Exception, e:
        raise
        # return HttpResponse(repr(e))



@register_view(access=UserAccess.master, title=ugettext_lazy("Media Display Test"))
def MEDIA_TEST(request):

    return render(request,
                  "administration/media_test.html",
                    {
                     'audioplayer': mediaplayers.generate_audio_player([game_file_url("test_samples/music.mp3")]),
                     'videoplayers': ["<p>%s</p>" % extension +
                                      mediaplayers.generate_media_player(game_file_url("test_samples/video." + extension),
                                                                         game_file_url('test_samples/image.jpg'))
                                      for extensions in mediaplayers._media_player_templates
                                      for extension in extensions]
                    })









