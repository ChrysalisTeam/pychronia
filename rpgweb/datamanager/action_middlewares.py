# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals


from rpgweb.common import *
from rpgweb.datamanager.datamanager_tools import readonly_method



ACTION_MIDDLEWARES = []

def register_action_middleware(klass):

    # class format checking is done here, since no metaclass is used
    assert set(klass.COMPATIBLE_ACCESSES) <= set(UserAccess.enum_values)

    assert klass not in ACTION_MIDDLEWARES
    for _klass in ACTION_MIDDLEWARES:
        assert klass.__name__ != _klass.__name__
    ACTION_MIDDLEWARES.append(klass)

    return klass


def with_action_middlewares(action_name):
    # OBSOLETE DEPRECATED
    return lambda a: a


class AbstractActionMiddleware(object):

    COMPATIBLE_ACCESSES = None # must be overriden as a list of UserAccess entries, for which that middleware can be activated

    @classmethod
    def _setup_action_middleware_settings(cls, settings):
        """
        These methods must call their parent.
        """
        settings.setdefault("middlewares", PersistentDict()) # mapping action_name => dict of (middleware_name => data_dict) entries

    def _setup_private_action_middleware_data(self, private_data):
        """
        These methods must call their parent.
        """
        private_data.setdefault("middlewares", PersistentDict())  # structure similar to middleware settings above

    def _check_action_middleware_data_sanity(self, strict=False):
        """
        These methods must call their parent.
        """
        # we check that no unknown middleware is in settings or private data (could be a typo),
        # and that activated middlewares are well compatible with current ability (security measure)

        middleware_settings = self.settings["middlewares"].values()
        if "middlewares" in self.all_private_data:
            middleware_private_data_packs = self.all_private_data["middlewares"].values()
        else: # not yet lazy-initialized
            middleware_private_data_packs = []
        all_middleware_data_packs = middleware_settings + middleware_private_data_packs

        known_middleware_names_set = set([klass.__name__ for klass in ACTION_MIDDLEWARES])
        compatible_middleware_names_set = set([klass.__name__ for klass in ACTION_MIDDLEWARES if self.ACCESS in klass.COMPATIBLE_ACCESSES])

        for pack in all_middleware_data_packs:
            pack_keys = set(pack.keys())
            if strict:
                assert pack_keys <= known_middleware_names_set, known_middleware_names_set - pack_keys # unknown middleware (typo ?)
            assert pack_keys <= compatible_middleware_names_set, (pack_keys, compatible_middleware_names_set, self.ACCESS, known_middleware_names_set) # middleware can't be used with that kind of ability ACCESS


    def get_all_middleware_settings(self, middleware_class):
        """
        Returns a dict action_name => middleware settings) for that specific middleware_class.
        """
        action_settings_dicts = {}
        for action_name, tree in self.settings["middlewares"].items():
            if middleware_class.__name__ in tree:
                action_settings_dicts[action_name] = tree[middleware_class.__name__]
        return action_settings_dicts


    def get_middleware_settings(self, action_name, middleware_class):
        assert action_name and middleware_class
        assert self.is_action_middleware_activated(action_name, middleware_class)
        middleware_settings = self.settings["middlewares"][action_name][middleware_class.__name__]
        return middleware_settings


    def get_all_private_middleware_data(self, middleware_class, filter_by_action_name=None):
        """
        Returns a list of private middleware data dicts (those that have already
        been lazy-initialized, actually), for a specific middleware type, and
        for all "users" of that ability.
        
        Use *filter_by_action_name* to restrict the result to a specific action name, too.
        """
        assert middleware_class
        data_dicts = []
        for user_id, private_data in self.all_private_data.items():
            for action_name, tree in private_data.get("middlewares", {}).items():
                if filter_by_action_name is not None and filter_by_action_name != action_name:
                    continue
                if middleware_class.__name__ in tree:
                    data_dicts.append(tree[middleware_class.__name__])
        return data_dicts


    def get_private_middleware_data(self, action_name, middleware_class, create_if_unexisting=False):
        assert action_name and middleware_class
        assert self.is_action_middleware_activated(action_name, middleware_class)
        middleware_data = self.private_data["middlewares"]
        if create_if_unexisting:
            middleware_data.setdefault(action_name, PersistentDict())
            middleware_data[action_name].setdefault(middleware_class.__name__, PersistentDict())
        return middleware_data[action_name][middleware_class.__name__]


    def has_action_middlewares_activated(self, action_name):
        return (action_name in self.settings["middlewares"])


    def is_action_middleware_activated(self, action_name, middleware_class):
        """
        We assume a middleware is activated only if it has an entry in middleware settings 
        for that action (even if that entry is None/empty).
        """
        assert action_name
        res = (action_name in self.settings["middlewares"] and
                middleware_class.__name__ in self.settings["middlewares"][action_name])
        print("is_action_middleware_activated", action_name, middleware_class, res, "---------", self.settings) # FIXME REMOVE
        return res


    def _lazy_setup_private_action_middleware_data(self, action_name):
        """
        To be overriden by each subclass.
        """
        assert action_name


    def _process_action_through_middlewares(self, action_name, method, params):
        if __debug__: self.notify_event("TOP_LEVEL_PROCESS_ACTION_THROUGH_MIDDLEWARES")
        assert action_name
        return method(**params)


    def process_action_through_middlewares(self, action_name, method, params):
        """
        The chain of middleware processing ends here, by normal execution of the
        proper *method* callable (possibly a flattened version of thge original callback) 
        with the dict of arguments *params*.
        """
        self._lazy_setup_private_action_middleware_data(action_name=action_name)
        return self._process_action_through_middlewares(action_name=action_name, method=method, params=params)


    def _get_middleware_data_explanations(self, action_name):
        """
        Override this to agregate a list of lists/tuples of human-readable instruction strings.
        """
        return []


    @readonly_method
    def get_middleware_data_explanations(self, action_name):
        if not self.has_action_middlewares_activated(action_name=action_name):
            return []
        else:
            return self._get_middleware_data_explanations(action_name=action_name)


    @readonly_method
    def get_game_actions_explanations(self):
        """
        BEWARE - overrides AbstractGameView stuffs!
        """
        res = super(AbstractActionMiddleware, self).get_game_actions_explanations()
        for (action_name, action_data) in sorted(self.GAME_ACTIONS.items()): # sorted by IDENTIFIER order at the moment....
            explanations = self.get_middleware_data_explanations(action_name=action_name) # atm, we assume that ALWAYS at least 1 middelware class is merged into hierarchy...
            if explanations: # empty if no middlewares activated for that action_name
                res.append((action_data["title"], explanations))
        return res




@register_action_middleware
class CostlyActionMiddleware(AbstractActionMiddleware):
    """
    Mix-in class that manages the purchase of items/services
    by characters, in an ability.
    
    If payement by gem is activated, then the concerned action callable
    must accept a *use_gems* argument (list of gem values) in input.
    
    settings:
    
        money_price: 115 (None if forbidden)
        gems_price: 234 (None if forbidden)
        
    private_data:
        
        <nothing>
        
    """

    COMPATIBLE_ACCESSES = (UserAccess.character,)


    def _lazy_setup_private_action_middleware_data(self, action_name):
        super(CostlyActionMiddleware, self)._lazy_setup_private_action_middleware_data(action_name)
        if self.is_action_middleware_activated(action_name, CostlyActionMiddleware):
            data = self.get_private_middleware_data(action_name, CostlyActionMiddleware, create_if_unexisting=True)
            if not data:
                pass # nothing to store for that middleware, actually


    def _check_action_middleware_data_sanity(self, strict=False):
        super(CostlyActionMiddleware, self)._check_action_middleware_data_sanity(strict=strict)

        for _action_name_, settings in self.get_all_middleware_settings(CostlyActionMiddleware).items():

            for setting in "money_price gems_price".split():
                if settings[setting] is not None: # None means "impossible to buy this way"
                    utilities.check_is_positive_int(settings[setting], non_zero=True)
            assert settings["money_price"] or settings["gems_price"] # at least one means must be offered


    def _get_middleware_data_explanations(self, action_name):
        """
        Override this to agregate the whole list of huma-readable instruction strings.
        """

        other_instructions = super(CostlyActionMiddleware, self)._get_middleware_data_explanations(action_name)
        
        if self.is_action_middleware_activated(action_name, CostlyActionMiddleware):
            
            res = []
            middleware_settings = self.get_middleware_settings(action_name, CostlyActionMiddleware)

            if middleware_settings["money_price"] is not None:
                res.append(_("Cost when paying with money: %s kashes.") % middleware_settings["money_price"])
            else:
                res.append(_("Can't be bought with money."))

            if middleware_settings["gems_price"] is not None:
                res.append(_("Cost when paying with gems: %s kashes.") % middleware_settings["gems_price"])
            else:
                res.append(_("Can't be bought with gems."))

            assert res
            return [res] + other_instructions # list of lists of strings!

        else:
            return other_instructions

        assert False
        

    def _process_action_through_middlewares(self, action_name, method, params):

        if self.is_action_middleware_activated(action_name, CostlyActionMiddleware):

            middleware_settings = self.get_middleware_settings(action_name, CostlyActionMiddleware)

            if not middleware_settings["gems_price"] and not middleware_settings["money_price"]:
                pass # too bad misconfiguration, we let full action to that ability...
            else:
                use_gems = params.get("use_gems", ())

                # non-fatal coherency checks
                if middleware_settings["gems_price"] and "use_gems" not in params:
                    self.logger.critical("Action %s was configured to be payable by gems, but no input field is available for this : %r", action_name, params)
                if not middleware_settings["gems_price"] and use_gems:
                    self.logger.critical("Action %s was configured to be NOT payable by gems, but gems were sent via input field", action_name)
                    use_gems = ()

                character_properties = self.get_character_properties()

                if use_gems or not middleware_settings["money_price"]:
                    self._pay_with_gems(character_properties, middleware_settings, use_gems)
                else:
                    self._pay_with_money(character_properties, middleware_settings)

        return super(CostlyActionMiddleware, self)._process_action_through_middlewares(action_name=action_name, method=method, params=params)


    def _pay_with_gems(self, character_properties, middleware_settings, gems_list):
        gems_values = [i[0] for i in gems_list] if gems_list else []
        gems_price = middleware_settings["gems_price"]
        assert gems_price

        provided_gems_value = sum(gems_values) if gems_values else 0 # gems_list could be empty!!
        if (provided_gems_value < gems_price):
            raise NormalUsageError(_("You need at least %(gems_price)s kashes of gems to buy this asset") % SDICT(gems_price=gems_price))

        min_gem_value = min(gems_values) if gems_values else 0 # necessarily non-empty here
        if (provided_gems_value - gems_price) >= min_gem_value:
            raise NormalUsageError(_("You provided too many gems for the value of that asset, please top off") % SDICT(gems_price=gems_price))


        # we don't care if the player has given too many gems
        remaining_gems = utilities.substract_lists(character_properties["gems"], gems_list)

        if remaining_gems is None:
            raise AbnormalUsageError(_("You don't possess the gems required")) # shouldn't happen since we use a form
        else:
            character_properties["gems"] = PersistentList(remaining_gems)
            self.data["global_parameters"]["spent_gems"] += gems_list


    def _pay_with_money(self, character_properties, middleware_settings):
        money_price = middleware_settings["money_price"]
        assert money_price
        #print("PAYING WITH", money_price)

        if character_properties["account"] < money_price:
            raise NormalUsageError(_("You need at least %(price)s kashes in money to buy this asset") % SDICT(price=money_price))

        character_properties["account"] -= money_price
        self.data["global_parameters"]["bank_account"] += money_price



@register_action_middleware
class CountLimitedActionMiddleware(AbstractActionMiddleware):
    """
    Mix-in class that limits the count of uses of an action,
    on a global or per-player basis.

    settings::
    
        max_per_character: 3 (None if no limit is set)
        max_per_game: 6 (None if no limit is set)
        
    private_data::
        
        private_usage_count: 3
        
    """

    COMPATIBLE_ACCESSES = (UserAccess.character,)


    def _lazy_setup_private_action_middleware_data(self, action_name):
        super(CountLimitedActionMiddleware, self)._lazy_setup_private_action_middleware_data(action_name)
        if self.is_action_middleware_activated(action_name, CountLimitedActionMiddleware):

            data = self.get_private_middleware_data(action_name, CountLimitedActionMiddleware, create_if_unexisting=True)
            if not data:
                data.setdefault("private_usage_count", 0)


    def _check_action_middleware_data_sanity(self, strict=False):
        super(CountLimitedActionMiddleware, self)._check_action_middleware_data_sanity(strict=strict)

        settings = self.settings
        for action_name, settings in self.get_all_middleware_settings(CountLimitedActionMiddleware).items():

            assert settings["max_per_character"] is not None or settings["max_per_game"] is not None # else misconfiguration

            if settings["max_per_character"] is not None:
                utilities.check_is_positive_int(settings["max_per_character"], non_zero=True)
                for data in self.get_all_private_middleware_data(CountLimitedActionMiddleware, filter_by_action_name=action_name):
                    assert data["private_usage_count"] <= settings["max_per_character"]

            if settings["max_per_game"] is not None:
                utilities.check_is_positive_int(settings["max_per_game"], non_zero=True)
                assert self._get_global_usage_count(action_name) <= settings["max_per_game"]


    def _get_middleware_data_explanations(self, action_name):
        """
        Override this to agregate the whole list of huma-readable instruction strings.
        """
        other_instructions = super(CountLimitedActionMiddleware, self)._get_middleware_data_explanations(action_name)


        if self.is_action_middleware_activated(action_name, CountLimitedActionMiddleware):

            res = []
            middleware_settings = self.get_middleware_settings(action_name, CountLimitedActionMiddleware)

            if middleware_settings["max_per_game"] is not None:
                res.append(_("Total units available: %s.") % middleware_settings["max_per_game"])
                res.append(_("Tital units already used: %s.") % self._get_global_usage_count(action_name))

            if middleware_settings["max_per_character"] is not None:
                res.append(_("Units available per user: %s.") % middleware_settings["max_per_character"])

            # in ANY case
            try:
                private_data = self.get_private_middleware_data(action_name, CountLimitedActionMiddleware, create_if_unexisting=False) # important
                units_consumed = private_data["private_usage_count"]
            except LookupError: # user has never used that action
                units_consumed = 0
            res.append(_("Units already consumed by yourself: %s.") % units_consumed)

            assert res
            return [res] + other_instructions # list of lists of strings!

        else:
            return other_instructions

        assert False


    def _get_global_usage_count(self, action_name):
        data_dicts = self.get_all_private_middleware_data(middleware_class=CountLimitedActionMiddleware,
                                                          filter_by_action_name=action_name)
        global_usage_count = sum(data["private_usage_count"] for data in data_dicts)
        return global_usage_count


    def _process_action_through_middlewares(self, action_name, method, params):

        if self.is_action_middleware_activated(action_name, CountLimitedActionMiddleware):

            middleware_settings = self.get_middleware_settings(action_name, CountLimitedActionMiddleware)
            private_data = self.get_private_middleware_data(action_name, CountLimitedActionMiddleware) # MUST EXIST HERE

            if middleware_settings["max_per_game"]: # 0 <-> None
                if self._get_global_usage_count(action_name) >= middleware_settings["max_per_game"]:
                    raise NormalUsageError(_("You have exceeded the global quota (%(max_per_game)s uses) for that asset") % SDICT(max_per_game=middleware_settings["max_per_game"]))

            if middleware_settings["max_per_character"]: # 0 <-> None
                if private_data["private_usage_count"] >= middleware_settings["max_per_character"]:
                    raise NormalUsageError(_("You have exceeded your quota (%(max_per_character)s uses) for that asset") % SDICT(max_per_character=middleware_settings["max_per_character"]))

            private_data["private_usage_count"] += 1 # important

        return super(CountLimitedActionMiddleware, self)._process_action_through_middlewares(action_name=action_name, method=method, params=params)








@register_action_middleware
class TimeLimitedActionMiddleware(AbstractActionMiddleware):
    """
    Mix-in class that limits the use of an action per period of time.

    settings::
    
        waiting_period_mn: 3 (None if no limit is set)
        max_uses_per_period: 2
        
    private_data::
        
        last_use_times: array of datetimes
        
    """
    COMPATIBLE_ACCESSES = (UserAccess.character,)


    def _lazy_setup_private_action_middleware_data(self, action_name):
        super(TimeLimitedActionMiddleware, self)._lazy_setup_private_action_middleware_data(action_name)
        if self.is_action_middleware_activated(action_name, TimeLimitedActionMiddleware):

            data = self.get_private_middleware_data(action_name, TimeLimitedActionMiddleware, create_if_unexisting=True)
            if not data:
                data.setdefault("last_use_times", PersistentList())


    def _check_action_middleware_data_sanity(self, strict=False):
        super(TimeLimitedActionMiddleware, self)._check_action_middleware_data_sanity(strict=strict)

        settings = self.settings
        now = datetime.utcnow()

        for action_name, settings in self.get_all_middleware_settings(TimeLimitedActionMiddleware).items():

            # all these settings must be > 0 !!
            utilities.check_is_positive_float(settings["waiting_period_mn"], non_zero=True)
            utilities.check_is_positive_float(settings["max_uses_per_period"], non_zero=True)

            for data in self.get_all_private_middleware_data(TimeLimitedActionMiddleware, filter_by_action_name=action_name):
                last_uses = data["last_use_times"]
                utilities.check_is_list(last_uses)
                assert len(last_uses) <= settings["max_uses_per_period"] # must be ensured even if setting changes!
                for item in last_uses:
                    assert isinstance(item, datetime)
                    assert item <= now


    def _get_middleware_data_explanations(self, action_name):
        """
        Override this to agregate the whole list of huma-readable instruction strings.
        """

        other_instructions = super(TimeLimitedActionMiddleware, self)._get_middleware_data_explanations(action_name)

        if self.is_action_middleware_activated(action_name, TimeLimitedActionMiddleware):

            res = []
            middleware_settings = self.get_middleware_settings(action_name, TimeLimitedActionMiddleware)

            res.append(_("This action can be performed %s time(s) every %s minutes.") %
                        (middleware_settings["max_uses_per_period"], middleware_settings["waiting_period_mn"]))

            if middleware_settings["waiting_period_mn"] and middleware_settings["max_uses_per_period"]: # in case of misconfiguration
                try:
                    private_data = self.get_private_middleware_data(action_name, TimeLimitedActionMiddleware, create_if_unexisting=False) # important
                    blocking_times = self._computed_purge_old_use_times(middleware_settings=middleware_settings, last_use_times=private_data["last_use_times"])
                except LookupError: # user has never used that action
                    blocking_times = ()
            else:
                blocking_times = ()
                
            res.append(_("In this last period, you've done it %s time(s).") % len(blocking_times))

            assert res
            return [res] + other_instructions # list of lists of strings!

        else:
            return other_instructions

        assert False





    def _computed_purge_old_use_times(self, middleware_settings, last_use_times):
        """
        Returns a copied list, with non-outdated last use dates.
        """
        threshold = self.compute_remote_datetime(delay_mn= -middleware_settings["waiting_period_mn"]) # in the past
        purged_old_use_times = [dt for dt in last_use_times if dt > threshold]
        return PersistentList(purged_old_use_times)
        #res = bool(len(purged_old_use_times) < len(last_use_times))
        ##private_data["last_use_times"] = PersistentList(purged_old_use_times)
        #return res


    def _process_action_through_middlewares(self, action_name, method, params):

        if self.is_action_middleware_activated(action_name, TimeLimitedActionMiddleware):

            middleware_settings = self.get_middleware_settings(action_name, TimeLimitedActionMiddleware)
            private_data = self.get_private_middleware_data(action_name, TimeLimitedActionMiddleware) # MUST EXIST

            if middleware_settings["waiting_period_mn"] and middleware_settings["max_uses_per_period"]: # in case of misconfiguration

                private_data["last_use_times"] = self._computed_purge_old_use_times(middleware_settings=middleware_settings, last_use_times=private_data["last_use_times"])

                last_use_times = private_data["last_use_times"]
                now = datetime.utcnow() # to debug
                if len(last_use_times) >= middleware_settings["max_uses_per_period"]:
                    raise NormalUsageError(_("You must respect a waiting period to use that asset."))

            private_data["last_use_times"].append(datetime.utcnow()) # updated in any case

        return super(TimeLimitedActionMiddleware, self)._process_action_through_middlewares(action_name=action_name, method=method, params=params)






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


        player_properties = self.get_character_properties()

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
