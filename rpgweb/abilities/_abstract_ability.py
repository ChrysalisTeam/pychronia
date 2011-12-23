# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *

from django.http import HttpResponse
from django.shortcuts import render_to_response
from django.template import RequestContext, loader

from ..datamanager import *
from rpgweb.datamanager.datamanager_tools import NormalUsageError, AbnormalUsageError, PermissionError




###### NOTE - To specify dynamic initial data, see the Form.initial parameter. TODO



### Abstract types and miscellaneous utilities ###







'''
@decorator.decorator
def transaction_watcher(func, self, *args, **kwargs): # TODO DUPLICATED !!

    # TO BE REMOVED !!!!!!!!!!!!!!
    #self._datamanager._check_database_coherency() # WARNING - quite CPU intensive, to be removed later on ? TODO TODO REMOVE PAKAL !!!

    if self._datamanager.is_shutdown:
        raise AbnormalUsageError(_("ZODB connection has been definitely shutdown - please finish killing the server process!"))
    if not self._datamanager.is_ini    tialized:
        raise AbnormalUsageError(_("Game databases haven't yet been initialized !"))
    if not self._datamanager.get_global_parameter("game_is_started"):
        # some state-changing methods are allowed even before the game starts !
        if func.__name__ not in ["set_message_read_state", "set_new_message_notification", "force_message_sending", "set_online_status"]:
            raise UsageError(_("This feature is unavailable at the moment, since the game isn't started"))

    try:
        res = func(self, *args, **kwargs)
        #self._datamanager._check_database_coherency() # WARNING - quite CPU intensive, to be removed later on ? TODO TODO REMOVE PAKAL !!!
        self._datamanager.commit_all()
    except Exception:
        self._datamanager.abort_all()
        raise
    return res



@contextmanager
def action_failure_handler(request, success_message=None):
    """
    Context manager handling success/error messages when a game action is performed,
    depending on *success_message* (which could be None) and potential exceptions encountered.
    """
    
    user = request.datamanager.user
    
    # nothing in __enter__()
    try:
        yield None
    except UsageError, e:
        if isinstance(e, AbnormalUsageError):
            logging.critical(repr(e))
        user.add_error(unicode(e))
    except Exception, e:
        # we must localize this serious error, since often (eg. assertion errors) there is no specific message attached...
        msg = repr(e)+" - " + traceback.format_exc()
        logging.critical(msg)
        if config.DEBUG:
            user.add_error(msg)
        else:
            user.add_error(_("An internal error occurred"))
    else:
        if success_message: # might be left empty sometimes, if a more precise message must be built during action
            user.add_message(success_message)

'''




class AbstractAbilityForm(forms.Form):
    """
    Base class for ability forms,
    adding some predefined fields.
    """

    _ability_field = "_ability_form"

    def __init__(self, datamanager, *args, **kwargs):
        super(AbstractAbilityForm, self).__init__(*args, **kwargs)
        self._datamanager = datamanager
        self.fields.insert(0, self.__class__._ability_field, forms.CharField(initial=self._get_dotted_class_name(),
                                                  widget=forms.HiddenInput))
        self.target_url = "" # by default we stay on the same page


    @classmethod
    def _get_dotted_class_name(cls):
        return "%s.%s" % (cls.__module__, cls.__name__)

    @classmethod
    def matches(cls, post_data):
        if post_data.get(cls._ability_field, None) == cls._get_dotted_class_name():
            return True
        return False

    def get_normalized_values(self):
        values = self.cleaned_data.copy()
        del values[self._ability_field]
        return values



class AbstractAbilityMetaclass(type):
    """
    Metaclass automatically registering the new ability in a global registry.
    """
    def __init__(NewClass, name, bases, new_dict):

        if NewClass.__name__ != "AbstractAbilityHandler":

            if __debug__:

                RESERVED_NAMES = AbstractAbilityHandler.__dict__.keys()

                assert utilities.check_is_slug(NewClass.NAME)
                assert utilities.check_is_lazy_object(NewClass.TITLE) # delayed translation
                assert NewClass.ACCESS in ["master", "player", "authenticated", "anonymous"]
                if NewClass.ACCESS != "player":
                    assert not NewClass.REQUIREMENTS
                assert loader.get_template(NewClass.TEMPLATE)

                def _check_callback(name):
                    assert getattr(NewClass, callback)
                    assert callback not in RESERVED_NAMES
                    assert not callback.startswith("_")

                for (form_name, (FormClass, callback)) in NewClass.FORMS.items():
                    assert issubclass(FormClass, AbstractAbilityForm)
                    _check_callback(callback)
                for (action_name, callback) in NewClass.ACTIONS.items():
                    _check_callback(callback)

            assert not GameDataManager.ABILITIES_REGISTRY.has_key(NewClass.NAME), NewClass.NAME
            GameDataManager.ABILITIES_REGISTRY[NewClass.NAME] = NewClass # we register the ability


'''
@decorator.decorator
def inject_ability_context(func, self, *args, **kwargs):
    full_kwargs = inspect.getcallargs(func, self, *args, **kwargs)
    if "settings" in full_kwargs and full_kwargs["settings"] is None:
        full_kwargs["settings"] = self.ability_data["settings"]
    if "private_data" in full_kwargs and full_kwargs["private_data"] is None:
        private_key = self._get_private_key()
        full_kwargs["private_data"] = self.ability_data[private_key]
    return func(**full_kwargs)
'''

class AbstractAbilityHandler(object):

    __metaclass__ = AbstractAbilityMetaclass

    NAME = None # slug to be overridden, used as primary identifier
    TITLE = None # menu title, use lazy gettext when setting

    FORMS = {} # dict mapping form identifiers to tuples (form class, processing method name)
    ACTIONS = {} # dict mapping action identifiers to processing method names

    TEMPLATE = "" # HTML template name

    ACCESS = None # "master", "player", "authenticated" (player or master) or "anonymous"
    REQUIREMENTS = [] # list of required permission names, only for "player" access



    _action_field = "_action_" # for ajax and no-form request



    def __init__(self, datamanager, ability_data):
        self.__datamanager = weakref.ref(datamanager)
        self._ability_data = weakref.ref(ability_data)
        self.logger = logging.getLogger("abilities")
        self._perform_lazy_initializations()


    @property
    def _datamanager(self):
        return self.__datamanager() # could be None

    def __getattr__(self, name):
        assert not name.startswith("_") # if we arrive here, it's probably a typo in an attribute fetching
        
        try:
            value = getattr(self._datamanager, name)
        except AttributeError:
            raise AttributeError("Neither ability nor datamanager have attribute '%s'" % name)
        return value

 
    def _check_permissions(self):
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





    @property
    def ability_data(self):
        return self._ability_data() # could be None


    @property
    def settings(self):
        return self._ability_data()["settings"]


    @property
    def private_data(self):
        assert self._datamanager.user.is_character
        private_key = self._get_private_key()
        return self._ability_data()["data"][private_key]

    @property
    def all_private_data(self):
        return self._ability_data()["data"]


    def get_ability_parameter(self, name):
        return self.settings[name]


    def get_master_summary(self):
        # should return a dict of variables to be displayed in the "master summary" template
        raise NotImplementedError


    def _instantiate_form(self,
                          new_form_name, # id of the form to be potentially instantiated
                          hide_on_success=False, # should we return None if this form has just been submitted successfully?
                          previous_form_name=None, previous_form_instance=None, previous_form_successful=None, # data about previously submitted form, if any
                          initial_data=None
                          ):

        NewFormClass = self.FORMS[new_form_name][0]

        if __debug__:
            form_data = (previous_form_name, previous_form_instance, (previous_form_successful is not None))
            assert all(form_data) or not any(form_data)

        if new_form_name == previous_form_name:
            # this particular form has just been submitted
            if previous_form_successful:
                if hide_on_success:
                    return None
                else:
                    pass

            else:
                return previous_form_instance # atm we ALWAYS redisplay a failed form
        else:
            pass

        form = NewFormClass(self._datamanager, initial=initial_data)

        return form


    def get_template_vars(self, previous_form_name=None, previous_form_instance=None, previous_form_successful=None):
        raise RuntimeError("Unimplemented get_template_vars in %s" % self)



    @classmethod
    def get_menu_title(cls):
        return cls.TITLE

    @readonly_method
    def get_ability_summary(self):
        return self._get_ability_summary()

    def _get_ability_summary(self):
        """
        Summary for master
        """
        raise NotImplementedError


    def process_request(self, request):

        self._check_permissions()

        #if not self.datamanager.player.has_permission(self.NAME): #TODO
        #    raise RuntimeError("Player has no permission to use ability")

        if request.is_ajax() or request.GET.get(self._action_field, None):
            return self._process_ajax_request(request.REQUEST) # TODO REMOVE EVENTUALLY
        else:
            return self._process_html_request(request)


    def _process_ajax_request(self, data):
        res = self._try_processing_action(data) # we let exceptions flow atm
        return HttpResponse(res)


    def _process_html_request(self, request):

        user = self.user

        previous_form_data = {}

        if request.method == "POST":
            data = request.POST

            if data.get("_action_", None): # manually built form
                with action_failure_handler(request, success_message=None): # only for unhandled exceptions
                    self._try_processing_action(data)

            else: # it must be a call using django newforms
                for (form_name, (FormClass, action_name)) in self.FORMS.items():
                    if FormClass.matches(data): # class method
                        bound_form = FormClass(self._datamanager, data=data)
                        form_successful = False
                        if bound_form.is_valid():
                            with action_failure_handler(request, success_message=None): # only for unhandled exceptions
                                action = getattr(self, action_name)

                                relevant_args = utilities.adapt_parameters_to_func(bound_form.get_normalized_values(), action)
                                success_message = action(**relevant_args)

                                form_successful = True
                                if not isinstance(success_message, basestring):
                                    logging.error("Action %s returned wrong success message: %r", action_name, success_message)
                                    user.add_message(_("Operation successful")) # default msg
                                else:
                                    user.add_message(success_message)
                        else:
                            user.add_error(_("Submitted data is invalid"))
                        previous_form_data = dict(previous_form_name=form_name,
                                                  previous_form_instance=bound_form,
                                                  previous_form_successful=form_successful)
                        break # IMPORTANT
                else:
                    user.add_error(_("Submitted form data hasn't been recognized"))
                    logging.error("Unexpected form data sent to %s - %r" % (self.NAME, request.POST))


        template_vars = self.get_template_vars(**previous_form_data)

        if not isinstance(template_vars, collections.Mapping):
            raise RuntimeError("WRONG TEMPLATE VARS %r" % template_vars) #DEBUG TODO remove
        #print ("Rendering with", template_vars, user.__dict__)
        response = render_to_response(self.TEMPLATE,
                                      template_vars,
                                      context_instance=RequestContext(request))
        return response


    def _try_processing_action(self, data):
        func = getattr(self, self.ACTIONS[data[self._action_field]])
        relevant_args = utilities.adapt_parameters_to_func(data, func)
        res = func(**relevant_args)
        return res



    def _get_private_key(self):
        assert self._datamanager.user.is_character # game master has no private storage here atm
        return self._datamanager.user.username



    @classmethod
    def setup_main_ability_data(cls, ability_data):
        # no transaction handling here - it's all up to the caller of that classmethod
        settings = ability_data.setdefault("settings", PersistentDict())
        ability_data.setdefault("data", PersistentDict())
        cls._setup_ability_settings(settings=settings)

    @classmethod
    def _setup_ability_settings(cls, settings):
        pass # to be overridden



    """
    def _____get_action_contexts(self): #TODO REMOVE
        private_key = self._get_private_key()
        if private_key:
            private_data = self.ability_data[private_key]
        else:
            private_data = None
        return (self.ability_data["settings"], private_data)
    """

    @transaction_watcher
    def _perform_lazy_initializations(self):

        user = self._datamanager.user

        if not user.is_character:
            return # nothing to do

        private_key = self._get_private_key()
        if not self.ability_data.has_key(private_key):
            self.logger.debug("Setting up private data %s", private_key)
            private_data = self.ability_data["data"].setdefault(private_key, PersistentDict())
            self._setup_private_ability_data(private_data=private_data)


    def _setup_private_ability_data(self, private_data):
        """
        Not called in the case of game-level abilities
        """
        pass # to be overridden

    @readonly_method
    def check_data_sanity(self, strict=False):

        # self.logger.debug("Checking data sanity")

        assert isinstance(self.ability_data["settings"], collections.Mapping), self.ability_data["settings"]
        assert isinstance(self.ability_data["data"], collections.Mapping), self.ability_data["data"]

        if strict:
            for name, value in self.ability_data["data"].items():
                if self.LEVEL == "player":
                    assert name in self._datamanager.get_character_names()
                elif self.LEVEL == "domain":
                    assert name in self._datamanager.get_domain_names()
                else:
                    assert name == "global"
                assert isinstance(value, collections.Mapping)

        self._check_data_sanity(strict=strict)


    def _check_data_sanity(self, strict=False):
        pass # to be overridden









class PayableAbilityHandler(object):
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
            raise PermissionError(_("Only regular users may purchase items and services")) # shouldn't happen

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
