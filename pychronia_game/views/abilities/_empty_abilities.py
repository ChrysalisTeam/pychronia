# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from pychronia_game.common import *
from pychronia_game.datamanager.abstract_game_view import AbstractGameView
from pychronia_game.datamanager.abstract_ability import AbstractAbility
from pychronia_game.views.gameview_mixins import AbstractCaptchaProtectedView

class EmptyAbilityMixin(object):

    GAME_ACTIONS = {}
    TEMPLATE = "abilities/_empty_ability.html"

    def get_template_vars(self, previous_form_data=None):
        return {}
    def _setup_private_ability_data(self, private_data):
        pass
    def _check_data_sanity(self, strict=False):
        pass



class AbilityIntroduction(EmptyAbilityMixin, AbstractAbility):

    TITLE = ugettext_lazy("Extra Plugins")
    NAME = "ability_introduction"

    ACCESS = UserAccess.authenticated
    REQUIRES_CHARACTER_PERMISSION = False
    REQUIRES_GLOBAL_PERMISSION = False # let's not risk to forget it


class GeoipLocationAbility(EmptyAbilityMixin, AbstractAbility):

    TITLE = ugettext_lazy("Web Geolocation")
    NAME = "geoip_location"

    ACCESS = UserAccess.authenticated
    REQUIRES_CHARACTER_PERMISSION = True
    REQUIRES_GLOBAL_PERMISSION = True


class BusinessEscrowAbility(EmptyAbilityMixin, AbstractGameView): # actually a simple GAMEVIEW at the moment, without captcha

    TITLE = ugettext_lazy("Business Escrow")
    NAME = "business_escrow"

    ACCESS = UserAccess.authenticated
    REQUIRES_CHARACTER_PERMISSION = False
    REQUIRES_GLOBAL_PERMISSION = True


class BlackMarketAbility(EmptyAbilityMixin, AbstractCaptchaProtectedView): # actually a simple GAMEVIEW at the moment, but captcha-protected

    TITLE = ugettext_lazy("Black Market")
    NAME = "black_market"

    ACCESS = UserAccess.authenticated
    REQUIRES_CHARACTER_PERMISSION = False
    REQUIRES_GLOBAL_PERMISSION = True
