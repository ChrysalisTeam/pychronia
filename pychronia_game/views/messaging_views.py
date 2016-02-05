# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

import urllib
from pprint import pprint

from pychronia_game.common import *
from pychronia_game.datamanager import AbstractGameView, register_view, VISIBILITY_REASONS, AbstractGameForm
from django import forms
from django.http import Http404, HttpResponseRedirect, HttpResponse
from pychronia_game.utilities.select2_extensions import Select2TagsField
from django.core.exceptions import ValidationError
from pychronia_game.templatetags.helpers import format_enriched_text
from pychronia_game import utilities



"""
    categories = Select2TagsField(label=ugettext_lazy("Categories"), required=False)
    keywords = Select2TagsField(label=ugettext_lazy("Keywords"), required=False)

"""

class MessageComposeForm(AbstractGameForm):
    """
    A form for text-based messages.
    """

    # origin = forms.CharField(required=False, widget=forms.HiddenInput) # the id of the message to which we replay, if any   #FIXME, still valid name???


    recipients = Select2TagsField(label=ugettext_lazy("Recipients"), required=True)

    mask_recipients = forms.BooleanField(label=ugettext_lazy("Mask recipients"), initial=False, required=False)

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
        mask_recipients = (url_data.get("mask_recipients", "") == "1")

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
                    mask_recipients = tpl["mask_recipients"]
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

                subject = msg["subject"]  # always retrieved here (but might be prefixed)

                if visibility_reason == VISIBILITY_REASONS.sender: # we simply recontact recipients (even if we were one of the recipients too)
                    if user.is_master:
                        sender = msg["sender_email"] # for master
                    recipients = msg["recipient_emails"]  # even if "mask_recipients" is activated, since we're the sender

                    if _("Bis:") not in msg["subject"]:
                        subject = _("Bis:") + " " + subject
                    # don't resend attachment! #

                elif visibility_reason == VISIBILITY_REASONS.recipient: # we reply to a message
                    if user.is_master:
                        sender = msg["recipient_emails"][0] if len(msg["recipient_emails"]) == 1 else None # let the sender empty for master, if we're not sure which recipient we represent
                    recipients = [msg["sender_email"]]
                    if user.is_master or not msg["mask_recipients"]:  # IMPORTANT - else spoilers!!
                        my_email = datamanager.get_character_email() if user.is_character else None
                        # works OK if my_email is None (i.e game master) or sender is None
                        recipients += [_email for _email in msg["recipient_emails"] if _email != my_email and _email != sender]
                    if _("Re:") not in msg["subject"]:
                        subject = _("Re:") + " " + subject
                    # don't resend attachment, here too! #

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

        default_use_restructuredtext = user.is_master  # by default, players use raw text
        self.fields = utilities.add_to_ordered_dict(self.fields, 2, "use_restructuredtext", forms.BooleanField(label=ugettext_lazy("Use markup language (RestructuredText)"), initial=default_use_restructuredtext, required=False))

        if user.is_master:

            sender = Select2TagsField(label=ugettext_lazy("Sender"), required=True, initial=([sender] if sender else [])) # initial MUST be a 1-item list!
            master_emails = datamanager.global_contacts.keys() + datamanager.get_character_emails(is_npc=True) # PLAYERS EMAILS are not included!
            sender.choice_tags = datamanager.sort_email_addresses_list(master_emails)
            assert sender.max_selection_size is not None
            sender.max_selection_size = 1
            self.fields = utilities.add_to_ordered_dict(self.fields, 0, "sender", sender)

            ''' OBSOLETE CHOCIE FIELD
            _delay_values_minutes = [unicode(value) for value in [0, 5, 10, 15, 30, 45, 60, 120, 720, 1440]]
            _delay_values_minutes_labels = [_("%s minutes") % value for value in _delay_values_minutes]
            _delay_values_minutes_choices = zip(_delay_values_minutes, _delay_values_minutes_labels)
           self.fields = add_to_ordered_dict(self.fields, 2, "delay_mn", forms.ChoiceField(label=_("Sending delay"), choices=_delay_values_minutes_choices, initial="0"))
            '''
            self.fields = utilities.add_to_ordered_dict(self.fields, 2, "delay_h", forms.FloatField(label=_("Sending delay in hours (eg. 2.4)"), initial=0))

        else:
            pass # no sender or delay_mn fields!

        available_recipients = datamanager.get_sorted_user_contacts()  # current username should not be "anonymous", since it's used only in member areas !
        self.fields["recipients"].initial = list(recipients)  # prevents ZODB types...
        self.fields["recipients"].choice_tags = available_recipients

        self.fields["mask_recipients"].initial = mask_recipients

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


def _check_message_display_context(ctx, msg):
    assert ctx["display_id"]
    for k, v in ctx.items():
        if "can_" in k and v:
            assert msg.get("id")  # neeeded for message controls


def _determine_template_display_context(datamanager, template_id, template):
    """
    Only used for message templates, not real ones.
    """
    assert datamanager.is_master()
    ctx = dict(
                template_id=template_id, # allow use as template
                is_used=template["is_used"],
                is_ignored=template["is_ignored"],
                has_read=None, # no buttons at all for that
                visibility_reason=None,
                intercepted_by=None,
                can_transfer=False,
                has_starred=None,  # useless for now
                has_archived=None,
                can_reply=False,
                can_recontact=False,
                can_force_sending=False,
                can_permanently_delete=False,
                display_id=template_id, # USED IN UI controls!
                force_recipients_display=False, # useless, since we're MASTER here...
                )
    _check_message_display_context(ctx, msg=template)
    return ctx

def _determine_message_display_context(datamanager, msg, is_pending):
    """
    Useful for both pending and dispatched messages.
    
    If "is_pending" is True, this means the message is queued for sending.
    """
    assert msg
    assert msg["id"]
    assert datamanager.is_authenticated()
    username = datamanager.user.username
    visibility_reason = msg["visible_by"].get(username, None) # one of VISIBILITY_REASONS, or None

    ctx = dict(
                template_id=None,
                is_used=None, # for templates only
                is_ignored=None,
                has_read=(username in msg["has_read"]) if not is_pending else None,
                visibility_reason=visibility_reason,
                intercepted_by=datamanager.get_characters_for_visibility_reason(msg, visibility_reason=VISIBILITY_REASONS.interceptor) if datamanager.is_master() else None,
                can_transfer=True if not is_pending else None,
                has_starred=(username in msg["has_starred"]) if not is_pending else None,
                has_archived=(username in msg["has_archived"]) if not is_pending else None,
                can_reply=(visibility_reason == VISIBILITY_REASONS.recipient) if not is_pending else None,
                can_recontact=(visibility_reason == VISIBILITY_REASONS.sender) if not is_pending else None,
                can_force_sending=is_pending,
                can_permanently_delete=datamanager.is_master(),
                display_id=msg["id"], # USED IN UI controls!
                force_recipients_display=(visibility_reason == VISIBILITY_REASONS.sender),
                )
    _check_message_display_context(ctx, msg=msg)
    return ctx

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

    NO_CATEGORY_PLACEHOLDER = "[NONE]"
    ALL_CATEGORIES_PLACEHOLDER = "[ALL]"

    message_template_categories = request.datamanager.get_global_parameter("message_template_categories") # already sorted, ATM
    message_template_categories = [NO_CATEGORY_PLACEHOLDER] + message_template_categories + [ALL_CATEGORIES_PLACEHOLDER]

    selected_category = request.GET.get("category")
    if selected_category and selected_category not in message_template_categories:
        request.datamanager.user.add_error(_("Unknown template category '%(category)s'") % SDICT(category=selected_category))
        selected_category = None

    selected_category = selected_category or NO_CATEGORY_PLACEHOLDER

    if not selected_category or selected_category == NO_CATEGORY_PLACEHOLDER:
        enriched_templates = []  # security, because too many placeholders
    else:
        templates = request.datamanager.get_messages_templates().items() # PAIRS (template_id, template_dict)
        templates.sort(key=lambda msg: (msg[1]["order"], msg[0]))  # we sort by order and then template name
        enriched_templates = [(_determine_template_display_context(request.datamanager, template_id=tpl[0], template=tpl[1]), tpl[1])
                              for tpl in templates if (selected_category == ALL_CATEGORIES_PLACEHOLDER or selected_category in tpl[1]["categories"])]

    return render(request,
                  template_name,
                  dict(messages=enriched_templates,
                       contact_cache=_build_contact_display_cache(request.datamanager),
                       message_categories=message_template_categories,
                       selected_category=selected_category))


@register_view(access=UserAccess.authenticated, requires_global_permission=False, title=ugettext_lazy("Conversations"))
def standard_conversations(request, template_name='messaging/conversation.html'):

    CONVERSATIONS_LIMIT = 40

    display_all_conversations = bool(request.GET.get("display_all", None) == "1")

    visibility_reasons = (VISIBILITY_REASONS.sender, VISIBILITY_REASONS.recipient)  # we EXCLUDE intercepted messages from this
    messages = request.datamanager.get_user_related_messages(visibility_reasons=visibility_reasons, archived=False)  # for current master or character

    _grouped_messages = request.datamanager.sort_messages_by_conversations(messages)
    enriched_messages = _determine_message_list_display_context(request.datamanager, messages=_grouped_messages, is_pending=False)
    del _grouped_messages

    if len(enriched_messages) <= CONVERSATIONS_LIMIT:
        display_all_conversations = True # it makes no sense to "limit" then...

    if not display_all_conversations:
        enriched_messages = enriched_messages[0:CONVERSATIONS_LIMIT] # we arbitrarily limit to 15 recent conversations

    dm = request.datamanager
    if dm.is_game_writable() and dm.is_character():
        dm.set_new_message_notification(concerned_characters=[dm.username], increment=0)

    return render(request,
                  template_name,
                  dict(page_title=_("All My Conversations") if display_all_conversations else _("My Recent Conversations"),
                       display_all_conversations=display_all_conversations,
                       conversations=enriched_messages,
                       contact_cache=_build_contact_display_cache(request.datamanager)))


@register_view(access=UserAccess.character, requires_global_permission=False, title=ugettext_lazy("Intercepted Messages"))  # master doesn't INTERCEPT messages...
def intercepted_messages(request, template_name='messaging/messages.html'):
    visibility_reasons = [VISIBILITY_REASONS.interceptor]  # we EXCLUDE intercepted messages from this
    messages = request.datamanager.get_user_related_messages(visibility_reasons=visibility_reasons, archived=False)  # no LIMIT for now...
    messages = list(reversed(messages))
    enriched_messages = _determine_message_list_display_context(request.datamanager, messages=messages, is_pending=False)
    return render(request,
                  template_name,
                  dict(page_title=_("Intercepted Messages"),
                       messages=enriched_messages,
                       contact_cache=_build_contact_display_cache(request.datamanager)))

@register_view(access=UserAccess.authenticated, requires_global_permission=False, title=ugettext_lazy("Archived Messages"))  # ALSO for master
def all_archived_messages(request, template_name='messaging/messages.html'):
    visibility_reasons = VISIBILITY_REASONS  # in this archive, we list ALL messages, even intercepted
    messages = request.datamanager.get_user_related_messages(visibility_reasons=visibility_reasons, archived=True)  # no LIMIT for now...
    messages = list(reversed(messages))
    enriched_messages = _determine_message_list_display_context(request.datamanager, messages=messages, is_pending=False)
    return render(request,
                  template_name,
                  dict(page_title=_("Archived Messages"),
                       messages=enriched_messages,
                       contact_cache=_build_contact_display_cache(request.datamanager)))


@register_view(attach_to=standard_conversations, title=ugettext_lazy("Set Template Boolean Flags"))
def ajax_set_message_template_state_flags(request):
    # to be used by AJAX
    tpl_id = request.REQUEST.get("tpl_id", None)

    fields = ["is_ignored"]
    flags = {k: (request.REQUEST.get(k, None) in ("1", "true")) for k in fields if k in request.REQUEST}

    utilities.usage_assert(tpl_id)
    utilities.usage_assert(flags)
    request.datamanager.set_template_state_flags(tpl_id=tpl_id, **flags)

    return HttpResponse("OK")
    # in case of error, an HTTP error code will be returned


@register_view(attach_to=standard_conversations, title=ugettext_lazy("Set Message Boolean Flags"))
def ajax_set_dispatched_message_state_flags(request):
    # to be used by AJAX
    msg_id = request.REQUEST.get("msg_id", None)

    fields = request.datamanager.EMAIL_BOOLEAN_FIELDS_FOR_USERS

    flags = {k: (request.REQUEST.get(k, None) in ("1", "true")) for k in fields if k in request.REQUEST}

    utilities.usage_assert(msg_id)
    utilities.usage_assert(flags)
    request.datamanager.set_dispatched_message_state_flags(msg_id=msg_id, **flags)

    return HttpResponse("OK")
    # in case of error, an HTTP error code will be returned


@register_view(access=UserAccess.master, requires_global_permission=False, title=ugettext_lazy("Delete Message"))
def ajax_permanently_delete_message(request):
    # to be used by AJAX
    msg_id = request.REQUEST.get("id", None)

    request.datamanager.permanently_delete_message(msg_id=msg_id) # should never fail

    return HttpResponse("OK")
    # in case of error, an HTTP error code will be returned



@register_view(attach_to=standard_conversations, title=ugettext_lazy("Compose Message"))
def compose_message(request, template_name='messaging/compose.html'):

    user = request.datamanager.user
    message_sent = False
    form = None
    sent_msg_id = None

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

                use_restructuredtext = form.cleaned_data["use_restructuredtext"]
                body_format = "rst" if use_restructuredtext else "raw"

                sending_date = datetime.utcnow() + timedelta(hours=delay_h)
                assert isinstance(sending_date, datetime)
                del delay_h

                # we parse the list of emails
                recipient_emails = form.cleaned_data["recipients"]
                mask_recipients = form.cleaned_data["mask_recipients"]

                subject = form.cleaned_data["subject"]
                body = form.cleaned_data["body"]
                attachment = form.cleaned_data["attachment"]
                transferred_msg = form.cleaned_data["transferred_msg"]

                parent_id = form.cleaned_data.get("parent_id", None)
                use_template = form.cleaned_data.get("use_template", None)  # standard players might have it one day

                # sender_email and one of the recipient_emails can be the same email, we don't care !
                sent_msg_id = request.datamanager.post_message(sender_email, recipient_emails, subject, body,
                                                              attachment=attachment, transferred_msg=transferred_msg,
                                                              date_or_delay_mn=sending_date, mask_recipients=mask_recipients,
                                                              parent_id=parent_id, use_template=use_template,
                                                              body_format=body_format)
                assert sent_msg_id
                message_sent = True
                form = MessageComposeForm(request)  # new empty form
        else:
            user.add_error(_("Errors in message fields."))
    else:
        form = MessageComposeForm(request)


    if sent_msg_id:
        # we redirect towards the most probable view
        if not request.datamanager.is_master():
            target_view = "pychronia_game.views.standard_conversations"
        else:
            try:
                msg = request.datamanager.get_dispatched_message_by_id(sent_msg_id)
                del msg
                target_view = "pychronia_game.views.all_dispatched_messages"
            except UsageError:
                assert len([message for message in request.datamanager.messaging_data["messages_queued"] if message["id"] == sent_msg_id]) == 1
                target_view = "pychronia_game.views.all_queued_messages"

        conversations_url = game_view_url(target_view, datamanager=request.datamanager)
        conversations_url += '?' + urllib.urlencode(dict(message_sent="1"))
        return HttpResponseRedirect(redirect_to=conversations_url)


    user_contacts = request.datamanager.get_sorted_user_contacts() # properly SORTED list
    contacts_display = request.datamanager.get_contacts_display_properties(user_contacts) # DICT FIELDS: address avatar description

    parent_messages = ()
    parent_msg_id = request.GET.get("parent_id", None)
    if parent_msg_id:
        try:
            _parent_msg = request.datamanager.get_dispatched_message_by_id(msg_id=parent_msg_id)  # even if archived...
            # for now, only the DIRECT parent is displayed...
            parent_messages = _determine_message_list_display_context(request.datamanager, messages=[_parent_msg], is_pending=False)
        except UsageError as e:
            request.datamanager.logger.error("Ignoring invalid parent_id %s in message composition view", parent_msg_id, exc_info=True)

    #pprint(parent_messages)

    return render(request,
                  template_name,
                    {
                     'page_title': _("Compose Message"),
                     'message_form': form,
                     'mode': "compose", # TODO DELETE THIS
                     'contacts_display': contacts_display,
                     'message_sent': message_sent, # to destroy saved content
                     'parent_messages': parent_messages,
                     'contact_cache': _build_contact_display_cache(request.datamanager)
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


@register_view(access=UserAccess.authenticated, requires_global_permission=False, title=ugettext_lazy("View Single Message"))
def view_single_message(request, msg_id, template_name='messaging/view_single_message.html', popup_template_name='messaging/single_message.html'):
    """
    Meant to be used in event logging or for message transfer.
    
    On purpose, NO PERMISSION CHECK is done here (msg_ids are random enough), 
    however user must be authenticated (required by some messaging utilities like for "message display context").
    """
    user = request.datamanager.user
    message = None
    ctx = None
    is_queued = False

    popup_mode = (request.GET.get("popup") == "1")

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
            if not popup_mode:
                user.add_error(_("The requested message doesn't exist."))

    if message:
        ctx = _determine_message_display_context(request.datamanager, message, is_pending=is_queued)

    if popup_mode:
        if not message:
            return HttpResponse(_("Message couldn't be found."))
        return render(request,
                      popup_template_name,
                        {
                         'ctx': None,  # no operation possible
                         'message': message,  # SHALL NOT be empty
                         'contact_cache': _build_contact_display_cache(request.datamanager),
                         'no_background': True,
                        })
    else:
        return render(request,
                      template_name,
                        {
                         'page_title': _("Single Message"),
                         'is_queued': is_queued,
                         'ctx': ctx,
                         'message': message,  # might be None here
                         'contact_cache': _build_contact_display_cache(request.datamanager),
                        })


@register_view(access=UserAccess.anonymous, requires_global_permission=False, title=ugettext_lazy("Message Preview"))
def preview_message(request):

    rst = request.REQUEST.get("content", _("No content submitted for display")) # we take from both GET and POST

    html = format_enriched_text(request.datamanager, rst, initial_header_level=2, report_level=1).strip() # we let ALL debug output here!!

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

