# -*- coding: utf-8 -*-


from __future__ import print_function
from __future__ import unicode_literals

import random
from textwrap import dedent
import tempfile
import shutil
import inspect
from pprint import pprint

from ._test_tools import *
from ._dummy_abilities import *

import fileservers
from django.utils.functional import Promise # used eg. for lazy-translated strings
from django.utils import timezone

from pychronia_game.datamanager.abstract_ability import AbstractAbility
from pychronia_game.datamanager.action_middlewares import CostlyActionMiddleware, \
    CountLimitedActionMiddleware, TimeLimitedActionMiddleware
from pychronia_game.common import _undefined, config, AbnormalUsageError, reverse, \
    UsageError, checked_game_file_path, NormalUsageError, determine_asset_url
from pychronia_game.templatetags.helpers import _generate_encyclopedia_links, \
    advanced_restructuredtext, _generate_messaging_links, _generate_site_links, \
    format_enriched_text, _generate_game_file_links, _generate_game_image_thumbnails
from pychronia_game import views, utilities, authentication
from pychronia_game.utilities import autolinker
from django.test.client import RequestFactory
from pychronia_game.datamanager.datamanager_administrator import retrieve_game_instance, \
    _get_zodb_connection, GameDataManager, get_all_instances_metadata, \
    delete_game_instance, check_zodb_structure, change_game_instance_status, \
    GAME_STATUSES, list_backups_for_game_instance, backup_game_instance_data, \
    _get_backup_folder
from pychronia_game.tests._test_tools import temp_datamanager
from django.forms.fields import Field
from django.core.urlresolvers import resolve, NoReverseMatch
from pychronia_game.views import friendship_management
from pychronia_game.views.abilities import house_locking, \
    wiretapping_management, runic_translation, artificial_intelligence_mod, telecom_investigation_mod
from django.contrib.auth.models import User
from pychronia_game.authentication import clear_all_sessions
from pychronia_game.utilities.mediaplayers import generate_image_viewer
from django.core.urlresolvers import RegexURLResolver
from pychronia_game.datamanager.abstract_form import AbstractGameForm, GemPayementFormMixin
from ZODB.POSException import POSError
from pychronia_game.meta_administration_views import compute_game_activation_token, \
    decode_game_activation_token

from pychronia_game.common import *
from pychronia_game.datamanager.abstract_game_view import register_view
from pychronia_game.datamanager.datamanager_tools import readonly_method, \
    transaction_watcher
from pychronia_game.forms import OtherCharactersForm
#from django.utils.html import strip_tags
from django.template.loader import render_to_string
from types import *


class TestSpecialAbilities(BaseGameTestCase):

    def test_telecom_investigations(self):
    
        
        telecom = self.dm.instantiate_ability("telecom_investigation")
        telecom.perform_lazy_initializations()
        #self._reset_messages()
        
        #Message initialization
        email_guy1 = self.dm.get_character_email("guy1")
        email_guy2 = self.dm.get_character_email("guy2")
        email_guy3 = self.dm.get_character_email("guy3")
        email_guy4 = self.dm.get_character_email("guy4")
        email_external = sorted(self.dm.global_contacts.keys())[0]
        
        msg_id1 = self.dm.post_message(sender_email=email_guy1, recipient_emails=email_external, subject="test", body="test")
        msg1 = self.dm.get_dispatched_message_by_id(msg_id1)
        
        msg_id2 = self.dm.post_message(sender_email=email_guy3, recipient_emails=email_guy4, subject="test2", body="test2")
        msg2 = self.dm.get_dispatched_message_by_id(msg_id2)
    
        time.sleep(1)
    
        msg_id3 = self.dm.post_message(sender_email=email_guy4, recipient_emails=email_guy3, subject = "RE:%s" % msg2["subject"], body="test3", parent_id=msg_id2)
        msg3 = self.dm.get_dispatched_message_by_id(msg_id3)
        
        
        #TESTS FOR FIRST FUNCTION :
        
        assert telecom.extract_conversation_summary("guy4")
        res = telecom.extract_conversation_summary("guy4")
        assert type(res) is ListType
        
        #test on guy4 with fixed value:
        
        
        res = telecom.extract_conversation_summary("guy4")
        self.assertEqual(len(res), 2) # Guy4 has 2 conversations, we must have len = 2.
        
        res = telecom.extract_conversation_summary("my_npc")
        self.assertEqual(res, []) #npc n'a pas de conversation!
        
        #test on all guys with non fixed value:
        
        guys=["guy1", "guy2", "guy3", "guy4", "my_npc"]
        for guy in guys:
            res = telecom.extract_conversation_summary(guy)
            all_messages = self.dm.get_user_related_messages(guy, None, None)
            conversations = self.dm.sort_messages_by_conversations(all_messages)
            self.assertEqual(len(res),len(conversations))

        #time check:
        
        #test on guy4:
        res = telecom.extract_conversation_summary("guy4")
        for message in res:
            first_message_date = message["first_message"]
            last_message_date = message["last_message"]
            assert not first_message_date > last_message_date

        #test on all guys:
        guys = ["guy1", "guy2", "guy3", "guy4"]
        for guy in guys:
            res = telecom.extract_conversation_summary(guy)
            for message in res:
                first_message_date = message["first_message"]
                last_message_date = message["last_message"]
                assert not first_message_date > last_message_date

        #TESTS FOR SECOND FUNCTION:

        context_list = telecom.extract_conversation_summary("guy4")
        assert telecom.conversation_formatting(context_list)
        conversation_formatting = telecom.conversation_formatting(context_list)
        assert type(conversation_formatting) is UnicodeType

        #testing for guys with conversations :

        guys = ["guy1", "guy2", "guy3", "guy4"]
        for guy in guys :
            context_list = telecom.extract_conversation_summary(guy)
            assert telecom.conversation_formatting(guy)
            assert(telecom.conversation_formatting(context_list) != "Target has no conversation!")

        #testing for someone who has no conversation:

        context_list = telecom.extract_conversation_summary("my_npc")
        self.assertEqual(telecom.conversation_formatting(context_list), "Target has no conversation!")

        #TESTING FULL ABILITY:
        
        self._set_user("guy1")
        
        assert type(telecom.process_telecom_investigation("guy2")) is UnicodeType
        
        guys = ["guy2", "guy3", "guy4", "my_npc"]
    
        for guy in guys:
            assert telecom.process_telecom_investigation(guy)
            self.assertEqual(telecom.process_telecom_investigation(guy), "Telecom is in process, you will receive an e-mail with the intercepted messages soon!")
        
        #checking message writting:

        initial_length_sent_msgs = len(self.dm.get_all_dispatched_messages())

        self.assertEqual(len(self.dm.get_all_dispatched_messages()), initial_length_sent_msgs + 0)

        telecom.process_telecom_investigation("guy4")
        
        msgs = self.dm.get_all_dispatched_messages()
        
        self.assertEqual(len(msgs), initial_length_sent_msgs + 2) #We have a "+2" because there are 2 sent messages : one for requesting the investigation and one for the investigation results.

        #We could do the same for all the guys.

        guys = ["guy2", "guy3", "guy4", "my_npc"]
        self._reset_messages()

        for guy in guys:
            initial_length_sent_msgs = len(self.dm.get_all_dispatched_messages())
            telecom.process_telecom_investigation(guy)
            msgs = self.dm.get_all_dispatched_messages()
            self.assertEqual(len(msgs), initial_length_sent_msgs + 2)

        #Checking the e-mail subject, body and participants:

        self._reset_messages()
        self._set_user("guy1")
        telecom.process_telecom_investigation("guy4")
        
        #Request e-mail:
    
        msgs = self.dm.get_all_dispatched_messages()
        msg = msgs[-2]
        self.assertEqual(msg["sender_email"],"guy1@pangea.com")
        self.assertEqual(msg["recipient_emails"], ["investigator@spies.com"])
        self.assertEqual(msg["body"], "Please look for anything you can find about this person.")
        self.assertEqual(msg["subject"], "Investigation Request - Kha")
            
        #Investigation Results e-mail:
    
        context_list = telecom.extract_conversation_summary("guy4")
        body = telecom.conversation_formatting(context_list)

        msg = msgs[-1]
        self.assertEqual(msg["sender_email"], "investigator@spies.com")
        assert msg["recipient_emails"] == [u'guy1@pangea.com']
        self.assertEqual(msg["body"], body)
        self.assertEqual(msg["subject"], "<Investigation Results for Kha>")













