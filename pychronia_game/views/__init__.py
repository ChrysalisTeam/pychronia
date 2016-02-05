# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

import sys
import os
from datetime import datetime, timedelta
import json
import traceback
import collections
import copy
import fileservers

from contextlib import contextmanager
from django.conf import settings

from django.core.mail import mail_admins
from django.http import Http404, HttpResponseRedirect, HttpResponse, \
    HttpResponseForbidden
from django.shortcuts import render
from django.template import RequestContext
from django.utils.html import escape
from django.utils.translation import ugettext as _, ugettext_lazy, ungettext
from pychronia_game.common import *
from .. import forms  # AFTER common, to replace django.forms
from pychronia_game.datamanager import AbstractGameView, register_view
from ..authentication import try_authenticating_with_credentials, logout_session
from .. import datamanager as dm_module
from pychronia_game.utilities import mediaplayers
from pychronia_game.datamanager import GameDataManager


from .auction_views import (_build_display_data_from_viewer_settings, homepage, view_characters,
                            view_sales, auction_items_slideshow, personal_items_slideshow, item_3d_view, ajax_chat, chatroom)

from .info_views import (view_encyclopedia, view_static_page,
                         personal_webradio_popup, personal_webradio_page, get_radio_xml_conf, public_webradio,
                         ajax_get_next_audio_message, ajax_notify_audio_message_finished,
                         personal_folder, view_media, encrypted_folder, view_world_map)

from .profile_views import login, logout, secret_question, character_profile, friendship_management, game_events


from .messaging_views import (ajax_set_message_template_state_flags, ajax_set_dispatched_message_state_flags, ajax_force_email_sending, ajax_permanently_delete_message,
                              standard_conversations, view_single_message, compose_message, preview_message,
                              all_dispatched_messages, all_queued_messages, intercepted_messages, all_archived_messages, messages_templates)

from .abilities import (house_locking, runic_translation, wiretapping_management, artificial_intelligence,
                        mercenaries_hiring, matter_analysis, world_scan, chess_challenge, geoip_location,
                        business_escrow, black_market, ability_introduction, telecom_investigation)

from .admin_views import (admin_dashboard, webradio_management, gamemaster_manual,
                          manage_databases, static_pages_management, global_contacts_management,
                          game_items_management, radio_spots_editing, admin_information,
                          manage_characters, CHARACTERS_IDENTITIES,
                          DATABASE_OPERATIONS, FAIL_TEST, MEDIA_TEST)





#### Here are the views that don't belong to any particular category ####


def game_homepage_without_username(request):
    """
    Simple redirection when homepage URL lacks the "game_username" part.
    """
    username_homepage = game_view_url("pychronia_game-homepage", datamanager=request.datamanager)
    return HttpResponseRedirect(redirect_to=username_homepage)


def serve_game_file(request, hash="", path="", **kwargs):

    real_hash = hash_url_path(path)

    if not hash or not real_hash or hash != real_hash:
        raise Http404("File access denied")

    full_path = os.path.join(config.GAME_FILES_ROOT, path)
    return fileservers.serve_file(request, path=full_path)




@register_view(access=UserAccess.anonymous, requires_global_permission=False, title=ugettext_lazy("Logo Animation"))
def ___logo_animation(request, template_name='utilities/item_3d_viewer.html'):
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
                            music=None)


    return render(request,
                  template_name,
                    {
                     'settings': _build_display_data_from_viewer_settings(viewer_settings),
                    })



@register_view(access=UserAccess.anonymous, requires_global_permission=False, title=ugettext_lazy("View Help Page"))
def view_help_page(request, keyword, template_name='utilities/help_page.html'):
    """
    Access for targeted pages is checked here!
    """

    datamanager = request.datamanager

    allowed_entry = None
    if keyword:
        view_name = keyword[len("help-"):]
        if view_name in datamanager.get_game_views():
            token = datamanager.get_game_view_access_token(view_name)
            del view_name
            if token == AccessResult.available: # IMPORTANT
                entry = datamanager.get_categorized_static_page(datamanager.HELP_CATEGORY, keyword)
                if entry:
                    allowed_entry = entry

    if not allowed_entry:
        raise Http404  # no corresponding help page found, or no access permissions

    if datamanager.is_game_writable():
        datamanager.mark_static_page_as_accessed(keyword)

    return render(request,
                  template_name,
                    {
                     'page_title': _("Help"),
                     'entry': allowed_entry,
                    })


@register_view(access=UserAccess.anonymous, requires_global_permission=False, title=ugettext_lazy("Bug Report"))
def bug_report_treatment(request):

    if request.method != "POST":
        return HttpResponse("KO - bug not reported")

    report_data = request.POST.get("report_data", "[no report_data]")
    location = request.POST.get("location", "[no location]")

    """
    from django.views import debug
    res = debug.technical_500_response(request, None, None, None)
    print (res.content)
    """
    dm = request.datamanager
    message = dedent("""
                    Bug report submitted by player %(username)s.
                    
                    URL: %(location)s
                    
                    Message: %(report_data)s
                    """) % dict(username=dm.user.username,
                                location=location,
                                report_data=report_data)

    dm.logger.warning("Submitting pychronia bug report by email:\n%r", message)

    mail_admins("Pychronia Bug Report", message=message, html_message=None) # we don't know if it REALLY sends stuffs...

    return HttpResponse("OK - bug reported")






'''
   ---------- DEPRECATED STUFFS ---------
    TO DELETE ASAP

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


# no security authentication
@register_view(access=UserAccess.anonymous, requires_global_permission=False)
def _______ajax_domotics_security(request):

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
def _________domotics_security(request, template_name='generic_operations/domotics_security.html'):

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




@register_view(access=UserAccess.character)(permission="manage_translations")
def translations_management(request,  template_name='specific_operations/translations_management.html'):

    form = None

    if request.method == "POST":
        form = forms.TranslationForm(request.datamanager, request.POST)
        if form.is_valid():
            with action_failure_handler(request, _("Runes transcription successfully submitted, the result will be emailed to you.")):
                target_item = form.cleaned_data["target_item"]
                transcription = form.cleaned_data["transcription"]
                request.datamanager.process_translation_submission(,
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
                request.datamanager.change_current_user_wiretapping_targets(targets)
        else:
            user.add_error(_("Wiretap operation failed - invalid parameters."))
    # we rebuild the formulary anyway !
    current_targets = request.datamanager.get_wiretapping_targets()
    current_target_form_data = {}
    for i in range(request.datamanager.get_global_parameter("max_wiretapping_targets")):
        current_target_form_data["target_%d"%i] = request.datamanager.get_official_name(current_targets[i]) if i<len(current_targets) else "__none__"

    displayed_form = forms.WiretapTargetsForm(request.datamanager, user, current_target_form_data)
    assert displayed_form.is_valid()

    return render_to_response(template_name,
                                {
                                 'page_title': _("Wiretap Management"),
                                 'current_targets': [request.datamanager.get_official_name(current_target) for current_target in current_targets],
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
def __akarith_attacks(request, template_name='specific_operations/armed_interventions.html'):

    user = request.datamanager.user

    instructions = _("You may here send intervention orders to akarith zealots accointed with us, and who are spread over the world.\n<Baazel>")

    available_locations = sorted(request.datamanager.get_locations().keys()) # NO FILTERING

    form = None

    if available_locations:

        if request.method == "POST":

            form = forms.ArmedInterventionForm(available_locations, request.POST)
            if form.is_valid():
                message = form.cleaned_data["message"]
                city_name = form.cleaned_data["city_name"]
                with action_failure_handler(request, _("Attack successfully launched on %s.") % city_name):
                    request.datamanager.trigger_akarith_attack(user.username, city_name, message) # might be game master
                    form = forms.ArmedInterventionForm(available_locations) # new empty formulary
            else:
                user.add_error(_("Attack not launched - invalid instructions."))

        else:
            form = forms.ArmedInterventionForm(available_locations)

    intervention_impossible_msg = None # akarith people can ALWAYS attack, at the moment

    return render_to_response(template_name,
                                {
                                 'page_title': _("Holy Attacks"),
                                 'instructions': instructions,
                                 'intervention_form': form,
                                 'intervention_impossible_msg': intervention_impossible_msg,
                                 'target_url': reverse(akarith_attacks, kwargs=dict(game_instance_id=request.datamanager.game_instance_id)),
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





