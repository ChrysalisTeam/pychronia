# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from pychronia_game.common import *


from .datamanager_administrator import GameDataManager
from .datamanager_tools import readonly_method, transaction_watcher
from .abstract_game_view import GameViewMetaclass, AbstractGameView
from .action_middlewares import ACTION_MIDDLEWARES

from pychronia_game.utilities import resolving_decorator


class AbilityMetaclass(GameViewMetaclass, type):
    """
    Metaclass automatically registering the new ability (which is also a view) in a global registry.
    """
    def __init__(NewClass, name, bases, new_dict):

        super(AbilityMetaclass, NewClass).__init__(name, bases, new_dict)

        if not NewClass.__name__.startswith("Abstract"):
            GameDataManager.register_ability(NewClass)




# we us this syntax, because we can't dynamically assign a tuple of bases in a normal "class" definition
AbstractAbilityBases = tuple(reversed(ACTION_MIDDLEWARES)) + (AbstractGameView,) # middlewares FIRST, so that they can override game view stuffs...
AbstractAbilityBasesAdapter = AbilityMetaclass(str('AbstractAbilityBasesAdapter'), AbstractAbilityBases, {})



"""
print (">>>>>>>>>", AbstractAbilityBases)

for _base in AbstractAbilityBases:
    print (_base, type(_base))
    assert issubclass(AbilityMetaclass, type(_base))
"""


class AbstractAbility(AbstractAbilityBasesAdapter):

    ### Uses AbstractAbilityBases metaclass ###
    ### Inherits from action middlewares and AbstractGameView ###

    # NOT ATM - TITLE = None # menu title, use lazy gettext when setting

    def __init__(self, request, *args, **kwargs):
        super(AbstractAbility, self,).__init__(request, *args, **kwargs)
        self._ability_data = weakref.ref(self.datamanager.get_ability_data(self.NAME))

    @property
    def datamanager(self):
        return self # TRICK - abilities behaves as extensions of the datamanager!!



    # can't be a classmethod anymore because we need action middleware settings
    def _common_instantiate_form(self,
                                  new_action_name,
                                  form_options=None,
                                  **kwargs):
        final_form_options = self.get_game_form_extra_params(action_name=new_action_name)
        if form_options:
            final_form_options.update(form_options)
        del form_options
        return super(AbstractAbility, self)._common_instantiate_form(new_action_name=new_action_name,
                                                                     form_options=final_form_options,
                                                                     **kwargs)



    def _execute_game_action_with_middlewares(self, action_name, method, *args, **kwargs):
        assert "_test_" in action_name or method.__name__ == self.GAME_ACTIONS[action_name]["callback"], (action_name, method) # only in tests it could be false
        if __debug__: self.notify_event("EXECUTE_GAME_ACTION_WITH_MIDDLEWARES")

        # we transform the callback method so that it only expects keyword arguments (easier to deal with, in middleware chain)
        flattened_method = resolving_decorator.flatten_function_signature(method)
        params = resolving_decorator.resolve_call_args(flattened_method, *args, **kwargs)

        return self.process_action_through_middlewares(action_name=action_name, method=flattened_method, params=params)


    def _execute_game_action_callback(self, action_name, unfiltered_params):
        assert self.is_in_writing_transaction()
        if not self.has_action_middlewares_configured(action_name=action_name):
            # slight optimization, we bypass all the middlewares chain
            return super(AbstractAbility, self)._execute_game_action_callback(action_name=action_name,
                                                                              unfiltered_params=unfiltered_params)
        else:
            callback_name = self.GAME_ACTIONS[action_name]["callback"]
            (callback, relevant_args) = self._resolve_callback_callargs(callback_name=callback_name, unfiltered_params=unfiltered_params)
            return self._execute_game_action_with_middlewares(action_name=action_name, method=callback, **relevant_args)



    def _process_standard_request(self, request, *args, **kwargs):
        # Access checks have already been done here, so we may initialize lazy data
        self.perform_lazy_initializations()
        return super(AbstractAbility, self)._process_standard_request(request, *args, **kwargs)



    def __getattr__(self, name):
        assert not name.startswith("_") # if we arrive here, it's probably a typo in an attribute fetching
        try:
            value = getattr(self._inner_datamanager, name)
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
        """
        Also works for anonymous access (anonymous users share their data,
        whereas authenticated ones have their one data slot).
        """
        private_key = self._get_private_key()
        return self._ability_data()["data"][private_key]


    def _get_private_key(self):
        return self._inner_datamanager.user.username # can be guest/anonymous, or a character


    @property
    def all_private_data(self):
        return self._ability_data()["data"]


    def get_ability_parameter(self, name):
        try:
            return self.settings[name]
        except KeyError:
            msg = "Missing %s setting in view %s" % (name, self.NAME)
            raise RuntimeError(msg)

    '''
    @classmethod
    def get_menu_title(cls):
        return cls.TITLE

    @readonly_method
    def get_ability_summary(self):
        # FIXME - how does it work actually ?
        return self._get_ability_summary()


    def _get_ability_summary(self):
        """
        Summary for super user ?
        """
        raise NotImplementedError
    '''

    @classmethod
    def setup_main_ability_data(cls, ability_data):
        # no transaction handling here - it's all up to the caller of that classmethod
        ##print("setup_main_ability_data", cls.NAME)
        settings = ability_data.setdefault("settings", PersistentMapping())
        ability_data.setdefault("data", PersistentMapping())
        cls._setup_ability_settings(settings=settings) # FIRST
        cls._setup_action_middleware_settings(settings=settings) # SECOND


    @classmethod
    def _setup_ability_settings(cls, settings):
        pass # to be overridden


    @transaction_watcher(always_writable=True) # lazy setup is authorized anytime
    def perform_lazy_initializations(self):
        private_key = self._get_private_key()
        #print ("@@@@@@@@@@", self.ability_data)
        if not self.ability_data["data"].has_key(private_key):
            self.logger.warning("Setting up private data for '%s'", private_key)
            private_data = self.ability_data["data"].setdefault(private_key, PersistentMapping())
            self._setup_private_ability_data(private_data=private_data) # FIRST
            self._setup_private_action_middleware_data(private_data=private_data) # SECOND



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
            assert len(self.ability_data.keys()) == 2 # prevents misconfigurations
            available_logins = self._inner_datamanager.get_available_logins()
            for name, value in self.ability_data["data"].items():
                assert name in available_logins
                assert isinstance(value, collections.Mapping)

        self._check_action_middleware_data_sanity(strict=strict)
        self._check_data_sanity(strict=strict)


    def _check_data_sanity(self, strict=False):
        raise NotImplementedError("_check_data_sanity") # to be overridden





class AbstractPartnershipAbility(AbstractAbility):
    """
    An abstract ability offering some notion of "remote contact" (with automated email exchanges).
    """

    @property
    def dedicated_email(self):
        """
        Email address used to send fake automated "requests" to,
        and to send processing results from.
        """
        return self.get_ability_parameter("dedicated_email")

    @property
    def auto_answer_delay_mn(self):
        """
        Delay to send processing results back to the player.
        """
        return self.get_ability_parameter("result_delay")

    @readonly_method
    def check_data_sanity(self, strict=False):
        super(AbstractPartnershipAbility, self).check_data_sanity(strict=strict)

        assert self.ACCESS in (UserAccess.character, UserAccess.authenticated)  # WORKAROUND

        email = self.dedicated_email
        utilities.check_is_email(email)
        contact = self.datamanager.global_contacts[email]
        assert contact["initial"] # else game master might break all

        result_delay = self.auto_answer_delay_mn
        if result_delay is not None:
            utilities.check_is_range_or_num(result_delay)


    def _send_processing_request(self, subject, body, requires_manual_answer=False):
        """
        Returns the new message ID.
        """

        msg_id = self.post_message(sender_email=self.get_character_email(),
                                   recipient_emails=[self.dedicated_email],
                                   subject=subject,
                                   body=body,
                                   attachment=None,
                                   date_or_delay_mn=None, # immediate
                                   parent_id=None)
        if requires_manual_answer:
            pass
        else:
            self.set_dispatched_message_state_flags(username=self.master_login, msg_id=msg_id, has_read=True)

        self._last_request_msg_id = msg_id # for coherence checking
        return msg_id


    def _send_back_processing_result(self, parent_id, subject, body, attachment=None):
        """
        Returns the new message ID.
        """

        assert parent_id == self._last_request_msg_id # ATM always true

        msg_id = self.post_message(sender_email=self.dedicated_email,
                                   recipient_emails=[self.get_character_email()],
                                   subject=subject,
                                   body=body,
                                   attachment=attachment,
                                   date_or_delay_mn=self.auto_answer_delay_mn,
                                   parent_id=parent_id)
        return msg_id


    def _process_standard_exchange_with_partner(self, request_msg_data, response_msg_data=None):
        """
        Workflow from a standard request message, and (potentially) its auto-response.
        """

        auto_response_disabled = self.get_global_parameter("disable_automated_ability_responses")

        auto_response_must_occur = response_msg_data and not auto_response_disabled

        request_msg_id = self._send_processing_request(subject=request_msg_data["subject"],
                                                      body=request_msg_data["body"],
                                                      requires_manual_answer=not auto_response_must_occur)
        assert self.get_dispatched_message_by_id(request_msg_id)  # immediately sent

        response_msg_id = None
        if auto_response_must_occur:
            response_msg_id = self._send_back_processing_result(parent_id=request_msg_id,
                                                                 subject=response_msg_data["subject"],
                                                                 body=response_msg_data["body"],
                                                                 attachment=response_msg_data["attachment"])
        else:
            # we notify gamemaster that he MUST answer the request by himself
            self.set_dispatched_message_state_flags(username=self.master_login,
                                                    msg_id=request_msg_id,
                                                    has_starred=True)


        return (response_msg_id or request_msg_id)










'''
    def _instantiate_game_form(self,
                          new_action_name, 
                          hide_on_success=False,
                          previous_form_data=None, 
                          initial_data=None,
                          form_initializer=None):
        form_initializer = form_initializer if form_initializer else self # the ability behaves as an extended datamanager
        return super(AbstractAbility, self)._instantiate_game_form(new_action_name=new_action_name, 
                                                              hide_on_success=hide_on_success,
                                                              previous_form_data=previous_form_data,
                                                              initial_data=initial_data,
                                                              form_initializer=form_initializer) 
       '''







'''
    def _check_permissions(self):
        ###USELESS
        """
        This method should be called at django view level only, not from another ability
        method (unittests don't have to care about permissions).
        """
        user = self.datamanager.user
        
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
        self.__record = PersistentMapping(
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


    def ability_check_record_coherence(self, ability_name):
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
