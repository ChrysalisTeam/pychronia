# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

import string, random

from pychronia_game.common import *
from pychronia_game.common import _, ugettext_lazy, ugettext_noop, _undefined # mainly to shut up the static checker...
from pychronia_game import utilities

from .datamanager_tools import *
from .datamanager_user import GameUser
from .datamanager_core import BaseDataManager
from .data_table_manager import *

PLACEHOLDER = object()


MODULES_REGISTRY = [] # IMPORTANT



def register_module(Klass):
    MODULES_REGISTRY.append(Klass)
    return Klass



VISIBILITY_REASONS = Enum([ugettext_noop("sender"),
                           ugettext_noop("recipient"),
                           ugettext_noop("interceptor")]) # tokens identifying why one can see an email


@register_module
class GameMasterManual(BaseDataManager):

    GAMEMASTER_MANUAL_PARTS = ("common_content", "pdf_prefix", "html_prefix")

    def ____FIXME_USELESS__load_initial_data(self, **kwargs):
        super(GameMasterManual, self)._load_initial_data(**kwargs)

        game_data = self.data

        game_data.setdefault("gamemaster_manual", {})

        for key in self.GAMEMASTER_MANUAL_PARTS:
            game_data["gamemaster_manual"].setdefault(key, "This is a Placeholder")


    def _check_database_coherence(self, **kwargs):
        super(GameMasterManual, self)._check_database_coherence(**kwargs)
        return # TEMP HACK FIXME

        game_data = self.data

        for key in self.GAMEMASTER_MANUAL_PARTS:
            utilities.check_is_string(game_data["gamemaster_manual"][key])

        utilities.check_is_restructuredtext(game_data["gamemaster_manual"]["common_content"])


    @readonly_method
    def get_gamemaster_manual_for_html(self):
        return self.data["gamemaster_manual"]["html_prefix"] + "\n\n" + self.data["gamemaster_manual"]["common_content"]


@register_module
class GameGlobalParameters(BaseDataManager):

    def _load_initial_data(self, **kwargs):
        super(GameGlobalParameters, self)._load_initial_data(**kwargs)

        game_data = self.data

        game_data["global_parameters"]["world_map_image"] = os.path.normpath(game_data["global_parameters"]["world_map_image"])
        game_data["global_parameters"]["world_map_image_bw"] = os.path.normpath(game_data["global_parameters"]["world_map_image_bw"])

    def _check_database_coherence(self, **kwargs):
        super(GameGlobalParameters, self)._check_database_coherence(**kwargs)

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
        assert self.is_master() or config.DEBUG
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
    def _set_user(self, username, impersonation_target=None, impersonation_writability=False, is_superuser=False, is_observer=False):
        assert not hasattr(super(CurrentUserHandling, self), "_set_user") # we're well top-level here
        self.user = GameUser(datamanager=self,
                             username=username,
                             impersonation_target=impersonation_target,
                             impersonation_writability=impersonation_writability,
                             is_superuser=is_superuser,
                             is_observer=is_observer) # might raise UsageError
        del username
        self._notify_user_change(username=self.user.username) # might have been normalized, eg. None -> anonymous_login

        return self.user


    def _resolve_username(self, username):
        if username is None:
            raise RuntimeError("Wrong username==None detected")
        if username == CURRENT_USER:
            return self.user.username
        return username


    @readonly_method
    def determine_actual_game_writability(self):
        if not self.user.has_write_access:
            assert self.user.is_impersonation or self.user.is_observer # only cases ATM
            return dict(writable=False,
                        reason=_("Your impersonation is in read-only mode."))
        else:
            # game can be written #
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


    def _check_database_coherence(self, **kwargs):
        super(FlexibleTime, self)._check_database_coherence(**kwargs)
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
            evt.setdefault("visible_by", PersistentList())
        game_data["events_log"].sort(key=lambda evt: evt["time"])


    def _check_database_coherence(self, **kwargs):
        super(GameEvents, self)._check_database_coherence(**kwargs)

        event_reference = {
            "time": datetime,
            "message": basestring, # TRANSLATED message
            "substitutions": (types.NoneType, PersistentMapping),
            "url": (types.NoneType, basestring),
            "username": (types.NoneType, basestring),
            "visible_by": (types.NoneType, PersistentList),
        }
        previous_time = None
        for event in self.data["events_log"]:
            assert event["message"]
            if previous_time:
                assert previous_time <= event["time"] # event lists are sorted by chronological order
            previous_time = event["time"] # UTC time
            event.setdefault("visible_by", None) # FIXME TEMP FIX
            utilities.check_dictionary_with_template(event, event_reference)
            username = event["username"]

            character_names = self.get_character_usernames()

            message = event["message"]
            visible_by = event["visible_by"]
            assert visible_by is None or all([(c in character_names) for c in visible_by])

            # test is a little brutal, if we reset master login it might fail...
            assert username in self.get_character_usernames() or \
                    username == self.get_global_parameter("master_login") or \
                    username == self.get_global_parameter("anonymous_login")

    @transaction_watcher
    def log_game_event(self, message, substitutions=None, url=None, visible_by=_undefined, additional_details=None):
        """
        Input message must be an UNTRANSLATED string, since we handle translation directly in this class. 
        So use "ugettext_noop()" to mark it.
        
        The optional parameter "additional_details" will be concatenated but not translate.
        
        The sequence "visible_by" lists characters able to view this log entry, by default only MASTER can view it.
        """

        assert visible_by is not _undefined, "visible_by parameter must be explicitly defined in log_game_event() call"
        visible_by = visible_by if visible_by is not _undefined else None  # double security...

        assert message, "game event log message must not be empty"
        utilities.check_is_string(message) # no lazy objects
        assert url is None or (url and isinstance(url, basestring))

        message = _(message) # TODO - force language to "official game language", not "user interface language"

        if additional_details:
            message += "\n" + additional_details

        if substitutions:
            assert isinstance(substitutions, PersistentMapping), (message, substitutions)
            assert not re.search(r"[^%]%[^(%]", message)  # we forbid single % signs
            if config.DEBUG:
                message % substitutions # may raise formatting errors if corrupt...
        else:
            assert "%(" not in message, "Message %s needs substitution arguments" % message
            pass

        utcnow = datetime.utcnow() # NAIVE UTC datetime

        record = PersistentMapping({
            "time": utcnow,
            "message": message, # TRANSLATED message !
            "substitutions": PersistentMapping(substitutions),
            "url": url,
            "username": self.user.username,
            "visible_by": PersistentList(visible_by)
            # FIXME - add impersonation data here!!
        })
        self.data["events_log"].append(record)


    @readonly_method
    def get_game_events(self, username=CURRENT_USER):
        """
        If concerned user is a character, filters log entries according to their (potential) white-list.
        """
        username = self._resolve_username(username)
        all_entries = self.data["events_log"]
        is_master = self.is_master(username)
        return [entry for entry in all_entries if (is_master or (entry["visible_by"] is not None and username in entry["visible_by"]))]





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
        game_data.setdefault("novelty_tracker", PersistentMapping())


    def _check_database_coherence(self, **kwargs):
        super(NovaltyTracker, self)._check_database_coherence(**kwargs)
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
                character["avatar"] = utilities.find_game_file("images", character["avatar"])  # NOT an external URL
            character.setdefault("real_life_identity", None)
            character.setdefault("real_life_email", None)

            if character["gamemaster_hints"]:
                character["gamemaster_hints"] = character["gamemaster_hints"].strip()


    def _check_database_coherence(self, **kwargs):
        super(CharacterHandling, self)._check_database_coherence(**kwargs)

        game_data = self.data

        assert game_data["character_properties"]

        from pychronia_game.authentication import UNIVERSAL_URL_USERNAME, TEMP_URL_USERNAME  # let's not conflict with these
        reserved_names = [game_data["global_parameters"][reserved] for reserved in ["master_login", "anonymous_login"]] + [UNIVERSAL_URL_USERNAME, TEMP_URL_USERNAME]

        for (name, character) in game_data["character_properties"].items():

            utilities.check_is_slug(name)
            assert name not in reserved_names
            assert "@" not in name # let's not mess with email addresses...
            assert name == name.lower()  # important, for easy case-insensitive lookups

            utilities.check_is_bool(character["is_npc"])

            utilities.check_is_slug(character["character_color"])

            if character["avatar"]:
                utilities.check_is_game_file(character["avatar"])  # NOT an external URL

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
    def get_character_usernames(self, exclude_current=False, is_npc=None):
        """
        We sort "players first, NPC second, and then secodary sorting by username".
        """
        items = ((k, v) for (k, v) in self.data["character_properties"].items() if (is_npc is None) or v["is_npc"] == is_npc)
        items = sorted(items, key=lambda x: (x[1]["is_npc"], x[0]))
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
    def get_all_other_character_usernames(self, username=CURRENT_USER):
        # also works for game master : returns ALL players
        username = self._resolve_username(username)
        others = [name for name in self.get_character_usernames() if name != username]
        return others

    @readonly_method
    def build_visible_character_names(self, usernames):
        """
        Returns display names (combining logins and official names) for these characters
        """
        _chars_data = self.get_character_sets()
        visible_names = [username + u" (%s)" % (_chars_data[username]["official_name"] or _("Unidentified"))
                         for username in usernames]
        return visible_names

    @readonly_method
    def build_select_choices_from_character_usernames(self, usernames, add_empty=False):
        visible_names = self.build_visible_character_names(usernames)
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
    def update_official_character_data(self, username=CURRENT_USER, official_name=None, official_role=None, gamemaster_hints=None, is_npc=None, extra_goods=None):
        username = self._resolve_username(username)
        data = self.get_character_properties(username)

        updates_done = False

        character_keys = ["official_name", "official_role", "gamemaster_hints", "is_npc", "extra_goods"]
        mandatory_keys = character_keys[:2]  # name and role only ATM, can't be empty string

        new_data = locals()
        for key in character_keys:
            if new_data[key] or (key not in mandatory_keys and new_data[key] is not None):
                if new_data[key] != data[key]:
                    updates_done = True
                    data[key] = new_data[key]

        return updates_done




@register_module
class DomainHandling(BaseDataManager): # TODO REFINE


    def _load_initial_data(self, **kwargs):
        super(DomainHandling, self)._load_initial_data(**kwargs)

        game_data = self.data
        for (name, content) in game_data["domains"].items():
            if content["national_anthem"]:
                content["national_anthem"] = utilities.find_game_file("audio", content["national_anthem"])

    def _check_database_coherence(self, **kwargs):
        super(DomainHandling, self)._check_database_coherence(**kwargs)

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

    def _load_initial_data(self, skip_randomizations=False, **kwargs):
        super(PlayerAuthentication, self)._load_initial_data(skip_randomizations=skip_randomizations, **kwargs)

        for character in self.get_character_sets().values():
            character.setdefault("secret_question", None)
            character.setdefault("secret_answer", None)
            character["secret_answer"] = character["secret_answer"] if not character["secret_answer"] else character["secret_answer"].strip().lower()

        if not skip_randomizations:
            old_master_login = self.data["global_parameters"]["master_login"]
            self.randomize_passwords_for_players() # basic security
            assert self.data["global_parameters"]["master_login"] == old_master_login # later we might randomize master login too, for now it must NEVER change!

    def _check_database_coherence(self, **kwargs):
        super(PlayerAuthentication, self)._check_database_coherence(**kwargs)

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
        assert global_parameters["anonymous_login"] == global_parameters["anonymous_login"].lower()  # important

        utilities.check_is_slug(global_parameters["master_login"])
        assert global_parameters["master_login"] == global_parameters["master_login"].lower()  # important

        utilities.check_is_slug(global_parameters["master_password"])
        if global_parameters["master_real_email"]:
            utilities.check_is_email(global_parameters["master_real_email"])

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

        if self.user.is_observer:
            display_impersonation_writability_shortcut = False # OVERRIDE
            has_writability_control = False # OVERRIDE

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

        # BEWARE - game_username may be None, it's same as "anonymous" actually
        game_username = session_ticket.get("game_username", None) # instance-local user set via login page
        assert game_username != self.anonymous_login # would be absurd, we store "None" for this

        is_superuser = False
        if not game_username: # instance-local authentication COMPLETELY HIDES the fact that one is a django superuser
            if django_user and django_user.is_active and (django_user.is_staff or django_user.is_superuser):
                is_superuser = True

        is_observer = session_ticket.get("is_observer", False)

        # first, we compute the impersonation we REALLY want #
        if requested_impersonation_target is None: # means "use legacy one"
            requested_impersonation_target = session_ticket.get("impersonation_target", None)
        elif not is_superuser and (game_username is None and requested_impersonation_target == self.anonymous_login):
            # simply remain "anonymous"
            requested_impersonation_target = None
        elif (requested_impersonation_target in ("",  # special case "delete current impersonation target"
                                                 game_username)):  # means "just stay as real authenticated user"
            # game_username *might* be None, we don't care
            requested_impersonation_target = None
        else:
            pass # we let submitted requested_impersonation_target continue

        # now that impersonation is per-tab, we NEVER force-reset impersonation writability
        requested_impersonation_writability = (requested_impersonation_writability
                                               if requested_impersonation_writability is not None
                                               else session_ticket.get("impersonation_writability", None))

        # we reset session if session/request data is abnormal
        _available_logins = self.get_available_logins()
        if game_username is not None and game_username not in _available_logins:
            raise AbnormalUsageError(_("Invalid instance username: '%s'") % game_username)
        if requested_impersonation_target and requested_impersonation_target not in _available_logins:
            raise AbnormalUsageError(_("Invalid requested impersonation target: %s") % requested_impersonation_target)  # might be typos when manipulating URLs

        if requested_impersonation_target is not None:
            # we filter out forbidden impersonation choices #
            if is_superuser or (game_username and self.can_impersonate(game_username, requested_impersonation_target)):
                pass # OK, impersonation granted
            else:
                # here we don't erase the session data, but this stops impersonation completely
                self.user.add_error(_("Unauthorized user impersonation detected: %s") % requested_impersonation_target)
                requested_impersonation_target = requested_impersonation_writability = None # TODO FIXME TEST THAT CURRENT GAME USERNAME REMAINS

        if requested_impersonation_writability is not None:
            if not is_observer and (is_superuser or (game_username and self.is_master(game_username))):
                pass # OK, writability control authorized
            else:
                self.logger.critical("Attempt at controlling impersonation writability (%s) by non-privileged player %r", requested_impersonation_writability, game_username)
                requested_impersonation_writability = None # we just reset that flag for now, no exception raised

        return dict(is_superuser=is_superuser,
                    game_username=game_username,
                    impersonation_target=requested_impersonation_target,
                    impersonation_writability=requested_impersonation_writability,
                    is_observer=is_observer)


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
        assert len(new_session_data) == 5
        is_superuser = new_session_data["is_superuser"]
        game_username = new_session_data["game_username"]
        impersonation_target = new_session_data["impersonation_target"]
        impersonation_writability = new_session_data["impersonation_writability"]
        is_observer = new_session_data["is_observer"]

        self.logger.info("Authenticating user with ticket, as %r",
                             repr(dict(username=game_username, impersonation_target=impersonation_target,
                                       impersonation_writability=impersonation_writability, is_superuser=is_superuser,
                                       is_observer=is_observer)))

        # this will raise error if data is not fully coherent
        self._set_user(username=game_username,
                        impersonation_target=impersonation_target,
                        impersonation_writability=impersonation_writability,
                        is_superuser=is_superuser,
                        is_observer=is_observer)

        # we check changes from the old session ticket
        assert session_ticket
        assert session_ticket["game_instance_id"] == self.game_instance_id
        assert session_ticket["game_username"] == game_username # NEVER TOUCHED ATM
        session_ticket.update(
                              impersonation_target=impersonation_target,
                              impersonation_writability=impersonation_writability,
                              ) # NO change on "is_observer" ATM

        return session_ticket


    @transaction_watcher(always_writable=True)
    def authenticate_with_credentials(self, username, password):
        """
        Tries to authenticate an user from its credentials, and raises an UsageError on failure,
        or returns a session ticket for that user.
        
        Username can't be "anonymous_login" of course...
        """
        username = username.strip().lower()  # IMPORTANT, case-insensitive
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
        username = username.strip().lower()  # IMPORTANT, case-insensitive

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

        username = username.strip().lower()  # IMPORTANT, case-insensitive

        self.get_secret_question(username) # checks coherence of that call

        user_properties = self.get_character_properties(username)

        secret_answer_attempt = secret_answer_attempt.lower().strip() # double security
        expected_answer = user_properties["secret_answer"].lower().strip() # may NOT be None here
        assert expected_answer, expected_answer

        # WARNING - if by bug, no answer is actually expected, attempts must ALWAYS fail
        if expected_answer and (secret_answer_attempt == expected_answer):
            if target_email not in self.get_all_existing_emails():
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
                                 PersistentMapping(username=username, target_email=target_email),
                                 url=self.get_message_viewer_url_or_none(msg_id),
                                 visible_by=None) # on purpose, we hide that hacking!

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

    @readonly_method
    def should_display_admin_tips(self):
        return self.user.is_superuser or self.is_master(self.user.real_username) # tips also visible when impersonation!

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
        cls.PERMISSIONS_REGISTRY.update(names)  # SET operation, not dict


    def _load_initial_data(self, **kwargs):
        super(PermissionsHandling, self)._load_initial_data(**kwargs)

        game_data = self.data

        for (name, character) in game_data["character_properties"].items():
            character.setdefault("permissions", PersistentList())

        # USELESS ATM
        for (name, domain) in game_data["domains"].items():
            domain.setdefault("permissions", PersistentList())

    def _check_database_coherence(self, **kwargs):
        super(PermissionsHandling, self)._check_database_coherence(**kwargs)

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


    @transaction_watcher
    def set_permission(self, username=CURRENT_USER, permission=None, is_present=None):
        assert permission in self.PERMISSIONS_REGISTRY
        assert is_present in(True, False)
        username = self._resolve_username(username)
        data = self.get_character_properties(username)
        if is_present:
            permissions = set(data["permissions"]) | set([permission])
        else:
            permissions = set(data["permissions"]) - set([permission])
        assert isinstance(permissions, set)
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
        game_data.setdefault("friendships", PersistentMapping())
        game_data["friendships"].setdefault("proposed", PersistentMapping()) # mapping (proposer, recipient) => dict(proposal_date)
        game_data["friendships"].setdefault("sealed", PersistentMapping()) # mapping (proposer, accepter) => dict(proposal_date, acceptance_date)

    def _check_database_coherence(self, strict=False, **kwargs):
        super(FriendshipHandling, self)._check_database_coherence(**kwargs)

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
            raise UsageError(_("Forbidden friendship proposal: %(username)s -> %(recipient)s") % SDICT(username=username, recipient=recipient))
        if username == recipient:
            raise UsageError(_("User %s can't be friend with himself") % username)
        if self.are_friends(username, recipient):
            raise UsageError(_("Already existing friendship between %(username)s and %(recipient)s") % SDICT(username=username, recipient=recipient))

        friendship_proposals = self.data["friendships"]["proposed"]
        friendships = self.data["friendships"]["sealed"]
        if (username, recipient) in friendship_proposals:
            raise UsageError(_("%(username)s has already requested the friendship of %(recipient)s") % SDICT(username=username, recipient=recipient))

        current_date = datetime.utcnow()
        if (recipient, username) in friendship_proposals:
            # we seal the deal, with "recipient" as the initial proposer!
            existing_data = friendship_proposals[(recipient, username)]
            del friendship_proposals[(recipient, username)] # important
            friendships[(recipient, username)] = PersistentMapping(proposal_date=existing_data["proposal_date"],
                                                                acceptance_date=current_date)
            res = True
        else:
            friendship_proposals[(username, recipient)] = PersistentMapping(proposal_date=current_date)
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

        for other_username in self.get_all_other_character_usernames(username):
            character_statuses.setdefault(other_username, None) # other characters that are NOT related at all to current user get "None"

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

    def _check_database_coherence(self, **kwargs):
        super(GameInstructions, self)._check_database_coherence(**kwargs)

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

        return PersistentMapping(prologue_music=prologue_music,
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


    def _check_database_coherence(self, **kwargs):
        super(LocationsHandling, self)._check_database_coherence(**kwargs)

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

    def _check_database_coherence(self, **kwargs):
        super(OnlinePresence, self)._check_database_coherence(**kwargs)
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

    AVAILABLE_TEXT_FORMATS = Enum(("raw", "rst"))

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

            msg["body"] = utilities.load_multipart_rst(msg["body"])

            msg.setdefault("body_format", self.AVAILABLE_TEXT_FORMATS.rst)  # beware, initial content is considered as RICH TEXT

            msg["attachment"] = msg.get("attachment", None)
            if msg["attachment"]:
                msg["attachment"] = game_file_url(msg["attachment"])

            msg["is_certified"] = msg.get("is_certified", False)
            msg["mask_recipients"] = msg.get("mask_recipients", False)

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




    def _check_database_coherence(self, strict=False, **kwargs):
        super(TextMessagingCore, self)._check_database_coherence(strict=strict, **kwargs)

        messaging = self.messaging_data
        message_reference = {
                             "sender_email": basestring, # only initial one
                             "recipient_emails": PersistentList, # only initial, theoretical ones
                             "visible_by": PersistentMapping, # mapping usernames (including master_login) to translatable (ugettext_noop'ed) string "reason of visibility" or None (if obvious)
                             "mask_recipients": bool,  # equivalent of "full black-carbon-copy", even for current user

                             "subject": basestring,
                             "body": basestring,
                             "attachment": (types.NoneType, basestring), # a plainly functional URL, a personal document mostly
                             "transferred_msg": (types.NoneType, basestring), # text message id, might be "broken" if transferred message got deleted

                             "sent_at": datetime,
                             "is_certified": bool, # for messages sent via automated processes
                             "body_format": basestring,
                             "id": basestring,
                             "group_id": basestring,
                             }

        def _check_message_list(msg_list):
            previous_sent_at = None
            for msg in msg_list:

                # let's keep these IDs simple for now: ASCII...
                msg["id"].encode("ascii")
                msg["group_id"].encode("ascii")

                assert msg["subject"] # body can be empty, after all...

                if previous_sent_at:
                    assert previous_sent_at <= msg["sent_at"] # message lists are sorted by chronological order
                previous_sent_at = msg["sent_at"]

                utilities.check_dictionary_with_template(msg, message_reference, strict=False)

                utilities.check_is_email(msg["sender_email"])
                for recipient in msg["recipient_emails"]:
                    utilities.check_is_email(recipient)
                utilities.check_no_duplicates(msg["recipient_emails"])

                utilities.check_is_in_set(msg["body_format"], self.AVAILABLE_TEXT_FORMATS)

                if msg["body"]: # might be empty
                    pass #utilities.check_is_restructuredtext(msg["body"]) - there might be formatting errors in new emails...

                if msg["attachment"]:
                    assert msg["attachment"].startswith("/") or msg["attachment"].startswith("http")

                if msg["transferred_msg"]:
                    msg["transferred_msg"].encode("ascii")
                    try:
                        assert self.get_dispatched_message_by_id(msg_id=msg["transferred_msg"]) # must ALREADY be dispatched
                    except UsageError as e:
                        pass  # message might have been deleted by game master, we ignore this

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
                           date_or_delay_mn=None, is_certified=False,
                           parent_id=None, mask_recipients=False,
                           body_format="rst", **kwargs):
        """
        Beware, if a delay, date_or_delay_mn is treated as FLEXIBLE TIME.
        
        sender_email can be in recipient_emails too.
        
        mask_recipients is the equivalent of "full BCC", bo one can see the list of recipients
        
        TODO - is_certified is unused ATM.
        """
        # TOP LEVEL HERE - no parent call #
        assert body_format in self.AVAILABLE_TEXT_FORMATS
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
            # we IMMEDIATELY set the parent as answered, even if date_or_delay_mn is in the future
            try:
                parent_msg = self.get_dispatched_message_by_id(parent_id)
                group_id = parent_msg["group_id"]
                sender_username = self.get_username_from_email(sender_email) # character, or fallback to master
                self._set_dispatched_message_state_flags(username=sender_username, msg_id=parent_id, has_replied=True)  # do not touch the READ state - must be done MANUALLY
            except UsageError, e:
                self.logger.error(e, exc_info=True)  # something ugly happened to messaging history ? let it be...

        msgs_count = len(self.messaging_data["messages_dispatched"]) + len(self.messaging_data["messages_queued"])
        new_id = self._get_new_msg_id(msgs_count,
                                      subject + body) # unicity more than guaranteed

        if isinstance(date_or_delay_mn, datetime):
            sent_at = date_or_delay_mn # shall already have been computed with "flexible time" !
        else:
            sent_at = self.compute_effective_remote_datetime(date_or_delay_mn) # date_or_delay_mn is None or (negative/positive) number or pair

        msg = PersistentMapping({
                              "sender_email": sender_email,
                              "recipient_emails": recipient_emails,
                              "mask_recipients": mask_recipients,
                              "subject": subject,
                              "body": body,
                              "attachment": attachment, # None or string, a valid URL
                              "transferred_msg": transferred_msg, # msg id or None, might become invalidated
                              "sent_at": sent_at,
                              "is_certified": is_certified,
                              "id": new_id,
                              "group_id": group_id if group_id else new_id, # msg might start a new conversation
                              "body_format": body_format
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
    def get_message_viewer_url_or_none(self, msg_id): # FIXME - where shall this method actually be ?
        if not msg_id:
            return None
        return game_view_url('pychronia_game.views.view_single_message', datamanager=self, msg_id=msg_id)


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

        self.messaging_data.setdefault("globally_registered_contacts", PersistentMapping()) # identifier -> None or dict(description, avatar)
        self.global_contacts._load_initial_data(**kwargs)



    def _check_database_coherence(self, strict=False, **kwargs):
        super(TextMessagingExternalContacts, self)._check_database_coherence(strict=strict, **kwargs)

        self.global_contacts._check_database_coherence(strict=strict, **kwargs)


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
                    details = PersistentMapping()
                    self._table[identifier] = details
                details.setdefault("initial", True) # contacts that are necessary to gameplay CANNOT be edited/deleted
                details.setdefault("avatar", None)
                if details["avatar"]:
                    details["avatar"] = utilities.find_game_file_or_url("images", details["avatar"])
                details.setdefault("description", None)
                details.setdefault("access_tokens", None) # PUBLIC contact

                details.setdefault("gamemaster_hints", "")
                if details["gamemaster_hints"]:
                    details["gamemaster_hints"] = details["gamemaster_hints"].strip()


        def _preprocess_new_item(self, key, value):
            assert "initial" not in value
            print("_preprocess_new_item", key, self._table.get(key, {}))
            value["initial"] = self._table.get(key, {}).get("initial", False) # new entries are mutable by default
            value.setdefault("access_tokens", None)
            value.setdefault("gamemaster_hints", "")
            return (key, PersistentMapping(value))
            # other params are supposed to exist in "value"

        def _check_item_validity(self, key, value, strict=False):
            utilities.check_is_slug(key) # not necessarily an email
            utilities.check_has_keys(value, ["initial", "avatar", "description", "access_tokens"], strict=strict)
            utilities.check_is_bool(value["initial"])
            if value["access_tokens"] is not None: # None means "public"
                all_usernames = self._inner_datamanager.get_character_usernames()
                for username in value["access_tokens"]:
                    assert username in all_usernames, username # this check could be removed in the future, if other kinds of tokens are used!!
            if value["description"]: # optional
                utilities.check_is_string(value["description"], multiline=False)
            if value["avatar"]: # optional
                utilities.check_is_game_file_or_url(value["avatar"])

            if value.get("gamemaster_hints"): # optional
                utilities.check_is_restructuredtext(value["gamemaster_hints"])


        def _sorting_key(self, item_pair):
            return item_pair[0] # we sort by email, simply...

        def _get_table_container(self, root):
            return root["messaging"]["globally_registered_contacts"]

        def _item_can_be_deleted(self, key, value):
            return not value["initial"]

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
        messaging.setdefault("manual_messages_templates", PersistentMapping())

        if isinstance(messaging["manual_messages_templates"], list): # to simplify exchanges with dispatched emails, we allow list fixtures
            for idx, t in enumerate(messaging["manual_messages_templates"]):
                if "id" not in t:
                    if "subject" in t:
                        fallback_id = t["subject"].replace(" ", "_")  # somehow slugified subject
                    else:
                        fallback_id = random.randint(10000000, 100000000)
                    t["id"] = fallback_id
                t.setdefault("order", idx * 10)
            messaging["manual_messages_templates"] = dict((t["id"], t) for t in messaging["manual_messages_templates"]) # indexed by ID

        existing_template_categories = set() # we build initial list of template "tags"

        def _normalize_messages_templates(msg_list):

            for msg in msg_list:

                msg.setdefault("categories", ["unsorted"]) # to FILTER for gamemaster

                msg["categories"] = [c.replace(" ", "_") for c in msg["categories"]]  # somehow slugify them

                msg.setdefault("gamemaster_hints", "")
                if msg["gamemaster_hints"]:
                    msg["gamemaster_hints"] = msg["gamemaster_hints"].strip()

                msg["sender_email"], msg["recipient_emails"] = self._normalize_message_addresses(msg.get("sender_email", ""), msg.get("recipient_emails", []))

                msg["subject"] = msg.get("subject", "")
                msg["body"] = utilities.load_multipart_rst(msg.get("body", ""))
                msg["attachment"] = msg.get("attachment", None)
                msg["transferred_msg"] = msg.get("transferred_msg", None)
                msg["is_used"] = msg.get("is_used", False)
                msg["is_ignored"] = msg.get("is_ignored", False)
                msg["parent_id"] = msg.get("parent_id", None)
                msg["mask_recipients"] = msg.get("mask_recipients", False)

                if "id" in msg:
                    del msg["id"] # cleanup

                existing_template_categories.update(msg["categories"])

        # complete_messages_templates(game_data["automated_messages_templates"], is_manual=False)
        _normalize_messages_templates(messaging["manual_messages_templates"].values())

        existing_template_categories = sorted(existing_template_categories)
        game_data["global_parameters"]["message_template_categories"] = existing_template_categories # OVERRIDDEN and STATIC for now !


    def _check_database_coherence(self, strict=False, **kwargs):
        super(TextMessagingTemplates, self)._check_database_coherence(**kwargs)

        self.data["global_parameters"].setdefault("message_template_categories", PersistentList(["unsorted"])) # FIXME TEMP FIX

        existing_template_categories = self.get_global_parameter("message_template_categories")
        for cat in existing_template_categories:
            utilities.check_is_slug(cat)

        messaging = self.messaging_data

        #FIXME - BEWARE group_id not used yet, but it will be someday!!!

        template_fields = set("sender_email recipient_emails subject body attachment transferred_msg is_used is_ignored parent_id gamemaster_hints categories sent_at group_id order mask_recipients".split())

        for msg in messaging["manual_messages_templates"].values():

            assert set(msg.keys()) <= template_fields, (set(msg.keys()) - template_fields, msg["subject"])

            utilities.check_is_int(msg["order"])  # important - order of messages

            utilities.check_is_string(msg["subject"], multiline=False) # necessary for sidebar menu

            msg.setdefault("categories", PersistentList(["unsorted"])) # FIXME TEMP FIX
            assert isinstance(msg["categories"], PersistentList)
            assert msg["categories"] # ALL templates need to be categorized
            for cat in msg["categories"]:
                utilities.check_is_slug(cat)
                assert cat in existing_template_categories, cat

            if msg.get("gamemaster_hints"): # optional
                utilities.check_is_restructuredtext(msg["gamemaster_hints"])

            if msg["sender_email"]:
                utilities.check_is_email(msg["sender_email"])
            for recipient in msg["recipient_emails"]:
                utilities.check_is_email(recipient)

            if msg["subject"]:
                utilities.check_is_string(msg["subject"])
            if msg["body"]: # might be empty
                pass #utilities.check_is_restructuredtext(msg["body"])

            if msg["attachment"]:
                assert msg["attachment"].startswith("/") or msg["attachment"].startswith("http")

            if msg["transferred_msg"]:
                msg["transferred_msg"].encode("ascii")
                try:
                    assert self.get_dispatched_message_by_id(msg_id=msg["transferred_msg"]) # must ALREADY be dispatched
                except UsageError as e:
                    pass  # message might have been deleted by game master, we ignore this

            utilities.check_is_bool(msg["mask_recipients"])
            utilities.check_is_bool(msg["is_used"])
            utilities.check_is_bool(msg["is_ignored"])

            if msg["parent_id"]:
                assert self.get_dispatched_message_by_id(msg_id=msg["parent_id"])

    def _build_new_message(self, *args, **kwargs):
        use_template = kwargs.pop("use_template", None) # we remove our specific use_template param
        msg = super(TextMessagingTemplates, self)._build_new_message(*args, **kwargs)

        if use_template:
            try:
                tpl = self.get_message_template(use_template)
                tpl["is_used"] = True # will stay True even if queued message is actually canceled - we don't care
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

    @transaction_watcher(always_writable=True)
    def set_template_state_flags(self, tpl_id=None, is_ignored=None):
        assert is_ignored in (True, False)
        tpl = self.get_message_template(tpl_id)
        tpl["is_ignored"] = is_ignored

    @readonly_method
    def convert_msg_to_template(self, msg):
        """
        Takes as argument a msg object which was already dispatched previously.
        
        Returns a new, non-persistent, template object.
        """

        res = dict(categories=["unsorted"],
                   gamemaster_hints="")

        copied_fields = "sender_email recipient_emails mask_recipients subject body attachment transferred_msg".split()
        res.update({k: utilities.safe_copy(v) for (k, v) in msg.items() if k in copied_fields and v is not None})  # beware copy()

        return res




@register_module
class TextMessagingForCharacters(BaseDataManager): # TODO REFINE

    EMAIL_BOOLEAN_FIELDS_FOR_USERS = ("has_read", "has_replied", "has_starred", "has_archived")

    def _load_initial_data(self, **kwargs):
        super(TextMessagingForCharacters, self)._load_initial_data(**kwargs)

        game_data = self.data
        messaging = self.messaging_data

        utilities.check_is_game_file(game_data["global_parameters"]["default_contact_avatar"])
        game_data["global_parameters"]["default_contact_avatar"] = os.path.normpath(game_data["global_parameters"]["default_contact_avatar"])

        for (name, character) in game_data["character_properties"].items():
            character.setdefault("has_new_messages", 0)
            character.setdefault("new_messages_notification", None)

            # ADDRESS BOOK may contain any email, including characters' and "self" #
            character.setdefault("address_book", []) # just for memory - will be overridden below

        pangea_network = game_data["global_parameters"]["pangea_network_domain"]

        for (index, msg) in enumerate(messaging["messages_dispatched"] + messaging["messages_queued"]):
            # we modify the dicts in place

            if "@" not in msg["sender_email"]:
                msg["sender_email"] = (msg["sender_email"] + "@" + pangea_network) # we allow short character usernames as sender/recipient

            for field in self.EMAIL_BOOLEAN_FIELDS_FOR_USERS:
                msg.setdefault(field, PersistentList())

            msg["visible_by"] = msg.get("visible_by", PersistentMapping())
            msg["visible_by"].update(self._determine_basic_visibility(msg)) # we might override here

        # we compute automatic address_book for the first time
        self._recompute_all_address_book_via_msgs()
        assert not self._recompute_all_address_book_via_msgs()

        # initial coherence check
        all_emails = self.get_all_existing_emails() # ALL available

        ''' TODO FIXME BETTER CHECK ??
        #print (">>>>>>>>###", all_emails)
        for msg in messaging["messages_dispatched"] + messaging["messages_queued"]:
            assert msg["sender_email"] in all_emails, (msg["sender_email"], all_emails)
            for recipient_email in msg["recipient_emails"]:
                assert recipient_email in all_emails, (recipient_email, all_emails)
        '''

    def _check_database_coherence(self, **kwargs):
        super(TextMessagingForCharacters, self)._check_database_coherence(**kwargs)

        # TODO - check all messages and templates with utilities.check_is_restructuredtext(value) ? What happens if invalid rst ?

        game_data = self.data
        messaging = self.messaging_data

        utilities.check_is_slug(game_data["global_parameters"]["pangea_network_domain"])

        message_reference = {field: PersistentList for field in self.EMAIL_BOOLEAN_FIELDS_FOR_USERS}
        message_reference["is_certified"] = bool  # for messages sent via automated processes


        def _check_message_list(msg_list, is_queued):

            master = self.get_global_parameter("master_login")

            for msg in msg_list:

                utilities.check_dictionary_with_template(msg, message_reference, strict=False)

                all_chars = game_data["character_properties"].keys()
                all_users = all_chars + [game_data["global_parameters"]["master_login"]]
                for field in self.EMAIL_BOOLEAN_FIELDS_FOR_USERS:
                    assert all((char in all_users) for char in msg[field]), msg[field]

                potential_viewers = self.get_character_usernames() + [self.master_login] # master_login is set if NPCs were concerned
                for username, reason in msg["visible_by"].items():
                    assert username in potential_viewers
                    utilities.check_is_slug(reason)
                    assert reason in VISIBILITY_REASONS, reason

                if not is_queued: # queued message don't have basic visibility settings yet
                    # later, special script events might make it normal that even senders or recipients do NOT see the message anymore, but NOT NOW
                    pass ##TODO-REUSE assert set(self._determine_basic_visibility(msg).keys()) - set([master]) <= set(msg["visible_by"].keys()), [self._determine_basic_visibility(msg).keys(), msg]


        # WARNING - we must check the two lists separately, because little incoherencies can appear at their junction due to the workflow
        # (the first queued messages might actually be younger than the last ones of the sent messages list)
        _check_message_list(messaging["messages_dispatched"], is_queued=False)
        _check_message_list(messaging["messages_queued"], is_queued=True)

        # new-message audio notification system (characters may have no dedicated notification)
        all_msg_files = [self.data["audio_messages"][properties["new_messages_notification"]]["file"]
                         for properties in self.data["character_properties"].values() if properties["new_messages_notification"]]
        utilities.check_no_duplicates(all_msg_files) # users must NOT have the same new-message audio notifications

        for character_set in self.data["character_properties"].values():
            utilities.check_is_int(character_set["has_new_messages"])
            utilities.check_no_duplicates(character_set["address_book"])
            for external_contact in character_set["address_book"]: # MIGHT BE A CHARACTER CONTACT!!
                utilities.check_is_email(external_contact) # FIXME - check that it exists and is authorized, too ???
        assert not self._recompute_all_address_book_via_msgs() # we recompute address_book, and check everything is coherent


        # special mailing list
        ml_address = self.get_global_parameter("all_players_mailing_list")
        ml_props = self.global_contacts[ml_address] # MUST exist
        assert ml_props["initial"]


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

        assert not any(field in msg for field in self.EMAIL_BOOLEAN_FIELDS_FOR_USERS)
        msg.update({field: PersistentList(kwargs.get(field, {})) for field in self.EMAIL_BOOLEAN_FIELDS_FOR_USERS})

        assert "visible_by" not in msg
        msg["visible_by"] = PersistentMapping()

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
        self.set_new_message_notification(concerned_characters=target_characters, increment=1)

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

        npc_usernames = self.get_character_usernames(is_npc=True)

        assert utilities.check_no_duplicates(msg["recipient_emails"]) # already normalized
        for recipient_email in msg["recipient_emails"]:
            if recipient_email == ml:
                for usr in (username for (username, data) in self.get_character_sets().items() if not data["is_npc"]): # only PLAYER characters
                    visibilities[usr] = VISIBILITY_REASONS.recipient
            else:
                recipient_username = self.get_character_or_none_from_email(recipient_email)
                if recipient_username:
                    visibilities[recipient_username] = VISIBILITY_REASONS.recipient
                if not recipient_username or recipient_username in npc_usernames: # both external contacts and NPCs concern game master
                    visibilities[self.master_login] = VISIBILITY_REASONS.recipient # might occur several times, we don't care

        sender_username = self.get_character_or_none_from_email(msg["sender_email"])
        if sender_username:
            visibilities[sender_username] = VISIBILITY_REASONS.sender # might override "recipient" status, in case of self-mailing
        if not sender_username or sender_username in npc_usernames:
            visibilities[self.master_login] = VISIBILITY_REASONS.sender # overrides existing - both external contacts and NPCs concern game master


        return visibilities


    @readonly_method
    def get_character_email(self, username=CURRENT_USER):
        username = self._resolve_username(username)
        assert self.is_character(username)
        return username + "@" + self.get_global_parameter("pangea_network_domain")

    @readonly_method
    def get_character_emails(self, is_npc=None):
        pangea_network_domain = self.get_global_parameter("pangea_network_domain")
        return [username + "@" + pangea_network_domain for username in self.get_character_usernames(is_npc=is_npc)]

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



    def _set_dispatched_message_state_flags(self, username, msg_id, **flags):
        # we don't care about whether user had the right to view msg or not, basically
        assert username and msg_id, (username, msg_id)
        utilities.check_is_subset(flags, self.EMAIL_BOOLEAN_FIELDS_FOR_USERS)
        msg = self.get_dispatched_message_by_id(msg_id)
        for (k, v) in flags.items():
            assert v in (True, False)  # NOT NONE!
            if v and username not in msg[k]:
                msg[k].append(username)
            elif not v and username in msg[k]:
                msg[k].remove(username)

    @transaction_watcher(always_writable=True)
    def set_dispatched_message_state_flags(self, username=CURRENT_USER, msg_id=None, **flags):
        username = self._resolve_username(username) # username can be master login here !
        self._set_dispatched_message_state_flags(username=username, msg_id=msg_id, **flags)

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
            self.set_new_message_notification(concerned_characters=[username], increment=0)
        return records

    @readonly_method
    def get_user_related_messages(self, username=CURRENT_USER, visibility_reasons=None, archived=None):
        """
        For game master, actually returns all emails sent to external contacts.
        Preserves msg order by date ascending.
        
        If specified, "visibility_reasons" is a sequence of allowed visibility reasons for the messages to be returned.
        
        If "archived" is not None, it's a boolean specifying if we must consider inbox or archived messages.
        """
        assert visibility_reasons is None or visibility_reasons and utilities.check_is_subset(visibility_reasons, VISIBILITY_REASONS)
        assert archived in (None, True, False)
        username = self._resolve_username(username)
        all_messages = self.get_all_dispatched_messages()
        visibility_reasons = visibility_reasons or VISIBILITY_REASONS  # by default, ANY visibility reason is OK
        assert None not in visibility_reasons
        def msg_filter(msg):
            return msg["visible_by"].get(username) in visibility_reasons and (archived is None or ((username in msg["has_archived"]) == archived))
        return [msg for msg in all_messages if msg_filter(msg)]


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
        # FIXME !!!!!!!!!!!!!! OBSOLETED ???
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
                        description=props["description"] if "description" in props else (props["official_name"] + " - " + props["official_role"]),
                        gamemaster_hints=props.get("gamemaster_hints")) # for both characters and external contacts!

            if as_dict:
                results_dict[email] = data
            else:
                results.append(data)

        return results_dict if as_dict else results

    @staticmethod
    def sort_email_addresses_list(emails_list):
        return sorted(emails_list, key=lambda email: (email[0] != '[',) + tuple(reversed(email.split("@")))) # sort by domain then username

    @readonly_method
    def get_all_existing_emails(self):
        """
        Unsorted list is output.
        """
        return self.get_character_emails() + self.global_contacts.keys()

    @readonly_method
    def get_sorted_user_contacts(self, username=CURRENT_USER):
        """
        For both master and characters.
        """
        _sorter = self.sort_email_addresses_list

        username = self._resolve_username(username)
        assert not self.is_anonymous(username)
        if self.is_master(username=username):
            res = _sorter(self.get_character_emails()) + _sorter(self.global_contacts.keys()) # separate characters from external contacts
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


    @readonly_method
    def get_other_known_characters(self, username=CURRENT_USER):
        """
        Currently HEAVY method.
        """
        username = self._resolve_username(username)
        if self.is_master(username):
            return self.get_character_usernames()
        else:
            emails = self.get_character_address_book(username=username)
            other_characters_and_nones = [self.get_character_or_none_from_email(email) for email in emails]
            return [char for char in other_characters_and_nones if char and char != username]


    # Audio notifications for new messages #

    @readonly_method
    def get_pending_new_message_notifications(self):
        # returns users that must be notified, with corresponding message audio_id
        needing_notifications = PersistentMapping((username, properties["new_messages_notification"])
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
        return self.data["character_properties"][username]["has_new_messages"] # integer

    @transaction_watcher
    def set_new_message_notification(self, concerned_characters, increment):
        """
        Only for CHARACTERS ATM. used both to increment and RESET the counter.
        """
        for character in concerned_characters:
            if increment:
                assert isinstance(increment, (int, long)) and increment > 0, increment
                self.data["character_properties"][character]["has_new_messages"] += increment
            else:
                self.data["character_properties"][character]["has_new_messages"] = 0 # RESET





@register_module
class TextMessagingInterception(BaseDataManager):

    def _load_initial_data(self, **kwargs):
        super(TextMessagingInterception, self)._load_initial_data(**kwargs)

        game_data = self.data
        messaging = self.messaging_data

        for (name, data) in game_data["character_properties"].items():
            data.setdefault("wiretapping_targets", PersistentList())
            data.setdefault("confidentiality_activation_datetime", None) # UTC datetime when SSL/TLS security was bought

    def _check_database_coherence(self, **kwargs):
        super(TextMessagingInterception, self)._check_database_coherence(**kwargs)

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

    @readonly_method
    def get_characters_for_visibility_reason(self, msg, visibility_reason):
        assert visibility_reason in VISIBILITY_REASONS
        character_usernames = set(self.get_character_usernames())
        return sorted([username for (username, reason) in msg["visible_by"].items()
                                if username in character_usernames and reason == visibility_reason])


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

    def _check_database_coherence(self, **kwargs):
        super(RadioMessaging, self)._check_database_coherence(**kwargs)
        self.radio_spots._check_database_coherence(**kwargs)

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

                assert "url" not in details, details  # LEGACY format, not used anymore

                details.setdefault("gamemaster_hints", "")
                if details["gamemaster_hints"]:
                    details["gamemaster_hints"] = details["gamemaster_hints"].strip()

                # audio messages that are necessary to gameplay CANNOT be edited/deleted
                # (ex. new-message-notifications, victory/defeat sounds...
                details.setdefault("initial", True)

                details.setdefault("file", None) # LOCAL file or URL
                if details["file"]:
                    details["file"] = utilities.find_game_file_or_url("audio", "radio_spots", details["file"])

            # we DO NOT care about duplicates, which might happen when editing and reloading DB...


        def _preprocess_new_item(self, key, value):
            assert "initial" not in value
            value["initial"] = self._table.get(key, {}).get("initial", False) # new entries are mutable by default
            value.setdefault("gamemaster_hints", "")
            value["title"] = value["title"].strip()
            value["text"] = value["text"].strip()
            return (key, PersistentMapping(value))
            # other params are supposed to exist in "value"

        def _check_item_validity(self, key, value, strict=False):

            #print ("RADIOSPOT IS", key, value)

            radio_spot_fields = set("initial gamemaster_hints title text file".split())
            assert set(value.keys()) == radio_spot_fields, (set(value.keys()) - radio_spot_fields, key)

            utilities.check_is_slug(key)

            utilities.check_is_bool(value["initial"])

            if value.get("gamemaster_hints"): # optional
                pass # utilities.check_is_restructuredtext(value["gamemaster_hints"])

            utilities.check_is_string(value["title"])

            assert isinstance(value["text"], basestring) and value["text"]   # might NOT be empty

            # it might be that 'file' is None (gamemaster must then use text-to-speech generation)
            if value["file"] is not None:
                utilities.check_is_string(value["file"], forbidden_chars=["|"])
                utilities.check_is_game_file_or_url(value["file"])


        def _sorting_key(self, item_pair):
            return item_pair[0] # we sort by key, simply...

        def _get_table_container(self, root):
            return root["audio_messages"]

        def _item_can_be_deleted(self, key, value):
            return not value["initial"]

        def _callback_on_any_update(self):
            self._inner_datamanager._prune_obsolete_radio_playlist_entries()

    radio_spots = LazyInstantiationDescriptor(RadioSpotsManager)


    def _prune_obsolete_radio_playlist_entries(self):
        filtered_radio_messages = [audio_id for audio_id in self.data["global_parameters"]["pending_radio_messages"]
                                   if audio_id in self.radio_spots]
        self.data["global_parameters"]["pending_radio_messages"] = PersistentList(filtered_radio_messages)

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
                properties["has_new_messages"] = 0 # RESET
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

    def _check_database_coherence(self, **kwargs):
        super(Chatroom, self)._check_database_coherence(**kwargs)

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
        chatting_usernames = [username for username in self.get_character_usernames(exclude_current=exclude_current) if self.get_chatting_status(username)]
        return chatting_usernames

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

        record = PersistentMapping(time=datetime.utcnow(), username=self.user.username, message=message)
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



    def _check_database_coherence(self, **kwargs):
        super(ActionScheduling, self)._check_database_coherence(**kwargs)

        game_data = self.data

        scheduled_action_reference = {
            "execute_at": datetime,
            "function": (basestring, collections.Callable), # string to represent a datamanager method
            "args": tuple,
            "kwargs": PersistentMapping
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
        kwargs = PersistentMapping(kwargs)

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

        record = PersistentMapping({
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


    def _check_database_coherence(self, **kwargs):
        super(PersonalFiles, self)._check_database_coherence(**kwargs)

        # common and personal file folders
        assert os.path.isdir(os.path.join(config.GAME_FILES_ROOT, "personal_files", self.COMMON_FILES_DIRS))
        for name in (self.data["character_properties"].keys() + [self.data["global_parameters"]["master_login"]]):
            folder_path = os.path.join(config.GAME_FILES_ROOT, "personal_files", name)
            assert os.path.isdir(folder_path), folder_path
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
                             PersistentMapping(folder=folder, password=password, username=username),
                             url=None,
                             visible_by=None) # only game master shall see this

        return decrypted_files

    @readonly_method
    def get_all_encrypted_folders_info(self):
        """
        Retursn a mapping {folder_name => passwords_list}
        """
        folders_info = {}
        folders = os.listdir(os.path.join(config.GAME_FILES_ROOT, "encrypted"))
        for f in folders:
            folder_path = os.path.join(config.GAME_FILES_ROOT, "encrypted", f)
            if folder_path.startswith("_") or not os.path.isdir(folder_path):
                continue # might be a README file or stuffs
            pwds = os.listdir(folder_path)
            pwds = [pwd for pwd in pwds if (not pwd.startswith("_") and os.path.isdir(os.path.join(config.GAME_FILES_ROOT, "encrypted", f, pwd)))]
            if not pwds:
                continue # empty folder
            folders_info[f] = sorted(pwds)
        return folders_info


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

        all_files = sorted(common_files + personal_files, key=lambda x: os.path.basename(x)) # sort by basename!

        if absolute_urls:
            domain = config.SITE_DOMAIN # "http://%s" % Site.objects.get_current().domain
            all_files = [domain + user_file for user_file in all_files]

        return all_files







@register_module
class MoneyItemsOwnership(BaseDataManager):

    # FIXME - fix forms containing gems, now (value, origin) tuples


    def _load_initial_data(self, **kwargs):
        super(MoneyItemsOwnership, self)._load_initial_data(**kwargs)

        game_data = self.data

        game_data["global_parameters"].setdefault("bank_name", "bank")
        game_data["global_parameters"].setdefault("bank_account", 0) # can be negative
        game_data["global_parameters"].setdefault("spent_gems", []) # gems which were used in abilities or manually debited

        total_digital_money = game_data["global_parameters"]["bank_account"]
        total_gems = game_data["global_parameters"]["spent_gems"][:] # COPY

        for (name, character) in game_data["character_properties"].items():
            character["account"] = character.get("account", 0)

            character.setdefault("extra_goods", "") # restructuredtext string

            character_gems = character.get("gems", [])
            character_gems = [tuple(i) for i in character_gems]
            character["gems"] = sorted(character_gems)

            total_gems += [i[0] for i in character["gems"]]
            total_digital_money += character["account"]

        # We initialize some runtime checking parameters #
        game_data["global_parameters"]["total_digital_money"] = total_digital_money # integer
        game_data["global_parameters"]["total_gems"] = PersistentList(sorted(total_gems)) # sorted list of integer values

        self.game_items._load_initial_data(**kwargs)  # important


    def _check_database_coherence(self, **kwargs):
        super(MoneyItemsOwnership, self)._check_database_coherence(**kwargs)

        game_data = self.data

        def _check_gems(gems_list):
            for gem in gems_list:
                assert isinstance(gem, tuple) # must be hashable!!
                (gem_value, gem_origin) = gem
                utilities.check_is_positive_int(gem_value)
                if gem_origin is not None:
                    # important - we must not break that reference to an existing game item
                    assert gem_origin in self.game_items
                    assert self.game_items[gem_origin]["is_gem"]

        total_digital_money = game_data["global_parameters"]["bank_account"]
        total_gems = game_data["global_parameters"]["spent_gems"][:] # COPY!
        # print ("^^^^^^^^^^^^", "spent_gems", total_gems.count(500))

        _check_gems(game_data["global_parameters"]["spent_gems"])

        for (name, character) in game_data["character_properties"].items():
            utilities.check_is_positive_int(character["account"], non_zero=False)
            total_digital_money += character["account"]

            character.setdefault("extra_goods", "") # FIXME TEMP

            assert isinstance(character["extra_goods"], basestring)
            if character["extra_goods"]:
                utilities.check_is_restructuredtext(character["extra_goods"])

            #assert character["gems"] == sorted(character["gems"]), character["gems"] FIXME TEMP

            _check_gems(character["gems"])
            total_gems += character["gems"]
            # print ("---------", name, total_gems.count(500))

        old_total_digital_money = game_data["global_parameters"]["total_digital_money"]
        assert old_total_digital_money == total_digital_money, "%s != %s" % (old_total_digital_money, total_digital_money)

        self.game_items._check_database_coherence(**kwargs)  # important


    class GameItemsManager(DataTableManager):

        TRANSLATABLE_ITEM_NAME = ugettext_lazy("objects/gems")

        def _load_initial_data(self, **kwargs):

            for (name, properties) in self._table.items():

                # SAFETY, we forbid modifying initial items, for now, to avoid incoherences with abilities
                properties.setdefault("initial", True)

                properties.setdefault("gamemaster_hints", "")
                if properties["gamemaster_hints"]:
                    properties["gamemaster_hints"] = properties["gamemaster_hints"].strip()

                properties["auction"] = properties.get('auction') or ""  # NON NULL

                properties['total_price'] = properties.get('total_price') or 0  # NON NULL

                if properties.get('unit_cost') is None:
                    properties['unit_cost'] = self._compute_items_unit_cost(total_cost=properties['total_price'], num_gems=properties['num_items'])

                properties['owner'] = properties.get('owner', None)

                #if properties["is_gem"] and not properties['owner']: # we dont recount gems appearing in character["gems"]
                #    total_gems += [properties['unit_cost']] * properties["num_items"]

                properties['image'] = utilities.find_game_file_or_url("images", properties['image'])

        def _preprocess_new_item(self, key, value):
            assert "initial" not in value
            value["initial"] = self._table.get(key, {}).get("initial", False) # new entries are mutable by default
            value.setdefault('owner', None)
            return (key, PersistentMapping(value))
            # other params are supposed to exist in "value"

        def _check_item_validity(self, key, value, strict=False):
            (name, properties) = (key, value)

            game_data = self._inner_datamanager.data

            utilities.check_is_bool(value["initial"])

            if properties["gamemaster_hints"]: # optional
                pass # utilities.check_is_restructuredtext(properties["gamemaster_hints"])

            utilities.check_is_slug(name)
            assert isinstance(properties['is_gem'], bool)
            assert utilities.check_is_positive_int(properties['num_items'], non_zero=True)

            # these two values can be NON RELATED!
            assert utilities.check_is_positive_int(properties['total_price'], non_zero=False)
            assert utilities.check_is_positive_int(properties['unit_cost'], non_zero=False)

            assert properties['owner'] is None or properties['owner'] in game_data["character_properties"].keys()

            assert isinstance(properties['title'], basestring) and properties['title']
            assert isinstance(properties['comments'], basestring) and properties['comments']
            utilities.check_is_game_file_or_url(properties['image'])

            # item might be out of auction, with auction == ""
            assert isinstance(properties['auction'], basestring)

            """ useless now
            if properties["is_gem"] and not properties["owner"]:
                total_gems += [properties['unit_cost']] * properties["num_items"]
                # (">>>>>>>>>>", name, total_gems.count(500))
            """

            # we DO NOT care about duplicates, which might happen when editing and reloading DB...


        def _sorting_key(self, item_pair):
            return item_pair[0] # we sort by key, simply...

        def _get_table_container(self, root):
            return root["game_items"]

        def _item_can_be_modified(self, key, value):
            return not (value["owner"])  # can't change values then

        def _item_can_be_deleted(self, key, value):
            return not (value["owner"] or value["initial"])

        def _callback_on_any_update(self):
            pass


        def _compute_items_unit_cost(self, total_cost, num_gems):
            assert total_cost >= 0
            assert num_gems > 0
            return int(math.ceil(float(total_cost / num_gems)))

        def _compute_items_total_price(self, unit_cost, num_gems):
            assert unit_cost >= 0
            assert num_gems > 0
            return unit_cost * num_gems # simpler


    game_items = LazyInstantiationDescriptor(GameItemsManager)


    @readonly_method
    def get_all_items(self):
        return self.data["game_items"]  # directly expose data

    @readonly_method
    def get_gem_items(self):
        return {key: value for (key, value) in self.game_items.items() if value["is_gem"]}

    @readonly_method
    def get_non_gem_items(self):
        return {key: value for (key, value) in self.game_items.items() if not value["is_gem"]}

    @readonly_method
    def get_auction_items(self):
        return {key: value for (key, value) in self.game_items.items() if value["auction"]}

    @readonly_method
    def get_item_properties(self, item_name):
        try:
            return self.game_items[item_name]
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
    def transfer_money_between_characters(self, from_name, to_name, amount, reason=None):

        amount = int(amount) # might raise error
        if amount <= 0:
            raise UsageError(_("Money amount must be positive"))

        if from_name == to_name:
            raise UsageError(_("Sender and recipient must be different"))

        if reason:
            reason = reason.strip()
            reason = reason if reason else None

        bank_name = self.get_global_parameter("bank_name")
        visible_by = []

        if from_name == bank_name: # special case
            if self.get_global_parameter("bank_account") < amount:
                raise UsageError(_("Bank doesn't have enough money available"))
            self.data["global_parameters"]["bank_account"] -= amount
        else:
            from_char = self.get_character_properties(from_name) # might raise error
            if from_char["account"] < amount:
                raise UsageError(_("Sender doesn't have enough money"))
            from_char["account"] -= amount
            visible_by.append(from_name)

        if to_name == bank_name: # special case
            self.data["global_parameters"]["bank_account"] += amount
        else:
            to_char = self.get_character_properties(to_name) # might raise error
            to_char["account"] += amount
            visible_by.append(to_name) # can't be the same as from_name, due to checks above

        # FIXME - bug here with early translation !!! #
        msg = ugettext_noop("Bank operation: %(amount)s kashes transferred from %(from_name)s to %(to_name)s.")
        if reason:
            msg += " " + ugettext_noop("Reason: %(reason)s") % SDICT(reason=reason)

        self.log_game_event(msg,
                             PersistentMapping(amount=amount, from_name=from_name, to_name=to_name),
                             url=None,
                             visible_by=(visible_by or None))


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
            remaining_gems.sort()
            character["gems"] = remaining_gems
        item["owner"] = None

    def _assign_free_item_to_character(self, item_name, item, char_name):
        assert self.get_item_properties(item_name) == item
        assert item["owner"] is None
        character = self.get_character_properties(char_name)
        if item["is_gem"]:
            gems = self._get_item_separate_gems(item_name)
            character["gems"] += gems # we add each gem separately, along with its reference
            character["gems"].sort()
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
        from_name = item["owner"] if item["owner"] else _("no one") # must be done IMMEDIATELY
        visible_by = []

        if previous_owner is not None and previous_owner != item["owner"]:
            raise NormalUsageError(_("This object doesn't belong to %s") % previous_owner)

        if item["owner"] == char_name:
            raise NormalUsageError(_("Impossible to have same origin and destination for item transfer"))

        if item["owner"]:
            visible_by.append(item["owner"]) # FIRST
            self._free_item_from_character(item_name, item)

        if char_name:
            visible_by.append(char_name)
            self._assign_free_item_to_character(item_name=item_name, item=item, char_name=char_name)

        self.log_game_event(ugettext_noop("Item %(item_name)s transferred from %(from_name)s to %(char_name)s."),
                             PersistentMapping(item_name=item_name, from_name=from_name, char_name=char_name),
                             url=None,
                             visible_by=visible_by) # characters involved thus see the transaction in events


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
        
        Also works for master.
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
            available_items = PersistentMapping([(name, value) for (name, value)
                                              in my_getter().items()
                                              if value['owner'] in all_sharing_users])
        return available_items

    @readonly_method
    def get_user_artefacts(self, username=CURRENT_USER):
        username = self._resolve_username(username)
        return PersistentMapping([(name, value) for (name, value)
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
            raise UsageError(_("Sender doesn't possess these gems"))

        remaining_gems.sort()
        sender_char["gems"] = remaining_gems
        gems_choices.sort()
        recipient_char["gems"] += gems_choices

        self.log_game_event(ugettext_noop("Gems transferred from %(from_name)s to %(to_name)s: %(gems_choices)s."),
                             PersistentMapping(from_name=from_name, to_name=to_name, gems_choices=gems_choices),
                             url=None,
                             visible_by=[from_name, to_name]) # event visible by both characters


    @transaction_watcher
    def debit_character_gems(self, username=CURRENT_USER, gems_choices=None):
        """
        Remove some of a character's gems from the game.
        """
        assert isinstance(gems_choices, (list, PersistentList))
        gems_choices = PersistentList(gems_choices)
        username = self._resolve_username(username)
        character_properties = self.get_character_properties(username)
        remaining_gems = utilities.substract_lists(character_properties["gems"], gems_choices)
        if remaining_gems is None:
            raise UsageError(_("Sender doesn't possess these gems"))
        else:
            character_properties["gems"] = PersistentList(remaining_gems)
            self.data["global_parameters"]["spent_gems"] += gems_choices

        self.log_game_event(ugettext_noop("Gems debited from %(username)s: %(gems_choices)s."),
                             PersistentMapping(username=username, gems_choices=gems_choices),
                             url=None,
                             visible_by=[username])

    @transaction_watcher
    def credit_character_gems(self, username=CURRENT_USER, gems_choices=None):
        """
        Revive some gems that were previously spent.
        """
        assert isinstance(gems_choices, (list, PersistentList))
        gems_choices = PersistentList(gems_choices)
        username = self._resolve_username(username)
        character_properties = self.get_character_properties(username)

        remaining_gems = utilities.substract_lists(self.data["global_parameters"]["spent_gems"], gems_choices)
        if remaining_gems is None:
            raise UsageError(_("Selected gems couldn't be found among spent gems"))
        else:
            self.data["global_parameters"]["spent_gems"] = PersistentList(remaining_gems)
            character_properties["gems"] += gems_choices

        self.log_game_event(ugettext_noop("Gems credited to %(username)s: %(gems_choices)s."),
                             PersistentMapping(username=username, gems_choices=gems_choices),
                             url=None,
                             visible_by=[username])


@register_module
class Items3dViewing(BaseDataManager):


    def _load_initial_data(self, **kwargs):
        super(Items3dViewing, self)._load_initial_data(**kwargs)

    def _check_database_coherence(self, **kwargs):
        super(Items3dViewing, self)._check_database_coherence(**kwargs)

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
            #assert name in self.game_items.keys(), name
            #assert self.game_items[name]["initial"], name
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
        ##print("WE REGISTER", view_class.NAME, view_class.REQUIRES_CHARACTER_PERMISSION, view_class.get_access_permission_name() if view_class.REQUIRES_CHARACTER_PERMISSION else None)

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
        game_data.setdefault("views", PersistentMapping())
        game_data["views"].setdefault("activated_views", PersistentList())
        # no need to sync - it will done later in _init_from_db()


    def _check_database_coherence(self, **kwargs):
        super(GameViews, self)._check_database_coherence(**kwargs)

        game_data = self.data
        utilities.check_no_duplicates(game_data["views"]["activated_views"])
        for view_name in game_data["views"]["activated_views"]:
            assert view_name in self.ACTIVABLE_VIEWS_REGISTRY.keys(), (view_name, self.ACTIVABLE_VIEWS_REGISTRY.keys())


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

    @readonly_method
    def get_game_view_admin_summaries(self):
        """
        Gets a dict in format {view_name: html_chunk}, with summaries of the states 
        """
        chunks_dict = {}

        for klass_name, klass in self.GAME_VIEWS_REGISTRY.items():
            view = self.instantiate_game_view(self.GAME_VIEWS_REGISTRY[klass_name])
            html_chunk = view.get_admin_summary_html()
            if html_chunk:
                chunks_dict[klass_name] = dict(title=view.TITLE,
                                               html_chunk=html_chunk)

        return chunks_dict



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
                ability_data = self.data["abilities"][key] = PersistentMapping()
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


    def _check_database_coherence(self, strict=False, **kwargs):
        super(SpecialAbilities, self)._check_database_coherence(**kwargs)

        utilities.check_is_bool(self.get_global_parameter("disable_automated_ability_responses"))

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

    def _check_database_coherence(self, **kwargs):
        super(StaticPages, self)._check_database_coherence(**kwargs)
        self.static_pages._check_database_coherence(**kwargs)


    # bunch of standard categories #
    CONTENT_CATEGORY = "content"
    HELP_CATEGORY = "content" # SAME CATEGORY, because same security settings actually...


    @readonly_method
    def get_categorized_static_page(self, category, name):
        assert category and name
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
                details.setdefault("initial", False) # we assume ANY static page is optional for the game, and can be edited/deleted

                details.setdefault("categories", []) # distinguishes possibles uses of static pages
                details["categories"] = [details["categories"]] if isinstance(details["categories"], basestring) else details["categories"]

                details.setdefault("keywords", []) # useful for encyclopedia articles mainly
                details["keywords"] = [details["keywords"]] if isinstance(details["keywords"], basestring) else details["keywords"]

                details.setdefault("gamemaster_hints", "") # for gamemaster only
                details["gamemaster_hints"] = details["gamemaster_hints"].strip()

                details.setdefault("title", "")
                if details["title"]:
                    details["title"] = details["title"].strip()


        def _preprocess_new_item(self, key, value):
            assert "initial" not in value
            value["initial"] = self._table.get(key, {}).get("initial", False) # new entries are mutable by default
            value.setdefault("gamemaster_hints", "")
            return (key, PersistentMapping(value))
            # other params are supposed to exist in "value"

        def _check_item_validity(self, key, value, strict=False):
            utilities.check_is_slug(key)
            assert key.lower() == key # handy

            utilities.check_has_keys(value, ["initial", "categories", "content", "gamemaster_hints", "keywords"], strict=strict) # SOON -> "title" TOO!! FIXME TODO

            utilities.check_is_bool(value["initial"])

            if value["title"]:
                utilities.check_is_string(value["title"], multiline=False)
                assert value["title"] == value["title"].strip(), value["title"]

            utilities.check_is_restructuredtext(value["content"])

            utilities.check_is_list(value["categories"])
            for category in (value["categories"]):
                utilities.check_is_slug(category)

            utilities.check_is_list(value["keywords"])
            for keyword in (value["keywords"]):
                utilities.check_is_string(keyword, multiline=False)

            if value.get("gamemaster_hints"): # optional
                utilities.check_is_restructuredtext(value["gamemaster_hints"])


        def _sorting_key(self, item_pair):
            """
            We separate articles by "dashed" prefixes (none, or "help", "top", "bottom"...)
            """
            key = item_pair[0]
            if "-" in key:
                res = key.partition("-")
            else:
                res = ("", "-", key) # non-categorized, must be first in list!
            return res

        def _get_table_container(self, root):
            return root["static_pages"]

        def _item_can_be_deleted(self, key, value):
            return not value["initial"]

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


    def _check_database_coherence(self, **kwargs):
        super(Encyclopedia, self)._check_database_coherence(**kwargs)

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
        Returns the entry dict, or None.
        Fetching is case-insensitive.
        """
        key = article_id.lower().strip()
        article = self.get_categorized_static_page(category=self.ENCYCLOPEDIA_CATEGORY, name=key)
        return article if article else None


    @readonly_method
    def get_encyclopedia_matches(self, search_string):
        """
        Returns the list of encyclopedia article whose keywords (primary or not) match *search_string*, 
        sorted by most relevant first.
        
        Matching is very tolerant, since it's case-insensitive, and keywords needn't be "separate words" in the searched string.
        """
        keywords_mapping = self.get_encyclopedia_keywords_mapping(only_primary_keywords=False)

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
    def get_encyclopedia_keywords_mapping(self, excluded_link=None, only_primary_keywords=False):
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
                if only_primary_keywords:
                    break  # other keywords are not meant eg. for auto-linking
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
                value["image"] = utilities.find_game_file("images", "captchas", value["image"])

    def _check_database_coherence(self, strict=False, **kwargs):
        super(NightmareCaptchas, self)._check_database_coherence(**kwargs)

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

            assert (value["answer"] is not None) == bool(value["explanation"]), value  # let's be coherent


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
            raise NormalUsageError(_("Nope, it looks like this captcha had no known answer..."))

        normalized_attempt = attempt.strip().lower().replace(" ", "")
        normalized_answer = value["answer"].lower() # necessarily slug, but not always lowercase

        if normalized_attempt != normalized_answer:
            raise NormalUsageError(_("Incorrect captcha answer '%s'") % attempt)

        assert value["explanation"], repr(value["explanation"])
        return value["explanation"]



@register_module
class NoveltyNotifications(BaseDataManager):


    def _check_database_coherence(self, strict=False, **kwargs):
        super(NoveltyNotifications, self)._check_database_coherence(**kwargs)

        self.data["global_parameters"].setdefault("disable_real_email_notifications", False) ## TEMP FIXME
        utilities.check_is_bool(self.get_global_parameter("disable_real_email_notifications"))


    @readonly_method
    def get_single_character_external_notifications(self, username=CURRENT_USER):
        username = self._resolve_username(username)
        assert self.is_character(username)

        signal_new_radio_messages = not self.has_read_current_playlist(username=username)
        signal_new_text_message = self.has_new_message_notification(username=username) # only for characters atm

        res = {
                'signal_new_radio_messages': signal_new_radio_messages,
                'signal_new_text_messages': signal_new_text_message,
              }
        return res


    @readonly_method
    def get_characters_external_notifications(self):
        """
        Only players having a good "real life email" will be returned here.
        
        Both players and NPCs can have these external notifications (eg. if someone is in charge of an NPC).
        """

        if self.get_global_parameter("disable_real_email_notifications"):
            return []

        all_notifications = []

        for username in self.get_character_usernames(exclude_current=False, is_npc=None): # ALL characters

            real_email = self.get_character_properties(username)["real_life_email"]

            if real_email:
                notifications = self.get_single_character_external_notifications(username=username)
                all_notifications.append(dict(username=username,
                                              real_email=real_email,
                                              **notifications))

        return all_notifications

