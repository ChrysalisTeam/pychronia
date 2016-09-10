# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from datetime import datetime

from pychronia_game.common import *
from pychronia_game.datamanager.abstract_ability import AbstractPartnershipAbility
from pychronia_game.datamanager.abstract_game_view import register_view
from pychronia_game.datamanager.datamanager_tools import readonly_method, \
    transaction_watcher
from pychronia_game.forms import OtherKnownCharactersForm
from django.utils.html import strip_tags
from django.utils import formats as django_formats
from django.template.loader import render_to_string


@register_view
class TelecomInvestigationAbility(AbstractPartnershipAbility):
    TITLE = ugettext_lazy("Telecom Investigation")
    NAME = "telecom_investigation"

    GAME_ACTIONS = dict(investigation_form=dict(title=ugettext_lazy("Process Telecom Investigation"),
                                                form_class=OtherKnownCharactersForm,
                                                callback="process_telecom_investigation"))

    TEMPLATE = "abilities/telecom_investigation.html"

    ACCESS = UserAccess.character
    REQUIRES_CHARACTER_PERMISSION = True
    REQUIRES_GLOBAL_PERMISSION = True

    @classmethod
    def _setup_ability_settings(cls, settings):
        pass  # nothing to do

    def _setup_private_ability_data(self, private_data):
        pass  # nothing to do

    def _check_data_sanity(self, strict=False):
        pass  # nothing to do

    def get_template_vars(self, previous_form_data=None):
        investigation_form = self._instantiate_game_form(new_action_name="investigation_form",
                                                         hide_on_success=False,
                                                         previous_form_data=previous_form_data)
        return {
            'page_title': _("Telecom Investigation"),
            "investigation_form": investigation_form,
        }

    @readonly_method
    def extract_conversation_summary(self, target_username):

        result = self.get_user_related_messages(target_username, visibility_reasons=None, archived=None)

        conversations = self.sort_messages_by_conversations(result)
        context_list = []

        for conversation in conversations:
            messages_count = len(conversation)
            subject = conversation[-1]["subject"]
            first_message_date = conversation[-1]["sent_at"]
            last_message_date = conversation[0]["sent_at"]

            participants = set()  # set of EMAIL ADDRESSES
            for message in conversation:
                participants.add(message["sender_email"])
                participants.update(message["recipient_emails"])
            participants = sorted(participants)

            context = {"subject": subject,
                       "messages_count": messages_count,
                       "participants": ", ".join(participants),
                       "first_message_date": django_formats.date_format(first_message_date, "SHORT_DATE_FORMAT"),
                       "last_message_date": django_formats.date_format(last_message_date, "SHORT_DATE_FORMAT")}
            context_list.append(context)

        return context_list

    @readonly_method
    def format_conversation_summary(self, context_list):
        html = []
        if context_list == []:
            html = [_("No conversations found in target data.")]
        else:
            for context in context_list:
                html.append(render_to_string("abilities/telecom_summary_format.html", context))
        return "\n\n-----\n\n".join(html)

    @transaction_watcher
    def process_telecom_investigation(self, target_username, use_gems=()):

        target_official_name = self.get_official_name(target_username)

        # request e-mail
        subject = _("Telecom Investigation Request - %(target_name)s") % dict(target_name=target_official_name)
        body = _("Please look for anything you can find about this person.")
        request_msg_data = dict(subject=subject,
                                body=body)

        # response e-mail
        subject = _('Telecom Investigation Results - %(target_name)s') % dict(target_name=target_official_name)
        _context_list = self.extract_conversation_summary(target_username)
        body = self.format_conversation_summary(_context_list)
        response_msg_data = dict(subject=subject,
                                 body=body,
                                 attachment=None)
        del subject, body

        best_msg_id = self._process_standard_exchange_with_partner(request_msg_data=request_msg_data,
                                                                   response_msg_data=response_msg_data)

        self.log_game_event(ugettext_noop("Telecom investigation launched on target '%(target_name)s'."),
                            PersistentMapping(target_name=target_official_name),
                            url=self.get_message_viewer_url_or_none(best_msg_id),
                            visible_by=[self.username])

        return _("Telecom investigation is in process, you will receive an e-mail with the intercepted messages soon!")
