# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from pychronia_game.common import *
from pychronia_game.datamanager.abstract_ability import AbstractAbility
from pychronia_game.datamanager.abstract_game_view import register_view
from pychronia_game.datamanager.datamanager_tools import readonly_method, \
    transaction_watcher
from pychronia_game.forms import OtherCharactersForm

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
        conversations = "\n"
    
        result = self.get_user_related_messages(target_username, visibility_reasons, archived)
    
        conv = self.sort_messages_by_conversations(result)
    
        for i in range (0, len(conv)):
            conversations += ("**" + _("Conversation number %(numero)s :") % dict(numero=(i+1)) + "**" + "\n\n")
            recipient_num = len(conv[i][0]["recipient_emails"])
            for j in range(0, recipient_num):
                conversations += ( _("Parcticipants :  ") + conv[i][0]["sender_email"] + _(" ; ") + str(conv[i][0]["recipient_emails"][j]) + "\n\n")
            conversations += ( _("Subject of conversation :  ") + conv[i][0]["subject"] + "\n\n")
            num = len(conv[i])
            conversations += ( _("Number of messages exchanged :  ") + str(num) + "\n\n")
            conversations += ( _("First sent message :  ") + str(conv[i][0]["sent_at"]) + "\n\n")
            conversations += ( _("Last sent message :  ") +  str(conv[i][num-1]["sent_at"]) + "\n\n")
        
        return conversations

    @transaction_watcher
    def process_telecom_investigation(self, target_username, use_gems=()):
        
        target_name = self.get_official_name(target_username)
        user_email = self.get_character_email()
        remote_email = "investigator@spies.com"
        
        
        #request e-mail:
        subject = _("Investigation Request - %(target_name)s") % dict(target_name=target_name)
        
        body = _("Please look for anything you can find about this person.")
        self.post_message(user_email, remote_email, subject, body, date_or_delay_mn=0)
        
        #answer e-mail:
        subject = _('<Investigation Results for %(target_name)s>') % dict(target_name=target_name)
        
        body = self.extract_conversation_summary(target_username)
        
        msg_id = self.post_message(remote_email, user_email, subject, body, date_or_delay_mn=0)

        #ajouter délai avec self.get_global_parameter("telecom_investigation_delays") - IMPLEMENTER LES INVESTIGATION DELAYS DANS LES SETTINGS

        return _("Telecom is in process, you will receive an e-mail with the intercepted messages soon!")
