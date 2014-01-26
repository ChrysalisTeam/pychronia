# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

import string
from pychronia_game.common import *
from pychronia_game.common import _, ugettext_lazy, ugettext_noop, _undefined # mainly to shut up the static checker...

from .datamanager_tools import *
from .datamanager_user import GameUser
from .datamanager_core import BaseDataManager
from .data_table_manager import *
from persistent.list import PersistentList

PLACEHOLDER = object()


MODULES_REGISTRY = [] # IMPORTANT



def register_module(Klass):
    MODULES_REGISTRY.append(Klass)
    return Klass



VISIBILITY_REASONS = Enum([ugettext_noop("sender"),
                           ugettext_noop("recipient"),
                           ugettext_noop("interceptor")]) # tokens identifying why one can see an email


@register_module
class GameGlobalParameters(BaseDataManager):

    def _load_initial_data(self, **kwargs):
        super(GameGlobalParameters, self)._load_initial_data(**kwargs)

        game_data = self.data

        game_data["global_parameters"]["world_map_image"] = os.path.normpath(game_data["global_parameters"]["world_map_image"])
        game_data["global_parameters"]["world_map_image_bw"] = os.path.normpath(game_data["global_parameters"]["world_map_image_bw"])

    def _check_database_coherency(self, **kwargs):
        super(GameGlobalParameters, self)._check_database_coherency(**kwargs)

        game_data = self.data
        utilities.check_is_bool(game_data["global_parameters"]["game_is_started"])

        utilities.check_is_game_file(game_data["global_parameters"]["world_map_image"])
        utilities.check_is_game_file(game_data["global_parameters"]["world_map_image_bw"])
        assert game_data["global_parameters"]["world_map_image"] != game_data["global_parameters"]["world_map_image_bw"]

        utilities.check_is_string(game_data["global_parameters"]["game_random_seed"], multiline=False)


    @readonly_method
    def get_global_parameters(self):
        return self.data["global_parameters"]

    @readonly_method
    def get_global_parameter(self, name):
        return self.data["global_parameters"][name]

    @transaction_watcher
    def set_global_parameter(self, name, value):
        assert self.is_master()
        if name not in self.data["global_parameters"]:
            raise AbnormalUsageError(_("Unexisting setting %s") % name)
        self.data["global_parameters"][name] = value


    @readonly_method
    def is_game_started(self):
        """
        This is meant to block players, not master or other "back office" actors.
        """
        return self.get_global_parameter("game_is_started")

    @transaction_watcher(always_writable=True) # for testing mainly
    def set_game_state(self, started):
        self.data["global_parameters"]["game_is_started"] = started



CURRENT_USER = object() # placeholder for use in method signatures

@register_module
class CurrentUserHandling(BaseDataManager):
    """
    Initial setup of self.user, and useful hooks and proxies for 
    current user handling.
    """

    def _init_from_db(self, **kwargs):
        super(CurrentUserHandling, self)._init_from_db(**kwargs)
        self.user = None
        self._set_user(username=None) # TODO - improve by doing player authentication at init time?


    def _notify_user_change(self, username, **kwargs):
        assert not hasattr(super(CurrentUserHandling, self), "_notify_user_change") # we're well top-level here


    @transaction_watcher(always_writable=True)
    def _set_user(self, username, impersonation_target=None, impersonation_writability=False, is_superuser=False):
        assert not hasattr(super(CurrentUserHandling, self), "_set_user") # we're well top-level here
        self.user = GameUser(datamanager=self,
                             username=username,
                             impersonation_target=impersonation_target,
                             impersonation_writability=impersonation_writability,
                             is_superuser=is_superuser) # might raise UsageError
        del username
        self._notify_user_change(username=self.user.username) # might have been normalized, eg. None -> anonymous_login

        return self.user


    def _resolve_username(self, username):
        if username is None:
            raise RuntimeError("Wrong username==None detected")
        if username == CURRENT_USER:
            return self.user.username
        return username


    @readonly_method # TODO FIXME TEST THIS UTIL!!
    def determine_actual_game_writability(self):
        if not self.user.has_write_access:
            assert self.user.is_impersonation # only case ATM
            return dict(writable=False,
                        reason=_("Your impersonation is in read-only mode."))
        else:
            if self.is_master() or self.is_game_started(): # master is NOT impacted by game state
                return dict(writable=True,
                            reason=_("Beware, your impersonation is in writable mode.") if self.user.is_impersonation else None)
            else:
                assert not self.is_master()
                return dict(writable=False,
                            reason=_("Website currently in read-only mode, for maintenance."))
        assert False

    @readonly_method
    def is_game_writable(self):
        """Summary between the state of the game, and the permissions of current user!"""
        return self.determine_actual_game_writability()["writable"]



@register_module
class FlexibleTime(BaseDataManager): # TODO REFINE
    """
    All delays set in the game, in minutes, should be scaled
    as if the whole game lasted only 24 full hours, then these settings scale that duration up or down.
     
    To be used for scheduled actions, delayed email sendings etc.
    """

    def _load_initial_data(self, **kwargs):
        super(FlexibleTime, self)._load_initial_data(**kwargs)


    def _check_database_coherency(self, **kwargs):
        super(FlexibleTime, self)._check_database_coherency(**kwargs)
        utilities.check_is_positive_float(self.get_global_parameter("game_theoretical_length_days"), non_zero=True)


    @readonly_method
    def compute_effective_delay_s(self, delay_mn):
        """
        Components of delay_mn can be negative or zero, too.
        """
        # IMPORTANT - we assume a standard game is actually 1 day long!
        factor_to_s = self.get_global_parameter("game_theoretical_length_days") * 60

        if not isinstance(delay_mn, (int, long, float)):
            assert len(delay_mn) == 2

            delay_s_min = int(delay_mn[0] * factor_to_s)
            delay_s_max = int(delay_mn[1] * factor_to_s)
            assert delay_s_min <= delay_s_max, "delay min must be < delay max - %s vs %s" % (delay_s_min, delay_s_max)

            delay_s = random.randint(delay_s_min, delay_s_max) # time range in seconds

        else:
            assert isinstance(delay_mn, (float, int, long)) # can be negative or zero
            delay_s = delay_mn * factor_to_s # no need to coerce to integer here

        return delay_s


    @readonly_method
    def compute_effective_remote_datetime(self, delay_mn):
        """"
        delay_mn can be a number or a range (of type int or float, positive or negative)
        
        We always work in UTC
        """

        new_time = datetime.utcnow()
        # print (">>>>>>>>>>>>>>>>>> DATETIME", new_time, "WITH DELAYS", delay_mn)

        if delay_mn:
            actual_delay_s = self.compute_effective_delay_s(delay_mn=delay_mn)
            # print "DELAY ADDED : %s s" % delay_s
            new_time += timedelta(seconds=actual_delay_s) # delay_s can be a float

        assert isinstance(new_time, datetime)
        return new_time



@register_module
class GameEvents(BaseDataManager): # TODO REFINE


    def _load_initial_data(self, **kwargs):
        super(GameEvents, self)._load_initial_data(**kwargs)

        game_data = self.data
        game_data.setdefault("events_log", PersistentList())
        for evt in game_data["events_log"]:
            if isinstance(evt["time"], (long, int, float)): # NEGATIVE offset in minutes
                assert evt["time"] <= 0
                evt["time"] = self.compute_effective_remote_datetime(delay_mn=evt["time"])
        game_data["events_log"].sort(key=lambda evt: evt["time"])


    def _check_database_coherency(self, **kwargs):
        super(GameEvents, self)._check_database_coherency(**kwargs)

        event_reference = {
            "time": datetime,
            "message": basestring, # TRANSLATED message
            "substitutions": (types.NoneType, PersistentDict),
            "url": (types.NoneType, basestring),
            "username": (types.NoneType, basestring)
        }
        previous_time = None
        for event in self.data["events_log"]:
            assert event["message"]
            if previous_time:
                assert previous_time <= event["time"] # event lists are sorted by chronological order
            previous_time = event["time"] # UTC time
            utilities.check_dictionary_with_template(event, event_reference)
            username = event["username"]

            # test is a little brutal, if we reset master login it might fail...
            assert username in self.get_character_usernames() or \
                    username == self.get_global_parameter("master_login") or \
                    username == self.get_global_parameter("anonymous_login")

    @transaction_watcher
    def log_game_event(self, message, substitutions=None, url=None):
        """
        Message must be an UNTRANSLATED string, since we handle translation directly in this class.
        """
        assert message, "log message must not be empty"
        utilities.check_is_string(message) # no lazy objects

        message = _(message) # TODO - force language to "official game language", not "user interface language"

        if substitutions:
            assert isinstance(substitutions, PersistentDict), (message, substitutions)
            if config.DEBUG:
                message % substitutions # may raise formatting errors if corrupt...
        else:
            assert "%(" not in message, "Message %s needs substitution arguments" % message
            pass

        utcnow = datetime.utcnow() # NAIVE UTC datetime

        record = PersistentDict({
            "time": utcnow,
            "message": message, # TRANSLATED message !
            "substitutions": substitutions,
            "url": url,
            "username": self.user.username
            # FIXME - add impersonation data here!!
        })
        self.data["events_log"].append(record)

    @readonly_method
    def get_game_events(self):
        return self.data["events_log"]





@register_module
class NovaltyTracker(BaseDataManager):
    """
    
    # Actually depends on CharacterHandling... #
    
    Tracks the *resources* (references by a unique key) that each authenticated 
    player (and the game master) has, or not, already "accessed".
    
    Useful for new help pages, new radio playlists, new menu entries...
    
    Tracking objects are lazily created, only the first time a resource is accessed.
    
    That registry can be used on a cumulative way (giving a new name to each different
    version of a resource), or "limited" way, creating/deleting the same novelty token
    when the underlying resource has new data for users.
    """

    _default_novelty_category = u"default"

    def _load_initial_data(self, **kwargs):
        super(NovaltyTracker, self)._load_initial_data(**kwargs)
        game_data = self.data
        game_data.setdefault("novelty_tracker", PersistentDict())


    def _check_database_coherency(self, strict=False, **kwargs):
        super(NovaltyTracker, self)._check_database_coherency(**kwargs)
        game_data = self.data

        allowed_usernames = self.get_character_usernames() + [self.get_global_parameter("master_login")]
        for item_key, usernames in game_data["novelty_tracker"].items():
            assert isinstance(item_key, tuple) and len(item_key) == 2
            for username in usernames:
                assert username in allowed_usernames

    @readonly_method
    def get_novelty_registry(self):
        """For tests..."""
        return copy.deepcopy(self.data["novelty_tracker"])


    def _build_novelty_key(self, category, item_key):
        assert isinstance(item_key, basestring) and (" " not in item_key) and item_key
        assert isinstance(category, basestring) and (" " not in category) and category
        full_key = (category, item_key)
        return full_key


    @transaction_watcher
    def access_novelty(self, username=CURRENT_USER, item_key=None, category=_default_novelty_category):
        """Returns True iff the user has accessed that resource for the first time, None if anonymous."""
        username = self._resolve_username(username)
        assert username in self.get_available_logins() # anonymous too, let's be tolerant
        if self.is_anonymous(username):
            return None
        full_key = self._build_novelty_key(category, item_key)
        del category, item_key # security
        tracker = self.data["novelty_tracker"]
        if full_key not in tracker:
            tracker[full_key] = PersistentList()
        if username not in tracker[full_key]:
            tracker[full_key].append(username)
            return True
        return False

    @readonly_method
    def has_accessed_novelty(self, username=CURRENT_USER, item_key=None, category=_default_novelty_category):
        """Returns always True for anonymous users (no novelty tracking for them)."""
        username = self._resolve_username(username)
        assert username in self.get_available_logins() # anonymous too, let's be tolerant
        if self.is_anonymous(username):
            return True # beware!
        full_key = self._build_novelty_key(category, item_key)
        del category, item_key # security
        tracker = self.data["novelty_tracker"]
        if full_key in tracker and username in tracker[full_key]:
            return True
        return False

    @transaction_watcher
    def reset_novelty_accesses(self, item_key, category=_default_novelty_category):
        full_key = self._build_novelty_key(category, item_key)
        del category, item_key # security
        tracker = self.data["novelty_tracker"]
        if full_key in tracker:
            del tracker[full_key]



@register_module
class CharacterHandling(BaseDataManager): # TODO REFINE

    CHARACTER_REAL_LIFE_ATTRIBUTES = ["real_life_identity", "real_life_email"] # OPTIONAL DATA

    def _load_initial_data(self, **kwargs):
        super(CharacterHandling, self)._load_initial_data(**kwargs)

        game_data = self.data
        for (name, character) in game_data["character_properties"].items():
            if character["avatar"]:
                character["avatar"] = utilities.find_game_file(character["avatar"], "images")
            character.setdefault("real_life_identity", None)
            character.setdefault("real_life_email", None)

    def _check_database_coherency(self, **kwargs):
        super(CharacterHandling, self)._check_database_coherency(**kwargs)

        game_data = self.data

        assert game_data["character_properties"]

        reserved_names = [game_data["global_parameters"][reserved] for reserved in ["master_login", "anonymous_login"]]

        for (name, character) in game_data["character_properties"].items():

            utilities.check_is_slug(name)
            assert name not in reserved_names
            assert "@" not in name # let's not mess with email addresses...

            utilities.check_is_bool(character["is_npc"])

            utilities.check_is_slug(character["character_color"])

            if character["avatar"]:
                utilities.check_is_game_file(character["avatar"])

            if character["gamemaster_hints"]:
                utilities.check_is_string(character["gamemaster_hints"], multiline=True)

            utilities.check_is_string(character["official_name"], multiline=False)
            utilities.check_is_string(character["official_role"], multiline=False)

            if character["real_life_identity"]: # OPTIONAL
                utilities.check_is_string(character["real_life_identity"], multiline=False)
            if character["real_life_email"]: # OPTIONAL
                utilities.check_is_email(character["real_life_email"])


        stolen_identities = [char["official_name"].replace(" ", "").lower() for char in
                             game_data["character_properties"].values()]
        utilities.check_no_duplicates(stolen_identities) # each character stole the identity of someone different, on Pangea



    @readonly_method
    def get_character_color_or_none(self, username=CURRENT_USER):
        """
        Very tolerant function, returns None if username is None or not a real character name.
        """
        if not username:
            return None # let it be
        assert (isinstance("username", basestring) and " " not in username)
        username = self._resolve_username(username)
        if username and self.data["character_properties"].has_key(username):
            return self.data["character_properties"][username]["character_color"]
        return None

    @readonly_method
    def get_character_sets(self):
        return self.data["character_properties"]

    @readonly_method
    def get_character_usernames(self, exclude_current=False):
        """
        We sort "players first, NPC second".
        """
        items = sorted(((k, v) for (k, v) in self.data["character_properties"].items()), key=lambda x: (x[1]["is_npc"], x[0]))
        res = [item[0] for item in items]
        if exclude_current and self.user.username in res:
            res.remove(self.user.username)
        return res

    @readonly_method
    def get_character_official_names(self):
        return sorted([char["official_name"] for char in self.data["character_properties"].values()])

    @readonly_method
    def get_official_name(self, username=CURRENT_USER):
        username = self._resolve_username(username)
        properties = self.data["character_properties"][username]
        return properties["official_name"]

    @readonly_method
    def get_username_from_official_name(self, official_name):
        matches = [name for (name, value) in self.data["character_properties"].items() if
                   value["official_name"] == official_name]
        return matches[0] # may raise error

    @readonly_method
    def get_character_properties(self, username=CURRENT_USER):
        # for normal characters only
        username = self._resolve_username(username)
        try:
            res = self.data["character_properties"][username] # .copy()
            #res["items"] = [] # FIXME !!!!
            return res
        except KeyError:
            raise UsageError(_("Unknown username %s") % username)

    @readonly_method
    def _______get_fellow_usernames(self, username=CURRENT_USER): # OBSOLETE FIXME
        # returns team mates only, doesn't work for game master
        username = self._resolve_username(username)
        domain = self.get_character_properties(username)["domain"]
        fellows = [name for (name, props) in self.get_character_sets().items() if
                   props["domain"] == domain and name != username]
        return fellows


    @readonly_method
    def get_other_character_usernames(self, username=CURRENT_USER):
        # also works for game master : returns ALL players
        username = self._resolve_username(username)
        others = [name for name in self.get_character_usernames() if name != username]
        return others

    @readonly_method
    def build_select_choices_from_usernames(self, usernames, add_empty=False):
        visible_names = [username.capitalize() for username in usernames] # no need for real official names here
        character_choices = zip(usernames, visible_names)
        if add_empty:
            character_choices = [("", _("None"))] + character_choices # by default, None selected
        return character_choices

    @transaction_watcher
    def update_real_life_data(self, username=CURRENT_USER, real_life_email=None, real_life_identity=None):
        username = self._resolve_username(username)
        data = self.get_character_properties(username)

        action_done = False

        if real_life_identity is not None and real_life_identity != data["real_life_identity"]:
            data["real_life_identity"] = real_life_identity
            action_done = True

        if real_life_email is not None and real_life_email != data["real_life_email"]:
            if real_life_email and not utilities.is_email(real_life_email):
                raise NormalUsageError(_("Wrong email %s") % real_life_email)
            data["real_life_email"] = real_life_email
            action_done = True

        return action_done

    @transaction_watcher
    def update_official_character_data(self, username=CURRENT_USER, official_name=None, official_role=None):
        username = self._resolve_username(username)
        data = self.get_character_properties(username)

        action_done = False

        if official_name and official_name != data["official_name"]:
            data["official_name"] = official_name # can't be an empty string
            action_done = True

        if official_role and official_role != data["official_role"]:
            data["official_role"] = official_role # can't be an empty string
            action_done = True

        return action_done




@register_module
class DomainHandling(BaseDataManager): # TODO REFINE


    def _load_initial_data(self, **kwargs):
        super(DomainHandling, self)._load_initial_data(**kwargs)

        game_data = self.data
        for (name, content) in game_data["domains"].items():
            if content["national_anthem"]:
                content["national_anthem"] = utilities.find_game_file(content["national_anthem"], "audio")

    def _check_database_coherency(self, **kwargs):
        super(DomainHandling, self)._check_database_coherency(**kwargs)

        game_data = self.data

        for (name, character) in game_data["character_properties"].items():
            utilities.check_is_list(character["domains"])
            for domain in character["domains"]: # list might be empty
                assert domain in game_data["domains"].keys(), domain

        assert game_data["domains"]
        for (name, content) in game_data["domains"].items():

            utilities.check_is_slug(name)

            if content["national_anthem"]:
                utilities.check_is_game_file(content["national_anthem"])


    @readonly_method
    def get_domain_names(self):
        return sorted(self.data["domains"].keys())

    @readonly_method
    def get_domain_properties(self, domain_name):
        return self.data["domains"][domain_name]

    @transaction_watcher
    def update_allegiances(self, username=CURRENT_USER, allegiances=None):
        assert allegiances is not None and len(set(allegiances)) == len(allegiances)
        username = self._resolve_username(username)
        available_domains = self.get_domain_names()
        data = self.get_character_properties(username)

        for allegiance in allegiances:
            if allegiance not in available_domains:
                raise AbnormalUsageError(_("Wrong domain name %s") % allegiance)

        added_domains = sorted(set(allegiances) - set(data["domains"]))
        removed_domains = sorted(set(data["domains"]) - set(allegiances))

        data["domains"] = PersistentList(set(allegiances)) # we make them unique, just in case

        return (added_domains, removed_domains)

    @readonly_method
    def build_domain_select_choices(self):
        domain_choices = [(name, name.capitalize()) for name in self.get_domain_names()]
        return domain_choices







@register_module
class PlayerAuthentication(BaseDataManager):
    """
    That class is mostly used BEFORE actual setup of user, so we don't
    play much with CURRENT_USER placeholder here.
    """

    def _load_initial_data(self, **kwargs):
        super(PlayerAuthentication, self)._load_initial_data(**kwargs)

        for character in self.get_character_sets().values():
            character.setdefault("secret_question", None)
            character.setdefault("secret_answer", None)
            character["secret_answer"] = character["secret_answer"] if not character["secret_answer"] else character["secret_answer"].strip().lower()


    def _check_database_coherency(self, **kwargs):
        super(PlayerAuthentication, self)._check_database_coherency(**kwargs)

        game_data = self.data

        for character in self.get_character_sets().values():
            if character["password"]: # might be None==disabled
                utilities.check_is_slug(character["password"])
            if not character["secret_question"]:
                assert not character["secret_answer"]
            else:
                utilities.check_is_string(character["secret_question"])
                utilities.check_is_slug(character["secret_answer"])
                assert character["secret_answer"] == character["secret_answer"].lower()

        utilities.check_no_duplicates([c["password"] for c in self.get_character_sets().values() if c["password"]])

        # MASTER and ANONYMOUS cases

        global_parameters = game_data["global_parameters"]

        utilities.check_is_slug(global_parameters["anonymous_login"])

        utilities.check_is_slug(global_parameters["master_login"])
        utilities.check_is_slug(global_parameters["master_password"])
        if global_parameters["master_real_email"]:
            utilities.check_is_slug(global_parameters["master_real_email"])

        utilities.check_is_range_or_num(global_parameters["password_recovery_delay_mn"])


    @transaction_watcher(always_writable=True)
    def override_master_credentials(self, master_password=_undefined, master_real_email=_undefined):
        """
        The master_login shall NEVER be changed after game got created!!
        """
        assert master_password is not _undefined or master_real_email is not _undefined
        global_parameters = self.data["global_parameters"]
        if master_password is not _undefined:
            global_parameters["master_password"] = master_password
        if master_real_email is not _undefined:
            global_parameters["master_real_email"] = master_real_email # might be overridden with "None"


    @transaction_watcher(always_writable=True)
    def randomize_passwords_for_players(self):
        """
        Does NOT touch passwords of NPCs, or of disabled accounts.
        """
        choices = config.PASSWORDS_POOL[:]
        assert choices is not config.PASSWORDS_POOL # ensure no side effects here
        for character in self.get_character_sets().values():
            if not character["is_npc"] and character["password"]: # might be None==disabled
                character["password"] = random.choice(choices)
                choices.remove(character["password"]) # to avoid that, by miracle, two people get the same one...

    @readonly_method
    def get_available_logins(self):
        return ([self.get_global_parameter("anonymous_login")] +
                self.get_character_usernames() +
                [self.get_global_parameter("master_login")])


    @transaction_watcher(always_writable=True)
    def logout_user(self):
        self._set_user(username=None)


    @readonly_method
    def can_impersonate(self, username, impersonation):
        """
        This method must play it safe, we're not sure username or impersonation is valid here!
        
        Returns True iff user *username* can temporarily take the identity of *impersonation*.
        """
        assert username and impersonation

        if username == impersonation: # no sense - and also prevents master from impersonating master
            return False

        if self.is_master(username) and impersonation in self.get_available_logins():
            return True # impersonation can be a character or anonymous (or even master for django superuser)

        return False


    @readonly_method
    def get_impersonation_targets(self, username):  #FIXME TODO? USELESS ??
        """Only for game users, not external superusers."""
        assert username
        possible_impersonations = [target for target in self.get_available_logins()
                                   if self.can_impersonate(username, target)]
        return possible_impersonations

    @readonly_method
    def get_current_user_impersonation_capabilities(self):
        """
        Beware, we consider REAL USER permissions here, not impersonated user's!
        """
        # safe default values
        display_impersonation_target_shortcut = False
        display_impersonation_writability_shortcut = False
        impersonation_targets = []
        has_writability_control = False

        real_username = self.user.real_username
        if self.user.is_superuser or self.is_master(real_username):
            display_impersonation_target_shortcut = True
            display_impersonation_writability_shortcut = True
            impersonation_targets = self.get_available_logins() if self.user.is_superuser else self.get_impersonation_targets(real_username)
            has_writability_control = True
            if not self.user.is_superuser and self.user.is_master:
                assert real_username == self.master_login
                assert not self.user.is_impersonation # no one except super user can, at the moment, impersonate master...
                assert impersonation_targets == self.get_impersonation_targets(self.master_login)
        else:
            # we don't care about current impersonation status of player here
            assert self.is_character(real_username) or self.is_anonymous(real_username)
            impersonation_targets = self.get_impersonation_targets(username=real_username) # INCLUDING ANONYMOUS, for fun
            display_impersonation_target_shortcut = bool(impersonation_targets)
            display_impersonation_writability_shortcut = False # ALWAYS

        assert not self.user.impersonation_target or self.user.impersonation_target in impersonation_targets
        assert has_writability_control or not self.user.impersonation_writability
        return dict(display_impersonation_target_shortcut=display_impersonation_target_shortcut,
                    display_impersonation_writability_shortcut=display_impersonation_writability_shortcut,

                    impersonation_targets=impersonation_targets,
                    has_writability_control=has_writability_control, # TODO FIXME REMOVE THAT STUFF

                    current_impersonation_target=self.user.impersonation_target,
                    current_impersonation_writability=self.user.impersonation_writability)


    def _compute_new_session_data(self,
                                   session_ticket,
                                   requested_impersonation_target,
                                   requested_impersonation_writability,
                                   django_user):

        assert session_ticket.get("game_instance_id") == self.game_instance_id
        assert requested_impersonation_writability in (None, True, False) # forced by the way we extract it from request data

        game_username = session_ticket.get("game_username", None) # instance-local user set via login page
        assert game_username != self.anonymous_login # would be absurd, we store "None" for this

        # first, we compute the impersonation we actually want #
        if requested_impersonation_target == "": # special case "delete current impersonation target"
            requested_impersonation_target = None
            requested_impersonation_writability = False # for security, we reset that too
        elif requested_impersonation_target is None: # means "use legacy one"
            requested_impersonation_target = session_ticket.get("impersonation_target", None)
        else:
            pass # we let submitted requested_impersonation_target continue

        requested_impersonation_writability = (requested_impersonation_writability
                                               if requested_impersonation_writability is not None
                                               else session_ticket.get("impersonation_writability", None))

        # we reset session if session/request data is abnormal
        _available_logins = self.get_available_logins()
        if game_username and game_username not in _available_logins:
            raise AbnormalUsageError(_("Invalid instance username: %s") % game_username)
        if requested_impersonation_target and requested_impersonation_target not in _available_logins:
            raise AbnormalUsageError(_("Invalid requested impersonation target: %s") % requested_impersonation_target)

        is_superuser = False
        if not game_username: # instance-local authentication COMPLETELY HIDES the fact one is a django superuser
            if django_user and django_user.is_active and (django_user.is_staff or django_user.is_superuser):
                is_superuser = True

        if requested_impersonation_target is not None:
            # we filter out forbidden impersonation choices #
            if is_superuser or (game_username and self.can_impersonate(game_username, requested_impersonation_target)):
                pass # OK, impersonation granted
            else:
                # here we don't erase the session data, but this stops impersonation completely
                self.user.add_error(_("Unauthorized user impersonation detected: %s") % requested_impersonation_target)
                requested_impersonation_target = requested_impersonation_writability = None # TODO FIXME TEST THAT CURRENT GAME USERNAME REMAINS


        if requested_impersonation_writability is not None:
            if is_superuser or (game_username and self.is_master(game_username)):
                pass # OK, writability control authorized
            else:
                self.logger.critical("Attempt at controlling impersonation writability (%s) by non-privileged player %r", requested_impersonation_writability, game_username)
                requested_impersonation_writability = None # we just reset that flag for now, no exception raised

        return dict(is_superuser=is_superuser,
                    game_username=game_username,
                    impersonation_target=requested_impersonation_target,
                    impersonation_writability=requested_impersonation_writability)


    def _generate_session_ticket(self):
        return dict(game_instance_id=self.game_instance_id,
                      game_username=None,
                      impersonation_target=None,
                      impersonation_writability=None)


    @transaction_watcher(always_writable=True)
    def authenticate_with_session_data(self,
                                 session_ticket=None,
                                 requested_impersonation_target=None,
                                 requested_impersonation_writability=None,
                                 django_user=None):
        """
        Allows a logged other to continue using his normal session,
        or to impersonate a lower-rank user.
        
        Raises UsageError if problem.
        """
        assert requested_impersonation_target is None or isinstance(requested_impersonation_target, basestring)
        assert requested_impersonation_writability in (None, True, False)

        if not session_ticket:
            session_ticket = self._generate_session_ticket()

        # we reset session if session/request data is abnormal
        if not isinstance(session_ticket, dict):
            raise AbnormalUsageError(_("Invalid session ticket: %s") % repr(session_ticket))
        game_instance_id = session_ticket.get("game_instance_id", None)
        if game_instance_id != self.game_instance_id: # redundant security
            raise AbnormalUsageError(_("Invalid session ticket: %s") % repr(session_ticket)) # only ticket for THIS instance should have been given

        new_session_data = self._compute_new_session_data(session_ticket=session_ticket,
                                                                   requested_impersonation_target=requested_impersonation_target,
                                                                   requested_impersonation_writability=requested_impersonation_writability,
                                                                   django_user=django_user)
        assert len(new_session_data) == 4
        is_superuser = new_session_data["is_superuser"]
        game_username = new_session_data["game_username"]
        impersonation_target = new_session_data["impersonation_target"]
        impersonation_writability = new_session_data["impersonation_writability"]

        self.logger.info("Authenticating user with ticket, as %r",
                             repr(dict(username=game_username, impersonation_target=impersonation_target,
                                       impersonation_writability=impersonation_writability, is_superuser=is_superuser)))

        self._set_user(username=game_username,
                        impersonation_target=impersonation_target,
                        impersonation_writability=impersonation_writability,
                        is_superuser=is_superuser)

        if session_ticket is not None:
            assert session_ticket.get("game_instance_id") == self.game_instance_id
            assert session_ticket.get("game_username") == game_username # NEVER TOUCHED ATM
            session_ticket.update(impersonation_target=impersonation_target,
                                  impersonation_writability=impersonation_writability)

        return session_ticket


    @transaction_watcher(always_writable=True)
    def authenticate_with_credentials(self, username, password):
        """
        Tries to authenticate an user from its credentials, and raises an UsageError on failure,
        or returns a session ticket for that user.
        
        Username can't be "anonymous_login" of course...
        """
        username = username.strip()
        password = password.strip()
        if username == self.get_global_parameter("master_login"): # do not use is_master here, just in case...
            wanted_pwd = self.get_global_parameter("master_password")
        else:
            data = self.get_character_properties(username) # might raise UsageError
            wanted_pwd = data["password"]

        if password and wanted_pwd and password == wanted_pwd: # BEWARE - ensure accounts have not been disabled via password=None
            # when using credentials, it's always a real user, with writability (and django user status is hidden)
            self._set_user(username, impersonation_target=None, impersonation_writability=False, is_superuser=False)
            session_ticket = dict(game_instance_id=self.game_instance_id,
                                  game_username=username,
                                  impersonation_target=None,
                                  impersonation_writability=None) # we reset impersonation then
            return session_ticket

        else:
            raise NormalUsageError(_("Wrong password"))

        assert False


    @transaction_watcher # requires game started mode
    def process_password_change_attempt(self, username, old_password, new_password):
        user_properties = self.get_character_properties(username)

        if not new_password or " " in new_password or "\n" in new_password or len(new_password) > 60:
            raise AbnormalUsageError(_("Invalid new password submitted"))

        if old_password != user_properties["password"]:
            raise NormalUsageError(_("Wrong current password submitted"))

        user_properties["password"] = new_password


    @readonly_method
    def get_secret_question(self, username):
        """
        Raises UsageError if username is incorrect or doesn't have a secret question setup.
        """
        if username == self.get_global_parameter("master_login"):
            raise NormalUsageError(_("Game master can't recover his password through a secret question."))
        elif username not in self.get_character_usernames():
            raise NormalUsageError(_("Invalid username."))
        else:
            secret_question = self.get_character_properties(username)["secret_question"]
            if not secret_question:
                raise NormalUsageError(_("That user has no secret question set up."))
            return secret_question


    @transaction_watcher # requires game started mode
    def process_secret_answer_attempt(self, username, secret_answer_attempt, target_email):

        self.get_secret_question(username) # checks coherency of that call

        user_properties = self.get_character_properties(username)

        secret_answer_attempt = secret_answer_attempt.lower().strip() # double security
        expected_answer = user_properties["secret_answer"].lower().strip() # may NOT be None here
        assert expected_answer, expected_answer

        # WARNING - if by bug, no answer is actually expected, attempts must ALWAYS fail
        if expected_answer and (secret_answer_attempt == expected_answer):
            if target_email not in self.get_sorted_user_contacts(self.get_global_parameter("master_login")): # all emails available
                raise UsageError(_("Right answer, but invalid email address %s." % target_email))
            # success !

            sender_email = "authenticator@hightech.com" # dummy email

            password = user_properties["password"]

            subject = "<Password Recovery System>"

            body = dedent("""
                    The password corresponding to your login %(username)s is '%(password)s'.
                    Please keep it carefully and do not share it with anyone else.
                   """) % SDICT(username=username, password=password)

            attachment = None

            msg_id = self.post_message(sender_email=sender_email, recipient_emails=target_email,
                                       subject=subject, body=body, attachment=attachment,
                                       date_or_delay_mn=self.get_global_parameter("password_recovery_delay_mn"))

            self.log_game_event(ugettext_noop("Password of %(username)s has been recovered by %(target_email)s."),
                                 PersistentDict(username=username, target_email=target_email),
                                 url=self.get_message_viewer_url(msg_id))

            return password

        else:
            raise NormalUsageError(_("Wrong answer supplied."))



    # Utility functions for tests on other usernames than current player's one #

    @property
    def username(self):
        return self.user.username

    @readonly_method
    def is_anonymous(self, username=CURRENT_USER):
        username = self._resolve_username(username)
        return (username == self.anonymous_login)

    @readonly_method
    def is_authenticated(self, username=CURRENT_USER):
        username = self._resolve_username(username)
        return (username != self.anonymous_login)

    @readonly_method
    def is_master(self, username=CURRENT_USER):
        username = self._resolve_username(username)
        return (username == self.master_login)

    @readonly_method
    def is_character(self, username=CURRENT_USER):
        username = self._resolve_username(username)
        return (username in self.get_character_usernames())


    @property
    def anonymous_login(self):
        return self.get_global_parameter("anonymous_login")

    @property
    def master_login(self):
        return self.get_global_parameter("master_login")





@register_module
class PermissionsHandling(BaseDataManager): # TODO REFINE

    PERMISSIONS_REGISTRY = Enum()

    """"
    contact_djinns manage_agents 
                        manage_wiretaps manage_teleportations 
                        manage_scans manage_scans manage_translations 
                        launch_telecom_investigations
                        """ # TODO transfer these to abilities and modules

    @classmethod
    def register_permissions(cls, names):
        assert all((name and name.lower() == name and " " not in name) for name in names)
        cls.PERMISSIONS_REGISTRY.update(names) # SET operation, not dict


    def _load_initial_data(self, **kwargs):
        super(PermissionsHandling, self)._load_initial_data(**kwargs)

        game_data = self.data

        for (name, character) in game_data["character_properties"].items():
            character.setdefault("permissions", PersistentList())

        # USELESS ATM
        for (name, domain) in game_data["domains"].items():
            domain.setdefault("permissions", PersistentList())

    def _check_database_coherency(self, **kwargs):
        super(PermissionsHandling, self)._check_database_coherency(**kwargs)

        for permission in self.PERMISSIONS_REGISTRY: # check all available permissions
            utilities.check_is_slug(permission)
            assert permission.lower() == permission

        game_data = self.data

        """ BROKEN ATM because we use new views in tests # TODO FIXME LATER

        # BEWARE - if one day we change installed views, this will break
        for (name, character) in game_data["character_properties"].items():
            for permission in character["permissions"]:
                assert permission in self.PERMISSIONS_REGISTRY

        # USELESS ATM
        for (name, domain) in game_data["domains"].items():
            for permission in domain["permissions"]:
                assert permission in self.PERMISSIONS_REGISTRY
        """

    @transaction_watcher
    def update_permissions(self, username=CURRENT_USER, permissions=None):
        username = self._resolve_username(username)
        assert self.is_character(username)
        assert all(p in self.PERMISSIONS_REGISTRY for p in permissions) # permissions can be empty

        data = self.get_character_properties(username)
        data["permissions"] = PersistentList(permissions)


    @readonly_method
    def has_permission(self, username=CURRENT_USER, permission=None):
        assert permission
        assert permission in self.PERMISSIONS_REGISTRY # handy check

        username = self._resolve_username(username)

        if not self.is_character(username):
            return False # anonymous and master must be handled differently

        props = self.get_character_properties(username=username)

        if permission in props["permissions"]:
            return True

        for domain_name in props["domains"]:
            domain = self.get_domain_properties(domain_name=domain_name)
            if permission in domain["permissions"]:
                return True

        return False


    @readonly_method
    def build_permission_select_choices(self):
        return [(perm, perm) for perm in sorted(self.PERMISSIONS_REGISTRY)]



@register_module
class FriendshipHandling(BaseDataManager):


    def _load_initial_data(self, strict=False, **kwargs):
        super(FriendshipHandling, self)._load_initial_data(**kwargs)
        game_data = self.data
        game_data.setdefault("friendships", PersistentDict())
        game_data["friendships"].setdefault("proposed", PersistentDict()) # mapping (proposer, recipient) => dict(proposal_date)
        game_data["friendships"].setdefault("sealed", PersistentDict()) # mapping (proposer, accepter) => dict(proposal_date, acceptance_date)

    def _check_database_coherency(self, strict=False, **kwargs):
        super(FriendshipHandling, self)._check_database_coherency(**kwargs)

        game_data = self.data

        delay = self.get_global_parameter("friendship_minimum_duration_mn_abs") # NOT a flexible delay!!
        utilities.check_is_positive_int(delay, non_zero=True)

        character_names = self.get_character_usernames()
        friendships = game_data["friendships"]

        if strict:
            assert len(friendships) == 2

        proposed_friendships = friendships["proposed"]
        utilities.check_no_duplicates(proposed_friendships)
        for (username1, username2), friendship_params in proposed_friendships.items():
            assert (username2, username1) not in proposed_friendships # ensures non-reciprocity of friendship offering (else it'd be sealed), and non-self-friendship
            assert username1 in character_names
            assert username2 in character_names
            template = {
                         "proposal_date": datetime,
                        }
            utilities.check_dictionary_with_template(friendship_params, template, strict=strict)

        sealed_friendships = friendships["sealed"]
        utilities.check_no_duplicates(sealed_friendships)
        for (username1, username2), friendship_params in sealed_friendships.items():
            assert username1 != username2
            assert (username2, username1) not in sealed_friendships # ensures both unicity and non-self-friendship, actually
            assert (username1, username2) not in proposed_friendships
            assert (username2, username1) not in proposed_friendships
            assert username1 in character_names
            assert username2 in character_names
            template = {
                         "proposal_date": datetime,
                         "acceptance_date": datetime,
                        }
            utilities.check_dictionary_with_template(friendship_params, template, strict=strict)


    @readonly_method
    def get_full_friendship_data(self):
        return copy.deepcopy(self.data["friendships"])

    @readonly_method
    def can_impersonate(self, username, impersonation):
        if (self.is_character(username) and self.is_character(impersonation) and
            self.are_friends(username, impersonation)):
            return True
        return super(FriendshipHandling, self).can_impersonate(username, impersonation)


    @transaction_watcher
    def propose_friendship(self, username=CURRENT_USER, recipient=None):
        """
        Can also act as "seal friendship", if a reciprocal request existed.
        Returns True iif that's the case, i.e both characters are friend at the end of the action.
        """
        assert recipient
        username = self._resolve_username(username)
        if not self.is_character(username) or not self.is_character(recipient):
            raise AbnormalUsageError(_("Forbidden friendship proposal: %(username)s -> %(recipient)s") % SDICT(username=username, recipient=recipient))
        if username == recipient:
            raise AbnormalUsageError(_("User %s can't be friend with himself") % username)
        if self.are_friends(username, recipient):
            raise AbnormalUsageError(_("Already existing friendship between %(username)s and %(recipient)s") % SDICT(username=username, recipient=recipient))

        friendship_proposals = self.data["friendships"]["proposed"]
        friendships = self.data["friendships"]["sealed"]
        if (username, recipient) in friendship_proposals:
            raise AbnormalUsageError(_("%(username)s has already requested the friendship of %(recipient)s") % SDICT(username=username, recipient=recipient))

        current_date = datetime.utcnow()
        if (recipient, username) in friendship_proposals:
            # we seal the deal, with "recipient" as the initial proposer!
            existing_data = friendship_proposals[(recipient, username)]
            del friendship_proposals[(recipient, username)] # important
            friendships[(recipient, username)] = PersistentDict(proposal_date=existing_data["proposal_date"],
                                                                acceptance_date=current_date)
            res = True
        else:
            friendship_proposals[(username, recipient)] = PersistentDict(proposal_date=current_date)
            res = False

        # TODO FIXME - add game events for both events
        return res


    @readonly_method
    def get_friendship_requests_for_character(self, username=CURRENT_USER):
        """
        Returns a dict with entries "proposed_to" and "requested_by" (lists of character names).
        These entries are of course exclusive (if a frienship was wanted by both sides, it'd be already sealed).
        """
        username = self._resolve_username(username)
        assert self.is_character(username)
        result = dict(proposed_to=[],
                      requested_by=[])
        for proposer, recipient in self.data["friendships"]["proposed"].keys():
            if proposer == username:
                result["proposed_to"].append(recipient)
            elif recipient == username:
                result["requested_by"].append(proposer)
        assert username not in result["proposed_to"] + ["requested_by"]
        return result


    @readonly_method
    def get_friendship_params(self, username1, username2):
        assert self.is_character(username1) and self.is_character(username2)
        friendships = self.data["friendships"]["sealed"]
        try:
            return (username1, username2), friendships[(username1, username2)]
        except KeyError:
            try:
                return (username2, username1), friendships[(username2, username1)]
            except KeyError:
                raise AbnormalUsageError(_("Unexisting friendship: %(username1)s<->%(username1)s") % SDICT(username1=username1, username2=username2))


    @readonly_method
    def are_friends(self, username1, username2):
        friendships = self.data["friendships"]["sealed"]
        if (username1, username2) in friendships or (username2, username1) in friendships:
            return True
        return False


    @readonly_method
    def get_friends_for_character(self, username=CURRENT_USER):
        username = self._resolve_username(username)
        assert self.is_character(username)
        friendships = self.data["friendships"]["sealed"]

        friends = []
        for (username1, username2) in friendships.keys():
            if username1 == username:
                friends.append(username2)
            elif username2 == username:
                friends.append(username1)

        assert username not in friends
        return friends


    @readonly_method
    def get_other_characters_friendship_statuses(self, username=CURRENT_USER):
        """
        Returns a dict of target_username=>status entries for that username, 
        where status is one of: (proposed_to, requested_by, recent_friend, old_friend).
        """
        username = self._resolve_username(username)
        friends = self.get_friends_for_character(username)

        recent_friend = []
        old_friend = []
        for friend in friends:
            __, friendship_data = self.get_friendship_params(username, friend)
            if self.is_friendship_too_young_to_be_terminated(friendship_data):
                recent_friend.append(friend)
            else:
                old_friend.append(friend)


        friendship_requests = self.get_friendship_requests_for_character(username)

        relation_groups = dict(proposed_to=friendship_requests["proposed_to"],
                               requested_by=friendship_requests["requested_by"],
                               recent_friend=recent_friend,
                               old_friend=old_friend)

        if __debug__:
            #print (">>>", relation_groups.values())
            _users = sum(relation_groups.values(), [])
            assert len(set(_users)) == len(_users), relation_groups # no duplicates!

        character_statuses = {username: relation_type for (relation_type, usernames) in relation_groups.items()
                                                      for username in usernames}

        for other_username in self.get_other_character_usernames(username):
            character_statuses.setdefault(other_username, None) # other characters that are related at all to current user get "None"

        return character_statuses


    @readonly_method
    def is_friendship_too_young_to_be_terminated(self, friendship_data):
        min_delay = self.get_global_parameter("friendship_minimum_duration_mn_abs")
        return (friendship_data["acceptance_date"] > datetime.utcnow() - timedelta(minutes=min_delay))


    @transaction_watcher
    def terminate_friendship(self, username=CURRENT_USER, rejected_user=None):
        """
        Can also act as "abort friendship proposal" if people weren't friends - returns True iff a real friendship was broken.
        """
        assert rejected_user
        username = self._resolve_username(username)
        friendship_proposals = self.data["friendships"]["proposed"]

        if (username, rejected_user) in friendship_proposals:
            del friendship_proposals[(username, rejected_user)]
            return False
        else:
            friendship_key, friendship_data = self.get_friendship_params(username, rejected_user) # raises error if not friends
            if self.is_friendship_too_young_to_be_terminated(friendship_data):
                raise AbnormalUsageError(_("That friendship is too young to be terminated - please respect the waiting period"))
            del self.data["friendships"]["sealed"][friendship_key]
            return True


    @transaction_watcher
    def reset_friendship_data(self):
        self.data["friendships"]["proposed"].clear()
        self.data["friendships"]["sealed"].clear()


"""WEIRD STUFF
@register_module
class GameInstructions(BaseDataManager):


    def _load_initial_data(self, **kwargs):
        super(GameInstructions, self)._load_initial_data(**kwargs)

    def _check_database_coherency(self, **kwargs):
        super(GameInstructions, self)._check_database_coherency(**kwargs)

        game_data = self.data

        utilities.check_is_string(game_data["global_parameters"]["global_introduction"])
        utilities.check_is_string(game_data["global_parameters"]["history_summary"])

        for (name, content) in game_data["domains"].items():
            assert isinstance(content["instructions"], (types.NoneType, basestring)) # can be empty


    @readonly_method
    def get_game_instructions(self, username=CURRENT_USER):
        username = self._resolve_username(username)
        global_introduction = self.get_global_parameter("global_introduction")

        team_introduction = None
        prologue_music = None

        '''
        if self.is_master(username):
            team_introduction = None
            prologue_music = None
        else:
            domain = self.get_domain_properties(self.get_character_properties(username)["domain"])
            team_introduction = domain["instructions"]
            prologue_music = game_file_url("musics/" + domain["prologue_music"])
        '''

        return PersistentDict(prologue_music=prologue_music,
                              global_introduction=global_introduction,
                              team_introduction=team_introduction)

"""






@register_module
class LocationsHandling(BaseDataManager):

    def _load_initial_data(self, **kwargs):
        super(LocationsHandling, self)._load_initial_data(**kwargs)

        game_data = self.data
        for (name, properties) in game_data["locations"].items():
            pass # NOTHING ATM


    def _check_database_coherency(self, **kwargs):
        super(LocationsHandling, self)._check_database_coherency(**kwargs)

        game_data = self.data
        assert game_data["locations"]
        for (name, properties) in game_data["locations"].items():

            utilities.check_is_slug(name)

            ''' DEPRECATED
            if properties["spy_message"] is not None:
                utilities.check_is_string(properties["spy_message"])
            if properties["spy_audio"]:
                utilities.check_is_game_file(os.path.join("spy_reports", "spy_" + name.lower() + ".mp3"))
            '''

    @readonly_method
    def get_locations(self):
        return self.data["locations"]








@register_module
class OnlinePresence(BaseDataManager):

    def _load_initial_data(self, **kwargs):
        super(OnlinePresence, self)._load_initial_data(**kwargs)
        for character in self.get_character_sets().values():
            character.setdefault("last_online_time", None)

        self.data["global_parameters"].setdefault("online_presence_timeout_s", 600)

    def _check_database_coherency(self, **kwargs):
        super(OnlinePresence, self)._check_database_coherency(**kwargs)
        for character in self.get_character_sets().values():
            assert not character["last_online_time"] or (isinstance(character["last_online_time"], datetime)
                                                         and character["last_online_time"] <= datetime.utcnow())

        utilities.check_is_positive_int(self.get_global_parameter("online_presence_timeout_s"))


    def _notify_user_change(self, username, **kwargs):
        super(OnlinePresence, self)._notify_user_change(username=username, **kwargs)
        if self.is_character(username): # MUST BE FIRST, as a validation
            if self.is_game_writable():
                self.set_online_status(username)


    def _set_online_status(self, username): # no fallback system here
        self.data["character_properties"][username]["last_online_time"] = datetime.utcnow()

    @transaction_watcher
    def set_online_status(self, username=CURRENT_USER):
        username = self._resolve_username(username)
        self._set_online_status(username=username)

    @readonly_method
    def get_online_status(self, username=CURRENT_USER):
        username = self._resolve_username(username)
        timestamp = self.data["character_properties"][username]["last_online_time"]
        return timestamp and timestamp >= (datetime.utcnow() - timedelta(seconds=self.get_global_parameter("online_presence_timeout_s")))

    @readonly_method
    def get_online_users(self):
        return [username for username in self.get_character_usernames() if self.get_online_status(username)]





@register_module
class TextMessagingCore(BaseDataManager):


    @property
    def messaging_data(self):
        return self.data["messaging"] # base mount point for all messaging-related features

    _alternate = list(string.ascii_letters)
    random.shuffle(_alternate)
    _alternate = u"".join(_alternate)
    OBFUSCATOR_TRANSTABLE = string.maketrans(string.ascii_letters, _alternate)
    del _alternate

    @classmethod
    def _obfuscate_initial_id(cls, my_id):
        """Beware, only works with ascii strings atm..."""
        my_id = my_id.encode("ascii") # required by string.translate()
        return unicode(string.translate(my_id, cls.OBFUSCATOR_TRANSTABLE))

    def _load_initial_data(self, **kwargs):
        super(TextMessagingCore, self)._load_initial_data(**kwargs)

        game_data = self.data

        messaging = game_data.setdefault("messaging", PersistentList())

        messaging.setdefault("messages_dispatched", PersistentList())
        messaging.setdefault("messages_queued", PersistentList())

        for (index, msg) in enumerate(messaging["messages_dispatched"] + messaging["messages_queued"]):
            # we modify the dicts in place

            msg["sender_email"], msg["recipient_emails"] = self._normalize_message_addresses(msg["sender_email"], msg["recipient_emails"])

            msg ["body"] = utilities.load_multipart_rst(msg ["body"])

            msg["attachment"] = msg.get("attachment", None)
            if msg["attachment"]:
                msg["attachment"] = utilities.complete_game_file_url(msg["attachment"])

            msg["is_certified"] = msg.get("is_certified", False)

            if isinstance(msg["sent_at"], (long, int)): # offset in minutes
                msg["sent_at"] = self.compute_effective_remote_datetime(msg["sent_at"])


            msg["transferred_msg"] = msg.get("transferred_msg", None)
            if msg["transferred_msg"]:
                msg["transferred_msg"] = self._obfuscate_initial_id(msg["transferred_msg"]) # ANTI LEAK

            if msg["id"]:
                msg["id"] = self._obfuscate_initial_id(msg["id"]) # ANTI LEAK
            else:
                msg["id"] = self._get_new_msg_id(index, msg["subject"] + msg["body"])

            if msg.get("group_id"):
                msg["group_id"] = self._obfuscate_initial_id(msg["group_id"]) # ANTI LEAK
            else:
                msg["group_id"] = msg["id"]

        # important - initial sorting #
        messaging["messages_dispatched"].sort(key=lambda msg: msg["sent_at"])
        messaging["messages_queued"].sort(key=lambda msg: msg["sent_at"])




    def _check_database_coherency(self, strict=False, **kwargs):
        super(TextMessagingCore, self)._check_database_coherency(strict=strict, **kwargs)

        messaging = self.messaging_data
        message_reference = {
                             "sender_email": basestring, # only initial one
                             "recipient_emails": PersistentList, # only initial, theoretical ones
                             "visible_by": PersistentDict, # mapping usernames (including master_login) to translatable (ugettext_noop'ed) string "reason of visibility" or None (if obvious)

                             "subject": basestring,
                             "body": basestring,
                             "attachment": (types.NoneType, basestring), # a plainly functional URL, a personal document mostly
                             "transferred_msg": (types.NoneType, basestring), # text message id

                             "sent_at": datetime,
                             "is_certified": bool, # for messages sent via automated processes

                             "id": basestring,
                             "group_id": basestring,
                             }

        def _check_message_list(msg_list):
            previous_sent_at = None
            for msg in msg_list:

                # let's keep these IDs simple for now: ASCII...
                msg["id"].encode("ascii")
                msg["group_id"].encode("ascii")
                if msg["transferred_msg"]:
                    msg["transferred_msg"].encode("ascii")

                assert msg["subject"] # body can be empty, after all...

                if previous_sent_at:
                    assert previous_sent_at <= msg["sent_at"] # message lists are sorted by chronological order
                previous_sent_at = msg["sent_at"]

                utilities.check_dictionary_with_template(msg, message_reference, strict=False)

                utilities.check_is_email(msg["sender_email"])
                for recipient in msg["recipient_emails"]:
                    utilities.check_is_email(recipient)
                utilities.check_no_duplicates(msg["recipient_emails"])

                if msg["body"]: # might be empty
                    utilities.check_is_restructuredtext(msg["body"])

                if msg["attachment"]:
                    assert msg["attachment"].startswith("/") or msg["attachment"].startswith("http")

                if msg["transferred_msg"]:
                    assert self.get_dispatched_message_by_id(msg_id=msg["transferred_msg"])

            all_ids = [msg["id"] for msg in msg_list]
            utilities.check_no_duplicates(all_ids)

        # WARNING - we must separate the two lists, because little incoherencies can appear at their junction due to the workflow
        # (the first queued messages might actually be younger than the last ones of the sent messages list)
        _check_message_list(messaging["messages_dispatched"])
        _check_message_list(messaging["messages_queued"])



    def _process_periodic_tasks(self, report):
        super(TextMessagingCore, self)._process_periodic_tasks(report)

        # WE SEND DELAYED MESSAGES #

        last_index_processed = None
        utcnow = datetime.utcnow()

        for (index, msg) in enumerate(self.messaging_data["messages_queued"]):
            if msg["sent_at"] <= utcnow:
                try:
                    self._immediately_dispatch_message(msg)
                except:
                    if __debug__: self.notify_event("DELAYED_MESSAGE_ERROR")
                    self.logger.critical("Delayed message couldn't be sent : %s" % msg, exc_info=True)
                last_index_processed = index # even if error, we remove the msg from list
            else:
                break # since messages are queued in CHRONOLOGICAL order...

        if last_index_processed is not None:
            self.messaging_data["messages_queued"] = self.messaging_data["messages_queued"][last_index_processed + 1:] # cleanup
            report["messages_dispatched"] = last_index_processed + 1
        else:
            report["messages_dispatched"] = 0


    @transaction_watcher
    def post_message(self, *args, **kwargs):

        msg = self._build_new_message(*args, **kwargs)
        sent_at = msg["sent_at"]

        if sent_at > datetime.utcnow():
            self.messaging_data["messages_queued"].append(msg)
            self.messaging_data["messages_queued"].sort(key=lambda msg: msg["sent_at"]) # python sorting is stable !
        else:
            self._immediately_dispatch_message(msg)

        return msg["id"]


    def _build_new_message(self, sender_email, recipient_emails, subject, body,
                           attachment=None, transferred_msg=None,
                           date_or_delay_mn=None, is_read=False, is_certified=False,
                           parent_id=None, **kwargs):
        """
        Beware, if a delay, date_or_delay_mn is treated as FLEXIBLE TIME.
        
        TODO - is_certified is unused ATM.
        """
        # TOP LEVEL HERE - no parent call #
        assert not hasattr(super(TextMessagingCore, self), "_build_new_message")

        sender_email, recipient_emails = self._normalize_message_addresses(sender_email, recipient_emails) # sender and recipient may be the same !

        self._check_message_addresses_authorizations(sender_email, recipient_emails) # very important

        subject = subject.strip()
        body = body.strip()
        if attachment:
            attachment = attachment.strip() # can be RELATIVE url

        if not all([sender_email, recipient_emails, subject]):
            raise UsageError(_("Sender, recipient, and subject of the message mustn't be empty"))

        group_id = None
        if parent_id:
            try:
                parent_msg = self.get_dispatched_message_by_id(parent_id)
                group_id = parent_msg["group_id"]
                sender_username = self.get_username_from_email(sender_email) # character, or fallback to master
                self._set_message_reply_state(sender_username, parent_msg, True) # do not touch the READ state - must be done MANUALLY
            except UsageError, e:
                self.logger.error(e, exc_info=True)

        new_id = self._get_new_msg_id(len(self.messaging_data["messages_dispatched"]) + len(self.messaging_data["messages_queued"]),
                                      subject + body) # unicity more than guaranteed

        if isinstance(date_or_delay_mn, datetime):
            sent_at = date_or_delay_mn # shall already have been computed with "flexible time" !
        else:
            sent_at = self.compute_effective_remote_datetime(date_or_delay_mn) # date_or_delay_mn is None or (negative/positive) number or pair

        msg = PersistentDict({
                              "sender_email": sender_email,
                              "recipient_emails": recipient_emails,
                              "subject": subject,
                              "body": body,
                              "attachment": attachment, # None or string, a valid URL
                              "transferred_msg": transferred_msg, # msg id or None
                              "sent_at": sent_at,
                              "is_certified": is_certified,
                              "id": new_id,
                              "group_id": group_id if group_id else new_id, # msg might start a new conversation
                              })
        return msg


    def _normalize_message_addresses(self, sender_email, recipient_emails):
        """
        We don't check the form of emails here, they might even be string
        with spaces or without "@".
        """
        assert not hasattr(super(TextMessagingCore, self), "_normalize_message_addresses")

        pangea_network = self.data["global_parameters"]["pangea_network_domain"]
        def _complete_domain(address):
            if address and "@" not in address:
                address = address + "@" + pangea_network
            return address

        sender_email = _complete_domain(sender_email.strip())

        if isinstance(recipient_emails, basestring):
            recipient_emails = recipient_emails.replace(",", ";")
            recipient_emails = recipient_emails.split(";")
        recipient_emails = [_complete_domain(stripped) for stripped in (email.strip() for email in recipient_emails) if stripped]
        recipient_emails = PersistentList(set(recipient_emails)) # we thus remove duplicates

        return sender_email, recipient_emails

    def _check_message_addresses_authorizations(self, sender_email, recipient_emails):
        """
        Special override system - each override of these methods below must return if access is permittedn 
        or raise an exception, or transmit to parent if unsure of what to answer.
        """
        assert not hasattr(super(TextMessagingCore, self), "_check_message_is_authorized")
        self._check_sender_email(sender_email)
        for recipient_email in recipient_emails:
            self._check_recipient_email(recipient_email, sender_email=sender_email)


    def _check_email_address_format(self, email_address):
        if not utilities.is_email(email_address):
            raise NormalUsageError(_("Email address %s is invalid") % email_address)


    def _check_sender_email(self, sender_email):
        """
        Default : ALLOW UNKNOWN ADDRESSES, ATM.
        
        To be overridden.
        """
        self._check_email_address_format(sender_email)
        return # raise UsageError(_("Unknown sender address %r") % sender_email)

    def _check_recipient_email(self, recipient_email, sender_email):
        """
        Default : ALLOW UNKNOWN ADDRESSES, ATM.
        
        Only *sender_email* must be taken into account as information source, not currently logged user,
        since some abilities might allow to send an email in the name of someone else.
        
        To be overridden.
        """
        self._check_email_address_format(recipient_email)
        return # raise UsageError(_("Unknown recipient address %r") % recipient_email)


    def _immediately_dispatch_message(self, msg):
        """
        Here we don't care about "enqueued messages" cleanup.
        """
        assert not hasattr(super(TextMessagingCore, self), "_immediately_dispatch_message")
        self.messaging_data["messages_dispatched"].append(msg)
        self.messaging_data["messages_dispatched"].sort(key=lambda msg: msg["sent_at"]) # python sorting is stable !

        self._message_dispatching_post_hook(copy.deepcopy(msg))


    def _message_dispatching_post_hook(self, frozen_msg):
        assert not hasattr(super(TextMessagingCore, self), "_message_dispatching_post_hook")
        pass


    @transaction_watcher
    def force_message_sending(self, msg_id):
        """
        Immediately sends a queued message, returns True if message was indeed in the "pending" queue, False else.
        """
        msg = self._remove_message_from_list(self.messaging_data["messages_queued"], msg_id=msg_id)
        if not msg:
            return False

        msg["sent_at"] = datetime.utcnow() # we force the timestamp to UTCNOW
        self._immediately_dispatch_message(msg)
        return True

    @staticmethod
    def _remove_message_from_list(msg_list, msg_id):
        """
        Returns the removed (single) message, or None.
        """
        items = [item for item in enumerate(msg_list) if item[1]["id"] == msg_id]
        assert len(items) <= 1
        if items:
            (index, msg) = items[0]
            del msg_list[index]
            return msg
        return None

    @transaction_watcher
    def permanently_delete_message(self, msg_id):
        """
        Returns True if message id existed in queued or dispatched messages lists, False else.
        
        DANGEROUS method, only for game master basically.
        """
        msg = self._remove_message_from_list(self.messaging_data["messages_dispatched"], msg_id=msg_id)
        if not msg:
            msg = self._remove_message_from_list(self.messaging_data["messages_queued"], msg_id=msg_id)
        return bool(msg)

    # manipulation of message lists #

    @staticmethod
    def _get_new_msg_id(index, content):
        # index should always grow, except when messages got deleted
        md5 = hashlib.md5()
        md5.update(content.encode('ascii', 'ignore'))
        my_hash = md5.hexdigest()[0:4]
        return unicode(index) + "_" + my_hash

    @readonly_method
    def get_message_viewer_url(self, msg_id): # FIXME - where shall this method actually be ?
        return reverse('pychronia_game.views.view_single_message',
                        kwargs=dict(msg_id=msg_id, game_instance_id=self.game_instance_id))


    @readonly_method
    def get_all_queued_messages(self):
        return self.messaging_data["messages_queued"][:]

    @readonly_method
    def get_all_dispatched_messages(self):
        return self.messaging_data["messages_dispatched"][:]


    @readonly_method
    def get_dispatched_message_by_id(self, msg_id):
        msgs = [message for message in self.messaging_data["messages_dispatched"] if message["id"] == msg_id]
        assert len(msgs) <= 1, "len(msgs) must be < 1"
        if not msgs:
            raise UsageError(_("Unknown message id '%s'" % msg_id))
        return msgs[0]

    ''' DEPRECATED
    @transaction_watcher
    def __TODO_REVIVE_try_filling_message_template(self, template, values, part_name, tpl_name):

        try:
            return template % values
        except:
            pass

        if __debug__: self.notify_event("MSG_TEMPLATE_FORMATTING_ERROR_1")
        self.logger.error("Impossible to format %s of automated message %s, retrying with defaultdict", part_name, tpl_name,
                      exc_info=True)

        try:
            new_values = collections.defaultdict(lambda: "<unknown>", values)
            return template % new_values
        except:
            if __debug__: self.notify_event("MSG_TEMPLATE_FORMATTING_ERROR_2")
            self.logger.critical("Definitely impossible to format %s of automated message %s, returning original value",
                             part_name, tpl_name, exc_info=True)
            return template
    '''




@register_module
class TextMessagingExternalContacts(BaseDataManager):


    def _load_initial_data(self, **kwargs):
        super(TextMessagingExternalContacts, self)._load_initial_data(**kwargs)

        self.messaging_data.setdefault("globally_registered_contacts", PersistentDict()) # identifier -> None or dict(description, avatar)
        self.global_contacts._load_initial_data(**kwargs)



    def _check_database_coherency(self, strict=False, **kwargs):
        super(TextMessagingExternalContacts, self)._check_database_coherency(strict=strict, **kwargs)

        self.global_contacts._check_database_coherency(strict=strict, **kwargs)


    def _check_sender_email(self, sender_email):
        if sender_email in self.global_contacts:
            return
        super(TextMessagingExternalContacts, self)._check_sender_email(sender_email=sender_email)

    def _check_recipient_email(self, recipient_email, sender_email):
        if recipient_email in self.global_contacts:
            sending_character = self.get_character_or_none_from_email(sender_email) # FIXME - here we cheat, method not existing yet
            if sending_character is None:
                return # external contacts can send emails to any existing contact
            else:
                data = self.global_contacts[recipient_email]
                if data["access_tokens"] is None:
                    return # OK, it's a public address
                elif sending_character in data["access_tokens"]:
                    return # character has the permission to contact that external mailbox
                else:
                    raise UsageError(_("Mailbox %s has rejected your email") % recipient_email)
        else:
            super(TextMessagingExternalContacts, self)._check_recipient_email(recipient_email=recipient_email, sender_email=sender_email)


    # Handling of contacts #

    class GloballyRegisteredContactsManager(DataTableManager):

        TRANSLATABLE_ITEM_NAME = ugettext_lazy("contact")

        def _load_initial_data(self, **kwargs):
            for identifier, details in self._table.items():
                if details is None:
                    details = PersistentDict()
                    self._table[identifier] = details
                details.setdefault("immutable", True) # contacts that are necessary to gameplay CANNOT be edited/deleted
                details.setdefault("avatar", None)
                if details["avatar"]:
                    details["avatar"] = utilities.find_game_file(details["avatar"], "images")
                details.setdefault("description", None)
                details.setdefault("access_tokens", None) # PUBLIC contact

        def _preprocess_new_item(self, key, value):
            assert "immutable" not in value
            value["immutable"] = False # always, else new entry can't even be deleted later on
            value.setdefault("access_tokens", None)
            return (key, PersistentDict(value))
            # other params are supposed to exist in "value"

        def _check_item_validity(self, key, value, strict=False):
            utilities.check_is_slug(key) # not necessarily an email
            utilities.check_has_keys(value, ["immutable", "avatar", "description", "access_tokens"], strict=strict)
            utilities.check_is_bool(value["immutable"],)
            if value["access_tokens"] is not None: # None means "public"
                all_usernames = self._inner_datamanager.get_character_usernames()
                for username in value["access_tokens"]:
                    assert username in all_usernames, username # this check could be removed in the future, if other kinds of tokens are used!!
            if value["description"]: # optional
                utilities.check_is_string(value["description"], multiline=False)
            if value["avatar"]: # optional
                utilities.check_is_game_file(value["avatar"]) # FIXME improve that

        def _sorting_key(self, item_pair):
            return item_pair[0] # we sort by email, simply...

        def _get_table_container(self, root):
            return root["messaging"]["globally_registered_contacts"]

        def _item_can_be_edited(self, key, value):
            return (True if not value.get("immutable") else False)

    global_contacts = LazyInstantiationDescriptor(GloballyRegisteredContactsManager)


    @transaction_watcher
    def grant_private_contact_access_to_character(self, username=CURRENT_USER, contact_id=None, avatar=None, description=None):
        """
        Contact MUST exist, and be a "restricted access" contact.
        
        Duplicate grants do not raise errors.
        
        UNUSED ATM
        """
        username = self._resolve_username(username)
        assert contact_id and username in self.get_character_usernames()
        if contact_id not in self.global_contacts:
            self.global_contacts[contact_id] = dict(avatar=avatar, description=description, access_token=PersistentList([username]))
        else:
            data = self.global_contacts[contact_id]
            data["avatar"] = avatar or data["avatar"] # we let current as fallback
            data["description"] = description or data["description"] # we let current as fallback
            if data["access_tokens"] is None:
                pass # let PUBLIC access remain as is
            elif username not in data["access_token"]:
                data["access_tokens"].append(username)
            else:
                pass # swallow "access already granted" error

    @transaction_watcher
    def revoke_private_contact_access_from_character(self, username=CURRENT_USER, contact_id=None):
        """
        Contact MUST exist, and be a "restricted access" contact.
        
        UNUSED ATM
        """
        assert contact_id
        if contact_id in self.global_contacts:
            data = self.global_contacts[contact_id]
            if data["access_tokens"] is None:
                pass # let PUBLIC access remain as is
            elif username in data["access_token"]:
                data["access_tokens"].remove(username)
                assert username not in data["s"] # only 1 occurrence existed
                if not data["access_tokens"]:
                    # no one has access to that contact anymore, do some cleanup!
                    del self.global_contacts[contact_id]
            else:
                pass # swallow "access already removed" error
        else:
            pass # swallow "no such contact" error




@register_module
class TextMessagingTemplates(BaseDataManager):

    def _load_initial_data(self, **kwargs):
        super(TextMessagingTemplates, self)._load_initial_data(**kwargs)

        game_data = self.data
        messaging = self.messaging_data
        messaging.setdefault("manual_messages_templates", PersistentDict())

        if isinstance(messaging["manual_messages_templates"], list): # to simplify exchanges with dispatched emails, we allow list fixtures
            for t in messaging["manual_messages_templates"]:
                assert ("id" in t), t
            messaging["manual_messages_templates"] = dict((t["id"], t) for t in messaging["manual_messages_templates"])

        def _normalize_messages_templates(msg_list):

            for msg in msg_list:

                msg["sender_email"], msg["recipient_emails"] = self._normalize_message_addresses(msg.get("sender_email", ""), msg.get("recipient_emails", []))

                msg["subject"] = msg.get("subject", "")
                msg["body"] = msg.get("body", "")
                msg["attachment"] = msg.get("attachment", None)
                msg["transferred_msg"] = msg.get("transferred_msg", None)
                msg["is_used"] = msg.get("is_used", False)
                msg["parent_id"] = msg.get("parent_id", None)

                if "id" in msg:
                    del msg["id"] # cleanup

        # complete_messages_templates(game_data["automated_messages_templates"], is_manual=False)
        _normalize_messages_templates(messaging["manual_messages_templates"].values())


    def _check_database_coherency(self, strict=False, **kwargs):
        super(TextMessagingTemplates, self)._check_database_coherency(**kwargs)

        messaging = self.messaging_data

        template_fields = "sender_email recipient_emails subject body attachment transferred_msg is_used parent_id".split()

        for tpl in messaging["manual_messages_templates"].values():
            utilities.check_has_keys(tpl, keys=template_fields, strict=strict)

        # FIXME - check templates more here #


    def _build_new_message(self, *args, **kwargs):
        use_template = kwargs.pop("use_template", None) # we remove our specific use_template param
        msg = super(TextMessagingTemplates, self)._build_new_message(*args, **kwargs)

        if use_template:
            try:
                tpl = self.get_message_template(use_template)
                tpl["is_used"] = True # will stay True even if message sending is actually canceled - we don't care
            except UsageError, e:
                self.logger.error(e, exc_info=True) # non-fatal error

        return msg


    @readonly_method
    def get_messages_templates(self):
        return self.messaging_data["manual_messages_templates"]

    @readonly_method
    def get_message_template(self, tpl_id):
        mydata = self.messaging_data["manual_messages_templates"]
        if tpl_id not in mydata:
            raise AbnormalUsageError(_("Unexisting template id %r") % tpl_id)
        return mydata[tpl_id]



@register_module
class TextMessagingForCharacters(BaseDataManager): # TODO REFINE

    def _load_initial_data(self, **kwargs):
        super(TextMessagingForCharacters, self)._load_initial_data(**kwargs)

        game_data = self.data
        messaging = self.messaging_data

        utilities.check_is_game_file(game_data["global_parameters"]["default_contact_avatar"])

        for (name, character) in game_data["character_properties"].items():
            character.setdefault("has_new_messages", False)
            character.setdefault("new_messages_notification", None)

            # ADDRESS BOOK may contain any email, including characters' and "self" #
            character.setdefault("address_book", []) # just for memory - will be overridden below

        pangea_network = game_data["global_parameters"]["pangea_network_domain"]

        for (index, msg) in enumerate(messaging["messages_dispatched"] + messaging["messages_queued"]):
            # we modify the dicts in place

            if "@" not in msg["sender_email"]:
                msg["sender_email"] = (msg["sender_email"] + "@" + pangea_network) # we allow short character usernames as sender/recipient

            msg["has_read"] = msg.get("has_read", PersistentList())
            msg["has_replied"] = msg.get("has_replied", PersistentList())

            msg["visible_by"] = msg.get("visible_by", PersistentDict())
            msg["visible_by"].update(self._determine_basic_visibility(msg)) # we might override here

        # we compute automatic address_book for the first time
        self._recompute_all_address_book_via_msgs()
        assert not self._recompute_all_address_book_via_msgs()

        # initial coherency check
        all_emails = self.get_sorted_user_contacts(self.master_login) # ALL available
        #print (">>>>>>>>###", all_emails)
        for msg in messaging["messages_dispatched"] + messaging["messages_queued"]:
            assert msg["sender_email"] in all_emails, msg["sender_email"]
            for recipient_email in msg["recipient_emails"]:
                assert recipient_email in all_emails, recipient_email


    def _check_database_coherency(self, **kwargs):
        super(TextMessagingForCharacters, self)._check_database_coherency(**kwargs)

        # TODO - check all messages and templates with utilities.check_is_restructuredtext(value) ? What happens if invalid rst ?

        game_data = self.data
        messaging = self.messaging_data

        utilities.check_is_slug(game_data["global_parameters"]["pangea_network_domain"])

        message_reference = {
                             "has_read": PersistentList,
                             "has_replied": PersistentList,
                             "is_certified": bool, # for messages sent via automated processes
                             }

        def _check_message_list(msg_list, is_queued):

            for msg in msg_list:

                utilities.check_dictionary_with_template(msg, message_reference, strict=False)

                all_chars = game_data["character_properties"].keys()
                all_users = all_chars + [game_data["global_parameters"]["master_login"]]
                assert all((char in all_users) for char in msg["has_read"]), msg["has_read"]
                assert all((char in all_users) for char in msg["has_replied"]), msg["has_replied"]

                potential_viewers = self.get_character_usernames() + [self.master_login] # master_login is set if NPCs were concerned
                for username, reason in msg["visible_by"].items():
                    assert username in potential_viewers
                    utilities.check_is_slug(reason)
                    assert reason in VISIBILITY_REASONS, reason

                if not is_queued: # queued message don't have basic visibility ysettings yet
                    # later, special script events might make it normal that even senders or recipients do NOT see the message anymore, but NOT NOW
                    assert set(self._determine_basic_visibility(msg).keys()) <= set(msg["visible_by"].keys()), [self._determine_basic_visibility(msg).keys(), msg]


        # WARNING - we must check the two lists separately, because little incoherencies can appear at their junction due to the workflow
        # (the first queued messages might actually be younger than the last ones of the sent messages list)
        _check_message_list(messaging["messages_dispatched"], is_queued=False)
        _check_message_list(messaging["messages_queued"], is_queued=True)

        # new-message audio notification system (characters may have no dedicated notification)
        all_msg_files = [self.data["audio_messages"][properties["new_messages_notification"]]["file"]
                         for properties in self.data["character_properties"].values() if properties["new_messages_notification"]]
        utilities.check_no_duplicates(all_msg_files) # users must NOT have the same new-message audio notifications

        for character_set in self.data["character_properties"].values():
            utilities.check_no_duplicates(character_set["address_book"])
            for external_contact in character_set["address_book"]: # MIGHT BE A CHARACTER CONTACT!!
                utilities.check_is_email(external_contact) # FIXME - check that it exists and is authorized, too ???
        assert not self._recompute_all_address_book_via_msgs() # we recompute address_book, and check everything is coherent


        # special mailing list
        ml_address = self.get_global_parameter("all_players_mailing_list")
        ml_props = self.global_contacts[ml_address] # MUST exist
        assert ml_props["immutable"]


    """
    @staticmethod
    def _sort_and_join_contact_parts(contact_parts):
        contact_parts = list(set(contact_parts)) # we remove duplicates...
        contact_parts.sort(key=lambda parts: parts[1] + parts[0])
        contacts = ["@".join(parts) for parts in contact_parts]
        return contacts
    """

    def _build_new_message(self, *args, **kwargs):
        msg = super(TextMessagingForCharacters, self)._build_new_message(*args, **kwargs)

        is_read = kwargs.get("is_read", False) # we expect it in keyword args... bring on py3k plz

        assert "has_read" not in msg and "has_replied" not in msg and "visible_by" not in msg
        msg.update({"has_read": PersistentList(),
                    "has_replied": PersistentList(),
                    "visible_by": PersistentDict(), })

        if is_read: # workaround : we add ALL users to the "has read" list !
            msg["has_read"] = PersistentList(self.get_character_usernames() + [self.master_login])

        return msg

    def _immediately_dispatch_message(self, msg):
        msg["visible_by"].update(self._determine_basic_visibility(msg)) # we shamelessly override more specialized visibilities
        for (k, v) in msg["visible_by"].items():
            if (v == VISIBILITY_REASONS.sender) and (k not in msg["has_read"]):
                msg["has_read"].append(k) # of course everyone knows his own sent messages...
        super(TextMessagingForCharacters, self)._immediately_dispatch_message(msg)

    def _message_dispatching_post_hook(self, frozen_msg):
        super(TextMessagingForCharacters, self)._message_dispatching_post_hook(frozen_msg)

        self._update_address_book(msg=frozen_msg)
        #print (">>>>>>>>>>>", frozen_msg["visible_by"])
        characters = set(self.get_character_usernames())
        target_characters = [username for username, reason in frozen_msg["visible_by"].items()
                                      if reason != VISIBILITY_REASONS.sender and username in characters] # thus we remove master_login and sender

        assert self.is_game_writable() # we MUST be in writable game here
        self.set_new_message_notification(concerned_characters=target_characters, new_status=True)

    def _check_sender_email(self, sender_email):
        if sender_email in self.get_character_emails():
            return # OK, sent by a character (player or not)
        super(TextMessagingForCharacters, self)._check_sender_email(sender_email=sender_email)

    def _check_recipient_email(self, recipient_email, sender_email):
        if recipient_email in self.get_character_emails():
            return # OK, sent by a character (player or not)
        super(TextMessagingForCharacters, self)._check_recipient_email(recipient_email=recipient_email, sender_email=sender_email)


    @readonly_method
    def _determine_basic_visibility(self, msg):
        """
        This method does NOT modify the message, it just returns a dict suitable as "visible_by" message field.
        """
        visibilities = {}
        ml = self.get_global_parameter("all_players_mailing_list")

        assert utilities.check_no_duplicates(msg["recipient_emails"]) # already normalized
        for recipient_email in msg["recipient_emails"]:
            if recipient_email == ml:
                for usr in (username for (username, data) in self.get_character_sets().items() if not data["is_npc"]): # only PLAYER characters
                    visibilities[usr] = VISIBILITY_REASONS.recipient
            else:
                recipient_username = self.get_character_or_none_from_email(recipient_email)
                if recipient_username:
                    visibilities[recipient_username] = VISIBILITY_REASONS.recipient
                else:
                    visibilities[self.master_login] = VISIBILITY_REASONS.recipient # might occur several times, we don't care

        sender_username = self.get_character_or_none_from_email(msg["sender_email"])
        if sender_username:
            visibilities[sender_username] = VISIBILITY_REASONS.sender # might override "recipient" status, in case of self-mailing
        else:
            visibilities[self.master_login] = VISIBILITY_REASONS.sender


        return visibilities


    @readonly_method
    def get_character_email(self, username=CURRENT_USER):
        username = self._resolve_username(username)
        assert self.is_character(username)
        return username + "@" + self.get_global_parameter("pangea_network_domain")

    @readonly_method
    def get_character_emails(self):
        pangea_network_domain = self.get_global_parameter("pangea_network_domain")
        return [username + "@" + pangea_network_domain for username in self.get_character_usernames()]

    @readonly_method
    def get_other_character_emails(self, username=CURRENT_USER):
        username = self._resolve_username(username)
        my_email = self.get_character_email(username=username)
        return [email for email in self.get_character_emails() if email != my_email]


    @readonly_method
    def get_character_or_none_from_email(self, email):
        """
        Returns the character username corresponding to that email, or None.
        """
        parts = email.split("@")
        if len(parts) != 2 or parts[1] != self.get_global_parameter("pangea_network_domain"):
            return None

        username = parts[0]
        if username in self.get_character_usernames():
            return username
        else:
            return None

    @readonly_method
    def get_username_from_email(self, email):
        """
        Returns the character username corresponding to that email, 
        or the login of the game master.
        """
        username = self.get_character_or_none_from_email(email)
        if username:
            return username
        else:
            return self.master_login


    """ DEPRECATED          FIXME FIXME
    @readonly_method    
    def get_external_emails(self, username=CURRENT_USER):
        # should NOT be called for anonymous users
        username = self._resolve_username(username)
        if self.is_master(username):
            char_sets = self.get_character_sets()
            all_contacts = [contact for (name, character) in char_sets.items()
                                         for contact in character["address_book"]]
            return sorted(set(all_contacts))
        else:
            character = self.get_character_properties(username)
            return character["address_book"]
    

    @readonly_method
    def get_sorted_user_contacts(self, username=CURRENT_USER):
        # should NOT be called for anonymous users
        username = self._resolve_username(username)
        return self.get_characters_email() + self.get_external_emails(username)


    @readonly_method
    def _BROKEN__get_available_contacts(self, username=CURRENT_USER): # FIXME
        username = self._resolve_username(username)
        return  {key: value for (key, value) in self.global_contacts}
    
    """

    '''
    @readonly_method USELESS, use get_user_related_messages
    def get_game_master_messages(self):  # FIXME with visible_by ****
        # returns all emails sent to external contacts or robots
        all_messages = self.get_all_dispatched_messages()
        master_login = self.master_login
        return [msg for msg in all_messages if master_login in msg["visible_by"]]
    '''



    def _set_message_read_state(self, username=CURRENT_USER, msg=None, is_read=None):
        # we don't care about whether user had the right to view msg or not
        username = self._resolve_username(username)
        assert username and msg and is_read is not None
        if is_read and username not in msg["has_read"]:
            msg["has_read"].append(username)
        elif not is_read and username in msg["has_read"]:
            msg["has_read"].remove(username)

    def _set_message_reply_state(self, username=CURRENT_USER, msg=None, is_read=None):
        # we don't care about whether user had the right to view msg or not
        username = self._resolve_username(username)
        assert username and msg and is_read is not None
        if is_read and username not in msg["has_replied"]:
            msg["has_replied"].append(username)
        elif not is_read and username in msg["has_replied"]:
            msg["has_replied"].remove(username)

    @transaction_watcher(always_writable=True)
    def set_message_read_state(self, username=CURRENT_USER, msg_id=None, is_read=None):
        username = self._resolve_username(username) # username can be master login here !
        assert username and msg_id and is_read is not None
        msg = self.get_dispatched_message_by_id(msg_id)
        self._set_message_read_state(username, msg, is_read)


    def _get_messages_visible_for_reason(self, reason, username):
        assert reason in VISIBILITY_REASONS
        assert username in self.get_character_usernames() + [self.master_login]
        username = self._resolve_username(username)
        records = [record for record in self.messaging_data["messages_dispatched"] if (record["visible_by"].get(username) == reason)]
        return records # chronological order

    @readonly_method
    def get_sent_messages(self, username=CURRENT_USER):
        username = self._resolve_username(username)
        return self._get_messages_visible_for_reason(reason=VISIBILITY_REASONS.sender, username=username)

    @readonly_method
    def get_received_messages(self, username=CURRENT_USER):
        username = self._resolve_username(username)
        res = self._get_messages_visible_for_reason(reason=VISIBILITY_REASONS.recipient, username=username)
        return res

    @transaction_watcher
    def pop_received_messages(self, username=CURRENT_USER):
        """
        Also resets the 'new message' notification of concerner character, if any.
        
        BUGGY AND NOT USED ANYMORE
        """
        username = self._resolve_username(username)
        records = self.get_received_messages(username=username)
        if self.is_character(username):
            self.set_new_message_notification(concerned_characters=[username], new_status=False)
        return records

    @readonly_method
    def get_user_related_messages(self, username=CURRENT_USER):
        """
        For game master, actually returns all emails sent to external contacts.
        Ptreserves msg order by date ascending.
        """
        username = self._resolve_username(username)
        all_messages = self.get_all_dispatched_messages()
        return [msg for msg in all_messages if username in msg["visible_by"]]


    @readonly_method
    def sort_messages_by_conversations(self, messages):
        """
        Returns groups of conversation-relation messages, sorted by "most recent first". 
        The first groups contain the conversations which have been updated most recently.
        
        Returns non-ZODB structures!
        """
        del self # static method actually
        assert sorted(messages, key=lambda msg: msg["sent_at"]) == messages # msgs must be naturally well sorted first, in DATE ASC order

        groups = OrderedDict()
        for msg in reversed(messages): # important
            groups.setdefault(msg["group_id"], [])
            groups[msg["group_id"]].append(msg)

        return groups.values()


    @readonly_method
    def get_unread_messages_count(self, username=CURRENT_USER):
        """
        Considers ALL user-related messages.
        """
        username = self._resolve_username(username)
        unread_msgs = [msg for msg in self.get_user_related_messages(username=username)
                           if username not in msg["has_read"]]
        return len(unread_msgs)


    @readonly_method
    def get_all_contacts_unsorted(self):
        return self.get_character_emails() + self.global_contacts.keys()


    @readonly_method
    def get_contacts_display_properties(self, email_contacts, as_dict=False):
        """
        Returns info needed to display the contact and its attributes, 
        for both characters and external contacts.
        
        Results are returned as a sequence in the same order as input, 
        unless as_dict is True (results are in this case indexed by email adressed).
        """
        results = []
        results_dict = {}

        default_avatar = self.get_global_parameter("default_contact_avatar")

        assert isinstance(email_contacts, (PersistentList, list, tuple))
        character_emails = set(self.get_character_emails())
        for email in email_contacts:
            if email in character_emails:
                props = self.get_character_properties(self.get_character_or_none_from_email(email))
                assert "character_color" in props
            elif email in self.global_contacts:
                props = self.global_contacts[email]
            else:
                props = dict(avatar=default_avatar,
                             description=_("Unidentified contact"))

            # as well characters as external contacts MUST have these fields in their properties
            data = dict(address=email,
                        avatar=props["avatar"],
                        color=props.get("character_color", None), # only present for characters
                        description=props["description"] if "description" in props else props["official_role"])

            if as_dict:
                results_dict[email] = data
            else:
                results.append(data)

        return results_dict if as_dict else results

    @staticmethod
    def sort_email_addresses_list(emails_list):
        return sorted(emails_list, key=lambda email: (email[0] != '[',) + tuple(reversed(email.split("@")))) # sort by domain then username

    @readonly_method
    def get_sorted_user_contacts(self, username=CURRENT_USER):
        """
        For both master and characters.
        """

        _sorter = self.sort_email_addresses_list

        username = self._resolve_username(username)
        assert not self.is_anonymous(username)
        if self.is_master(username=username):
            res = _sorter(self.get_character_emails()) + _sorter(self.global_contacts.keys())
        else:
            res = _sorter(self.get_character_address_book(username=username)) # including user himself

        # if available, enforce all-players mailing-list at the START of list #
        ml = self.get_global_parameter("all_players_mailing_list")
        if ml in res:
            res.remove(ml)
            res.insert(0, ml)

        return res


    @readonly_method
    def get_character_address_book(self, username=CURRENT_USER):
        username = self._resolve_username(username)
        props = self.get_character_properties(username)
        return props["address_book"] # not sorted


    def _recompute_all_address_book_via_msgs(self):
        address_book_changed = False
        for msg in self.messaging_data["messages_dispatched"]:
            new_contacts_added = self._update_address_book(msg)
            if new_contacts_added:
                #print("new_contacts_added", msg["subject"], new_contacts_added)
                address_book_changed = True
        return address_book_changed


    @transaction_watcher(always_writable=True)
    def _update_address_book(self, msg):
        new_contacts_added = False

        (concerned_characters, all_msg_emails) = self._get_address_book_updates(msg)

        for username in concerned_characters:
            props = self.get_character_properties(username)
            old_address_book = set(props["address_book"])
            new_address_book = old_address_book | all_msg_emails
            assert set(props["address_book"]) <= new_address_book # that list can only grow - of course
            props["address_book"] = PersistentList(new_address_book) # no particular sorting here, but unicity is ensured

            new_contacts_added = new_contacts_added or (new_address_book != old_address_book) # SETS comparison

        return new_contacts_added


    @readonly_method
    def _get_address_book_updates(self, msg):
        """
        OBSOLETE 
        
        Retrieve info needed to update the *address_book* fields of character accounts,
        when they send/receive this single message.
        """
        ###all_characters_emails = set(self.get_character_emails())
        all_msg_emails = set(msg["recipient_emails"] + [msg["sender_email"]])
        ##external_emails = msg_emails - all_characters_emails

        concerned_characters = {key: value for (key, value) in msg["visible_by"].items() if key != self.master_login} # can't use dict.copy() here because it modifies stuffs

        return (concerned_characters, all_msg_emails)



    # Audio notifications for new messages #

    @readonly_method
    def get_pending_new_message_notifications(self):
        # returns users that must be notified, with corresponding message audio_id
        needing_notifications = PersistentDict((username, properties["new_messages_notification"])
                                                for (username, properties) in self.get_character_sets().items()
                                                if properties["has_new_messages"])
        return needing_notifications

    @readonly_method
    def get_all_new_message_notification_sounds(self):
        return [char["new_messages_notification"] for char in self.get_character_sets().values()]

    @readonly_method
    def has_new_message_notification(self, username=CURRENT_USER):
        """Only for CHARACTERS ATM"""
        username = self._resolve_username(username)
        return self.data["character_properties"][username]["has_new_messages"] # boolean

    @transaction_watcher
    def set_new_message_notification(self, concerned_characters, new_status):
        """Only for CHARACTERS ATM"""
        for character in concerned_characters:
            self.data["character_properties"][character]["has_new_messages"] = new_status






@register_module
class TextMessagingInterception(BaseDataManager):

    def _load_initial_data(self, **kwargs):
        super(TextMessagingInterception, self)._load_initial_data(**kwargs)

        game_data = self.data
        messaging = self.messaging_data

        for (name, data) in game_data["character_properties"].items():
            data.setdefault("wiretapping_targets", PersistentList())
            data.setdefault("confidentiality_activation_datetime", None) # UTC datetime when SSL/TLS security was bought

    def _check_database_coherency(self, **kwargs):
        super(TextMessagingInterception, self)._check_database_coherency(**kwargs)

        game_data = self.data
        messaging = self.messaging_data

        character_names = self.get_character_usernames()
        for (name, data) in self.get_character_sets().items():
            for char_name in data["wiretapping_targets"]:
                assert char_name in character_names
            if data["confidentiality_activation_datetime"] is not None:
                utilities.check_is_datetime(data["confidentiality_activation_datetime"])

            wiretapping_targets_full1 = self.get_wiretapping_targets(username=name)
            wiretapping_targets_full2 = self.determine_broken_wiretapping_data(username=name).keys() + self.determine_effective_wiretapping_traps(username=name)
            utilities.check_no_duplicates(wiretapping_targets_full1)
            utilities.check_no_duplicates(wiretapping_targets_full2)
            assert set(wiretapping_targets_full1) == set(wiretapping_targets_full2)


    @transaction_watcher
    def _immediately_dispatch_message(self, msg):
        assert not msg["visible_by"] # this is the outer-most module at the moment
        for username in self.get_character_usernames():
            effective_wiretapping_targets_emails = [self.get_character_email(target)
                                                    for target in self.determine_effective_wiretapping_traps(username)] # EFFECTIVE, not mere wiretapping targets!!
            if (msg["sender_email"] in effective_wiretapping_targets_emails or
                    any((recipient in effective_wiretapping_targets_emails) for recipient in msg["recipient_emails"])):
                msg["visible_by"][username] = VISIBILITY_REASONS.interceptor # might be overriden by more basic visibility (sender, recipient...), in parent methods

        super(TextMessagingInterception, self)._immediately_dispatch_message(msg)


    @readonly_method
    def get_intercepted_messages(self, username=CURRENT_USER): # for wiretapping
        username = self._resolve_username(username)
        return self._get_messages_visible_for_reason(reason=VISIBILITY_REASONS.interceptor, username=username)


    # management of wiretapping targets #

    @transaction_watcher
    def set_wiretapping_targets(self, username=CURRENT_USER, target_names=None):
        assert target_names is not None
        username = self._resolve_username(username)
        target_names = sorted(list(set(target_names))) # renormalization, just in case

        character_names = self.get_character_usernames() # here we allow wiretapping oneself, even if it makes no sense
        for name in target_names:
            if name not in character_names:
                raise AbnormalUsageError(_("Unknown target username '%(target)s'") % SDICT(target=name)) # we can show it

        data = self.get_character_properties(username)
        data["wiretapping_targets"] = PersistentList(target_names)

        self.log_game_event(ugettext_noop("Wiretapping targets set to %(targets)s for %(username)s."),
                             PersistentDict(targets="[%s]" % (", ".join(target_names)), username=username),
                             url=None)

    @readonly_method
    def get_wiretapping_targets(self, username=CURRENT_USER):
        username = self._resolve_username(username)
        return self.get_character_properties(username)["wiretapping_targets"]

    @readonly_method
    def get_listeners_for(self, target):
        listeners = []
        for username, data in self.get_character_sets().items():
            if target in data["wiretapping_targets"]:
                listeners.append(username)
        return sorted(listeners) # list of character usernames


    @transaction_watcher
    def set_confidentiality_protection_status(self, username=CURRENT_USER, has_confidentiality=None):
        """
        Only for characters of course.
        """
        username = self._resolve_username(username)
        data = self.get_character_properties(username)
        data["confidentiality_activation_datetime"] = (datetime.utcnow() if has_confidentiality else None)

    @readonly_method
    def get_confidentiality_protection_status(self, username=CURRENT_USER):
        """
        Returns None, or the activation datetime.
        """
        username = self._resolve_username(username)
        return self.get_character_properties(username)["confidentiality_activation_datetime"]


    @readonly_method # FIXME UNTESTED
    def determine_effective_wiretapping_traps(self, username=CURRENT_USER):
        """
        Filters out wiretapping targets that have confidentiality layer enabled.
        """
        username = self._resolve_username(username)
        targets = self.get_character_properties(username=username)["wiretapping_targets"]
        effective_targets = [target for target in targets \
                             if self.get_character_properties(username=target)["confidentiality_activation_datetime"] is None]
        return effective_targets

    @readonly_method # FIXME UNTESTED
    def determine_broken_wiretapping_data(self, username=CURRENT_USER):
        """
        Filter out wiretapping targets that have confidentiality layer enabled.
        """
        username = self._resolve_username(username)
        targets = self.get_character_properties(username=username)["wiretapping_targets"]
        targets_data = {target: self.get_character_properties(username=target)["confidentiality_activation_datetime"] for target in targets}
        ineffective_targets = {key: value for (key, value) in targets_data.items() if value is not None}
        return ineffective_targets # returns a dict {username: ssl_activation_datetime}





@register_module
class RadioMessaging(BaseDataManager): # TODO REFINE

    _radio_playlist_novelty_marker = "radio_playlist"

    def _load_initial_data(self, **kwargs):
        super(RadioMessaging, self)._load_initial_data(**kwargs)
        self.radio_spots._load_initial_data(**kwargs)

    def _check_database_coherency(self, **kwargs):
        super(RadioMessaging, self)._check_database_coherency(**kwargs)
        self.radio_spots._check_database_coherency(**kwargs)

        game_data = self.data
        value = game_data["global_parameters"]["pending_radio_messages"]
        utilities.check_is_list(value) # must be ordered, we can't use a set !
        for audio_id in value:
            assert audio_id in self.radio_spots # audio IDs here

        utilities.check_is_slug(game_data["global_parameters"]["pangea_radio_frequency"])
        utilities.check_is_bool(game_data["global_parameters"]["radio_is_on"])


    class RadioSpotsManager(DataTableManager):

        TRANSLATABLE_ITEM_NAME = ugettext_lazy("radio spots")

        def _load_initial_data(self, **kwargs):

            for identifier, details in self._table.items():
                details.setdefault("immutable", False) # we assume ANY radio spot is optional for the game, and can be edited/delete
                details.setdefault("file", None) # LOCAL file
                if details["file"]:
                    details["file"] = utilities.find_game_file(details["file"], "audio", "radio_spots")
                details.setdefault("url", None) # LOCAL file

            audiofiles = [value["file"] for value in self._table.values()]
            utilities.check_no_duplicates(audiofiles) # only checked at load time, next game master can do whatever he wants


        def _preprocess_new_item(self, key, value):
            assert "immutable" not in value
            value["immutable"] = False
            return (key, PersistentDict(value))
            # other params are supposed to exist in "value"

        def _check_item_validity(self, key, value, strict=False):

            #print ("RADIOSPOT IS", key, value)

            utilities.check_is_slug(key)

            utilities.check_has_keys(value, ["title", "text", "file", "url", "immutable"], strict=strict)

            utilities.check_is_string(value["title"])
            assert value["text"] and isinstance(value["text"], basestring)

            assert not value["file"] or isinstance(value["file"], basestring), value["file"]
            assert not value["url"] or isinstance(value["url"], basestring), value["url"]

            assert value["url"] or value["file"] # if both, it's supposed to be the same sound file

            # TODO - ensure no "|" in file name!!
            if value["file"]:
                utilities.check_is_game_file(value["file"])
            if value["url"]:
                assert value["url"].startswith("http") # ROUGH check...


        def _sorting_key(self, item_pair):
            return item_pair[0] # we sort by key, simply...

        def _get_table_container(self, root):
            return root["audio_messages"]

        def _item_can_be_edited(self, key, value):
            return not value["immutable"]

    radio_spots = LazyInstantiationDescriptor(RadioSpotsManager)


    def _check_audio_ids(self, audio_ids):
        for audio_id in audio_ids:
            if audio_id not in self.data["audio_messages"].keys():
                raise UsageError(_("Unknown radio message identifier - %(audio_id)s") % SDICT(audio_id=audio_id))

    @transaction_watcher
    def add_radio_message(self, audio_id):
        """
        No-op if audio message already in queue.
        """
        self._check_audio_ids([audio_id])
        queue = self.data["global_parameters"]["pending_radio_messages"]
        if audio_id not in queue:
            queue.append(audio_id)
            self.reset_novelty_accesses(self._radio_playlist_novelty_marker)

    @transaction_watcher
    def set_radio_messages(self, audio_ids):
        """
        Allows duplicate audio messages.
        """
        self._check_audio_ids(audio_ids)
        new_list = PersistentList(audio_ids)
        if self.data["global_parameters"]["pending_radio_messages"] != new_list:
            self.data["global_parameters"]["pending_radio_messages"] = new_list
            self.reset_novelty_accesses(self._radio_playlist_novelty_marker)

    @transaction_watcher
    def mark_current_playlist_read(self, username=CURRENT_USER):
        username = self._resolve_username(username)
        self.access_novelty(username=username, item_key=self._radio_playlist_novelty_marker)

    @readonly_method
    def has_read_current_playlist(self, username=CURRENT_USER):
        username = self._resolve_username(username)
        return (not self.get_all_next_audio_messages() or
                self.has_accessed_novelty(username=username, item_key=self._radio_playlist_novelty_marker))

    @transaction_watcher
    def reset_audio_messages(self):
        # note that the web radio might already have retrieved the whole playlist...
        self.data["global_parameters"]["pending_radio_messages"] = PersistentList()

    @readonly_method
    def get_all_available_audio_messages(self):
        return self.radio_spots

    @readonly_method
    def check_radio_frequency(self, frequency):
        if frequency != self.get_global_parameter("pangea_radio_frequency"):
            raise UsageError(_("Unknown radio frequency"))

    @readonly_method
    def get_all_next_audio_messages(self):
        queue = self.data["global_parameters"]["pending_radio_messages"]
        return queue # audio ids

    @readonly_method
    def get_next_audio_message(self):
        queue = self.data["global_parameters"]["pending_radio_messages"]
        if queue:
            return queue[0] # we let the audio id in the queue anyway !
        else:
            return None

    @readonly_method
    def get_audio_message_properties(self, audio_id):
        """
        Returns audio properties.
        """
        return self.radio_spots[audio_id]


    @transaction_watcher
    def notify_audio_message_termination(self, audio_id):
        queue = self.data["global_parameters"]["pending_radio_messages"]

        res = False

        if audio_id in queue: # we check, in case several radio run simultaneously or if a reset occurred inbetween...
            queue.remove(audio_id)
            res = True

        if not queue: # playlist empty, we stop the radio
            self.data["global_parameters"]["radio_is_on"] = False

        for properties in self.get_character_sets().values():
            if properties["new_messages_notification"] == audio_id:
                # even if new messages have arrived just after the playing of the audio message, it's OK,
                # since anyway the user will need some time to reach his webmail...
                properties["has_new_messages"] = False
                break # users can't share the same audio message, so...

        return res

    @transaction_watcher
    def set_radio_state(self, is_on=True):
        self.data["global_parameters"]["radio_is_on"] = is_on















@register_module
class Chatroom(BaseDataManager):

    def _load_initial_data(self, **kwargs):
        super(Chatroom, self)._load_initial_data(**kwargs)

        game_data = self.data

        for (name, character) in game_data["character_properties"].items():
            character.setdefault("last_chatting_time", None)

        game_data.setdefault("chatroom_messages", PersistentList())

        game_data["global_parameters"].setdefault("chatroom_presence_timeout_s", 20)
        game_data["global_parameters"].setdefault("chatroom_timestamp_display_threshold_s", 120)

    def _check_database_coherency(self, **kwargs):
        super(Chatroom, self)._check_database_coherency(**kwargs)

        game_data = self.data

        utilities.check_is_positive_int(self.get_global_parameter("chatroom_presence_timeout_s"))
        utilities.check_is_positive_int(self.get_global_parameter("chatroom_timestamp_display_threshold_s"))

        for (name, character) in game_data["character_properties"].items():
            assert character["last_chatting_time"] is None or (
                    isinstance(character["last_chatting_time"], datetime) and
                    character["last_chatting_time"] <= datetime.utcnow())

        chatroom_msg_reference = {
            "time": datetime,
            "username": basestring,
            "message": basestring,
            }
        previous_time = None
        for msg in game_data["chatroom_messages"]:
            utilities.check_dictionary_with_template(msg, chatroom_msg_reference)
            assert msg["message"].strip() == msg["message"]
            assert msg["message"] # non empty
            if previous_time:
                assert previous_time <= msg["time"] # chat messages are sorted by chronological order
            previous_time = msg["time"]
            assert msg["username"] is None or msg["username"] == self.get_global_parameter("master_login") or msg["username"] in game_data["character_properties"].keys()

    @transaction_watcher # allows micro-transaction inside readonly method
    def _set_chatting_status(self, username=CURRENT_USER):
        username = self._resolve_username(username)
        self.data["character_properties"][username]["last_chatting_time"] = datetime.utcnow()
        self._set_online_status(username=username) # chatting means being there too...

    @readonly_method
    def get_chatting_status(self, username=CURRENT_USER):
        username = self._resolve_username(username)
        timestamp = self.data["character_properties"][username]["last_chatting_time"]
        return timestamp and timestamp >= (datetime.utcnow() - timedelta(seconds=self.get_global_parameter("chatroom_presence_timeout_s")))

    @readonly_method
    def get_chatting_users(self, exclude_current=False):
        return sorted([username for username in self.get_character_usernames(exclude_current=exclude_current) if self.get_chatting_status(username)])

    @transaction_watcher
    def send_chatroom_message(self, message):
        """
        Master can chat too, as "system" talker.
        """

        if not self.user.is_authenticated:
            raise AbnormalUsageError(_("Only authenticated users may chat"))

        if self.user.is_character:
            self._set_chatting_status()

        message = escape(message.strip()) # we escape messages immediately, it's much safer

        if not message:
            raise UsageError(_("Chat message can't be empty"))

        record = PersistentDict(time=datetime.utcnow(), username=self.user.username, message=message)
        self.data["chatroom_messages"].append(record)


    @readonly_method # inner mini-transactions might occur though
    def get_chatroom_messages(self, from_slice_index): # from_slice_index might be negative

        new_messages = self.data["chatroom_messages"][from_slice_index:]
        new_slice_index = from_slice_index + len(new_messages)

        if not from_slice_index: # (from_slice_index-1]) would bring us to the latest message, not a previous one
            previous_msg_timestamp = None
        else:
            try:
                previous_msg = self.data["chatroom_messages"][from_slice_index - 1]
                previous_msg_timestamp = previous_msg["time"]
            except IndexError:
                previous_msg_timestamp = None

        if self.is_game_writable() and self.is_character():
            self._set_chatting_status() # just reading chats is an act of presence

        return (new_slice_index, previous_msg_timestamp, new_messages)


@register_module
class ActionScheduling(BaseDataManager):
    # USELESS ATM ?? FIXME ??

    def _load_initial_data(self, **kwargs):
        super(ActionScheduling, self)._load_initial_data(**kwargs)

        game_data = self.data

        game_data.setdefault("scheduled_actions", PersistentList())

        for evt in game_data["scheduled_actions"]:
            if isinstance(evt["execute_at"], (long, int)): # offset in minutes
                evt["execute_at"] = self.compute_effective_remote_datetime(evt["execute_at"])
        game_data["scheduled_actions"].sort(key=lambda evt: evt["execute_at"])



    def _check_database_coherency(self, **kwargs):
        super(ActionScheduling, self)._check_database_coherency(**kwargs)

        game_data = self.data

        scheduled_action_reference = {
            "execute_at": datetime,
            "function": (basestring, collections.Callable), # string to represent a datamanager method
            "args": tuple,
            "kwargs": PersistentDict
        }
        previous_time = None
        for action in game_data["scheduled_actions"]:
            if previous_time:
                assert previous_time <= action["execute_at"] # event lists are sorted by chronological order
            previous_time = action["execute_at"]
            if isinstance(action["function"], basestring):
                assert hasattr(self, action["function"])
            utilities.check_dictionary_with_template(action, scheduled_action_reference)


    def _process_periodic_tasks(self, report):
        super(ActionScheduling, self)._process_periodic_tasks(report)

        last_index_processed = None
        utcnow = datetime.utcnow()

        for (index, action) in enumerate(self.data["scheduled_actions"]):
            if action["execute_at"] <= utcnow:
                try:
                    function = action["function"]
                    if isinstance(function, basestring):
                        function = getattr(self, function) # hack for pickling instance methods...
                    args = action["args"]
                    kwargs = action["kwargs"]
                    function(*args, **kwargs)
                    # print (">>>> executed ", function)
                except:
                    if __debug__: self.notify_event("DELAYED_ACTION_ERROR")
                    self.logger.critical("Delayed action raised an error when executing : %s" % action, exc_info=True)
                last_index_processed = index # even if error, we remove the msg from list
            else:
                break # since actions are queued in CHRONOLOGICAL order...

        if last_index_processed is not None:
            self.data["scheduled_actions"] = self.data["scheduled_actions"][last_index_processed + 1:]
            report["actions_executed"] = last_index_processed + 1
        else:
            report["actions_executed"] = 0




    @transaction_watcher
    def schedule_delayed_action(self, date_or_delay_mn, function, *args, **kwargs):
        """
        Registers the given callable for a single delayed call.

        The callable can be a string (representing a method of this DataManager instance) or a real callable object.

        WARNING - in any way the concerned callable must be PICKLABLE and not wrapped by a transaction_watcher.
        """

        args = tuple(args) # already the case, normally...
        kwargs = PersistentDict(kwargs)

        # print >>sys.stderr, "REGISTERING ONE SHOT  ", function

        if isinstance(function, basestring):
            # print ("SEARCHING", function, "IN", sorted(dir(self)))
            if not hasattr(self, function) or not hasattr(getattr(self, function), '__call__'):
                raise TypeError(_("Only strings representing DataManager methods can be scheduled as delayed actions, not %(function)s") %
                                SDICT(function=function))
        elif not hasattr(function, '__call__'):
            raise TypeError(_("You can only register a callable object as a delayed action, not a %(function)r") %
                            SDICT(function=function))

        if isinstance(date_or_delay_mn, datetime):
            time = date_or_delay_mn
        else:
            time = self.compute_effective_remote_datetime(date_or_delay_mn)

        record = PersistentDict({
            "execute_at": time,
            "function": function,
            "args": args,
            "kwargs": kwargs
        })

        self.data["scheduled_actions"].append(record)
        self.data["scheduled_actions"].sort(key=lambda x: x["execute_at"])




@register_module
class PersonalFiles(BaseDataManager):

    COMMON_FILES_DIRS = "_common_files_"

    def _load_initial_data(self, **kwargs):
        super(PersonalFiles, self)._load_initial_data(**kwargs)


    def _check_database_coherency(self, **kwargs):
        super(PersonalFiles, self)._check_database_coherency(**kwargs)

        # common and personal file folders
        assert os.path.isdir(os.path.join(config.GAME_FILES_ROOT, "personal_files", self.COMMON_FILES_DIRS))
        for name in (self.data["character_properties"].keys() + [self.data["global_parameters"]["master_login"]]):
            assert os.path.isdir(os.path.join(config.GAME_FILES_ROOT, "personal_files", name)), name
            assert name != self.COMMON_FILES_DIRS # reserved

    @readonly_method
    def encrypted_folder_exists(self, folder):
        encrypted_folder = os.path.join(config.GAME_FILES_ROOT, "encrypted", folder)
        return os.path.isdir(encrypted_folder)


    @transaction_watcher # because of logs...
    def get_encrypted_files(self, username=CURRENT_USER, folder=None, password=None, absolute_urls=False):
        """
        Might raise environment errors if older/password incorrect.
        Username is used just for event logging.
        """
        assert folder and password
        username = self._resolve_username(username)
        if not self.encrypted_folder_exists(folder):
            raise UsageError(_("This encrypted archive doesn't exist."))

        decrypted_folder = os.path.join(config.GAME_FILES_ROOT, "encrypted", folder,
                                        password.strip().lower()) # warning, password directory must always be lowercase !!
        # print(">>>>>> Trying get_encrypted_files on", decrypted_folder)
        if not os.path.isdir(decrypted_folder):
            raise UsageError(_("Wrong password for this encrypted folder."))

        # there , we shouldn't have environment errors, theoretically
        decrypted_files = sorted(
            [game_file_url("encrypted/" + folder + "/" + password + "/" + item) for item in
             os.listdir(decrypted_folder)
             if os.path.isfile(os.path.join(decrypted_folder, item))])

        if absolute_urls:
            domain = config.SITE_DOMAIN
            decrypted_files = [domain + decrypted_file for decrypted_file in decrypted_files]

        self.log_game_event(ugettext_noop("Encrypted folder '%(folder)s/%(password)s' accessed by user '%(username)s'."),
                             PersistentDict(folder=folder, password=password, username=username),
                             url=None)

        return decrypted_files


    @readonly_method
    def get_personal_files(self, username=CURRENT_USER, absolute_urls=False):
        """
        Might raise environment errors.
        
        Game master has a reserved folder with game administration files
        """
        username = self._resolve_username(username)
        assert self.is_master(username) or self.is_character(username), username

        """ # ACTUALLY NO ! Game master has its own files !!
            # DEPRECATED !!!!!!!!!!!!
            # we list all the files of users
            root_folder = os.path.join(config.GAME_FILES_ROOT, personal_files)
            #print "ROOT FOLDER: ", root_folder
            personal_folders = sorted([dir for dir in os.listdir(root_folder)
                                          if os.path.isdir(os.path.join(root_folder, dir))])
            #print "personal_folders: ", personal_folders
            personal_files = [("/files//personal_files/"+folder+"/"+filename) for folder in personal_folders
                                                            for filename in sorted(os.listdir(os.path.join(root_folder, folder)))  # None is a separator here
                                                            if filename and os.path.isfile(os.path.join(root_folder, folder, filename))]
            """

        common_folder_path = os.path.join(config.GAME_FILES_ROOT, "personal_files", self.COMMON_FILES_DIRS)
        common_files = [game_file_url("personal_files/" + self.COMMON_FILES_DIRS + "/" + filename) for filename in
                        os.listdir(common_folder_path)
                        if os.path.isfile(os.path.join(common_folder_path, filename))
                           and not filename.startswith(".") and not filename.startswith("~")] # hidden files removed

        personal_folder_path = os.path.join(config.GAME_FILES_ROOT, "personal_files", username)
        personal_files = [game_file_url("personal_files/" + username + "/" + filename) for filename in
                          os.listdir(personal_folder_path)
                          if os.path.isfile(os.path.join(personal_folder_path, filename))
                             and not filename.startswith(".") and not filename.startswith("~")] # hidden files removed

        all_files = sorted(common_files + personal_files)

        if absolute_urls:
            domain = config.SITE_DOMAIN # "http://%s" % Site.objects.get_current().domain
            all_files = [domain + user_file for user_file in all_files]

        return all_files







@register_module
class MoneyItemsOwnership(BaseDataManager):

    # FIXME - fix forms containing gems, now (value, origin) tuples

    def _compute_items_unit_cost(self, total_cost, num_gems):
        if not total_cost:
            return None
        return int(math.ceil(float(total_cost / num_gems)))
    def _compute_items_total_price(self, unit_cost, num_gems):
        if not unit_cost:
            return None
        return unit_cost * num_gems # simpler

    def _load_initial_data(self, **kwargs):
        super(MoneyItemsOwnership, self)._load_initial_data(**kwargs)

        game_data = self.data

        game_data["global_parameters"].setdefault("bank_name", "bank")
        game_data["global_parameters"].setdefault("bank_account", 0) # can be negative
        game_data["global_parameters"].setdefault("spent_gems", []) # gems used in abilities

        total_digital_money = game_data["global_parameters"]["bank_account"]
        total_gems = game_data["global_parameters"]["spent_gems"][:] # COPY

        for (name, character) in game_data["character_properties"].items():
            character["account"] = character.get("account", 0)
            character["gems"] = character.get("gems", [])
            character["gems"] = [tuple(i) for i in character["gems"]]

            total_gems += [i[0] for i in character["gems"]]
            total_digital_money += character["account"]

        for (name, properties) in game_data["game_items"].items():
            properties['unit_cost'] = self._compute_items_unit_cost(total_cost=properties['total_price'], num_gems=properties['num_items']) # works with NONE too
            properties['owner'] = properties.get('owner', None)
            properties["auction"] = properties.get('auction', None)

            if properties["is_gem"] and not properties['owner']: # we dont recount gems appearing in character["gems"]
                total_gems += [properties['unit_cost']] * properties["num_items"]

            properties['image'] = utilities.find_game_file(properties['image'], "images")

        # We initialize some runtime checking parameters #
        game_data["global_parameters"]["total_digital_money"] = total_digital_money # integer
        game_data["global_parameters"]["total_gems"] = PersistentList(sorted(total_gems)) # sorted list of integer values



    def _check_database_coherency(self, **kwargs):
        super(MoneyItemsOwnership, self)._check_database_coherency(**kwargs)

        game_data = self.data

        total_digital_money = game_data["global_parameters"]["bank_account"]
        total_gems = game_data["global_parameters"]["spent_gems"][:] # COPY!
        # print ("^^^^^^^^^^^^", "spent_gems", total_gems.count(500))


        for (name, character) in game_data["character_properties"].items():
            utilities.check_is_positive_int(character["account"], non_zero=False)
            total_digital_money += character["account"]

            for gem in character["gems"]:
                assert isinstance(gem, tuple) # must be hashable!!
                (gem_value, gem_origin) = gem
                utilities.check_is_positive_int(gem_value)
                if gem_origin is not None:
                    assert gem_origin in game_data["game_items"]
                    assert game_data["game_items"][gem_origin]["is_gem"]
                total_gems.append(gem_value) # only value in kashes, not gem origin
            # print ("---------", name, total_gems.count(500))

        assert game_data["game_items"]
        for (name, properties) in game_data["game_items"].items():

            utilities.check_is_slug(name)
            assert isinstance(properties['is_gem'], bool)
            assert utilities.check_is_positive_int(properties['num_items'], non_zero=True)
            if properties['total_price']:
                assert utilities.check_is_positive_int(properties['total_price'], non_zero=True)
                assert utilities.check_is_positive_int(properties['unit_cost'], non_zero=True)
            else:
                assert properties['total_price'] is None
                assert properties['unit_cost'] is None

            # OK for NONE values too ; doesn't work the other way round, due to rounding of division
            assert properties['unit_cost'] == self._compute_items_unit_cost(total_cost=properties['total_price'], num_gems=properties['num_items'])

            assert properties['owner'] is None or properties['owner'] in game_data["character_properties"].keys()

            assert isinstance(properties['title'], basestring) and properties['title']
            assert isinstance(properties['comments'], basestring) and properties['comments']
            utilities.check_is_game_file(properties['image'])

            # item might be out of auction
            assert properties['auction'] is None or isinstance(properties['auction'], basestring) and properties['auction']

            if properties["is_gem"] and not properties["owner"]:
                total_gems += [properties['unit_cost']] * properties["num_items"]
                # (">>>>>>>>>>", name, total_gems.count(500))

        old_total_gems = game_data["global_parameters"]["total_gems"]
        assert Counter(old_total_gems) == Counter(total_gems), (old_total_gems, total_gems)
        assert old_total_gems == sorted(total_gems), "%s != %s" % (old_total_gems, total_gems)

        old_total_digital_money = game_data["global_parameters"]["total_digital_money"]
        assert old_total_digital_money == total_digital_money, "%s != %s" % (old_total_digital_money, total_digital_money)


    @readonly_method
    def get_all_items(self):
        return self.data["game_items"]

    @readonly_method
    def get_gem_items(self):
        return {key: value for (key, value) in self.data["game_items"].items() if value["is_gem"]}

    @readonly_method
    def get_non_gem_items(self):
        return {key: value for (key, value) in self.data["game_items"].items() if not value["is_gem"]}

    @readonly_method
    def get_auction_items(self):
        return {key: value for (key, value) in self.data["game_items"].items() if value["auction"]}

    @readonly_method
    def get_item_properties(self, item_name):
        try:
            return self.data["game_items"][item_name]
        except KeyError:
            raise UsageError(_("Unknown item %s") % item_name)

    """ DEPRECATED
    @readonly_method
    def get_team_gems_count(self, domain):
        total_gems = 0
        for props in self.get_character_sets().values():
            if props["domain"] == domain:
                total_gems += len(props["gems"])
        return total_gems
    """

    @transaction_watcher
    def transfer_money_between_characters(self, from_name, to_name, amount):
        amount = int(amount) # might raise error
        if amount <= 0:
            raise UsageError(_("Money amount must be positive"))

        if from_name == to_name:
            raise UsageError(_("Sender and recipient must be different"))

        bank_name = self.get_global_parameter("bank_name")

        if from_name == bank_name: # special case
            if self.get_global_parameter("bank_account") < amount:
                raise UsageError(_("Bank doesn't have enough money available"))
            self.data["global_parameters"]["bank_account"] -= amount
        else:
            from_char = self.get_character_properties(from_name)
            if from_char["account"] < amount:
                raise UsageError(_("Sender doesn't have enough money"))
            from_char["account"] -= amount

        if to_name == bank_name: # special case
            self.data["global_parameters"]["bank_account"] += amount
        else:
            to_char = self.get_character_properties(to_name)
            to_char["account"] += amount

        self.log_game_event(ugettext_noop("Bank operation: %(amount)s kashes transferred from %(from_name)s to %(to_name)s."),
                             PersistentDict(amount=amount, from_name=from_name, to_name=to_name),
                             url=None)


    def _get_item_separate_gems(self, item_name):
        item = self.get_item_properties(item_name)
        assert item["is_gem"]
        return [(item["unit_cost"] or 0, item_name)] * item["num_items"] # tuples!


    def _free_item_from_character(self, item_name, item):
        assert self.get_item_properties(item_name) == item
        assert item["owner"]

        char_name = item["owner"]
        character = self.get_character_properties(char_name)
        if item["is_gem"]:
            # check that all single gems of the pack are still owned
            gems = self._get_item_separate_gems(item_name)
            remaining_gems = utilities.substract_lists(character["gems"], gems) # gems are pairs (value, origin) here!
            if remaining_gems is None:
                raise UsageError(_("Impossible to free item, some gems from this package have already been used"))
            character["gems"] = remaining_gems
        item["owner"] = None

    def _assign_free_item_to_character(self, item_name, item, char_name):
        assert self.get_item_properties(item_name) == item
        assert item["owner"] is None
        character = self.get_character_properties(char_name)
        if item["is_gem"]:
            gems = self._get_item_separate_gems(item_name)
            character["gems"] += gems # we add each gem separately, along with its reference
        item["owner"] = char_name



    @transaction_watcher
    def transfer_object_to_character(self, item_name, char_name, previous_owner=None):
        """
        Item might be free or not, and char_name may be a character 
        or None (i.e no more owner for the item).
        
        If previous_owner is set, we perform a check on it, to ensure it's
        well the current owner who's transferring the object.
        
        No payment is automatically done.
        """
        assert not previous_owner or previous_owner in self.get_available_logins()

        if char_name is not None and char_name not in self.get_character_usernames():
            raise NormalUsageError(_("Unknown user name '%s'") % char_name)

        ## FIXME - make this a character-method too !!!
        item = self.get_item_properties(item_name)
        from_name = item["owner"] if item["owner"] else ugettext_noop("no one") # must be done IMMEDIATELY

        if previous_owner is not None and previous_owner != item["owner"]:
            raise NormalUsageError(_("This object doesn't belong to %s") % previous_owner)

        if item["owner"] == char_name:
            raise NormalUsageError(_("Impossible to have same origin and destination for item transfer"))

        if item["owner"]:
            self._free_item_from_character(item_name, item)

        if char_name:
            self._assign_free_item_to_character(item_name=item_name, item=item, char_name=char_name)

        self.log_game_event(ugettext_noop("Item %(item_name)s transferred from %(from_name)s to %(char_name)s."),
                             PersistentDict(item_name=item_name, from_name=from_name, char_name=char_name),
                             url=None)


    ''' DEPRECATED
    @transaction_watcher
    def undo_object_transfer(self, item_name, char_name):
        obj = self.get_item_properties(item_name)

        if not obj["owner"]:
            raise UsageError(_("%(item_name)s hasn't been sold yet !") % SDICT(item_name=item_name))
        elif obj["owner"] != char_name:
            raise UsageError(_("%(char_name)s is not the owner of %(item_name)s !") % SDICT(char_name=char_name,
                                                                                            item_name=item_name))

        character = self.data["character_properties"][char_name]

        if obj["is_gem"]:
            gem_price = int(math.ceil(float(obj["total_price"]) / obj["num_items"])) # ceil value
            if character["gems"].count(gem_price) != obj["num_items"]: # pack of gems
                raise UsageError(_("Impossible to undo sale - user has already consumed gems"))

            for i in range(obj["num_items"]):
                del character["gems"][character["gems"].index(gem_price)] # we remove each gem separately

        del character["items"][character["items"].index(item_name)]

        self.data["game_items"][item_name]["owner"] = None # we reset the owner tag of the object

        '''


    @readonly_method
    def get_available_items_for_user(self, username=CURRENT_USER, auction_only=False):
        """
        Both items and artefacts.
        """
        username = self._resolve_username(username)

        if auction_only:
            my_getter = self.get_auction_items
        else:
            my_getter = self.get_all_items

        if self.is_master(username):
            available_items = my_getter()
        else:
            assert self.is_character(username)
            all_sharing_users = [username] # FIXME - which users should we include?
            # user_domain = self.get_character_properties(username)["domain"]
            # all_domain_users = [name for (name, value) in self.get_character_sets().items() if
            #                    value["domain"] == user_domain]
            available_items = PersistentDict([(name, value) for (name, value)
                                              in my_getter().items()
                                              if value['owner'] in all_sharing_users])
        return available_items

    @readonly_method
    def get_user_artefacts(self, username=CURRENT_USER):
        username = self._resolve_username(username)
        return PersistentDict([(name, value) for (name, value)
                                  in self.get_available_items_for_user(username=username).items()
                                  if not value['is_gem']])


    @transaction_watcher
    def transfer_gems_between_characters(self, from_name, to_name, gems_choices):
        sender_char = self.data["character_properties"][from_name] # may raise key error
        recipient_char = self.data["character_properties"][to_name] # may raise key error
        gems_choices = PersistentList(gems_choices)

        if from_name == to_name:
            raise UsageError(_("Sender and recipient must be different"))

        if not gems_choices:
            raise UsageError(_("You must transfer at least one gem"))

        remaining_gems = utilities.substract_lists(sender_char["gems"], gems_choices)

        if remaining_gems is None:
            raise UsageError(_("You don't possess the gems required"))

        sender_char["gems"] = remaining_gems
        recipient_char["gems"] += gems_choices

        self.log_game_event(ugettext_noop("Gems transferred from %(from_name)s to %(to_name)s : %(gems_choices)s."),
                             PersistentDict(from_name=from_name, to_name=to_name, gems_choices=gems_choices),
                             url=None)






@register_module
class Items3dViewing(BaseDataManager):


    def _load_initial_data(self, **kwargs):
        super(Items3dViewing, self)._load_initial_data(**kwargs)

    def _check_database_coherency(self, **kwargs):
        super(Items3dViewing, self)._check_database_coherency(**kwargs)

        game_data = self.data

        item_viewer_reference = \
            {'levels': (int, long),
             'per_level': (int, long),

             'index_steps': (int, long),
             'index_offset': (int, long),

             'start_level': (int, long),

             'file_template': basestring,

            'image_width': (int, long),
            'image_height': (int, long),
            'mode': basestring,

            'x_coefficient': (int, long),
            'y_coefficient': (int, long)   ,
            'autoreverse': bool,
            'rotomatic': (int, long) ,

             'music': (types.NoneType, basestring),
            }

        for (name, properties) in game_data["item_3d_settings"].items():
            assert name in game_data["game_items"].keys(), name
            utilities.check_dictionary_with_template(properties, item_viewer_reference)


    @readonly_method
    def get_items_3d_settings(self):
        return self.data["item_3d_settings"]





@register_module
class GameViews(BaseDataManager):

    GAME_VIEWS_REGISTRY = {} # all game views, including abilities, register themselves here thanks to their metaclass
    ACTIVABLE_VIEWS_REGISTRY = {} # only views that need to be activated by game master


    def _init_from_db(self, **kwargs):
        super(GameViews, self)._init_from_db(**kwargs)
        self.sync_game_view_data() # important if some views have disappeared since then


    @classmethod
    def get_game_views(self):
        return self.GAME_VIEWS_REGISTRY.copy()


    @classmethod
    def get_activable_views(self):
        return self.ACTIVABLE_VIEWS_REGISTRY.copy()


    @classmethod
    def register_game_view(cls, view_class):
        assert isinstance(view_class, type)

        assert view_class.NAME and view_class.NAME not in cls.GAME_VIEWS_REGISTRY, view_class.NAME
        cls.GAME_VIEWS_REGISTRY[view_class.NAME] = view_class

        if view_class.REQUIRES_GLOBAL_PERMISSION:
            assert view_class.NAME not in cls.ACTIVABLE_VIEWS_REGISTRY
            cls.ACTIVABLE_VIEWS_REGISTRY[view_class.NAME] = view_class

        if view_class.REQUIRES_CHARACTER_PERMISSION:
            cls.register_permissions([view_class.get_access_permission_name()])

        if view_class.EXTRA_PERMISSIONS:
            # auto registration of permission requirements brought by that view
            cls.register_permissions(view_class.EXTRA_PERMISSIONS)


    @transaction_watcher(always_writable=True)
    def sync_game_view_data(self):
        """
        If we add/remove views to pychronia_game without resetting the DB, a normal desynchronization occurs.
        So we should ensure that the data stays in sync.
        """
        new_view_data = set(self.data["views"]["activated_views"]) & set(self.ACTIVABLE_VIEWS_REGISTRY.keys())
        self.data["views"]["activated_views"] = PersistentList(sorted(new_view_data))
        self.notify_event("SYNC_GAME_VIEW_DATA_CALLED")


    def _load_initial_data(self, **kwargs):
        super(GameViews, self)._load_initial_data(**kwargs)
        game_data = self.data
        game_data.setdefault("views", PersistentDict())
        game_data["views"].setdefault("activated_views", PersistentList())
        # no need to sync - it will done later in _init_from_db()


    def _check_database_coherency(self, **kwargs):
        super(GameViews, self)._check_database_coherency(**kwargs)

        game_data = self.data
        utilities.check_no_duplicates(game_data["views"]["activated_views"])
        for view_name in game_data["views"]["activated_views"]:
            assert view_name in self.ACTIVABLE_VIEWS_REGISTRY.keys()


    @readonly_method
    def is_game_view_activated(self, view_name):
        # DO NOT CHECK that view_name is in self.ACTIVABLE_VIEWS_REGISTRY, could happen in rare cases
        return (view_name in self.data["views"]["activated_views"])


    @readonly_method
    def get_activated_game_views(self):
        return self.data["views"]["activated_views"]


    @transaction_watcher
    def set_activated_game_views(self, view_names):
        assert not isinstance(view_names, basestring)
        activable_views = self.ACTIVABLE_VIEWS_REGISTRY.keys()
        weird = [view_name for view_name in view_names if view_name not in activable_views]
        if weird:
            raise AbnormalUsageError(_("Unknown view names detected in the set of views to be activated: %r") % weird)
        self.data["views"]["activated_views"] = PersistentList(sorted(view_names))


    def _resolve_view_klass(self, name_or_klass):
        if isinstance(name_or_klass, basestring):
            klass = self.GAME_VIEWS_REGISTRY.get(name_or_klass)
        elif hasattr(name_or_klass, "klass"):
            klass = name_or_klass.klass # proxy
        else:
            assert isinstance(name_or_klass, type)
            klass = name_or_klass
        return klass


    # no transaction checker here
    def instantiate_game_view(self, name_or_klass):
        klass = self._resolve_view_klass(name_or_klass)
        return klass(self) # first arg (self) is the datamanager


    @readonly_method
    def get_game_view_access_token(self, name_or_klass):
        klass = self._resolve_view_klass(name_or_klass)
        token = klass.get_access_token(self) # class method!!
        return token


    @readonly_method
    def build_admin_widget_identifier(self, klass, action_name):
        assert isinstance(klass, type)
        assert isinstance(action_name, basestring)
        return "%s.%s" % (klass.NAME, action_name)

    @readonly_method
    def get_admin_widget_identifiers(self):
        """
        Gets a list of qualified names, each one targetting a single
        admin form widget.
        """
        ids = [self.build_admin_widget_identifier(klass, action_name)
               for klass in self.GAME_VIEWS_REGISTRY.values()
               for action_name in klass.ADMIN_ACTIONS]
        return ids

    @readonly_method
    def resolve_admin_widget_identifier(self, identifier):
        """
        Returns the (game_view_instance, action_name_string) tuple corresponding to that
        admin widget token (and its instantiation params), or None. 
        """
        if identifier.count(".") == 1:
            klass_name, action_name = identifier.split(".")
            if klass_name in self.GAME_VIEWS_REGISTRY:
                klass = self.GAME_VIEWS_REGISTRY[klass_name]
                if action_name in klass.ADMIN_ACTIONS:
                    return (self.instantiate_game_view(klass), action_name)
        return None


@register_module
class SpecialAbilities(BaseDataManager):
    # TODO TEST THAT MODULE TOO !! FIXME TODO TODO
    ABILITIES_REGISTRY = {} # abilities automatically register themselves with this dict, thanks to their metaclass


    def _init_from_db(self, **kwargs):
        super(SpecialAbilities, self)._init_from_db(**kwargs)
        # self.abilities = SpecialAbilities.AbilityLazyLoader(self)
        # self.sync_ability_data()


    @classmethod
    def register_ability(cls, view_class):
        assert isinstance(view_class, type)
        data = view_class, view_class.NAME
        assert view_class.NAME and view_class.NAME not in cls.ABILITIES_REGISTRY, data
        cls.ABILITIES_REGISTRY[view_class.NAME] = view_class


    @classmethod
    def get_abilities(self):
        return self.ABILITIES_REGISTRY.copy()


    # no transaction checker here
    def instantiate_ability(self, name_or_klass):
        assert name_or_klass in self.ABILITIES_REGISTRY.keys() + self.ABILITIES_REGISTRY.values()
        return self.instantiate_game_view(name_or_klass)

    '''
    @transaction_watcher(always_writable=True/False)
    def sync_ability_data(self):
        """
        NO - abilities cant be hot plugged!!
        If we add/remove abilities to pychronia_game without resetting the DB, a normal desynchronization occurs.
        So we must constantly ensure that this data stays in sync.
        """
        for (key, klass) in self.ABILITIES_REGISTRY.items():
            if key not in self.data["abilities"]:
                self.logger.warning("Lately setting up main settings for ability %s" % key)
                ability_data = self.data["abilities"][key] = PersistentDict()
                klass.setup_main_ability_data(ability_data) 
            assert self.data["abilities"][key]["data"]
        # if exceeding data exists (some abilities have disappeared), so be it
     '''

    def _load_initial_data(self, **kwargs):
        super(SpecialAbilities, self)._load_initial_data(**kwargs)

        game_data = self.data
        game_data.setdefault("abilities", {})
        for (key, klass) in self.ABILITIES_REGISTRY.items():
            #print("loading", klass)
            self.logger.debug("Setting up main settings for ability %s" % key) # TODO
            ability_data = game_data["abilities"].setdefault(key, {})
            klass.setup_main_ability_data(ability_data) # each ability fills its default values
            assert "settings" in game_data["abilities"][key] and "data" in game_data["abilities"][key]


    def _check_database_coherency(self, strict=False, **kwargs):
        super(SpecialAbilities, self)._check_database_coherency(**kwargs)
        for name in self.ABILITIES_REGISTRY.keys():
            ability = self.instantiate_ability(name)
            ability.check_data_sanity(strict=strict)


    @readonly_method
    def get_ability_data(self, ability_name):
        return self.data["abilities"][ability_name]


    ''' # NOPE - abilities are like views, external to the datamanager
    def _notify_user_change(self, username, **kwargs):
        super(SpecialAbilities, self)._notify_user_change(username, **kwargs)

        self.abilities = SpecialAbilities.AbilityLazyLoader(self) # important - because of weak refs to old data!!

    
    @transaction_watcher
    
    class AbilityLazyLoader:
        """
        Helper to easily load any ability through the datamanager.
        """
        def __init__(self, datamanager):
            self.__datamanager = weakref.ref(datamanager)

        @property
        def _datamanager(self):
            return self.__datamanager() # could be None

        def __getattr__(self, ability_name):
            try:
                ability_class = self._datamanager.ABILITIES_REGISTRY[ability_name]
                return ability_class(self._datamanager)  # do NOT cache it !!!
            except Exception, e:
                #print "error", e, traceback.print_exc() # TODO REMOVE
                raise
     '''








@register_module
class StaticPages(BaseDataManager):
    """
    Static pages for all purposes, depending on taxonomy: encyclopedia articles, 
    help pages, fictional adverts...
    """

    def _load_initial_data(self, **kwargs):
        super(StaticPages, self)._load_initial_data(**kwargs)
        self.static_pages._load_initial_data(**kwargs)

    def _check_database_coherency(self, **kwargs):
        super(StaticPages, self)._check_database_coherency(**kwargs)
        self.static_pages._check_database_coherency(**kwargs)


    # bunch of standard categories #
    CONTENT_CATEGORY = "content"
    HELP_CATEGORY = "content" # SAME CATEGORY, because same security settings actually...


    @readonly_method
    def get_categorized_static_page(self, category, name):
        assert " " not in category
        assert " " not in name
        if name not in self.static_pages:
            return None
        value = self.static_pages[name]
        if category in value["categories"]:
            return value
        else:
            return None # no leaks
        assert False

    @readonly_method
    def get_static_page_names_for_category(self, category):
        return [key for (key, value) in self.static_pages.get_all_data().items() if category in value["categories"]] # UNSORTED

    @readonly_method
    def get_static_pages_for_category(self, category):
        return {key: value for (key, value) in self.static_pages.get_all_data().items() if category in value["categories"]}


    class StaticPagesManager(DataTableManager):

        TRANSLATABLE_ITEM_NAME = ugettext_lazy("static pages")

        def _load_initial_data(self, **kwargs):

            for identifier, details in self._table.items():
                details.setdefault("immutable", False) # we assume ANY static page is optional for the game, and can be edited/deleted

                details.setdefault("categories", []) # distinguishes possibles uses of static pages
                details["categories"] = [details["categories"]] if isinstance(details["categories"], basestring) else details["categories"]

                details.setdefault("keywords", []) # useful for encyclopedia articles mainly
                details["keywords"] = [details["keywords"]] if isinstance(details["keywords"], basestring) else details["keywords"]

                details.setdefault("gamemaster_hints", "") # for gamemaster only
                details["gamemaster_hints"] = details["gamemaster_hints"].strip()


        def _preprocess_new_item(self, key, value):
            assert "immutable" not in value
            value["immutable"] = False
            return (key, PersistentDict(value))
            # other params are supposed to exist in "value"

        def _check_item_validity(self, key, value, strict=False):
            utilities.check_is_slug(key)
            assert key.lower() == key # handy

            utilities.check_has_keys(value, ["immutable", "categories", "content", "gamemaster_hints", "keywords"], strict=strict)

            utilities.check_is_bool(value["immutable"],)

            utilities.check_is_restructuredtext(value["content"])

            utilities.check_is_list(value["categories"])
            for category in (value["categories"]):
                utilities.check_is_slug(category)

            utilities.check_is_list(value["keywords"])
            for keyword in (value["keywords"]):
                utilities.check_is_slug(keyword)

            if value["gamemaster_hints"]: # optional
                utilities.check_is_restructuredtext(value["gamemaster_hints"])


        def _sorting_key(self, item_pair):
            return item_pair[0] # we sort by key, simply...

        def _get_table_container(self, root):
            return root["static_pages"]

        def _item_can_be_edited(self, key, value):
            return not value["immutable"]

    static_pages = LazyInstantiationDescriptor(StaticPagesManager)


    _static_page_novelty_category = "static_pages"

    @transaction_watcher
    def mark_static_page_as_accessed(self, item_key): # ONLY for current user
        return self.access_novelty(item_key=item_key, category=self._static_page_novelty_category)

    @readonly_method
    def has_user_accessed_static_page(self, item_key): # ONLY for current user
        return self.has_accessed_novelty(item_key=item_key, category=self._static_page_novelty_category)



@register_module
class Encyclopedia(BaseDataManager):

    ENCYCLOPEDIA_CATEGORY = "encyclopedia"

    def _load_initial_data(self, **kwargs):
        super(Encyclopedia, self)._load_initial_data(**kwargs)

        game_data = self.data

        game_data["global_parameters"].setdefault("encyclopedia_index_visible", False)

        for character in self.get_character_sets().values():
            character.setdefault("known_article_ids", PersistentList())


    def _check_database_coherency(self, **kwargs):
        super(Encyclopedia, self)._check_database_coherency(**kwargs)

        game_data = self.data

        utilities.check_is_bool(game_data["global_parameters"]["encyclopedia_index_visible"])

        all_keywords = []

        for (key, value) in self.get_static_pages_for_category(self.ENCYCLOPEDIA_CATEGORY).items():
            assert key.lower() == key # of course, since these are static pages...
            utilities.check_is_slug(key)

            all_keywords += value["keywords"]
            # the same keyword can be included in several article ids - no check_no_duplicates() here!

        for keyword in all_keywords:
            assert len(keyword) >= 3 # let's avoid too easy matches
            re.compile(keyword) # keyword must be a proper regular expression

        for character in self.get_character_sets().values():
            utilities.check_no_duplicates(character["known_article_ids"])
            assert set(character["known_article_ids"]) <= set(self.get_encyclopedia_article_ids())


    @readonly_method
    def is_encyclopedia_index_visible(self):
        return self.get_global_parameter("encyclopedia_index_visible")


    @transaction_watcher
    def set_encyclopedia_index_visibility(self, value):
        self.data["global_parameters"]["encyclopedia_index_visible"] = value


    @readonly_method
    def get_encyclopedia_entry(self, article_id):
        """
        Returns the rst entry, or None.
        Fetching is case-insensitive.
        """
        key = article_id.lower().strip()
        article = self.get_categorized_static_page(category=self.ENCYCLOPEDIA_CATEGORY, name=key)
        return article if article else None


    @readonly_method
    def get_encyclopedia_matches(self, search_string):
        """
        Returns the list of encyclopedia article whose keywords match *search_string*, 
        sorted by most relevant first.
        
        Matching is very tolerant, as keywords needn't be separate words in the search string.
        """
        keywords_mapping = self.get_encyclopedia_keywords_mapping()

        matches = Counter()

        for keyword, article_ids in keywords_mapping.items():
            if re.search(keyword, search_string, re.IGNORECASE | re.UNICODE):
                matches.update(article_ids)

        sorted_couples = matches.most_common()
        all_article_ids = [couple[0] for couple in sorted_couples] # we discard the exact count of each
        return all_article_ids


    @readonly_method
    def get_encyclopedia_article_ids(self):
        return self.get_static_page_names_for_category(self.ENCYCLOPEDIA_CATEGORY)

    @readonly_method
    def get_encyclopedia_keywords_mapping(self, excluded_link=None):
        """
        Returns a dict mapping keywords (which can be regular expressions) to lists 
        of targeted article ids.
        """
        mapping = {}
        for article_id, article in self.get_static_pages_for_category(self.ENCYCLOPEDIA_CATEGORY).items():
            if article_id == excluded_link:
                continue # we skip links to the current article of course
            for keyword in article["keywords"]:
                assert keyword
                mapping.setdefault(keyword, [])
                mapping[keyword].append(article_id)
        ###print (">>>>>>>>>>>", mapping)
        return mapping


    @readonly_method
    def get_character_known_article_ids(self, username=CURRENT_USER):
        username = self._resolve_username(username)
        return self.get_character_properties(username)["known_article_ids"]


    @transaction_watcher
    def update_character_known_article_ids(self, username=CURRENT_USER, article_ids=None):
        username = self._resolve_username(username)
        assert article_ids is not None
        known_article_ids = self.get_character_properties(username)["known_article_ids"]
        assert isinstance(known_article_ids, PersistentList), known_article_ids
        for article_id in article_ids:
            if article_id not in known_article_ids:
                known_article_ids.append(article_id)


    @transaction_watcher
    def reset_character_known_article_ids(self, username=CURRENT_USER):
        """
        Mainly for testing...
        """
        username = self._resolve_username(username)
        known_article_ids = self.get_character_properties(username)["known_article_ids"]
        del known_article_ids[:]




@register_module
class NightmareCaptchas(BaseDataManager):


    def _load_initial_data(self, **kwargs):
        super(NightmareCaptchas, self)._load_initial_data(**kwargs)
        game_data = self.data
        for (key, value) in game_data["nightmare_captchas"].items():
            value.setdefault("text", None)
            value.setdefault("image", None)
            value.setdefault("explanation", None)
            if value["image"]:
                value["image"] = utilities.find_game_file(value["image"], "images", "captchas")

    def _check_database_coherency(self, strict=False, **kwargs):
        super(NightmareCaptchas, self)._check_database_coherency(**kwargs)

        game_data = self.data

        assert game_data["nightmare_captchas"] # else random choice would nastily fail

        for (key, value) in game_data["nightmare_captchas"].items():

            utilities.check_is_slug(key)
            assert key.lower() == key # let's make its simple

            if strict:
                assert len(value.keys()) == 4

            assert not value.get("id") # to ensure no pollution exists by utility methods
            assert value["text"] or value["image"]
            if value["text"]:
                utilities.check_is_restructuredtext(value["text"])
            if value["image"]:
                utilities.check_is_game_file(value["image"])
            if value["explanation"]:
                utilities.check_is_restructuredtext(value["explanation"])

            if value["answer"] is not None: # None means "no answers" (sadistic)
                utilities.check_is_slug(value["answer"])
                assert "\n" not in value["answer"]


    def _get_captcha_data(self, captcha_id):
        """
        Returns a captcha as a dict, id, text and image keys (one of the 2 latter could be None).
        """
        # beware - using copy() on a dict marks it as modified in ZODB...
        value = self.data["nightmare_captchas"][captcha_id]
        return dict(id=captcha_id,
                    text=value["text"],
                    image=value["image"])



    @readonly_method
    def get_available_captchas(self):
        return self.data["nightmare_captchas"].keys()


    @readonly_method
    def get_selected_captcha(self, captcha_id):
        return self._get_captcha_data(captcha_id)


    @readonly_method
    def get_random_captcha(self):
        captchas = self.data["nightmare_captchas"]
        captcha_id = random.choice(captchas.keys())
        return self._get_captcha_data(captcha_id)


    @readonly_method
    def check_captcha_answer_attempt(self, captcha_id, attempt):
        """
        On success, returns the enigma explanation (which could be None).
        """
        assert isinstance(attempt, basestring)
        captchas = self.data["nightmare_captchas"]
        if captcha_id not in captchas:
            raise AbnormalUsageError(_("Unknown captcha id %s") % captcha_id)
        value = self.data["nightmare_captchas"][captcha_id]

        if not value["answer"]:
            raise NormalUsageError(_("Nope, it looked like this captcha had no known answer..."))

        normalized_attempt = attempt.strip().lower().replace(" ", "")
        normalized_answer = value["answer"].lower() # necessarily slug, but not always lowercase

        if normalized_attempt != normalized_answer:
            raise NormalUsageError(_("Incorrect captcha answer '%s'") % attempt)

        return value["explanation"]








