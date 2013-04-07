# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *
from rpgweb.datamanager import register_view, AbstractGameView



@register_view
class WebradioManagement(AbstractGameView):

    NAME = "webradio_management"

    GAME_ACTIONS = dict(save_radio_playlist=dict(title=_lazy("Save radio playlist"),
                                                          form_class=None,
                                                          callback="save_radio_playlist"))

    TEMPLATE = "administration/webradio_management.html"

    ACCESS = UserAccess.master
    PERMISSIONS = []
    ALWAYS_AVAILABLE = True


    def get_template_vars(self, previous_form_data=None):

        radio_is_on = self.datamanager.get_global_parameter("radio_is_on")

        pending_audio_messages = [(audio_id, self.datamanager.get_audio_message_properties(audio_id))
                                  for audio_id in self.datamanager.get_all_next_audio_messages()]

        players_with_new_messages = self.datamanager.get_pending_new_message_notifications()


        all_new_message_notifications = self.datamanager.get_all_new_message_notification_sounds()

        # we filter out numerous "new emails" messages, which can be summoned in batch anyway
        all_audio_messages = self.datamanager.get_all_audio_messages().items()
        special_audio_messages = [msg for msg in all_audio_messages if msg[0] not in all_new_message_notifications]

        special_audio_messages.sort(key=lambda x: x[0])

        return {
                 'page_title': _("Web Radio Management"),
                 'radio_is_on': radio_is_on,
                 'pending_audio_messages': pending_audio_messages,
                 'players_with_new_messages': players_with_new_messages,
                 'special_audio_messages': special_audio_messages
                }

    def _process_html_post_data(self):

        assert self.request.method == "POST"
        request = self.request
        POST = request.POST
        result = None

        # manual form management, since there are hell a lot of stuffs...
        if POST.has_key("turn_radio_off"):
            result = False
            with action_failure_handler(request, _("Web Radio has been turned OFF.")):
                self.datamanager.set_radio_state(is_on=False)
                result = True
        elif POST.has_key("turn_radio_on"):
            result = False
            with action_failure_handler(request, _("Web Radio has been turned ON.")):
                self.datamanager.set_radio_state(is_on=True)
                result = True
        elif POST.has_key("reset_playlist"):
            result = False
            with action_failure_handler(request, _("Audio Playlist has been emptied.")):
                self.datamanager.reset_audio_messages()
                result = True
        elif POST.has_key("notify_new_messages"):
            result = False
            with action_failure_handler(request, _("Player notifications have been enqueued.")):
                self.datamanager.add_radio_message("intro_audio_messages")
                for (username, audio_id) in self.datamanager.get_pending_new_message_notifications().items():
                    self.datamanager.add_radio_message(audio_id)
                result = True
        elif POST.has_key("add_audio_message"):
            result = False
            with action_failure_handler(request, _("Player notifications have been enqueued.")):
                audio_id = request.POST["audio_message_added"]  # might raise KeyError
                self.datamanager.add_radio_message(audio_id)
            result = True
        else:
            assert result is None
            return super(WebradioManagement, self)._process_html_request() # displays error if POST data is useless

        return dict(result=result,
                form_data=None) # no form data unless with went through super()._process_html_request() above


    def save_radio_playlist(self, audio_ids):
        self.datamanager.set_radio_messages(audio_ids) # breaks if not a proper list of audio ids
        return True



