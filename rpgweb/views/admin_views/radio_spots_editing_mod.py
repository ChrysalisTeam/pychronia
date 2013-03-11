# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from django import forms

from rpgweb.common import *
from rpgweb.datamanager import register_view, AbstractGameView, DataTableForm

from rpgweb.utilities.acapela_vaas_tts import AcapelaClient
from rpgweb.utilities import mediaplayers

class RadioSpotForm(DataTableForm):

    title = forms.CharField(label=_lazy("Title"), required=True)
    text = forms.CharField(label=_lazy("Content"), widget=forms.Textarea(attrs={'rows': '2', 'cols':'40'}), required=True)

    url = forms.CharField(label=_lazy("Remote url"), required=True)



@register_view
class RadioSpotsEditing(AbstractGameView):

    NAME = "radio_spots_editing"

    ACTIONS = {"generate_tts_sample": "generate_tts_sample"}
    TEMPLATE = "administration/radio_spots_editing.html"

    ACCESS = UserAccess.master
    PERMISSIONS = []
    ALWAYS_AVAILABLE = True


    def get_template_vars(self, previous_form_data=None):

        form = RadioSpotForm(self.datamanager)

        return dict(page_title=_("Radio Spots"),
                    form=form)


    def generate_tts_sample(self, text, voice="ipek8k"):

        tts = AcapelaClient(url="http://vaas.acapela-group.com/Services/Synthesizer",
                           login="EVAL_VAAS",
                           application="EVAL_4775608",
                           password="",
                           environment="PYTHON_2.7_WINDOWS_VISTA")
        print (">>>>>>>>>>>>> CALLING WITH %r" % text)

        try:
            res = {'alt_sound_size': None, 'sound_size': u'6799', 'sound_time': u'805.75', 'sound_id': u'289920127_cffb8f40d9f30', 'alt_sound_url': None, 'sound_url': u'http://vaas.acapela-group.com/MESSAGES/009086065076095086065065083/EVAL_4775608/sounds/289920127_cffb8f40d9f30.mp3', 'warning': u'', 'get_count': 0}
            ###res = tts.create_sample(voice=voice, text=text, response_type="INFO")
        except EnvironmentError, e:
            self.logger.critical("TTS generation failed for %s/%r: %r", voice, text, e)
            raise

        print (">>>>>>>>>>>>>", res)

        html_player = mediaplayers.build_proper_viewer(res["sound_url"], autostart=True)

        return dict(sound_url=res["sound_url"],
                    mediaplayer=html_player)

