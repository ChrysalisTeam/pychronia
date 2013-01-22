# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

import sys
import os
from datetime import datetime, timedelta
import json
import traceback
import logging
import collections
import copy
from contextlib import contextmanager
from django.conf import settings
from django.core.mail import send_mail
from django.http import Http404, HttpResponseRedirect, HttpResponse, \
    HttpResponseForbidden
from django.shortcuts import render
from django.template import RequestContext
from django.utils.html import escape
from django.utils.translation import ugettext as _, ugettext_lazy as _lazy, ungettext
from rpgweb.common import *
from .. import forms  # AFTER common, to replace django.forms
from rpgweb.datamanager.abstract_game_view import AbstractGameView, register_view
from ..authentication import authenticate_with_credentials, logout_session
from .. import datamanager as dm_module
from rpgweb.utilities import mediaplayers, fileservers
from rpgweb.datamanager import GameDataManager
from django.shortcuts import render

from decorator import decorator

from .gameviews import character_profile, friendship_management  # IMPORTANT

from .auction_views import (homepage, opening, view_characters, view_sales, items_slideshow, item_3d_view,
                            ajax_chat, chatroom)

from .info_views import view_encyclopedia

from .profile_views import login, logout, secret_question

from .abilities import house_locking_view, runic_translation_view, wiretapping_management_view, \
        admin_dashboard_view, mercenaries_hiring_view, matter_analysis_view, worl_scan_view
from rpgweb.views.auction_views import _build_display_data_from_viewer_settings



'''
# TODO - transform this into instance which exposes real views as attributes, wrapped with register_view !!!!
def ability(request, ability_name):

    user = request.datamanager.user

    # Custom permission checking, before instantiation of ability 
    # (to avoid meaningless lazy initialization of private ability data)
    ability_class = request.datamanager.ABILITIES_REGISTRY.get(ability_name, None)
    if not ability_class:
        print(ability_name, "not in", request.datamanager.ABILITIES_REGISTRY)
        raise Http404
    """
    try:
        ability_class.check_permissions(user)
    except PermisSSSsionError, e:
        user.add_error(unicode(e))
        # todo - put default page for abilities here
        raise Http404 ## temporary ##
    """
    ability_handler = getattr(request.datamanager.abilities, ability_name) # instantiation here

    response = ability_handler.process_request(request)

    return response
'''


def is_nightmare_captcha_successful(request):
    captcha_id = request.POST.get("captcha_id")  # CLEAR TEXT ATM
    if captcha_id:
        attempt = request.POST.get("captcha_answer")
        if attempt:
            try:
                explanation = request.datamanager.check_captcha_answer_attempt(captcha_id=captcha_id, attempt=attempt)
                del explanation  # how can we display it, actually ?
                request.user.add_message(_("Captcha check successful"))
                return True
            except UsageError:
                pass
    return False



def serve_game_file(request, hash="", path="", **kwargs):

    real_hash = hash_url_path(path)

    if not hash or not real_hash or hash != real_hash:
        raise Http404("File access denied")

    full_path = os.path.join(config.GAME_FILES_ROOT, path)
    return fileservers.serve_file(request, path=full_path)


@register_view(access=UserAccess.master)
def ajax_force_email_sending(request):
    # to be used by AJAX
    msg_id = request.GET.get("id", None)

    # this should never fail, even is msg doesn't exist or is already transferred
    request.datamanager.force_message_sending(msg_id)

    return HttpResponse("OK")
    # in case of error, a "500" code will be returned




# we don't put any security there, at worst a pirate might play with this and prevent playing
# some audio notifications, but it's neither critical nor discreet
@register_view(access=UserAccess.anonymous)
def ajax_notify_audio_message_finished(request, always_available=True):

    audio_id = request.GET.get("audio_id", None)

    try:
        audio_id = audio_id.decode("base64")
    except:
        return HttpResponse("ERROR")

    res = request.datamanager.notify_audio_message_termination(audio_id)

    return HttpResponse("OK" if res else "IGNORED")
    # in case of error, a "500" code will be returned (should never happen here)


# we don't put any security there either
@register_view(access=UserAccess.anonymous, always_available=True)
def ajax_get_next_audio_message(request):
    radio_is_on = request.datamanager.get_global_parameter("radio_is_on")

    if radio_is_on:
        next_audio_id = request.datamanager.get_next_audio_message()
        if next_audio_id:
            fileurl = request.datamanager.get_audio_message_properties(next_audio_id)["url"]
            next_audio_id = next_audio_id.encode("base64")
        else:
            fileurl = None
    else:
        next_audio_id = fileurl = None

    response = json.dumps([next_audio_id, fileurl])
    return HttpResponse(response)


# no security authentication
@register_view(access=UserAccess.anonymous, always_available=True)
def ajax_domotics_security(request):

    action = request.REQUEST.get("action", None)
    if action == "lock":
        request.datamanager.lock_house_doors()
    elif action == "unlock":
        password = request.REQUEST.get("password", None)
        if password:
            request.datamanager.try_unlocking_house_doors(password)

    response = unicode(request.datamanager.are_house_doors_open())
    return HttpResponse(response)  # "True" or "False"






@register_view(access=UserAccess.anonymous)
def domotics_security(request, template_name='generic_operations/domotics_security.html'):

    user = request.datamanager.user

    if request.method == "POST":

        action = request.POST.get("action", None)

        if action == "lock":
            with action_failure_handler(request, _("House doors successfully locked.")):
                request.datamanager.lock_house_doors()
        elif action == "unlock":
            with action_failure_handler(request, _("House doors successfully unlocked.")):
                password = request.POST.get("password", None)
                if not password:
                    raise dm_module.UsageError(_("Door password must be provided"))
                res = request.datamanager.try_unlocking_house_doors(password)
                if not res:
                    raise dm_module.UsageError(_("Wrong password"))
        else:
            user.add_error(_("Unknown action"))

    are_doors_open = request.datamanager.are_house_doors_open()

    return render(request,
                  template_name,
                    {
                     'page_title': _("Doors Security Management"),
                     'are_doors_open': are_doors_open
                    })



@register_view(access=UserAccess.authenticated)
def compose_message(request, template_name='messaging/compose.html'):

    user = request.datamanager.user
    form = None
    if request.method == "POST":
        form = forms.MessageComposeForm(request, data=request.POST)
        if form.is_valid():

            with action_failure_handler(request, _("Message successfully sent.")):

                if user.is_master:
                    sender_email = form.cleaned_data["sender"]
                    delay_mn = int(form.cleaned_data["delay_mn"])
                else:
                    sender_email = request.datamanager.get_character_email(user.username)
                    delay_mn = 0

                # we parse the list of emails
                recipient_emails = form.cleaned_data["recipients"]

                subject = form.cleaned_data["subject"]
                body = form.cleaned_data["body"]
                attachment = form.cleaned_data["attachment"]

                parent_id = form.cleaned_data.get("parent_id", None)

                use_template = form.cleaned_data.get("use_template", None)

                # sender_email and one of the recipient_emails can be the same email, we don't care !
                request.datamanager.post_message(sender_email, recipient_emails, subject, body, attachment, date_or_delay_mn=delay_mn,
                                                 parent_id=parent_id, use_template=use_template)

                form = forms.MessageComposeForm(request)  # new empty form

    else:
        form = forms.MessageComposeForm(request)

    return render(request,
                  template_name,
                    {
                     'page_title': _("Compose Message"),
                     'message_form': form,
                     'mode': "compose"
                    })



@register_view(access=UserAccess.authenticated)
def inbox(request, template_name='messaging/messages.html'):

    user = request.datamanager.user
    if user.is_master:
        # We retrieve ALL emails that others won't read !!
        messages = request.datamanager.get_game_master_messages()
        remove_to = False

    else:
        messages = request.datamanager.pop_received_messages(request.datamanager.get_character_email(user.username))
        remove_to = True

    messages = list(reversed(messages))  # most recent first

    return render(request,
                  template_name,
                    {
                     'page_title': _("Messages Received"),
                     'messages': messages,
                     'remove_from': False,
                     'remove_to': remove_to,
                     'mode': "inbox"
                    })

@register_view(attach_to=inbox)
def ajax_set_message_read_state(request):

    # to be used by AJAX
    msg_id = request.GET.get("id", None)
    is_read = request.GET.get("is_read", None) == "1"

    user = request.datamanager.user
    request.datamanager.set_message_read_state(user.username, msg_id, is_read)

    return HttpResponse("OK")
    # in case of error, a "500" code will be returned

@register_view(access=UserAccess.authenticated, always_available=True)
def conversation(request):

    mode = "conversation"
    user = request.datamanager.user
    if user.is_master:
        remove_to = False
        messages = request.datamanager.get_game_master_messages()
    else:
        remove_to = True
        messages = request.datamanager.get_user_related_messages(request.datamanager.get_character_email(user.username))

    group_ids = map(lambda message: message.get("group_id", ""), messages)
    group_ids = list(set(group_ids))
    grouped_messages = []

    for group_id in group_ids:
        unordered_messages = [message for message in messages if message.get("group_id", "") == group_id]
        ordered_messsages = list(reversed(unordered_messages))
        grouped_messages.append(ordered_messsages)
    return render(request, 'messaging/conversation.html', locals())

@register_view(access=UserAccess.authenticated)
def outbox(request, template_name='messaging/messages.html'):

    user = request.datamanager.user
    if user.is_master:
        all_messages = request.datamanager.get_all_sent_messages()
        external_contacts = request.datamanager.get_external_emails(user.username)  # we list only messages sent by external contacts, not robots
        messages = [message for message in all_messages if message["sender_email"] in external_contacts]
        remove_from = False
    else:
        messages = request.datamanager.get_sent_messages(request.datamanager.get_character_email(user.username))
        remove_from = True

    messages = list(reversed(messages))  # most recent first

    return render(request,
                  template_name,
                    {
                     'page_title': _("Messages Sent"),
                     'messages': messages,
                     'remove_from': remove_from,
                     'remove_to': False,
                     'mode': "outbox"
                    })

@register_view(access=UserAccess.master)
def view_single_message(request, msg_id, template_name='messaging/single_message.html'):

    user = request.datamanager.user
    message = None
    is_queued = False

    messages = [msg for msg in request.datamanager.get_all_sent_messages() if msg["id"] == msg_id]
    if messages:
        assert len(messages) == 1
        message = messages[0]
        is_queued = False
    else:
        messages = [msg for msg in request.datamanager.get_all_queued_messages() if msg["id"] == msg_id]
        if messages:
            assert len(messages) == 1
            message = messages[0]
            is_queued = True
        else:
            user.add_error(_("The requested message doesn't exist."))

    return render(request,
                  template_name,
                    {
                     'page_title': _("Single Message"),
                     'is_queued': is_queued,
                     'message': message
                    })



@register_view(access=UserAccess.master)
def all_sent_messages(request, template_name='messaging/messages.html'):

    messages = request.datamanager.get_all_sent_messages()

    messages = list(reversed(messages))  # most recent first

    return render(request,
                  template_name,
                    {
                     'page_title': _("All Transferred Messages"),
                     'messages': messages,
                     'remove_from': False,
                     'remove_to': False,
                     'mode': "all_sent_messages"
                    })


@register_view(access=UserAccess.master)
def all_queued_messages(request, template_name='messaging/messages.html'):

    messages = request.datamanager.get_all_queued_messages()

    messages = list(reversed(messages))  # most recent first

    return render(request,
                  template_name,
                    {
                     'page_title': _("All Queued Messages"),
                     'messages': messages,
                     'remove_from': False,
                     'remove_to': False,
                     'mode': "all_queued_messages"
                    })


@register_view(access=UserAccess.authenticated)
def intercepted_messages(request, template_name='messaging/messages.html'):

    username = request.datamanager.user.username
    messages = request.datamanager.get_intercepted_messages(username)

    messages = list(reversed(messages))  # most recent first

    return render(request,
                  template_name,
                    {
                     'page_title': _("Intercepted Messages"),
                     'messages': messages,
                     'remove_from': False,
                     'remove_to': False,
                     'mode': "intercepted_messages"
                    })



@register_view(access=UserAccess.master)
def messages_templates(request, template_name='messaging/templates.html'):

    messages = request.datamanager.get_messages_templates().items()
    messages.sort(key=lambda msg: msg[0])  # we sort by template name

    return render(request,
                  template_name,
                    {
                     'page_title': _("Message Templates"),
                     'messages': messages,
                     'mode': "messages_templates",
                    })








@register_view(access=UserAccess.anonymous, always_available=True)
def view_help_page(request, keyword, template_name='generic_operations/help_page.html'):

    # FIXME TODO - check access rights to the concerned view !!!

    datamanager = request.datamanager
    allowed_entry = None

    if keyword:
        if keyword in datamanager.get_game_views():
            token = datamanager.get_game_view_access_token(keyword)
            if token == AccessResult.available:
                entry = datamanager.get_help_page(keyword)
                if entry:
                    allowed_entry = entry

    if not allowed_entry:
        raise Http404  # no corresponding help page found, or no access permissions

    return render(request,
                  template_name,
                    {
                     'page_title': _("Manual Page"),
                     'entry': allowed_entry,
                    })






@register_view(access=UserAccess.anonymous, always_available=True)
def logo_animation(request, template_name='utilities/item_3d_viewer.html'):
    """
    These settings are heavily dependant on values hard-coded on templates (dimensions, colors...),
    so they needn't be exposed inside the YAML configuration file
    """
    viewer_settings = dict(levels=1,
                            per_level=31,  # real total of images : 157, but we use steps
                            index_steps=5,
                            index_offset=0,
                            start_level=1,
                            file_template="openinglogo/crystal%04d.jpg",
                            image_width=528,
                            image_height=409,
                            mode="object",
                            x_coefficient=12,
                            y_coefficient=160,
                            autoreverse=True,
                            rotomatic=150,  # ms between rotations
                            music="musics/" + request.datamanager.get_global_parameter("opening_music")
                            )


    return render(request,
                  template_name,
                    {
                     'settings': _build_display_data_from_viewer_settings(viewer_settings),
                    })


@register_view(access=UserAccess.character, always_available=True)
def instructions(request, template_name='generic_operations/instructions.html'):

    user = request.datamanager.user
    intro_data = request.datamanager.get_game_instructions(user.username)

    return render(request,
                  template_name,
                    {
                     'page_title': _("Instructions"),
                     'intro_data': intro_data,
                    })







'''
@register_view(access=UserAccess.character)(permission="manage_translations")
def translations_management(request,  template_name='specific_operations/translations_management.html'):

    form = None

    if request.method == "POST":
        form = forms.TranslationForm(request.datamanager, request.POST)
        if form.is_valid():
            with action_failure_handler(request, _("Runes transcription successfully submitted, the result will be emailed to you.")):
                target_item = form.cleaned_data["target_item"]
                transcription = form.cleaned_data["transcription"]
                request.datamanager.process_translation_submission(user.username,
                                                           target_item, transcription) # player must NOT be game master
                form = None
    else:
        form = forms.TranslationForm(request.datamanager)

    translation_delay = request.datamanager.get_global_parameter("translation_delays")

    return render_to_response(template_name,
                                {
                                 'page_title': _("Runes translations"),
                                 "translation_form": form,
                                 'min_delay_mn': translation_delay[0],
                                 'max_delay_mn': translation_delay[1],
                                },
                                context_instance=RequestContext(request))



@register_view(access=UserAccess.character)(permission="manage_wiretaps")
def wiretapping_management(request, template_name='specific_operations/wiretapping_management.html'):


    # we process wiretap management operations
    if request.method == "POST":
        form = forms.WiretapTargetsForm(request.datamanager, user, request.POST)
        if form.is_valid():
            with action_failure_handler(request, _("Wiretap operation successful.")):
                targets = [request.datamanager.get_username_from_official_name(form.cleaned_data[name]) for name in form.fields if (name.startswith("target") and form.cleaned_data[name] != "__none__")]
                request.datamanager.change_current_user_wiretapping_targets(user.username, targets)
        else:
            user.add_error(_("Wiretap operation failed - invalid parameters."))
    # we rebuild the formulary anyway !
    current_targets = request.datamanager.get_wiretapping_targets()
    current_target_form_data = {}
    for i in range(request.datamanager.get_global_parameter("max_wiretapping_targets")):
        current_target_form_data["target_%d"%i] = request.datamanager.get_official_name_from_username(current_targets[i]) if i<len(current_targets) else "__none__"

    displayed_form = forms.WiretapTargetsForm(request.datamanager, user, current_target_form_data)
    assert displayed_form.is_valid()

    return render_to_response(template_name,
                                {
                                 'page_title': _("Wiretap Management"),
                                 'current_targets': [request.datamanager.get_official_name_from_username(current_target) for current_target in current_targets],
                                 'wiretapping_form': displayed_form,
                                },
                                context_instance=RequestContext(request))




@register_view()#access=UserAccess.character)(permission="manage_scans")
def __scanning_management(request, template_name='specific_operations/scanning_management.html'):

    user = request.datamanager.user
    form = None
    available_items = request.datamanager.get_available_items_for_user(user.username)

    # we process scanning management operations
    if request.method == "POST":

        form = forms.ScanningForm(available_items, request.POST)
        if form.is_valid():
            with action_failure_handler(request, _("Scanning request submitted.")):
                item_name = form.cleaned_data["item_name"]
                description = form.cleaned_data["description"].strip()
                request.datamanager.process_scanning_submission(user.username, item_name, description) # might be game master
                form = None
        else:
            user.add_error(_("Scanning request failed - invalid parameters."))

    else:
        form = forms.ScanningForm(available_items)


    return render_to_response(template_name,
                                {
                                 'page_title': _("Scanning Management"),
                                 'scanning_form': form, # In ANY case we provide the form, since it's possible to provide only a description of objects to scan
                                 'available_items': available_items
                                },
                                context_instance=RequestContext(request))





@register_view(access=UserAccess.character)#(permission="manage_teleportations")
def __teldorian_teleportations(request, template_name='specific_operations/armed_interventions.html'):

    user = request.datamanager.user
    form = None
    available_locations = sorted(request.datamanager.get_locations().keys()) # NO FILTERING AT THE MOMENT !

    if available_locations:

        if request.method == "POST":

            form = forms.ArmedInterventionForm(available_locations, request.POST)
            if form.is_valid():
                message = form.cleaned_data["message"]
                city_name = form.cleaned_data["city_name"]
                with action_failure_handler(request, _("Teleportation operation successfully launched on %s.") % city_name):
                    request.datamanager.trigger_teldorian_teleportation(user.username, city_name, message) # might be game master
                    form = forms.ArmedInterventionForm(available_locations) # new empty formulary
            else:
                user.add_error(_("Teleportation operation not launched - invalid commands."))

        else:
            form = forms.ArmedInterventionForm(available_locations)


    # NOW we can refresh the parameters available

    teldorian_teleportations_done = request.datamanager.get_global_parameter("teldorian_teleportations_done")
    plural = "s" if teldorian_teleportations_done != 1 else ""
    max_teldorian_teleportations = request.datamanager.get_global_parameter("max_teldorian_teleportations")

    instructions = _("You may here trigger the teleportation of our intervention squads, according to the location and instructions you'll send.")

    instructions += " " + ungettext("You have already launched %(current)s teleportation, on a maximum allowed of %(maximum)s such operations.",
                                    "You have already launched %(current)s teleportations, on a maximum allowed of %(maximum)s such operations.",
                                    teldorian_teleportations_done) % dm_module.SDICT(current=teldorian_teleportations_done, maximum=max_teldorian_teleportations)


    intervention_impossible_msg = None
    if (teldorian_teleportations_done >= max_teldorian_teleportations):
        intervention_impossible_msg = _("You have already used all available teleportations.")


    return render_to_response(template_name,
                                {
                                 'page_title': _("Teleportation Operations"),
                                 'instructions': instructions,
                                 'intervention_form': form,
                                 'intervention_impossible_msg': intervention_impossible_msg,
                                 'target_url': reverse(teldorian_teleportations, kwargs=dict(game_instance_id=request.datamanager.game_instance_id)),
                                 'same_width_widgets': True
                                },
                                context_instance=RequestContext(request))




@register_view(access=UserAccess.character)#(permission="manage_agents")
def __mercenary_commandos(request, template_name='specific_operations/armed_interventions.html'):

    user = request.datamanager.user

    instructions = _("You may here send intervention commands to the mercenaries of the cities you control.")

    available_locations = sorted([city for (city, properties) in request.datamanager.get_locations().items() if properties["has_mercenary"]])

    form = None

    if available_locations: # else, we don't even show error messages if hacking attempts are made

        if request.method == "POST":

            form = forms.ArmedInterventionForm(available_locations, request.POST)
            if form.is_valid():

                message = form.cleaned_data["message"]
                city_name = form.cleaned_data["city_name"]
                with action_failure_handler(request, _("Commando operation successfully launched on %s.") % city_name):
                    request.datamanager.trigger_masslavian_mercenary_intervention(user.username, city_name, message) # might be game master
                    form = forms.ArmedInterventionForm(available_locations) # new empty formulary
            else:
                user.add_error(_("Commando operation not launched - invalid commands."))

        else:
            form = forms.ArmedInterventionForm(available_locations)

        intervention_impossible_msg = None

    else:
        intervention_impossible_msg = _("At the moment, there is no place where you can launch an armed operation.")

    return render_to_response(template_name,
                                {
                                 'page_title': _("Mercenary Commandos"),
                                 'instructions': instructions,
                                 'intervention_form': form,
                                 'intervention_impossible_msg': intervention_impossible_msg,
                                 'target_url': reverse(mercenary_commandos, kwargs=dict(game_instance_id=request.datamanager.game_instance_id)),
                                 'same_width_widgets': True
                                },
                                context_instance=RequestContext(request))




@register_view(access=UserAccess.character)#(permission="launch_attacks")
def __acharith_attacks(request, template_name='specific_operations/armed_interventions.html'):

    user = request.datamanager.user

    instructions = _("You may here send intervention orders to acharith zealots accointed with us, and who are spread over the world.\n<Baazel>")

    available_locations = sorted(request.datamanager.get_locations().keys()) # NO FILTERING

    form = None

    if available_locations:

        if request.method == "POST":

            form = forms.ArmedInterventionForm(available_locations, request.POST)
            if form.is_valid():
                message = form.cleaned_data["message"]
                city_name = form.cleaned_data["city_name"]
                with action_failure_handler(request, _("Attack successfully launched on %s.") % city_name):
                    request.datamanager.trigger_acharith_attack(user.username, city_name, message) # might be game master
                    form = forms.ArmedInterventionForm(available_locations) # new empty formulary
            else:
                user.add_error(_("Attack not launched - invalid instructions."))

        else:
            form = forms.ArmedInterventionForm(available_locations)

    intervention_impossible_msg = None # acharith people can ALWAYS attack, at the moment

    return render_to_response(template_name,
                                {
                                 'page_title': _("Holy Attacks"),
                                 'instructions': instructions,
                                 'intervention_form': form,
                                 'intervention_impossible_msg': intervention_impossible_msg,
                                 'target_url': reverse(acharith_attacks, kwargs=dict(game_instance_id=request.datamanager.game_instance_id)),
                                 'same_width_widgets': True
                                },
                                context_instance=RequestContext(request))



@register_view(access=UserAccess.character)#(permission="launch_telecom_investigations")
def __telecom_investigation(request, template_name='specific_operations/telecom_investigation.html'):

    user = request.datamanager.user
    form = None

    if request.method == "POST":

        form = forms.TelecomInvestigationForm(request.datamanager, user, request.POST)
        if form.is_valid():
            official_name = form.cleaned_data["official_name"]
            with action_failure_handler(request, _("Inquiry successfully begun into \"%s\".") % official_name):
                request.datamanager.launch_telecom_investigation(user.username, request.datamanager.get_username_from_official_name(official_name)) # might be game master
                form = forms.TelecomInvestigationForm(request.datamanager, user) # new empty formulary
        else:
            user.add_error(_("Inquiry not begun - invalid instructions."))

    else:
        form = forms.TelecomInvestigationForm(request.datamanager, user)


    telecom_investigations_done = request.datamanager.get_global_parameter("telecom_investigations_done")
    plural = "s" if telecom_investigations_done != 1 else ""
    max_telecom_investigations = request.datamanager.get_global_parameter("max_telecom_investigations")

    instructions = _("You may here test our new telecommunication interception and decryption system.")

    instructions += " " + ungettext("You have already tried it %(current)d time, on a maximum allowed of %(maximum)d such operations.",
                                "You have already tried it %(current)d times, on a maximum allowed of %(maximum)d such operations.",
                                telecom_investigations_done) % dm_module.SDICT(current=telecom_investigations_done, maximum=max_telecom_investigations)


    inquiry_impossible_msg = None
    if (telecom_investigations_done >= max_telecom_investigations):
        inquiry_impossible_msg = _("You have already used all available inquiries.")


    return render_to_response(template_name,
                                {
                                 'page_title': _("Telecom Investigations"),
                                 'instructions': instructions,
                                 'investigation_form': form,
                                 'investigation_impossible_msg': inquiry_impossible_msg,
                                },
                                context_instance=RequestContext(request))
'''



@register_view(access=UserAccess.anonymous, always_available=True)  # links in emails must NEVER be broken
def encrypted_folder(request, folder, entry_template_name="generic_operations/encryption_password.html", display_template_name='personal_folder.html'):

    if not request.datamanager.encrypted_folder_exists(folder):
        raise Http404

    user = request.datamanager.user
    files = []
    form = None

    if request.method == "POST":
        form = forms.SimplePasswordForm(request.POST)
        if form.is_valid():
            password = form.cleaned_data["simple_password"].lower()  # normalized !

            with action_failure_handler(request, _("Folder decryption successful.")):
                files = request.datamanager.get_encrypted_files(user.username, folder, password, absolute_urls=False)
                form = None  # triggers the display of files

    else:
        form = forms.SimplePasswordForm()


    if form:
        return render(request,
                      entry_template_name,
                        {
                            "page_title": _("Encrypted archive '%s'") % folder,
                            "password_form": form,
                            "folder": folder
                        })


    else:  # necessarily, we've managed to decrypt the folder

        files_to_display = zip([os.path.basename(myfile) for myfile in files], files)

        if not files_to_display:
            user.add_message = _("No files were found in the folder.")


        return render(request,
                      display_template_name,
                        {
                            "page_title": _("Decrypted archive '%s'") % folder,
                            "files": files_to_display,
                            "display_maintenance_notice": False,  # upload disabled notification
                        })



@register_view(access=UserAccess.authenticated, always_available=True)
def personal_folder(request, template_name='generic_operations/personal_folder.html'):

    user = request.datamanager.user

    try:

        personal_files = request.datamanager.get_personal_files(user.username if not user.is_master else None,
                                                                absolute_urls=False)  # to allow easier stealing of files from Loyd's session

    except EnvironmentError, e:
        personal_files = []
        user.add_error(_("Your personal folder is unreachable."))


    files_to_display = zip([os.path.basename(file) for file in personal_files], personal_files)

    if not files_to_display:
        user.add_message = _("You currently don't have any files in your personal folder.")

    return render(request,
                  template_name,
                    {
                        "page_title": _("Personal Folder"),
                        "files": files_to_display,
                        "display_maintenance_notice": True,  # upload disabled notification
                    })



# This page is meant for inclusion in pages offering all the required css/js files !
@register_view(access=UserAccess.authenticated, always_available=True)
def view_media(request, template_name='utilities/view_media.html'):

    fileurl = request.REQUEST.get("url", None)
    autostart = (request.REQUEST.get("autostart", "false") == "true")

    if fileurl:
        media_player = mediaplayers.build_proper_viewer(fileurl, autostart=autostart)
    else:
        media_player = "<p>" + _("You must provide a valid media url.") + "</p>"

    return render(request,
                  template_name,
                    {
                     'media_player': media_player
                    })


@register_view(access=UserAccess.master)
def game_events(request, template_name='administration/game_events.html'):

    events = request.datamanager.get_game_events()  # keys : time, message, username

    trans_events = []
    for event in events:
        trans_event = event.copy()
        if trans_event["substitutions"]:
            trans_event["trans_message"] = _(trans_event["message"]) % dm_module.SDICT(**trans_event["substitutions"])
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

'''
@register_view(access=UserAccess.authenticated) # obsolete...
def __personal_radio_messages_listing(request, template_name='generic_operations/personal_radio_messages.html'):

    user = request.datamanager.user

    new_messages_text = None
    #request_for_report_text = None
    victory_text = None
    defeat_text = None

    if user.is_master:
        is_master = True
    else:
        is_master = False

        character_properties = request.datamanager.get_character_properties(user.username)

        new_messages_text = request.datamanager.get_audio_message_properties(character_properties["new_messages_notification"])["text"]
        
        # FIXME ALL BUGGY
        #domain_properties = request.datamanager.get_domain_properties(character_properties["domain"])
        #request_for_report_text = request.datamanager.get_audio_message_properties(domain_properties["request_for_report"])["text"]
        victory_text = "VICTORYYY" # request.datamanager.get_audio_message_properties(domain_properties["victory"])["text"]
        defeat_text = "DEFEAAAT" ## request.datamanager.get_audio_message_properties(domain_properties["defeat"])["text"]

    return render_to_response(template_name,
                            {
                             'page_title': _("Personal radio messages"),
                             'is_master': is_master,
                             'new_messages_text': new_messages_text,
                             #'request_for_report_text': request_for_report_text,
                             'victory_text': victory_text,
                             'defeat_text': defeat_text,
                             'can_wiretap': user.has_permission("manage_wiretaps")
                            },
                            context_instance=RequestContext(request))
'''


@register_view(access=UserAccess.anonymous, always_available=True)
def listen_to_webradio(request, template_name='utilities/web_radio.html'):
    return render(request,
                  template_name,
                    {
                     "player_conf_url": reverse(get_radio_xml_conf, kwargs=dict(game_instance_id=request.datamanager.game_instance_id)),
                     "player_width": 300,
                     "player_height": 200,
                    })

@register_view(access=UserAccess.anonymous, always_available=True)
def get_radio_xml_conf(request, template_name='utilities/web_radio_conf.xml'):
    dm = request.datamanager
    current_playlist = dm.get_all_next_audio_messages()
    current_audio_messages = [dm.get_audio_message_properties(audio_id) for audio_id in current_playlist]

    if not current_audio_messages:
        # we had better not let the player empty, it's not tweaked for that case
        current_audio_messages = [dict(url="http://", title=_("[No radio spot currently available]"))]

    audio_urls = "|".join([msg["url"] for msg in current_audio_messages])  # we expect no "|" inside a single url
    audio_titles = "|".join([msg["title"].replace("|", "") for msg in current_audio_messages])  # here we can cleanup

    return render(request,
                  template_name,
                  dict(audio_urls=audio_urls,
                       audio_titles=audio_titles))


@register_view(access=UserAccess.anonymous, always_available=True)
def listen_to_audio_messages(request, template_name='utilities/web_radio_applet.html'):

    access_authorized = False

    if request.method == "POST":
        with action_failure_handler(request, _("You're listening to Pangea Radio.")):
            frequency = request.POST.get("frequency", None)
            if frequency:
                frequency = frequency.strip()
            request.datamanager.check_radio_frequency(frequency)  # raises UsageError on failure
            access_authorized = True

    if access_authorized:
        form = None
    else:
        form = forms.RadioFrequencyForm()


    assert (form and not access_authorized) or (not form and access_authorized)

    return render(request,
                  template_name,
                    {
                     'page_title': _("Radio Station"),
                     'access_authorized': access_authorized,
                     'form': form
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



# TODO - redo this as special ability
@register_view  # (access=UserAccess.character)#(permission="contact_djinns")
def chat_with_djinn(request, template_name='specific_operations/chat_with_djinn.html'):

    bot_name = request.POST.get("djinn", None)

    # TODO BAD - add security here !!!!!!!!!!

    if not request.datamanager.is_game_started():
        return HttpResponse(_("Game is not yet started"))

    if bot_name not in request.datamanager.get_bot_names():
        raise Http404

    history = request.datamanager.get_bot_history(bot_name)

    sentences = []
    for i in range(max(len(history[0]), len(history[1]))):
        if i < len(history[0]):
            sentences.append(history[0][i])  # input
        if i < len(history[1]):
            sentences.append(history[1][i])  # output

    return render(request,
                  template_name,
                    {
                     'page_title': _("Djinn Communication"),
                     'bot_name': bot_name,
                     'history': sentences
                    })


@register_view(attach_to=chat_with_djinn)  # access=UserAccess.character)(permission="contact_djinns")
def ajax_consult_djinns(request):
    user = request.datamanager.user
    message = request.REQUEST.get("message", "")
    bot_name = request.REQUEST.get("djinn", None)

    if bot_name not in request.datamanager.get_bot_names():
        raise Http404

    res = request.datamanager.get_bot_response(user.username, bot_name, message)
    return HttpResponse(escape(res))  # IMPORTANT - escape xml entities !!

    # in case of error, a "500" code will be returned

# TODO - redo this as special ability
@register_view  # (access=UserAccess.character)#(permission="contact_djinns")
def contact_djinns(request, template_name='specific_operations/contact_djinns.html'):

    user = request.datamanager.user

    bots_properties = request.datamanager.get_bots_properties()

    if user.is_master:  # FIXME
        available_bots = bots_properties.keys()
        # team_gems = None
    else:
        domain = request.datamanager.get_character_properties(user.username)["domain"]
        available_bots = [bot_name for bot_name in bots_properties.keys() if request.datamanager.is_bot_accessible(bot_name, domain)]
        # team_gems = request.datamanager.get_team_gems_count(domain)

    if available_bots:
        djinn_form = forms.DjinnContactForm(available_bots)
    else:
        djinn_form = None

    all_bots = bots_properties.items()
    all_bots.sort(key=lambda t: t[1]["gems_required"])

    return render(request,
                  template_name,
                    {
                     'page_title': _("Shrine of Oracles"),
                     'djinn_form': djinn_form,
                     'all_bots': all_bots,
                     # 'team_gems': team_gems,
                     'bots_max_answers': request.datamanager.get_global_parameter("bots_max_answers")
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


