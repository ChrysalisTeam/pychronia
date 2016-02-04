# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from datetime import datetime

from pychronia_game.common import *
from pychronia_game.datamanager.abstract_ability import AbstractAbility
from pychronia_game.datamanager.abstract_game_view import register_view
from pychronia_game.datamanager.datamanager_tools import readonly_method, \
    transaction_watcher
from pychronia_game.forms import OtherCharactersForm
from django.utils.html import strip_tags
from django.template.loader import render_to_string

@register_view
class TelecomInvestigationAbility(AbstractAbility):

    TITLE = ugettext_lazy("Telecom Investigation")
    NAME = "telecom_investigation"

    GAME_ACTIONS = dict(investigation_form=dict(title=ugettext_lazy("Process Telecom Investigation"),
                                               form_class=OtherCharactersForm,
                                               callback="process_telecom_investigation"))
    
    TEMPLATE = "abilities/telecom_investigation.html"

    ACCESS = UserAccess.authenticated
    REQUIRES_CHARACTER_PERMISSION = False
    REQUIRES_GLOBAL_PERMISSION = False

    @classmethod
    def _setup_ability_settings(cls, settings):
        pass # nothing to do

    def _setup_private_ability_data(self, private_data):
        pass # nothing to do

    def _check_data_sanity(self, strict=False):
        pass # nothing to do

    def get_template_vars(self, previous_form_data=None):
        translation_form = self._instantiate_game_form(new_action_name="investigation_form",
                                                       hide_on_success=False,
                                                      previous_form_data=previous_form_data)
        translation_delay = (2,3)
        return {
                 'page_title': _("Telecom Investigation"),
                 "investigation_form": translation_form,
                 'min_delay_mn': translation_delay[0],
                 'max_delay_mn': translation_delay[1],
               }



    def extract_conversation_summary(self, target_username):
    
        visibility_reasons = None
        archived=None
    
        result = self.get_user_related_messages(target_username, visibility_reasons, archived)
    
        conversations = self.sort_messages_by_conversations(result)
        context_list=[]
        
    
        for conversation in conversations:
            
            messages_count = len(conversation)
            subject = conversation[-1]["subject"]
            first_message_date = conversation[-1]["sent_at"].date()
            last_message_date = conversation[0]["sent_at"].date()
            sender = conversation[-1]["sender_email"]
            
            for message in conversation:
                
                recipients = message["recipient_emails"]
                participants = set(recipients) | set([sender])
        
            context = {"subject" : subject, "messages" : messages_count, "participants" : (", ".join(str(e) for e in participants)),  "first_message" : first_message_date, "last_message" :last_message_date}
            context_list.append(context)
        
        return context_list

    def conversation_formatting(self,context_list):
        body=""
        if context_list == []:
            body = _("Target has no conversation!")
        else:
            for context in context_list:
                body += render_to_string("abilities/telecom_summary_format.html", context)
        return body

    @transaction_watcher
    def process_telecom_investigation(self, target_username, use_gems=()):
        
        username = self.get_official_name()
        target_name = self.get_official_name(target_username)
        user_email = self.get_character_email()
        remote_email = "investigator@spies.com"
        
        
        #request e-mail:
        subject = _("Investigation Request - %(target_name)s") % dict(target_name=target_name)
        
        body = _("Please look for anything you can find about this person.")
        self.post_message(user_email, remote_email, subject, body, date_or_delay_mn=0)
        
        #answer e-mail:
        subject = _('<Investigation Results for %(target_name)s>') % dict(target_name=target_name)
        
        context_list = self.extract_conversation_summary(target_username)
        
        body = self.conversation_formatting(context_list)
        #body = str(len(self.extract_conversation_summary(target_username)))
        
        
        msg_id = self.post_message(remote_email, user_email, subject, body, date_or_delay_mn=0)

        #ajouter délai avec self.get_global_parameter("telecom_investigation_delays") - IMPLEMENTER LES INVESTIGATION DELAYS DANS LES SETTINGS
        
        self.log_game_event(ugettext_noop("Player '%(user)s' has ran a telecom investigation on '%(target_name)s'."), PersistentMapping(user = username, target_name = target_name), visible_by=None)

        return _("Telecom is in process, you will receive an e-mail with the intercepted messages soon!")
