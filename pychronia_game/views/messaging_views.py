# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from pychronia_game.common import *
from pychronia_game.datamanager import AbstractGameView, register_view, VISIBILITY_REASONS, AbstractGameForm
from django import forms
from django.http import Http404, HttpResponseRedirect, HttpResponse
from pychronia_game.utilities.select2_extensions import Select2TagsField
from pychronia_game.templatetags.helpers import advanced_restructuredtext
from django.core.exceptions import ValidationError


"""
    categories = Select2TagsField(label=ugettext_lazy("Categories"), required=False)
    keywords = Select2TagsField(label=ugettext_lazy("Keywords"), required=False)

"""

class MessageComposeForm(AbstractGameForm):
    """
    A simple default form for private messages.
    """

    # origin = forms.CharField(required=False, widget=forms.HiddenInput) # the id of the message to which we replay, if any


    recipients = Select2TagsField(label=ugettext_lazy("Recipients"), required=True)

    subject = forms.CharField(label=ugettext_lazy("Subject"), widget=forms.TextInput(attrs={'size':'35'}), required=True)

    body = forms.CharField(label=ugettext_lazy("Body"), widget=forms.Textarea(attrs={'rows': '8', 'cols':'35'}), required=False)

    attachment = Select2TagsField(label=ugettext_lazy("Attachment"), required=False)


    transferred_msg = forms.CharField(required=False, widget=forms.HiddenInput())

    parent_id = forms.CharField(required=False, widget=forms.HiddenInput())



    def __init__(self, request, *args, **kwargs):
        super(MessageComposeForm, self).__init__(request.datamanager, *args, **kwargs)

        url_data = request.GET

        # we initialize data with the querydict
        sender = url_data.get("sender")

        recipients = url_data.getlist("recipients") or ([url_data["recipient"]] if url_data.get("recipient") else [])
        assert isinstance(recipients, list)

        subject = url_data.get("subject")
        body = url_data.get("body")
        attachment = url_data.get("attachment")
        transferred_msg = url_data.get("transferred_msg", "")
        parent_id = url_data.get("parent_id", "")

        datamanager = request.datamanager
        user = request.datamanager.user

        # TODO - extract these decisions tables to a separate method and test it thoroughly #


        if user.is_master: # only master has templates ATM

            use_template = url_data.get("use_template", "")
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
                    transferred_msg = tpl["transferred_msg"] or transferred_msg
                    parent_id = tpl["parent_id"] or parent_id
            self.fields["use_template"] = forms.CharField(required=False, initial=(use_template or None), widget=forms.HiddenInput())


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
                    subject = _("Bis:") + " " + msg["subject"]
                    # don't resend attachment! #

                elif visibility_reason == VISIBILITY_REASONS.recipient: # we reply to a message
                    sender = msg["recipient_emails"][0] if len(msg["recipient_emails"]) == 1 else None # let the sender empty even for master, if we're not sure which recipient we represent
                    recipients = [msg["sender_email"]]
                    my_email = datamanager.get_character_email() if user.is_character else None
                    recipients += [_email for _email in msg["recipient_emails"] if _email != my_email and _email != sender]  # works OK if my_email is None (i.e game master) or sender is None
                    subject = _("Re:") + " " + msg["subject"]
                    attachment = msg["attachment"]

                else: # visibility reason is None, or another visibility case (eg. interception)
                    self.logger.warning("Access to forbidden message parent_id %s was attempted", parent_id)
                    user.add_error(_("Access to initial message forbidden."))
                    parent_id = None


        if transferred_msg:
            try:
                datamanager.get_dispatched_message_by_id(transferred_msg)
            except UsageError:
                datamanager.logger.warning("Unknown transferred_msg id %r encountered in url", transferred_msg)
                transferred_msg = ""


        # we build dynamic fields from the data we gathered #

        if user.is_master:

            sender = Select2TagsField(label=ugettext_lazy("Sender"), required=True, initial=([sender] if sender else [])) # initial MUST be a 1-item list!
            master_emails = datamanager.global_contacts.keys() + datamanager.get_character_emails(is_npc=True) # PLAYERS EMAILS are not included!
            sender.choice_tags = datamanager.sort_email_addresses_list(master_emails)
            assert sender.max_selection_size is not None
            sender.max_selection_size = 1
            self.fields.insert(0, "sender", sender)

            ''' OBSOLETE CHOCIE FIELD
            _delay_values_minutes = [unicode(value) for value in [0, 5, 10, 15, 30, 45, 60, 120, 720, 1440]]
            _delay_values_minutes_labels = [_("%s minutes") % value for value in _delay_values_minutes]
            _delay_values_minutes_choices = zip(_delay_values_minutes, _delay_values_minutes_labels)
            self.fields.insert(2, "delay_mn", forms.ChoiceField(label=_("Sending delay"), choices=_delay_values_minutes_choices, initial="0"))
            '''
            self.fields.insert(2, "delay_h", forms.FloatField(label=_("Sending delay in hours (eg. 2.4)"), initial=0))

        else:
            pass # no sender or delay_mn fields!


        available_recipients = datamanager.get_sorted_user_contacts()  # current username should not be "anonymous", since it's used only in member areas !
        self.fields["recipients"].initial = recipients
        self.fields["recipients"].choice_tags = available_recipients

        self.fields["subject"].initial = subject
        self.fields["body"].initial = body

        self.fields["attachment"].initial = [attachment] if attachment else None # BEWARE HERE, a list!!
        self.fields["attachment"].choice_tags = datamanager.get_personal_files(absolute_urls=False)
        self.fields["attachment"].max_selection_size = 1

        self.fields["parent_id"].initial = parent_id
        self.fields["transferred_msg"].initial = transferred_msg


    def _ensure_no_placeholder_left(self, value):
        if re.search(r"{{\s*[\w ]+\s*}}", value, re.IGNORECASE | re.UNICODE):
            raise ValidationError(_("Placeholder remaining in text"))

    def clean_subject(self):
        data = self.cleaned_data['subject']
        self._ensure_no_placeholder_left(data)
        return data

    def clean_body(self):
        data = self.cleaned_data['body']
        self._ensure_no_placeholder_left(data)
        return data

    def clean_sender(self):
        # called only for master
        data = self.cleaned_data['sender']
        return data[0] # MUST exist if we're here


    def clean_attachment(self):
        data = self.cleaned_data['attachment']
        return data[0] if data else None # MUST exist if we're here


    def clean_transferred_msg(self):
        transferred_msg = self.cleaned_data['transferred_msg']
        if transferred_msg:
            try:
                self._datamanager.get_dispatched_message_by_id(msg_id=transferred_msg)
            except UsageError:
                # really abnormal, since __init__ should have filtered out that hidden fields value at the beginning of process
                self._datamanager.logger.critical("Unknown transferred_msg id %r encountered in post data", transferred_msg)
                transferred_msg = None
        return transferred_msg or None




def _determine_template_display_context(datamanager, template_id, template):
    """
    Only used for message templates, not real ones.
    """
    assert datamanager.is_master()
    return dict(
                template_id=template_id, # allow use as template
                is_used=template["is_used"],
                has_read=None, # no buttons at all for that
                visibility_reason=None,
                was_intercepted=False,
                can_transfer=False,
                can_reply=False,
                can_recontact=False,
                can_force_sending=False,
                can_permanently_delete=False,
                )


def _determine_message_display_context(datamanager, msg, is_pending):
    """
    Useful for both pending and dispatched messages.
    """
    assert msg
    assert datamanager.is_authenticated()
    username = datamanager.user.username
    visibility_reason = msg["visible_by"].get(username, None) # one of VISIBILITY_REASONS, or None

    return dict(
                template_id=None,
                is_used=None, # for templates only
                has_read=(username in msg["has_read"]) if not is_pending else None,
                visibility_reason=visibility_reason,
                was_intercepted=(datamanager.is_master() and VISIBILITY_REASONS.interceptor in msg["visible_by"].values()),
                can_reply=(visibility_reason == VISIBILITY_REASONS.recipient) if not is_pending else None,
                can_recontact=(visibility_reason == VISIBILITY_REASONS.sender) if not is_pending else None,
                can_force_sending=is_pending,
                can_permanently_delete=datamanager.is_master(),
                can_transfer=True if not is_pending else None,
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


def _build_contact_display_cache(datamanager):
    all_contacts = datamanager.get_all_contacts_unsorted()
    return datamanager.get_contacts_display_properties(all_contacts, as_dict=True)



@register_view(access=UserAccess.master, title=ugettext_lazy("Dispatched Messages"))
def all_dispatched_messages(request, template_name='messaging/messages.html'):
    messages = list(reversed(request.datamanager.get_all_dispatched_messages()))
    enriched_messages = _determine_message_list_display_context(request.datamanager, messages=messages, is_pending=False)
    return render(request,
                  template_name,
                  dict(page_title=_("All Dispatched Messages"),
                       messages=enriched_messages,
                       contact_cache=_build_contact_display_cache(request.datamanager)))


@register_view(access=UserAccess.master, title=ugettext_lazy("Pending Messages"))
def all_queued_messages(request, template_name='messaging/messages.html'):
    messages = list(reversed(request.datamanager.get_all_queued_messages()))
    enriched_messages = _determine_message_list_display_context(request.datamanager, messages=messages, is_pending=True)
    return render(request,
                  template_name,
                  dict(page_title=_("All Queued Messages"),
                       messages=enriched_messages,
                       contact_cache=_build_contact_display_cache(request.datamanager)))

@register_view(attach_to=all_queued_messages, title=ugettext_lazy("Force Message Sending"))
def ajax_force_email_sending(request):
    # to be used by AJAX
    msg_id = request.REQUEST.get("id", None)

    # this should never fail, even is msg doesn't exist or is already transferred
    request.datamanager.force_message_sending(msg_id)

    return HttpResponse("OK")
    # in case of error, a "500" code will be returned



@register_view(access=UserAccess.master, title=ugettext_lazy("Message Templates"))
def messages_templates(request, template_name='messaging/messages.html'):
    templates = request.datamanager.get_messages_templates().items() # PAIRS (template_id, template_dict)
    templates.sort(key=lambda msg: msg[0])  # we sort by template name
    enriched_templates = [(_determine_template_display_context(request.datamanager, template_id=tpl[0], template=tpl[1]), tpl[1]) for tpl in templates]
    return render(request,
                  template_name,
                  dict(messages=enriched_templates,
                       contact_cache=_build_contact_display_cache(request.datamanager)))


@register_view(access=UserAccess.authenticated, requires_global_permission=False, title=ugettext_lazy("Conversations"))
def conversation(request, template_name='messaging/conversation.html'):

    CONVERSATIONS_LIMIT = 15

    display_all_conversations = bool(request.GET.get("display_all", None) == "1")

    messages = request.datamanager.get_user_related_messages() # for current master or character
    _grouped_messages = request.datamanager.sort_messages_by_conversations(messages)
    enriched_messages = _determine_message_list_display_context(request.datamanager, messages=_grouped_messages, is_pending=False)
    del _grouped_messages

    if len(enriched_messages) <= CONVERSATIONS_LIMIT:
        display_all_conversations = True # it makes no sense to "limit" then...

    if not display_all_conversations:
        enriched_messages = enriched_messages[0:CONVERSATIONS_LIMIT] # we arbitrarily limit to 15 recent conversations

    dm = request.datamanager
    if dm.is_game_writable() and dm.is_character():
        dm.set_new_message_notification(concerned_characters=[dm.username], new_status=False)

    return render(request,
                  template_name,
                  dict(page_title=_("All Conversations") if display_all_conversations else _("Recent Conversations"),
                       display_all_conversations=display_all_conversations,
                       conversations=enriched_messages,
                       contact_cache=_build_contact_display_cache(request.datamanager)))
                       


@register_view(attach_to=conversation, title=ugettext_lazy("Set Message Read State"))
def ajax_set_message_read_state(request):
    # to be used by AJAX
    msg_id = request.REQUEST.get("id", None)
    is_read = request.REQUEST.get("is_read", None) == "1"

    request.datamanager.set_message_read_state(msg_id=msg_id, is_read=is_read)

    return HttpResponse("OK")
    # in case of error, a "500" code will be returned


@register_view(access=UserAccess.master, requires_global_permission=False, title=ugettext_lazy("Delete Message"))
def ajax_permanently_delete_message(request):
    # to be used by AJAX
    msg_id = request.REQUEST.get("id", None)

    request.datamanager.permanently_delete_message(msg_id=msg_id) # should never fail

    return HttpResponse("OK")
    # in case of error, a "500" code will be returned



@register_view(attach_to=conversation, title=ugettext_lazy("Compose Message"))
def compose_message(request, template_name='messaging/compose.html'):

    user = request.datamanager.user
    message_sent = False
    form = None

    if request.method == "POST":
        form = MessageComposeForm(request, data=request.POST)
        if form.is_valid():

            with action_failure_handler(request, _("Message successfully sent.")):

                if user.is_master:
                    sender_email = form.cleaned_data["sender"]
                    delay_h = form.cleaned_data["delay_h"]
                    assert isinstance(delay_h, float)
                else:
                    sender_email = request.datamanager.get_character_email()
                    delay_h = 0
                sending_date = datetime.utcnow() + timedelta(hours=delay_h)
                assert isinstance(sending_date, datetime)
                del delay_h

                # we parse the list of emails
                recipient_emails = form.cleaned_data["recipients"]

                subject = form.cleaned_data["subject"]
                body = form.cleaned_data["body"]
                attachment = form.cleaned_data["attachment"]
                transferred_msg = form.cleaned_data["transferred_msg"]

                parent_id = form.cleaned_data.get("parent_id", None)
                use_template = form.cleaned_data.get("use_template", None)

                # sender_email and one of the recipient_emails can be the same email, we don't care !
                request.datamanager.post_message(sender_email, recipient_emails, subject, body,
                                                 attachment=attachment, transferred_msg=transferred_msg,
                                                 date_or_delay_mn=sending_date,
                                                 parent_id=parent_id, use_template=use_template)
                message_sent = True
                form = MessageComposeForm(request)  # new empty form
        else:
            user.add_error(_("Errors in message fields."))
    else:
        form = MessageComposeForm(request)

    user_contacts = request.datamanager.get_sorted_user_contacts() # properly SORTED list
    contacts_display = request.datamanager.get_contacts_display_properties(user_contacts) # DICT FIELDS: address avatar description

    return render(request,
                  template_name,
                    {
                     'page_title': _("Compose Message"),
                     'message_form': form,
                     'mode': "compose", # TODO DELETE THIS
                     'contacts_display': contacts_display,
                     'message_sent': message_sent, # to destroy saved content
                    })


'''
@register_view(access=UserAccess.authenticated, title=ugettext_lazy("ssss"))
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


@register_view(access=UserAccess.authenticated, title=ugettext_lazy("ddd"))
def ___outbox(request, template_name='messaging/messages.html'):

    user = request.datamanager.user
    if user.is_master:
        all_messages = request.datamanager.get_all_dispatched_messages()
        address_book = request.datamanager.get_external_emails()  # we list only messages sent by external contacts, not robots
        messages = [message for message in all_messages if message["sender_email"] in address_book]
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
'''


@register_view(access=UserAccess.anonymous, requires_global_permission=False, title=ugettext_lazy("View Single Message"))
def view_single_message(request, msg_id, template_name='messaging/view_single_message.html'):
    """
    Meant to be used in event logging or for message transfer.
    
    On purpose, NO AUTHORIZATION CHECK is done here (msg_ids are random enough).
    """
    user = request.datamanager.user
    message = None
    ctx = None
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

    if message:
        ctx = _determine_message_display_context(request.datamanager, message, is_pending=is_queued)

    return render(request,
                  template_name,
                    {
                     'page_title': _("Single Message"),
                     'is_queued': is_queued,
                     'ctx': ctx,
                     'message': message,
                     'contact_cache': _build_contact_display_cache(request.datamanager),
                    })


@register_view(access=UserAccess.anonymous, requires_global_permission=False, title=ugettext_lazy("Message Preview"))
def preview_message(request):

    rst = request.REQUEST.get("content", _("No content submitted for display")) # we take from both GET and POST

    html = advanced_restructuredtext(rst, initial_header_level=2, report_level=1).strip() # we let ALL debug output here!!

    return HttpResponse(html) # only a snippet of html, no html/head/body tags - might be EMPTY

'''
@register_view(access=UserAccess.authenticated, title=ugettext_lazy("sssss"))
def ___intercepted_messages(request, template_name='messaging/messages.html'):

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

'''

