# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *
from rpgweb.datamanager.abstract_game_view import AbstractGameView, register_view
from rpgweb import forms
from django.http import Http404, HttpResponseRedirect, HttpResponse


@register_view(access=UserAccess.master)
def ajax_force_email_sending(request):
    # to be used by AJAX
    msg_id = request.GET.get("id", None)

    # this should never fail, even is msg doesn't exist or is already transferred
    request.datamanager.force_message_sending(msg_id)

    return HttpResponse("OK")
    # in case of error, a "500" code will be returned



@register_view(access=UserAccess.authenticated, always_available=True)
def conversation(request):

    mode = "conversation"
    user = request.datamanager.user

    messages = request.datamanager.get_user_related_messages(user.username) # master or character

    group_ids = map(lambda message: message.get("group_id", ""), messages)
    group_ids = list(set(group_ids))
    grouped_messages = []

    group_id = message = None
    for group_id in group_ids:
        unordered_messages = [message for message in messages if message.get("group_id", "") == group_id]
        ordered_messsages = list(reversed(unordered_messages))
        grouped_messages.append(ordered_messsages)
    del group_id, message # shall not leak

    return render(request, 'messaging/conversation.html', locals())




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
                    sender_email = request.datamanager.get_character_email()
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
def ___inbox(request, template_name='messaging/messages.html'):

    user = request.datamanager.user
    if user.is_master:
        # We retrieve ALL emails that others won't read !!
        messages = request.datamanager.get_game_master_messages()
        remove_to = False

    else:
        messages = request.datamanager.pop_received_messages(request.datamanager.get_character_email())
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


@register_view(attach_to=conversation)
def ajax_set_message_read_state(request):

    # to be used by AJAX
    msg_id = request.GET.get("id", None)
    is_read = request.GET.get("is_read", None) == "1"

    user = request.datamanager.user
    request.datamanager.set_message_read_state(msg_id=msg_id, is_read=is_read)

    return HttpResponse("OK")
    # in case of error, a "500" code will be returned



@register_view(access=UserAccess.authenticated)
def ___outbox(request, template_name='messaging/messages.html'):

    user = request.datamanager.user
    if user.is_master:
        all_messages = request.datamanager.get_all_dispatched_messages()
        external_contacts = request.datamanager.get_external_emails()  # we list only messages sent by external contacts, not robots
        messages = [message for message in all_messages if message["sender_email"] in external_contacts]
        remove_from = False
    else:
        messages = request.datamanager.get_sent_messages(request.datamanager.get_character_email())
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

    messages = [msg for msg in request.datamanager.get_all_dispatched_messages() if msg["id"] == msg_id]
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
def all_dispatched_messages(request, template_name='messaging/messages.html'):

    messages = request.datamanager.get_all_dispatched_messages()

    messages = list(reversed(messages))  # most recent first

    return render(request,
                  template_name,
                    {
                     'page_title': _("All Transferred Messages"),
                     'messages': messages,
                     'remove_from': False,
                     'remove_to': False,
                     'mode': "all_sent_messages" # FIXME
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

    messages = request.datamanager.get_intercepted_messages()

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
