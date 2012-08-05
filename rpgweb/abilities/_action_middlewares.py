# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *



ACTION_MIDDLEWARES = []

def register_action_middleware(klass):
    
    # class format checking is done here, since no metaclass is used
    assert set(klass.COMPATIBLE_ACCESSES) <= UserAccess.enum_values
    
    assert klass not in ACTION_MIDDLEWARES
    for _klass in ACTION_MIDDLEWARES:
        assert klass.__name__ != _klass.__name__
    ACTION_MIDDLEWARES.append(klass)



class AbstractActionMiddleware(object):
    
    COMPATIBLE_ACCESSES = None # must be overriden as a list of UserAccess entries, for which that middleware can be activated
    
    @classmethod
    def _setup_ability_settings(cls, settings):    
        super(AbstractActionMiddleware, None)._setup_ability_settings(settings)
        settings.setdefault("middlewares", PersistentDict()) # mapping action_name => dict of (middleware_name => data_dict) entries

    def _setup_private_ability_data(self, private_data):
        super(AbstractActionMiddleware, None)._setup_private_ability_data(private_data)
        private_data.setdefault("middlewares", PersistentDict())  # structure similar to midelware settings above

    def _check_data_sanity(self, strict=False):
        super(AbstractActionMiddleware, self)._check_data_sanity(strict=strict)
    
        if strict: 
            
            # we check that no unknown middleware is configured (could be a typo), and that activated middlewares are well compatible
            
            middleware_settings = self.ability_data["settings"]["middlewares"]
            middleware_private_data_packs = self.all_private_data["settings"]["middlewares"].values
            all_middleware_data_packs = [middleware_settings] + middleware_private_data_packs
            
            known_middleware_names_set = set([klass.__name__ for klass in ACTION_MIDDLEWARES])
            compatible_middleware_names_set = set([klass.__name__ for klass in ACTION_MIDDLEWARES if self.ACCESS in klass.COMPATIBLE_ACCESSES])
            
            for pack in all_middleware_data_packs:
                pack_keys = set(pack.keys())
                if strict:
                    assert pack_keys <= known_middleware_names_set, known_middleware_names_set - pack_keys # unknown middleware (typo ?)
                assert pack_keys <= compatible_middleware_names_set, compatible_middleware_names_set - pack_keys # middleware can't be used with that kind of ability ACCESS



    def get_all_middleware_settings(self, middleware_class):
        """
        Returns a list of middleware settings.
        """
        data_dicts = []
        for action_name, tree in self.settings["middlewares"].items():
            if middleware_class.__name__ in tree:
                data_dicts.append(tree[middleware_class.__name__])
        return data_dicts
    
    def get_middleware_settings(self, action_name, middleware_class):
        assert self.is_action_middleware_activated(action_name, middleware_class)
        middleware_settings = self.settings["middlewares"][action_name][middleware_class.__name__]
        return middleware_settings


    def get_all_private_middleware_data(self, middleware_class):
        """
        Returns a list of private middleware data dicts (those that have already
        been lazy-initialized, actually).
        """
        data_dicts = []
        for action_name, tree in self.private_data["middlewares"].items():
            if middleware_class.__name__ in tree:
                data_dicts.append(tree[middleware_class.__name__])
        return data_dicts
      
    def get_private_middleware_data(self, action_name, middleware_class, create_if_unexisting=False):
        assert self.is_action_middleware_activated(action_name, middleware_class)
        middleware_data = self.private_data["middlewares"]
        if create_if_unexisting:
            middleware_data.setdefault(PersistentDict())
            middleware_data[action_name].setdefault(action_name, PersistentDict()) 
        return middleware_data[action_name][middleware_class.__name__]
    
        
    def is_action_middleware_activated(self, action_name, middleware_class):
        """
        We assume a middleware is activated only if it has an entry in middleware settings 
        for that actions (even if that entry is None/empty).
        """
        return (action_name in self.settings["middlewares"] and
                middleware_class.__name__ in self.settings["middlewares"][action_name])

    
    def _lazy_setup_private_action_middleware_data(self, action_name):
        """
        To be overriden by each subclass.
        """
        pass 
    
    def process_action_through_middlewares(self, action_name, method, params):  
        """The chain of middleware processing ends here, by normal execution of the
        proper action callable."""
        return method(**params)





@register_action_middleware
class CostlyActionMiddleware(AbstractActionMiddleware):
    """
    Mix-in class that manages the purchase of items/services
    by characters, in an ability.
    
    settings::
    
        money_price: 115 (None if forbidden)
        gems_price: 234 (None if forbidden)
        
    private_data::
        
        <nothing>
        
    """
    
    ACTION_MIDDLEWARES = (UserAccess.character,)
    
    
    def _lazy_setup_private_action_middleware_data(self, action_name):
        super(CostlyActionMiddleware, self)._lazy_setup_private_action_middleware_data(action_name)
        if self.is_action_middleware_activated(action_name, CostlyActionMiddleware):
            data = self.get_private_middleware_data(self, action_name, CostlyActionMiddleware, create_if_unexisting=True)
            if not data:
                pass # nothing to store for that middleware, actually
                
                
    def _check_data_sanity(self, strict=False):
        super(CostlyActionMiddleware, self)._check_data_sanity(strict=strict)

        settings = self.settings
        for settings in self.get_all_middleware_settings(CostlyActionMiddleware):
            
            for setting in "money_price gems_price".split():
                if settings[setting] is not None: # None means "impossible to buy this way"
                    utilities.check_positive_int(settings[setting], non_zero=True)
            assert settings["money_price"] or settings["gems_price"] # at least one means must be offered
                
    def process_action_through_middlewares(self, action_name, method, params):     
        
        middleware_settings = self.get_middleware_settings(action_name, CostlyActionMiddleware)
        character_properties = self.get_character_properties(self.user.username)

        if middleware_settings["gems_price"] and "use_gems" not in params:
            self.logger.critical("Action %s was configured to be payable by gems, but no input field is available for this", action_name)
   
        if middleware_settings["gems_price"]:
            self._pay_with_gems(character_properties, middleware_settings, params.get("use_gems", ()))
        elif middleware_settings["money_price"]:
            self._pay_with_money(character_properties, middleware_settings)
        else:
            # shouldn't happen, due to sanity check above
            raise AbnormalUsageError(_("Sorry, due to a server misconfiguration, the payment of that asset couldn't be performed"))
                
    
    def _pay_with_gems(self, character_properties, middleware_settings, gems_list):
        
        gems_price = middleware_settings["gems_price"]
        assert gems_price
        
        if sum(gems_list) < gems_price:
            raise NormalUsageError(_("You need at least %(price)s kashes of gems to buy this asset") % SDICT(gems_price=gems_price))

        # we don't care if the player has given too many gems
        remaining_gems = utilities.substract_lists(character_properties["gems"], gems_list)

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
                         
        super(CostlyActionMiddleware, self).process_action_through_middlewares(action_name, method, params)
        
        
                
''' TO BE USED                
                
        utilities.check_is_bool(settings["assets_allow_duplicates"])        
        
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

        user = self.datamanager.user

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



    def is_private_action_middleware_data_uninitialized(self, action_name, middleware_class): 
        """
        Initialize base structures if required.
        Returns True iff private middleware data for that action is necessary AND not yet initialized.
        """
        if self.is_action_middleware_activated(self, action_name, middleware_class): 
            middleware_data = self.private_datar["middlewares"]
            middleware_data.setdefault(action_name, PersistentDict()) 
            if middleware_class. name_ not in middleware_data[action_name]: 
                middleware_data[action_name].setdefault(action_name, PersistentDict()) 
                return True 
        return False'''