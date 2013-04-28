# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *
from rpgweb.datamanager import readonly_method, transaction_watcher, register_view, AbstractAbility, AbstractGameForm



@register_view
class ChessChallengeAbility(AbstractAbility):

    TITLE = _lazy("Chess Challenge")
    NAME = "chess_challenge"

    GAME_ACTIONS = dict(notify_chess_player_victory=dict(title=_lazy("Notify victory of a chess player"),
                                                          form_class=None,
                                                          callback="notify_chess_player_victory"))

    TEMPLATE = "abilities/chess_challenge.html"

    ACCESS = UserAccess.character
    PERMISSIONS = []
    ALWAYS_ACTIVATED = True


    @classmethod
    def _setup_ability_settings(cls, settings):
        pass

    def _setup_private_ability_data(self, private_data):
        settings = self.settings

    def _check_data_sanity(self, strict=False):
        settings = self.settings


    def get_template_vars(self, previous_form_data=None):
        return {
                'page_title': _("Chess Challenge"),
               }

    @transaction_watcher
    def notify_chess_player_victory(self):
        self.log_game_event(_noop("Chess AI has been defeated by user.")) # username auto-logged
