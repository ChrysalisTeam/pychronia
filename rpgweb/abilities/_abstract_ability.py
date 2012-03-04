# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *

from django.http import HttpResponse
from django.shortcuts import render_to_response
from django.template import RequestContext, loader

from ..datamanager import GameDataManager, readonly_method, transaction_watcher
from ..forms import AbstractGameForm
from ..views._abstract_game_view import GameViewMetaclass, AbstractGameView, register_view




class AbilityMetaclass(GameViewMetaclass):
    """
    Metaclass automatically registering the new ability (which is also a view) in a global registry.
    """ 
    def __init__(NewClass, name, bases, new_dict):
        
        super(AbilityMetaclass, NewClass).__init__(name, bases, new_dict)
        
        if not NewClass.__name__.startswith("Abstract"):

            if __debug__:
                pass
                #RESERVED_NAMES = AbstractAbility.__dict__.keys()
                ##assert utilities.check_is_lazy_object(NewClass.TITLE) # NO - unused atm !! delayed translation

            GameDataManager.register_ability(NewClass)
            





class AbstractAbility(AbstractGameView):

    __metaclass__ = AbilityMetaclass


    # NOT ATM - TITLE = None # menu title, use lazy gettext when setting


    def __init__(self, datamanager):
        self.__datamanager = weakref.ref(datamanager)
        self._ability_data = weakref.ref(datamanager.get_ability_data(self.NAME))
        self.logger = datamanager.logger # local cache
        self._perform_lazy_initializations() # so that tests work too, we need it immediately here
    
    
    def _process_request(self, request, *args, **kwargs):
        # do NOT call parent method (unimplemented)
        # Access checks have already been done here, so we may initialize lazy data
        return self._auto_process_request(request)
    

    @property
    def _datamanager(self):
        return self.__datamanager() # could be None


    def __getattr__(self, name):
        assert not name.startswith("_") # if we arrive here, it's probably a typo in an attribute fetching
        try:
            value = getattr(self._datamanager, name)
        except AttributeError:
            raise AttributeError("Neither ability nor datamanager has attribute '%s'" % name)
        return value


    @property
    def ability_data(self):
        return self._ability_data() # could be None


    @property
    def settings(self):
        return self._ability_data()["settings"]


    @property
    def private_data(self):
        private_key = self._get_private_key()
        return self._ability_data()["data"][private_key]
    
    
    def _get_private_key(self):
        return self._datamanager.user.username # can be None, a character or a superuser login!


    @property
    def all_private_data(self):
        return self._ability_data()["data"]


    def get_ability_parameter(self, name):
        return self.settings[name]


    '''
    @classmethod
    def get_menu_title(cls):
        return cls.TITLE
    '''
   
    @readonly_method
    def get_ability_summary(self):
        # FIXME - how does it work actually ?
        return self._get_ability_summary()


    def _get_ability_summary(self):
        """
        Summary for super user ?
        """
        raise NotImplementedError




    @classmethod
    def setup_main_ability_data(cls, ability_data):
        # no transaction handling here - it's all up to the caller of that classmethod
        settings = ability_data.setdefault("settings", PersistentDict())
        ability_data.setdefault("data", PersistentDict())
        cls._setup_ability_settings(settings=settings)

    @classmethod
    def _setup_ability_settings(cls, settings):
        pass # to be overridden


    @transaction_watcher(ensure_game_started=False) # authorized anytime
    def _perform_lazy_initializations(self):


        private_key = self._get_private_key()
        if not self.ability_data.has_key(private_key):
            self.logger.debug("Setting up private data %s", private_key)
            private_data = self.ability_data["data"].setdefault(private_key, PersistentDict())
            self._setup_private_ability_data(private_data=private_data)


    def _setup_private_ability_data(self, private_data):
        """
        Not called in the case of game-level abilities
        """
        raise NotImplementedError("_setup_private_ability_data") # to be overridden


    @readonly_method
    def check_data_sanity(self, strict=False):

        # self.logger.debug("Checking data sanity")

        assert isinstance(self.ability_data["settings"], collections.Mapping), self.ability_data["settings"]
        assert isinstance(self.ability_data["data"], collections.Mapping), self.ability_data["data"]

        if strict:
            available_logins = self._datamanager.get_available_logins()
            for name, value in self.ability_data["data"].items():
                assert name in available_logins
                assert isinstance(value, collections.Mapping)

        self._check_data_sanity(strict=strict)


    def _check_data_sanity(self, strict=False):
        raise NotImplementedError("_check_data_sanity") # to be overridden


    # now a standard method, not classmethod
    def _instantiate_form(self,
                          new_form_name, 
                          hide_on_success=False, 
                          previous_form_data=None,
                          initial_data=None):
        return super(AbstractAbility, self)._instantiate_form(datamanager=self, # the ability behaves as an extended datamanager
                                                              new_form_name=new_form_name, 
                                                              hide_on_success=hide_on_success,
                                                              previous_form_data=previous_form_data,
                                                              initial_data=initial_data)
                                    




class __PayableAbilityHandler(object):
    """
    Mix-in class that manages items/services purchased by players, in an ability context.
    
    """


    @classmethod
    def _setup_ability_settings(cls, settings):
        super(PayableAbilityHandler, None)._setup_ability_settings(settings)
        settings.setdefault("assets_max_per_game", None) # limit for the total number of such items bought by players, false value if unlimited
        settings.setdefault("assets_max_per_player", None) # limit for the number of such items bought by a particular player, false value if unlimited
        settings.setdefault("assets_money_price", None) # integer, false value if not possible to buy with money
        settings.setdefault("assets_gems_price", None) # integer, false value if not possible to buy with gems
        settings.setdefault("assets_allow_duplicates", True) # boolean indicating if the same key may appear several times in *assets_items_bought*


    def _setup_private_ability_data(self, private_data):
        super(PayableAbilityHandler, None)._setup_private_ability_data(private_data)
        private_data.setdefault("assets_items_bought", PersistentList()) # list of picklable keys identifying items bought by player


    def _check_data_sanity(self, strict=False):
        super(PayableAbilityHandler, None)._check_data_sanity(strict=strict)

        settings = self.settings

        for setting in "assets_max_per_game assets_max_per_player assets_money_price assets_max_per_player".split():
            if settings[setting]:
                utilities.check_positive_int(settings[setting])
        utilities.check_is_bool(settings["assets_allow_duplicates"])

        total_items = 0
        for private_data in self.all_private_data.values():
            player_items = private_data["assets_items_bought"]
            assert len(player_items) <= settings["assets_max_per_player"]
            if settings["assets_allow_duplicates"]:
                assert len(set(player_items)) == len(player_items)
            total_items += len(player_items)
        assert total_items <= settings["assets_max_per_game"]



    def _assets_bought_are_strictly_under_limits(self):

        settings = self.settings

        if settings["assets_max_per_player"]:
            private_data = self.private_data
            if private_data["assets_items_bought"] >= settings["assets_max_per_player"]:
                return False

        if settings["assets_max_per_game"]:
            total_items = sum(len(private_data["assets_items_bought"]) for private_data in self.all_private_data.values())
            if total_items >= settings["assets_max_per_game"]:
                return False

        return True


    @transaction_watcher
    def purchase_single_asset(self, asset_id, pay_with_gems=None):
        """
        *buy_with_gems* is None (if we buy with money), or list of gem values to use
        (gems that the player must possess, of course).
        """

        user = self._datamanager.user

        assert user.is_character

        if isinstance(asset_id, (list, dict, set)) and not isinstance(asset_id, Persistent):
            raise RuntimeError("Wrong mutable asset id %s, we need Persistent types instead for ZODB" % asset_id)

        if not user.is_character:
            raise AbnormalUsageError(_("Only regular users may purchase items and services")) # shouldn't happen

        settings = self.settings
        private_data = self.private_data

        if not self._assets_bought_are_strictly_under_limits():
            raise AbnormalUsageError(_("No more assets available for purchase"))

        if settings["assets_allow_duplicates"] and asset_id in private_data["assets_items_bought"]:
            raise AbnormalUsageError(_("You have already purchased that asset"))


        player_properties = self.get_character_properties(user.username)

        if pay_with_gems:

            gems_price = settings["assets_gems_price"]

            if not gems_price:
                raise AbnormalUsageError(_("That asset must be bought with money, not gems"))

            if sum(pay_with_gems) < gems_price:
                raise NormalUsageError(_("You need at least %(price)s kashes in gems to buy that asset") % SDICT(gems_price=gems_price))

            # we don't care if the player has given too many gems
            remaining_gems = utilities.substract_lists(character_properties["gems"], pay_with_gems)

            if remaining_gems is None:
                raise AbnormalUsageError(_("You don't possess the gems required"))
            else:
                character_properties["gems"] = remaining_gems


        else: # paying with bank money

            money_price = settings["assets_money_price"]

            if not money_price:
                raise AbnormalUsageError(_("That asset must be bought with gems, not money"))

            if character_properties["account"] < money_price:
                raise NormalUsageError(_("You need at least %(price)s kashes in money to hire these agents") % SDICT(price=money_price))

            character_properties["account"] -= money_price

            self.data["global_parameters"]["bank_account"] += money_price





'''
    def _check_permissions(self):
        ###USELESS
        """
        This method should be called at django view level only, not from another ability
        method (unittests don't have to care about permissions).
        """
        user = self._datamanager.user
        
        if self.ACCESS == "master":
            if not user.is_master:
                raise PermissionError(_("Ability reserved to administrators"))
        elif self.ACCESS == "player":
            if not user.is_character:
                raise PermissionError(_("Ability reserved to standard users"))
            if not user.has_permission(self.NAME):
                # todo - what permission tokens do we use actually for abilities ??
                raise PermissionError(_("Ability reserved to privileged users"))
        elif self.ACCESS == "authenticated":
            if not user.is_authenticated:
                raise PermissionError(_("Ability reserved to registered users"))
        else:
            assert self.ACCESS == "anonymous"


    def _____get_action_contexts(self): #TODO REMOVE
        private_key = self._get_private_key()
        if private_key:
            private_data = self.ability_data[private_key]
        else:
            private_data = None
        return (self.ability_data["settings"], private_data)

 
    def __init__(self, ability_name, max_items, items_available=0):
        self.__ability_name = ability_name
        self.__record = PersistentDict(
                                         items_consumed=0,
                                         items_available=items_available,
                                         max_items=max_items,
                                         item_price=item_price
                                      )

    def _ability_retrieve_record(ability_name):
        assert ability_name == self.__ability_name
        return self.__record

    ###################################################################



    def ability_get_team_value(ability_name, field):
        record = self._ability_retrieve_record(ability_name)
        return record[field]


    def ability_check_record_coherency(self, ability_name):
        record = self._ability_retrieve_record(ability_name)
        for (key, value) in record.items():
            assert isinstance(value, (int, long)), record
            assert value >= 0
        assert record["items_consumed"] + record["items_available"] <= record["max_items"]


    def ability_consume(self, ability_name, num_consumed=1):
        record = self._ability_retrieve_record(ability_name)

        if num_consumed >= record["items_available"]:
            raise NormalUsageError(_("Not enough '%s' items to consume"))

        record["items_available"] -= num_consumed
        record["items_consumed"] += num_consumed


    def ability_buy(self, ability_name, num_bought=1):
        record = self._ability_retrieve_record(ability_name)

        if record["items_consumed"] + record["items_available"] + num_bought > record["max_items"]:
            raise NormalUsageError(_("Impossible to get more than '%s' items altogether"))

        record["items_available"] += num_bought


    def ability_raise_limit(self, ability_name, num_more=1):

        record["max_items"] += num_more
'''

'''
    Abilities may be bought, used, and their maximum number changed
    according to game events.

    Ability record fields:
        items_consumed     # how many items are used and over (eg. scan operations completed)
        items_available     # how many items are ready for use, in a persistent (eg. listening slots) or temporary (eg. teleportations) way
        max_items     # limit value for (items_used+items_available)
        item_price     # how much it costs to have one more available item
        payment_types # tuple of values from ["gems", "money"]
'''
