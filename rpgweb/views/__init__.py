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
from django.http import Http404, HttpResponseRedirect, HttpResponse,\
    HttpResponseForbidden
from django.shortcuts import render
from django.template import RequestContext
from django.utils.html import escape
from django.utils.translation import ugettext as _, ugettext_lazy as _lazy, ungettext

from ..common import *
from .. import forms
from ._abstract_game_view import register_view
from ..authentication import authenticate_with_credentials, logout_session
from .. import datamanager as dm_module
from rpgweb.utilities import mediaplayers, fileservers
from rpgweb.datamanager import GameDataManager
from rpgweb.common import game_file_url, UsageError
from decorator import decorator


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
    captcha_id = request.POST.get("captcha_id") # CLEAR TEXT ATM
    if captcha_id:
        attempt = request.POST.get("captcha_answer")
        if attempt:
            try:
                explanation = request.datamanager.check_captcha_answer_attempt(captcha_id=captcha_id, attempt=attempt)
                del explanation # how can we display it, actually ?
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
def ajax_notify_audio_message_finished(request):

    audio_id = request.GET.get("audio_id", None)

    try:
        audio_id = audio_id.decode("base64")
    except:
        return HttpResponse("ERROR")

    res = request.datamanager.notify_audio_message_termination(audio_id)

    return HttpResponse("OK" if res else "IGNORED")
    # in case of error, a "500" code will be returned (should never happen here)


# we don't put any security there either
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
def ajax_domotics_security(request):

    action = request.REQUEST.get("action", None)
    if action == "lock":
        request.datamanager.lock_house_doors()
    elif action == "unlock":
        password = request.REQUEST.get("password", None)
        if password:
            request.datamanager.try_unlocking_house_doors(password)

    response = unicode(request.datamanager.are_house_doors_open())
    return HttpResponse(response) # "True" or "False"




@register_view(access=UserAccess.authenticated)
def ajax_chat(request):

    if request.method == "POST":
        # User has sent new data.
        msg_text = request.POST.get('message', "")
        msg_text = msg_text.strip()
        if msg_text: # Just ignore empty strings.
            request.datamanager.send_chatroom_message(msg_text) # will fail if user is master

        return HttpResponse("OK")

    else:
        slice_index = int(request.GET['slice_index']) # may raise exceptions

        (new_slice_index, previous_msg_timestamp, new_messages) = request.datamanager.get_chatroom_messages(slice_index)
        msg_format = "<b>%(official_name)s</b> - %(message)s"
        time_format = "<i>=== %d/%m/%Y - %H:%M:%S UTC ===</i>"

        threshold = request.datamanager.get_global_parameter("chatroom_timestamp_display_threshold_s")
        chatroom_timestamp_display_threshold = timedelta(seconds=threshold)
        text_lines = []
        for msg in new_messages:
            if not previous_msg_timestamp or (msg["time"] - previous_msg_timestamp) > chatroom_timestamp_display_threshold:
                text_lines.append(msg["time"].strftime(time_format))
            if msg["username"] in request.datamanager.get_character_usernames():
                official_name = request.datamanager.get_official_name_from_username(msg["username"])
                color = request.datamanager.get_character_color_or_none(msg["username"])
            else: # system message
                official_name = _("system")
                color = "#ea3f32" 
            data = dict(official_name=official_name,
                        message=msg["message"])
            text_lines.append({"username": msg["username"], 
                               "color": color,
                               "message": msg_format % data})
            previous_msg_timestamp = msg["time"]
        all_data = {"slice_index": new_slice_index,
                    "messages": text_lines
                }
        response = HttpResponse(json.dumps(all_data))
        response['Content-Type'] = 'text/plain; charset=utf-8'
        response['Cache-Control'] = 'no-cache'

        return response





@register_view(access=UserAccess.authenticated) # game master can view too
def chatroom(request, template_name='generic_operations/chatroom.html'):

    # TODO - move "chatting users" to ajax part, because it must be updated !!
    chatting_users = [request.datamanager.get_official_name_from_username(username)
                      for username in request.datamanager.get_chatting_users()]
    return render(request,
                  template_name,
                    {
                     'page_title': _("Common Chatroom"),
                     'chatting_users': chatting_users
                    })



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

                reply_to = form.cleaned_data.get("reply_to", None)
                use_template = form.cleaned_data.get("use_template", None)

                # sender_email and one of the recipient_emails can be the same email, we don't care !
                request.datamanager.post_message(sender_email, recipient_emails, subject, body, attachment, date_or_delay_mn=delay_mn,
                                           reply_to=reply_to, use_template=use_template)

                form = forms.MessageComposeForm(request) # new empty form

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
        messages = request.datamanager.get_received_messages(request.datamanager.get_character_email(user.username),
                                                             reset_notification=True)
        remove_to = True

    messages = list(reversed(messages)) # most recent first
    
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




@register_view(access=UserAccess.authenticated)
def outbox(request, template_name='messaging/messages.html'):

    user = request.datamanager.user
    if user.is_master:
        all_messages = request.datamanager.get_all_sent_messages()
        external_contacts = request.datamanager.get_external_emails(user.username) # we list only messages sent by external contacts, not robots
        messages = [message for message in all_messages if message["sender_email"] in external_contacts]
        remove_from = False
    else:
        messages = request.datamanager.get_sent_messages(request.datamanager.get_character_email(user.username))
        remove_from = True

    messages = list(reversed(messages)) # most recent first

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

    messages = list(reversed(messages)) # most recent first

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

    messages = list(reversed(messages)) # most recent first

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

    messages = list(reversed(messages)) # most recent first

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
    messages.sort(key=lambda msg: msg[0]) # we sort by template name

    return render(request,
                  template_name,
                    {
                     'page_title': _("Message Templates"),
                     'messages': messages,
                     'mode': "messages_templates",
                    })


@register_view(access=UserAccess.anonymous)
def secret_question(request, template_name='registration/secret_question.html'):

    secret_question = None
    form = None

    username = request.REQUEST.get("secret_username", None)
    if not username or username not in request.datamanager.get_character_usernames():
        # user.add_error("You must provide a valid username to recover your password") -> no, won't work with redirect !
        return HttpResponseRedirect(reverse(homepage, kwargs=dict(game_instance_id=request.datamanager.game_instance_id)))


    if request.method == "POST" and request.POST.get("recover", None):

        # WARNING - manual validation, so that secret answer is checked BEFORE email address
        secret_answer_attempt = request.POST.get("secret_answer", None)
        if secret_answer_attempt:
            secret_answer_attempt = secret_answer_attempt.strip()
        target_email = request.POST.get("target_email", None)
        if target_email:
            target_email = target_email.strip()

        with action_failure_handler(request, _("Your password has been successfully emailed to your backup address.")):
            try:
                request.datamanager.process_secret_answer_attempt(username, secret_answer_attempt, target_email) # raises error on bad answer/email
                # success
                form = None
                secret_question = None
            except:
                secret_question = request.datamanager.get_secret_question(username)
                form = forms.SecretQuestionForm(username, data=request.POST)
                form.full_clean()
                raise

    else:
        secret_question = request.datamanager.get_secret_question(username)
        form = forms.SecretQuestionForm(username)

    assert (not form and not secret_question) or (form and secret_question)

    return render(request,
                  template_name,
                    {
                     'page_title': _("Password Recovery"),
                     'secret_question': secret_question,
                     'secret_question_form': form,
                    })


@register_view(access=UserAccess.anonymous, always_available=True)
def login(request, template_name='registration/login.html'):

    form = None
    user = request.datamanager.user

    if request.method == "POST":
        if not request.session.test_cookie_worked():
            user.add_error(_("Your Web browser doesn't appear to have cookies enabled. Cookies are required for logging in."))
            # we let form == None, since anyway changing the settings of the browser is required before anything can work.
        else:
            form = forms.AuthenticationForm(data=request.POST)
            if form.is_valid():
                username = form.cleaned_data["secret_username"].strip()
                password = form.cleaned_data["secret_password"].strip()

                if request.POST.get("password_forgotten", None):

                    if username == "master":
                        user.add_error(_("Game master can't recover his password through a secret question."))
                    elif username not in request.datamanager.get_character_usernames():
                        user.add_error(_("You must provide a valid username to recover your password."))
                    else:
                        return secret_question(request)

                else: # normal authentication
                    with action_failure_handler(request, _("You've been successfully logged in.")): # message won't be seen because of redirect...
                        authenticate_with_credentials(request, username, password)
                        if request.datamanager.is_game_started():
                            return HttpResponseRedirect(reverse(homepage, kwargs=dict(game_instance_id=request.datamanager.game_instance_id)))
                        else: # little advertisement...
                            return HttpResponseRedirect(reverse(opening, kwargs=dict(game_instance_id=request.datamanager.game_instance_id)))

    else:
        request.session.set_test_cookie()
        form = forms.AuthenticationForm()

    return render(request,
                  template_name,
                    {
                     'page_title': _("User Authentication"),
                     'login_form': form
                    })


@register_view(access=UserAccess.authenticated, always_available=True)
def logout(request, template_name='registration/logout.html'):

    logout_session(request)
    
    user = request.datamanager.user # take user only NOW, after logout
    user.add_message(_("You've been successfully logged out."))  # will not be seen with redirection
    return HttpResponseRedirect(reverse(login, kwargs=dict(game_instance_id=request.datamanager.game_instance_id)))



@register_view(access=UserAccess.anonymous, always_available=True)
def homepage(request, template_name='generic_operations/homepage.html'):

    return render(request,
                  template_name,
                    {
                     'page_title': _("Realm Entrance"),
                     'opening_music': game_file_url("musics/" + request.datamanager.get_global_parameter("opening_music"))
                    })


@register_view(access=UserAccess.anonymous, always_available=True)
def opening(request, template_name='generic_operations/opening.html'):

    return render(request,
                  template_name,
                    {
                     'page_title': None,
                    })


@register_view(access=UserAccess.anonymous, always_available=True)
def view_encyclopedia(request, article_id=None, template_name='generic_operations/encyclopedia.html'):
    
    dm =  request.datamanager
    
    article_ids = None # index of encyclopedia
    entry = None # current article
    search_results = None # list of matching article ids
    
    if article_id:
        entry = dm.get_encyclopedia_entry(article_id)
        if not entry:
            dm.user.add_error(_("Sorry, no encyclopedia article has been found for id '%s'") % article_id)
    else:
        search_string = request.REQUEST.get("search") # needn't appear in browser history, but GET needed for encyclopedia links
        if search_string:
            if not dm.is_game_started():
                dm.user.add_error(_("Sorry, the search engine of the encyclopedia is currently under repair"))
            else:
                search_results = dm.get_encyclopedia_matches(search_string)
                if not search_results:
                    dm.user.add_error(_("Sorry, no matching encyclopedia article has been found for '%s'") % search_string)
                else:
                    if dm.is_character(): # not for master or anonymous!!
                        dm.update_character_known_article_ids(search_results)
                    if len(search_results) == 1:
                        dm.user.add_message(_("Your search has led to a single article, below."))
                        return HttpResponseRedirect(redirect_to=reverse(view_encyclopedia, kwargs=dict(game_instance_id=request.datamanager.game_instance_id,
                                                                                                  article_id=search_results[0])))                                     
    
    # NOW only retrieve article ids, since known article ids have been updated if necessary
    if request.datamanager.is_encyclopedia_index_visible() or dm.is_master():
        article_ids = request.datamanager.get_encyclopedia_article_ids()
    elif dm.is_character():
        article_ids = dm.get_character_known_article_ids()
    else:
        assert dm.is_anonymous() # we leave article_ids to None
             
    return render(request,
                  template_name,
                    {
                     'page_title': _("Pangea Encyclopedia"),
                     'article_ids': article_ids,
                     'entry': entry,
                     'search_results': search_results
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
        raise Http404 # no corresponding help page found, or no access permissions
    
    return render(request,
                  template_name,
                    {
                     'page_title': _("Manual Page"),
                     'entry': allowed_entry,
                    })
    


def _build_display_data_from_viewer_settings(viewer_settings):
    
    image_urls = []
    for level in range(viewer_settings["levels"]):
        level_urls = []
        for rel_index in range(viewer_settings["per_level"]*level, viewer_settings["per_level"]*(level + 1)):
            abs_index = viewer_settings["index_offset"] + rel_index * viewer_settings["index_steps"]
            rel_url = viewer_settings["file_template"] % abs_index
            level_urls.append(game_file_url(rel_url))
        if viewer_settings["autoreverse"]:
            level_urls = level_urls + list(reversed(level_urls))
        image_urls.append(level_urls)
        
    real_per_level = viewer_settings["per_level"] * (2 if viewer_settings["autoreverse"] else 1)
    assert set([len(imgs) for imgs in image_urls]) == set([real_per_level]) # all levels have the same number of images
    
    display_data = dict(levels=viewer_settings["levels"],
                            per_level=real_per_level,
                            x_coefficient=viewer_settings["x_coefficient"],
                            y_coefficient=viewer_settings["y_coefficient"],
                            rotomatic=viewer_settings["rotomatic"], # ms between rotations
                            image_width=viewer_settings["image_width"],
                            image_height=viewer_settings["image_height"],
                            start_level=viewer_settings["start_level"],
                            mode=viewer_settings["mode"],
                            image_urls=image_urls, # multi-level array
                            music_url=game_file_url(viewer_settings["music"]) if viewer_settings["music"] else None,)
    return display_data
    

@register_view(access=UserAccess.anonymous, always_available=True)
def logo_animation(request, template_name='utilities/item_3d_viewer.html'):
    """
    These settings are heavily dependant on values hard-coded on templates (dimensions, colors...),
    so they needn't be exposed inside the YAML configuration file
    """
    viewer_settings = dict( levels=1,
                            per_level=31, # real total of images : 157, but we use steps
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
                            rotomatic=150, # ms between rotations
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


@register_view(access=UserAccess.authenticated)
def view_characters(request, template_name='generic_operations/view_characters.html'):

    user = request.datamanager.user

    def refresh_gems_choice():
        # computing available gems
        if user.is_master:
            available_gems = []
            for character, properties in request.datamanager.get_character_sets().items():
                available_gems += properties["gems"]
        else:
            available_gems = request.datamanager.get_character_properties(user.username)["gems"]
        gems_choices = zip(available_gems, [_("Gem of %d Kashes") % available_gem for available_gem in available_gems])
        return gems_choices


    if request.method == "POST":
        if request.POST.get("money_transfer"):

            money_form = forms.MoneyTransferForm(request.datamanager, user, request.POST)
            if money_form.is_valid():

                if user.is_master:
                    sender = money_form.cleaned_data['sender_name']
                    if sender != request.datamanager.get_global_parameter("bank_name"):
                        sender = request.datamanager.get_username_from_official_name(sender)
                else:
                    sender = user.username

                recipient = money_form.cleaned_data['recipient_name']
                if recipient != request.datamanager.get_global_parameter("bank_name"):
                    recipient = request.datamanager.get_username_from_official_name(recipient)

                with action_failure_handler(request, _("Money transfer successful.")):
                    request.datamanager.transfer_money_between_characters(sender,
                                                                  recipient,
                                                                  money_form.cleaned_data['amount']) # amount can only be positive here
            else:
                user.add_error(_("Money transfer failed - invalid parameters."))


        elif request.POST.get("gems_transfer"):
            gems_choices = refresh_gems_choice()
            gems_form = forms.GemsTransferForm(request.datamanager, user, gems_choices, request.POST)
            if gems_form.is_valid():

                if user.is_master:
                    sender = request.datamanager.get_username_from_official_name(gems_form.cleaned_data['sender_name'])
                else:
                    sender = user.username

                with action_failure_handler(request, _("Gems transfer successful.")):
                    selected_gems = [int(gem) for gem in gems_form.cleaned_data['gems_choices']]
                    request.datamanager.transfer_gems_between_characters(sender,
                                                                  request.datamanager.get_username_from_official_name(gems_form.cleaned_data['recipient_name']),
                                                                  selected_gems)
            else:
                user.add_error(_("Gems transfer failed - invalid parameters."))



    ### IN ANY WAY WE RESET FORMS, BECAUSE CHARACTER SETTINGS MAY HAVE CHANGED ! ###

    # Preparing form for money transfer
    if user.is_master or request.datamanager.get_character_properties(user.username)["account"]:
        new_money_form = forms.MoneyTransferForm(request.datamanager, user)
    else:
        new_money_form = None

    # preparing gems transfer form
    gems_choices = refresh_gems_choice()
    if gems_choices:
        new_gems_form = forms.GemsTransferForm(request.datamanager, user, gems_choices)
    else:
        new_gems_form = None


    # we display the list of available character accounts

    characters = request.datamanager.get_character_sets().items()

    sorted_characters = sorted(characters, key=lambda (key, value): key) # sort by character name

    char_sets = [sorted_characters] # only one list for now...
    '''
    temp_set = []
    old_domain = None
    for key, value in sorted_characters:
        if old_domain is not None and value["domain"] != old_domain:
            char_sets.append(temp_set)
            temp_set = []
        temp_set.append((key, value))
        old_domain = value["domain"]
    if temp_set:
        char_sets.append(temp_set)
    '''

    if user.is_master:
        show_official_identities = True
    else:
        domain = request.datamanager.get_character_properties(user.username)["domains"][0]
        show_official_identities = request.datamanager.get_domain_properties(domain)["show_official_identities"]
    return render(request,
                  template_name,
                    {
                     'page_title': _("Account Management"),
                     'pangea_domain':request.datamanager.get_global_parameter("pangea_network_domain"),
                     'money_form': new_money_form,
                     'gems_form': new_gems_form,
                     'char_sets': char_sets,
                     'bank_data': (request.datamanager.get_global_parameter("bank_name"), request.datamanager.get_global_parameter("bank_account")),
                     'show_official_identities': show_official_identities,
                    })



@register_view(access=UserAccess.anonymous) # not always available
def items_slideshow(request, template_name='generic_operations/items_slideshow.html'):

    user = request.datamanager.user

    if user.is_authenticated:
        page_title = _("Team Items")
        items = request.datamanager.get_available_items_for_user(user.username)
        items_3D_settings = request.datamanager.get_items_3d_settings()
    else:
        page_title = _("Auction Items")
        items = request.datamanager.get_available_items_for_user(None) # all items
        items_3D_settings = {} # IMPORTANT - no access to 3D views here

    sorted_items = [(key, items[key]) for key in sorted(items.keys())]

    return render(request,
                  template_name,
                    {
                     'page_title': page_title,
                     'items': sorted_items,
                     'items_3D_settings': items_3D_settings
                    })


@register_view(access=UserAccess.authenticated) # not always available, so beware!! TODO FIXME ensure it's not displayed if not available!
def item_3d_view(request, item, template_name='utilities/item_3d_viewer.html'):

    user = request.datamanager.user

    available_items = request.datamanager.get_available_items_for_user(user.username)

    if item not in available_items.keys():
        raise Http404

    viewers_settings = request.datamanager.get_items_3d_settings()
    if item not in viewers_settings.keys():
        raise Http404

    viewer_settings = viewers_settings[item]

    return render(request,
                  template_name,
                    {
                     'settings': _build_display_data_from_viewer_settings(viewer_settings),
                    })




@register_view(access=UserAccess.authenticated)
def view_sales(request, template_name='generic_operations/view_sales.html'):

    user = request.datamanager.user

    if user.is_master:
        # we process sale management operations
        params = request.POST
        if "buy" in params and "character" in params and "object" in params:
            with action_failure_handler(request, _("Object successfully transferred to %s.") % params["character"]):
                request.datamanager.transfer_object_to_character(params["object"], request.datamanager.get_username_from_official_name(params["character"]))
        elif "unbuy" in params and "character" in params and "object" in params:
            with action_failure_handler(request, _("Sale successfully canceled for %s.") % params["character"]):
                request.datamanager.undo_object_transfer(params["object"], request.datamanager.get_username_from_official_name(params["character"]))


    # IMPORTANT - we copy, so that we can modify the object without changing DBs !
    items_for_sales = copy.deepcopy(request.datamanager.get_items_for_sale())

    # we inject the official name of object owner
    for item in items_for_sales.values():
        if item["owner"]:
            item["owner_official_name"] = request.datamanager.get_official_name_from_username(item["owner"])
        else:
            item["owner_official_name"] = None

    sorted_items_for_sale = items_for_sales.items()
    sorted_items_for_sale.sort(key=lambda x: x[1]['auction'])

    if user.is_master:
        total_items_price = sum(item["total_price"] for item in items_for_sales.values())
        total_cold_cash_available = sum(character["initial_cold_cash"] for character in request.datamanager.get_character_sets().values())
        total_bank_account_available = sum(character["account"] for character in request.datamanager.get_character_sets().values())
    else:
        total_items_price = None
        total_cold_cash_available = None
        total_bank_account_available = None

    total_gems_number = sum(item["num_items"] for item in items_for_sales.values() if item["is_gem"])
    total_archaeological_objects_number = sum(item["num_items"] for item in items_for_sales.values() if not item["is_gem"])

    return render(request,
                  template_name,
                    {
                     'page_title': _("Auction"),
                     'items_for_sale': sorted_items_for_sale,
                     'character_names': request.datamanager.get_character_official_names(),
                     'total_items_price': total_items_price,
                     'total_cold_cash_available': total_cold_cash_available,
                     'total_bank_account_available': total_bank_account_available,
                     'total_gems_number': total_gems_number,
                     'total_archaeological_objects_number': total_archaeological_objects_number
                    })
assert view_sales.NAME in GameDataManager.ACTIVABLE_VIEWS_REGISTRY.keys()


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
                request.datamanager.change_wiretapping_targets(user.username, targets)
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



@register_view(access=UserAccess.anonymous, always_available=True) # links in emails must NEVER be broken
def encrypted_folder(request, folder, entry_template_name="generic_operations/encryption_password.html", display_template_name='personal_folder.html'):

    if not request.datamanager.encrypted_folder_exists(folder):
        raise Http404

    user = request.datamanager.user
    files = []
    form = None

    if request.method == "POST":
        form = forms.SimplePasswordForm(request.POST)
        if form.is_valid():
            password = form.cleaned_data["simple_password"].lower() # normalized !

            with action_failure_handler(request, _("Folder decryption successful.")):
                files = request.datamanager.get_encrypted_files(user.username, folder, password, absolute_urls=False)
                form = None # triggers the display of files

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


    else: # necessarily, we've managed to decrypt the folder

        files_to_display = zip([os.path.basename(myfile) for myfile in files], files)

        if not files_to_display:
            user.add_message = _("No files were found in the folder.")


        return render(request,
                      display_template_name,
                        {
                            "page_title": _("Decrypted archive '%s'") % folder,
                            "files": files_to_display,
                            "display_maintenance_notice": False, # upload disabled notification
                        })



@register_view(access=UserAccess.authenticated, always_available=True)
def personal_folder(request, template_name='generic_operations/personal_folder.html'):

    user = request.datamanager.user

    try:

        personal_files = request.datamanager.get_personal_files(user.username if not user.is_master else None,
                                                                absolute_urls=False) # to allow easier stealing of files from Loyd's session

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
                        "display_maintenance_notice": True, # upload disabled notification
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

    events = request.datamanager.get_game_events() # keys : time, message, username

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

    trans_events = list(reversed(trans_events)) # most recent first

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
    
    audio_urls = "|".join([msg["url"] for msg in current_audio_messages]) # we expect no "|" inside a single url
    audio_titles = "|".join([msg["title"].replace("|", "") for msg in current_audio_messages]) # here we can cleanup
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
                audio_id = request.POST["audio_message_added"] # might raise KeyError
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
@register_view# (access=UserAccess.character)#(permission="contact_djinns")
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
            sentences.append(history[0][i]) # input
        if i < len(history[1]):
            sentences.append(history[1][i]) # output

    return render(request,
                  template_name,
                    {
                     'page_title': _("Djinn Communication"),
                     'bot_name': bot_name,
                     'history': sentences
                    })

 
@register_view(attach_to=chat_with_djinn) #access=UserAccess.character)(permission="contact_djinns")
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
@register_view#(access=UserAccess.character)#(permission="contact_djinns")
def contact_djinns(request, template_name='specific_operations/contact_djinns.html'):
    
    user = request.datamanager.user
    
    bots_properties = request.datamanager.get_bots_properties()

    if user.is_master: # FIXME
        available_bots = bots_properties.keys()
        team_gems = None
    else:
        domain = request.datamanager.get_character_properties(user.username)["domain"]
        available_bots = [bot_name for bot_name in bots_properties.keys() if request.datamanager.is_bot_accessible(bot_name, domain)]
        team_gems = request.datamanager.get_team_gems_count(domain)

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
                     'team_gems': team_gems,
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
                request.datamanager.pack_database(days=1) # safety measure - take at least one day of gap !

    formatted_data = request.datamanager.dump_zope_database()
  
    game_is_started = request.datamanager.is_game_started() # we refresh it
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
        form = forms.CharacterForm(data=request.POST,
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
        #print ("AZZZZ", form["target_username"].value(), username)
        if form and form["target_username"].value() == username:
            print (" REUSING FOR", username)
            f = form
        else:
            f = forms.CharacterForm(
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

    if user.is_master: # FIXME
        headers = "Username;Nickname;Official Identity;IRL Identity"
        lines = [";".join([K, V["official_name"], V["real_life_identity"]]) for (K, V) in char_sets]
    else:
        headers = "Nickname;Official Identity;IRL Identity"
        lines = [";".join([V["official_name"], V["real_life_identity"]]) for (K, V) in char_sets]

    body = "\n".join([headers] + lines).encode("latin-1")

    #body = chr(0xEF) + chr(0xBB) + chr(0xBF) + body # utf8 bom ?

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
        #return HttpResponse(repr(e))



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

 
