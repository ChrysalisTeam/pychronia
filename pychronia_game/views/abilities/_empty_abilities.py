# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from pychronia_game.common import *
from pychronia_game.datamanager.abstract_ability import AbstractAbility


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

    TITLE = _lazy("Extra Plugins")
    NAME = "ability_introduction"

    ACCESS = UserAccess.authenticated
    REQUIRES_CHARACTER_PERMISSION = False
    REQUIRES_GLOBAL_PERMISSION = False # let's not risk to forget it


class GeoipLocationAbility(EmptyAbilityMixin, AbstractAbility):

    TITLE = _lazy("Web Geolocation")
    NAME = "geoip_location"

    ACCESS = UserAccess.authenticated
    REQUIRES_CHARACTER_PERMISSION = True
    REQUIRES_GLOBAL_PERMISSION = True


class BusinessEscrowAbility(EmptyAbilityMixin, AbstractAbility):

    TITLE = _lazy("Business Escrow")
    NAME = "business_escrow"

    ACCESS = UserAccess.authenticated
    REQUIRES_CHARACTER_PERMISSION = False
    REQUIRES_GLOBAL_PERMISSION = True


class BlackMarketAbility(EmptyAbilityMixin, AbstractAbility):

    TITLE = _lazy("Black Market")
    NAME = "black_market"

    ACCESS = UserAccess.authenticated
    REQUIRES_CHARACTER_PERMISSION = False
    REQUIRES_GLOBAL_PERMISSION = True
