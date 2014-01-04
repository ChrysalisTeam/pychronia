# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from pychronia_game.common import *
from pychronia_game.datamanager import readonly_method, transaction_watcher, register_view, AbstractAbility, AbstractGameForm



@register_view
class ChessChallengeAbility(AbstractAbility):

    TITLE = ugettext_lazy("Chess Challenge")
    NAME = "chess_challenge"

    GAME_ACTIONS = dict(notify_chess_player_victory=dict(title=ugettext_lazy("Notify victory of a chess player"),
                                                          form_class=None,
                                                          callback="notify_chess_player_victory"))

    TEMPLATE = "abilities/chess_challenge.html"

    ACCESS = UserAccess.authenticated
    REQUIRES_CHARACTER_PERMISSION = False
    REQUIRES_GLOBAL_PERMISSION = False


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
    def notify_chess_player_victory(self, use_gems=()):
        if self.is_master():
            self.user.add_message(_("Master, your chess victory has well been detected and ignored by the server."))
        else:
            self.log_game_event(ugettext_noop("Chess AI has been defeated by user '%(winner)s'.",
                                              PersistentDict(winner=self.user.username)))
