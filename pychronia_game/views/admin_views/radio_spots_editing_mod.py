# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

import time
from django import forms

from pychronia_game.common import *
from pychronia_game.datamanager import register_view, AbstractGameView, DataTableForm, AbstractDataTableManagement

from pychronia_game.utilities.acapela_vaas_tts import AcapelaClient
from pychronia_game.utilities import mediaplayers
from pychronia_game.datamanager.abstract_form import GAMEMASTER_HINTS_FIELD


class RadioSpotForm(DataTableForm):

    title = forms.CharField(label=ugettext_lazy("Title"), required=True)

    text = forms.CharField(label=ugettext_lazy("Content"), widget=forms.Textarea(attrs={'rows': '5', 'cols':'40'}), required=True)

    file = forms.CharField(label=ugettext_lazy("File (url or local file)"), required=True)

    gamemaster_hints = GAMEMASTER_HINTS_FIELD()





@register_view
class RadioSpotsEditing(AbstractDataTableManagement):

    TITLE = ugettext_lazy("Radio Spots Editing")
    NAME = "radio_spots_editing"

    GAME_ACTIONS = dict(submit_item=dict(title=ugettext_lazy("Submit radio spot"),
                                                          form_class=RadioSpotForm,
                                                          callback="submit_item"),
                        delete_item=dict(title=ugettext_lazy("Delete radio spot"),
                                                          form_class=None,
                                                          callback="delete_item"),
                        generate_tts_sample=dict(title=ugettext_lazy("Generate text-to-speech sample"),
                                                          form_class=None,
                                                          callback="generate_tts_sample"))
    TEMPLATE = "administration/radio_spots_editing.html"

    def get_data_table_instance(self):
        return self.datamanager.radio_spots


    def generate_tts_sample(self, text, voice="antoine22k"):

        text = text.replace("\n", "").replace("\r", "") # TTS engine will stop sound mixing when a newline is encountered, so we remove them all

        if not config.ACAPELA_CLIENT_ARGS:
            if not config.DEBUG:
                raise RuntimeError("Text-to-speech engine is not configured")
            else:
                self.logger.warning("Generating DUMMY mp3 link for voice=%r and text=%r", voice, text)
                #sound_url = "http://dummy_test_url_%d.mp3" % int(time.time())
                sound_url = "http://localhost:8000/files/f26529e7/audio/radio_spots/personal_messages/A_intro_messages.mp3"

        else:

            tts = AcapelaClient(**config.ACAPELA_CLIENT_ARGS)

            self.logger.info("Generating TTS sample for voice=%r and text=%r", voice, text)

            try:
                #res = {'alt_sound_size': None, 'sound_size': u'6799', 'sound_time': u'805.75', 'sound_id': u'289920127_cffb8f40d9f30', 'alt_sound_url': None, 'sound_url': u'http://vaas.acapela-group.com/MESSAGES/009086065076095086065065083/EVAL_4775608/sounds/289920127_cffb8f40d9f30.mp3', 'warning': u'', 'get_count': 0}
                res = tts.create_sample(voice=voice, text=text, response_type="INFO")
            except EnvironmentError, e:
                self.logger.critical("TTS generation failed for %s/%r: %r", voice, text, e)
                raise # OK for AJAX request

            self.logger.info("TTS generation successful: %r", res)

            sound_url = res["sound_url"]

        html_player = mediaplayers.build_proper_viewer(sound_url, autostart=True)

        return dict(sound_url=sound_url,
                    mediaplayer=html_player)

