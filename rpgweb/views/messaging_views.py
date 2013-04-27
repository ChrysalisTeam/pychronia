# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *
from rpgweb.datamanager import AbstractGameView, register_view, VISIBILITY_REASONS, AbstractGameForm
from django import forms
from django.http import Http404, HttpResponseRedirect, HttpResponse
from rpgweb.utilities.select2_extensions import Select2TagsField
from rpgweb.templatetags.helpers import advanced_restructuredtext


"""
    categories = Select2TagsField(label=_lazy("Categories"), required=False)
    keywords = Select2TagsField(label=_lazy("Keywords"), required=False)

"""

class MessageComposeForm(AbstractGameForm):
    """
    A simple default form for private messages.
    """

    # origin = forms.CharField(required=False, widget=forms.HiddenInput) # the id of the message to which we replay, if any


    recipients = Select2TagsField(label=_lazy("Recipients"), required=True)

    subject = forms.CharField(label=_lazy("Subject"), widget=forms.TextInput(attrs={'size':'35'}), required=True)

    body = forms.CharField(label=_lazy("Body"), widget=forms.Textarea(attrs={'rows': '8', 'cols':'35'}), required=False)

    attachment = Select2TagsField(label=_lazy("Attachment"), required=False)



    def __init__(self, request, *args, **kwargs):
        super(MessageComposeForm, self).__init__(request.datamanager, *args, **kwargs)

        url_data = request.GET

        # we initialize data with the querydict
        sender = url_data.get("sender")
        recipients = url_data.getlist("recipients") or url_data.get("recipient")
        subject = url_data.get("subject")
        body = url_data.get("body")
        attachment = url_data.get("attachment")

        datamanager = request.datamanager
        user = request.datamanager.user

        # TODO - extract these decisions tables to a separate method and test it thoroughly #

        parent_id = url_data.get("parent_id", "")
        if parent_id:
            # we transfer data from the parent email, to help user save time #
            try:
                tpl = msg = request.datamanager.get_dispatched_message_by_id(parent_id)
            except UsageError:
                user.add_error(_("Parent message %s not found") % parent_id)
            else:

                visibility_reason = msg["visible_by"].get(user.username, None)

                if visibility_reason == VISIBILITY_REASONS.sender: # we simply recontact recipients (even if we were one of the recipients too)
                    sender = msg["sender_email"] # for master
                    recipients = msg["recipient_emails"]
                    subject = _("Bis: ") + msg["subject"]
                    attachment = None # don't resend it

                elif visibility_reason == VISIBILITY_REASONS.recipient: # we reply a message
                    sender = msg["recipient_emails"][0] if len(msg["recipient_emails"]) == 1 else None # let the sender empty even for master, if we're not sure which recipient we represent
                    recipients = [msg["sender_email"]]
                    my_email = datamanager.get_character_email() if user.is_character else None
                    recipients += [_email for _email in msg["recipient_emails"] if _email != my_email and _email != sender]  # works OK if my_email is None (i.e game master) or sender is None
                    subject = _("Re: ") + msg["subject"]
                    attachment = msg["attachment"]

                else: # visibility reason is None, or another visibility case (eg. interception)
                    self.logger.warning("Access to forbidden message parent_id %s was attempted", parent_id)
                    user.add_error(_("Access to initial message forbidden."))
                    parent_id = None
        self.fields["parent_id"] = forms.CharField(required=False, initial=parent_id, widget=forms.HiddenInput())


        use_template = url_data.get("use_template", "")
        if user.is_master: # only master has templates ATM

            if use_template:

                # non-empty template fields override parent message fields #

                try:
                    tpl = datamanager.get_message_template(use_template)
                except UsageError:
                    user.add_error(_("Message template %s not found") % use_template)
                else:
                    sender = tpl["sender_email"] or sender
                    recipients = tpl["recipient_emails"] or recipients
                    subject = tpl["subject"] or subject
                    body = tpl["body"] or body
                    attachment = tpl["attachment"] or attachment
        self.fields["use_template"] = forms.CharField(required=False, initial=use_template, widget=forms.HiddenInput())


        # we build dynamic fields from the data we gathered #

        if user.is_master:

            sender = Select2TagsField(label=_lazy("Sender"), required=True, initial=([sender] if sender else [])) # initial MUST be a 1-item list!
            sender.choice_tags = datamanager.global_contacts.keys()
            assert sender.max_selection_size is not None
            sender.max_selection_size = 1
            self.fields.insert(0, "sender", sender)

            _delay_values_minutes = [unicode(value) for value in [0, 5, 10, 15, 30, 45, 60, 120, 720, 1440]]
            _delay_values_minutes_labels = [_("%s minutes") % value for value in _delay_values_minutes]
            _delay_values_minutes_choices = zip(_delay_values_minutes, _delay_values_minutes_labels)
            self.fields.insert(2, "delay_mn", forms.ChoiceField(label=_("Sending delay"), choices=_delay_values_minutes_choices, initial="0"))

        else:
            pass # no sender or delay_mn fields!


        available_recipients = datamanager.get_user_contacts()  # current username should not be "anonymous", since it's used only in member areas !
        self.fields["recipients"].initial = recipients
        self.fields["recipients"].choice_tags = available_recipients

        self.fields["subject"].initial = subject
        self.fields["body"].initial = body

        self.fields["attachment"].initial = attachment
        self.fields["attachment"].choice_tags = datamanager.get_personal_files(absolute_urls=False)
        self.fields["attachment"].max_selection_size = 1

    def clean_sender(self):
        # called only for master
        data = self.cleaned_data['sender']
        return data[0] # MUST exist if we're here

    def clean_attachment(self):
        data = self.cleaned_data['attachment']
        return data[0] if data else None # MUST exist if we're here











def _determine_template_display_context(datamanager, template_id):
    """
    Only used for message templates, not real ones.
    """
    assert datamanager.is_master()
    return dict(
                template_id=template_id, # allow use as template
                has_read=None, # no buttons at all for that
                visibility_reason=None,
                was_intercepted=False,
                can_reply=False,
                can_recontact=False,
                can_force_sending=False,
                can_permanently_delete=False,
                )


def _determine_message_display_context(datamanager, msg, is_pending):
    """
    Useful for both pending and dispatched messages.
    """
    assert datamanager.is_authenticated()
    username = datamanager.user.username
    visibility_reason = msg["visible_by"].get(username, None) # one of VISIBILITY_REASONS, or None

    return dict(
                template_id=None,
                has_read=(username in msg["has_read"]) if not is_pending else None,
                visibility_reason=visibility_reason,
                was_intercepted=(datamanager.is_master() and VISIBILITY_REASONS.interceptor in msg["visible_by"].values()),
                can_reply=(visibility_reason == VISIBILITY_REASONS.recipient) if not is_pending else None,
                can_recontact=(visibility_reason == VISIBILITY_REASONS.sender) if not is_pending else None,
                can_force_sending=is_pending,
                can_permanently_delete=datamanager.is_master(),
                )

def _determine_message_list_display_context(datamanager, messages, is_pending):
    """
    Works for both conversations and simple message lists.
    """
    if not messages:
        res = []
    elif isinstance(messages[0], (list, tuple)):
        res = [[(_determine_message_display_context(datamanager, msg, is_pending=is_pending), msg) for msg in msg_list] for msg_list in messages] # conversations
    else:
        res = [(_determine_message_display_context(datamanager, msg, is_pending=is_pending), msg) for msg in messages]
    return res







@register_view(access=UserAccess.master, title=_lazy("Dispatched Messages"))
def all_dispatched_messages(request, template_name='messaging/messages.html'):
    messages = list(reversed(request.datamanager.get_all_dispatched_messages()))
    enriched_messages = _determine_message_list_display_context(request.datamanager, messages=messages, is_pending=False)
    return render(request,
                  template_name,
                  dict(page_title=_("All Transferred Messages"),
                       messages=enriched_messages))


@register_view(access=UserAccess.master, title=_lazy("Pending Messages"))
def all_queued_messages(request, template_name='messaging/messages.html'):
    messages = list(reversed(request.datamanager.get_all_queued_messages()))
    enriched_messages = _determine_message_list_display_context(request.datamanager, messages=messages, is_pending=True)
    return render(request,
                  template_name,
                  dict(page_title=_("All Queued Messages"),
                       messages=enriched_messages))

@register_view(attach_to=all_queued_messages, title=_lazy("Force Message Sending"))
def ajax_force_email_sending(request):
    # to be used by AJAX
    msg_id = request.REQUEST.get("id", None)

    # this should never fail, even is msg doesn't exist or is already transferred
    request.datamanager.force_message_sending(msg_id)

    return HttpResponse("OK")
    # in case of error, a "500" code will be returned



@register_view(access=UserAccess.master, title=_lazy("Message Templates"))
def messages_templates(request, template_name='messaging/messages.html'):
    templates = request.datamanager.get_messages_templates().items() # PAIRS (template_id, template_dict)
    templates.sort(key=lambda msg: msg[0])  # we sort by template name
    enriched_templates = [(_determine_template_display_context(request.datamanager, template_id=tpl[0]), tpl[1]) for tpl in templates]
    return render(request,
                  template_name,
                  dict(page_title=_("Message Templates"),
                       messages=enriched_templates))


@register_view(access=UserAccess.authenticated, always_available=True, title=_lazy("Conversations"))
def conversation(request, template_name='messaging/conversation.html'):
    messages = request.datamanager.get_user_related_messages() # for current master or character
    grouped_messages = request.datamanager.sort_messages_by_conversations(messages)
    enriched_messages = _determine_message_list_display_context(request.datamanager, messages=grouped_messages, is_pending=False)

    dm = request.datamanager
    if dm.is_game_writable() and dm.is_character():
        dm.set_new_message_notification(concerned_characters=[dm.username], new_status=False)

    return render(request,
                  template_name,
                  dict(page_title=_("Conversations"),
                       conversations=enriched_messages))

@register_view(attach_to=conversation, title=_lazy("Set Message Read State"))
def ajax_set_message_read_state(request):
    # to be used by AJAX
    msg_id = request.REQUEST.get("id", None)
    is_read = request.REQUEST.get("is_read", None) == "1"

    request.datamanager.set_message_read_state(msg_id=msg_id, is_read=is_read)

    return HttpResponse("OK")
    # in case of error, a "500" code will be returned


@register_view(access=UserAccess.master, always_available=True, title=_lazy("Delete Message"))
def ajax_permanently_delete_message(request):
    # to be used by AJAX
    msg_id = request.REQUEST.get("id", None)

    request.datamanager.permanently_delete_message(msg_id=msg_id) # should never fail

    return HttpResponse("OK")
    # in case of error, a "500" code will be returned



@register_view(attach_to=conversation, title=_lazy("Compose Message"))
def compose_message(request, template_name='messaging/compose.html'):

    user = request.datamanager.user
    form = None
    if request.method == "POST":
        form = MessageComposeForm(request, data=request.POST)
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

                form = MessageComposeForm(request)  # new empty form
        else:
            user.add_error(_("Errors in message fields."))
    else:
        form = MessageComposeForm(request)

    return render(request,
                  template_name,
                    {
                     'page_title': _("Compose Message"),
                     'message_form': form,
                     'mode': "compose"
                    })



@register_view(access=UserAccess.authenticated, title=_lazy("ssss"))
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


@register_view(access=UserAccess.authenticated, title=_lazy("ddd"))
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

@register_view(access=UserAccess.master, title=_lazy("View Single Message"))
def view_single_message(request, msg_id, template_name='messaging/view_single_message.html'):
    """
    Meant to be used only in event logging.
    """
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
                     'ctx': _determine_message_display_context(request.datamanager, message, is_pending=is_queued),
                     'message': message
                    })


@register_view(access=UserAccess.anonymous, always_available=True, title=_lazy("Message Preview"))
def preview_message(request):

    rst = request.REQUEST.get("content", _("No content submitted for display")) # we take from both GET and POST

    html = advanced_restructuredtext(rst, initial_header_level=2, report_level=1).strip() # we let ALL debug output here!!

    return HttpResponse(html) # only a snippet of html, no html/head/body tags - might be EMPTY


@register_view(access=UserAccess.authenticated, title=_lazy("sssss"))
def __intercepted_messages(request, template_name='messaging/messages.html'):

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



