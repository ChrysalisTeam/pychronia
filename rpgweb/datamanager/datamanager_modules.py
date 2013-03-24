# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *
from rpgweb.common import _, _lazy, _noop # just to shut up the static checker...

from .datamanager_tools import *
from .datamanager_user import GameUser, SUPERUSER_SPECIAL_LOGIN
from .datamanager_core import BaseDataManager
from .data_table_manager import *

PLACEHOLDER = object()


MODULES_REGISTRY = [] # IMPORTANT



def register_module(Klass):
    MODULES_REGISTRY.append(Klass)
    return Klass



VISIBILITY_REASONS = Enum(["sender", "recipient", "interceptor"]) # token identifying why one can see an email


@register_module
class GameGlobalParameters(BaseDataManager):

    def _load_initial_data(self, **kwargs):
        super(GameGlobalParameters, self)._load_initial_data(**kwargs)

        game_data = self.data
        game_data["global_parameters"]["opening_music"] = utilities.complete_game_file_path(game_data["global_parameters"]["opening_music"], "musics")


    def _check_database_coherency(self, **kwargs):
        super(GameGlobalParameters, self)._check_database_coherency(**kwargs)

        game_data = self.data
        utilities.check_is_bool(game_data["global_parameters"]["game_is_started"])
        utilities.check_is_game_file(game_data["global_parameters"]["opening_music"])


    @readonly_method
    def get_global_parameters(self):
        return self.data["global_parameters"]

    @readonly_method
    def get_global_parameter(self, name):
        return self.data["global_parameters"][name]

    @readonly_method
    def is_game_started(self):
        return self.get_global_parameter("game_is_started")

    @transaction_watcher(ensure_game_started=False)
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
        self._set_user(username=None, has_write_access=True) # TODO - improve by doing player authentication at init time?


    def _notify_user_change(self, username, **kwargs):
        assert not hasattr(super(CurrentUserHandling, self), "_notify_user_change") # we're well top-level here


    @transaction_watcher(ensure_game_started=False)
    def _set_user(self, username, has_write_access, impersonation=None):
        assert not hasattr(super(CurrentUserHandling, self), "_set_user") # we're well top-level here
        self.user = GameUser(datamanager=self,
                             username=username,
                             has_write_access=has_write_access,
                             impersonation=impersonation,) # might raise UsageError

        self._notify_user_change(username=username)

        return self.user


    def _resolve_username(self, username):
        if username is None:
            raise RuntimeError("Wrong username==None detected")
        if username == CURRENT_USER:
            return self.user.username
        return username



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
    def compute_remote_datetime(self, delay_mn):
        # delay can be a number or a range (of type int or float)
        # we always work in UTC

        new_time = datetime.utcnow()
        # print (">>>>>>>>>>>>>>>>>> DATETIME", new_time, "WITH DELAYS", delay_mn)

        if delay_mn:

            factor = 60 * self.get_global_parameter("game_theoretical_length_days") # important - we scale relatively to the duration of the game

            if not isinstance(delay_mn, (int, long, float)):
                assert len(delay_mn) == 2

                delay_s_min = int(delay_mn[0] * factor)
                delay_s_max = int(delay_mn[1] * factor)
                assert delay_s_min <= delay_s_max, "delay min must be < delay max - %s vs %s" % (delay_s_min, delay_s_max)

                delay_s = random.randint(delay_s_min, delay_s_max) # time range in seconds

            else:
                delay_s = delay_mn * factor # no need to coerce to integer here

            # print "DELAY ADDED : %s s" % delay_s
            new_time += timedelta(seconds=delay_s) # delay_s can be a float

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
                evt["time"] = self.compute_remote_datetime(delay_mn=evt["time"])
        game_data["events_log"].sort(key=lambda evt: evt["time"])


    def _check_database_coherency(self, **kwargs):
        super(GameEvents, self)._check_database_coherency(**kwargs)

        event_reference = {
            "time": datetime,
            "message": basestring, # UNTRANSLATED message
            "substitutions": (types.NoneType, PersistentDict),
            "url": (types.NoneType, basestring),
            "username": (types.NoneType, basestring)
        }
        previous_time = None
        for event in self.data["events_log"]:
            assert event["message"]
            if previous_time:
                assert previous_time <= event["time"] # event lists are sorted by chronological order
            previous_time = event["time"]
            utilities.check_dictionary_with_template(event, event_reference)
            username = event["username"]
            assert username in self.get_character_usernames() or \
                    username == self.get_global_parameter("master_login") or \
                    username == self.get_global_parameter("anonymous_login")

    @transaction_watcher
    def log_game_event(self, message, substitutions=None, url=None):
        assert message, "log message must not be empty"

        if substitutions:
            assert isinstance(substitutions, PersistentDict), (message, substitutions)
            if config.DEBUG:
                message % substitutions # may raise formatting errors if corrupt...
        else:
            assert "%(" not in message, "Message %s needs substitution arguments" % message
            pass

        utcnow = datetime.utcnow()

        record = PersistentDict({
            "time": utcnow,
            "message": message, # UNTRANSLATED message !
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
class CharacterHandling(BaseDataManager): # TODO REFINE

    CHARACTER_REAL_LIFE_ATTRIBUTES = ["real_life_identity", "real_life_email"]

    def _load_initial_data(self, **kwargs):
        super(CharacterHandling, self)._load_initial_data(**kwargs)


    def _check_database_coherency(self, **kwargs):
        super(CharacterHandling, self)._check_database_coherency(**kwargs)

        game_data = self.data

        assert game_data["character_properties"]

        reserved_names = [game_data["global_parameters"][reserved] for reserved in ["master_login", "anonymous_login"]]

        for (name, character) in game_data["character_properties"].items():

            utilities.check_is_slug(name)
            assert name not in reserved_names
            assert "@" not in name # let's not mess with email addresses...

            utilities.check_is_string(character["description"])
            utilities.check_is_string(character["official_name"])
            utilities.check_is_string(character["real_life_identity"])
            utilities.check_is_string(character["real_life_email"])
            utilities.check_is_slug(character["character_color"])

            identities = [char["official_name"].replace(" ", "").lower() for char in
                          game_data["character_properties"].values()]
            utilities.check_no_duplicates(identities)


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
        res = sorted(self.data["character_properties"].keys())
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
    def __get_fellow_usernames(self, username=CURRENT_USER):
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
    def build_select_choices_from_usernames(self, usernames):
        visible_names = [username.capitalize() for username in usernames] # no need for real official names here
        character_choices = zip(usernames, visible_names)
        return character_choices

    @transaction_watcher
    def update_real_life_data(self, username=CURRENT_USER, real_life_identity=None, real_life_email=None):
        username = self._resolve_username(username)
        data = self.get_character_properties(username)

        action_done = False

        if real_life_identity and real_life_identity != data["real_life_identity"]:
            data["real_life_identity"] = real_life_identity
            action_done = True

        if real_life_email and real_life_email != data["real_life_email"]:
            if not utilities.is_email(real_life_email):
                raise NormalUsageError(_("Wrong email %s") % real_life_email)
            data["real_life_email"] = real_life_email
            action_done = True

        return action_done




@register_module
class DomainHandling(BaseDataManager): # TODO REFINE


    def _load_initial_data(self, **kwargs):
        super(DomainHandling, self)._load_initial_data(**kwargs)

        game_data = self.data
        for (name, content) in game_data["domains"].items():
            content["prologue_music"] = utilities.complete_game_file_path(content["prologue_music"], "musics")

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

            assert isinstance(content["victory"], basestring) and content["victory"] in game_data["audio_messages"]
            assert isinstance(content["defeat"], basestring) and content["defeat"] in game_data["audio_messages"]

            assert isinstance(content["prologue_music"], basestring)

            utilities.check_is_game_file(content["prologue_music"])


    @readonly_method
    def get_domain_names(self):
        return sorted(self.data["domains"].keys())

    @readonly_method
    def get_domain_properties(self, domain_name):
        return self.data["domains"][domain_name]

    @transaction_watcher(ensure_game_started=False)
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
            character["secret_answer"] = character["secret_answer"] if not character["secret_answer"] else character["secret_answer"].strip().lower()


    def _check_database_coherency(self, **kwargs):
        super(PlayerAuthentication, self)._check_database_coherency(**kwargs)

        game_data = self.data

        assert self.get_global_parameter("anonymous_login") is None or \
               utilities.check_is_slug(self.get_global_parameter("anonymous_login"))
        utilities.check_is_slug(self.get_global_parameter("master_login"))
        utilities.check_is_slug(self.get_global_parameter("master_password"))

        for character in self.get_character_sets().values():
            utilities.check_is_slug(character["password"])
            if not character["secret_question"]:
                assert not character["secret_answer"]
            else:
                utilities.check_is_string(character["secret_question"])
                utilities.check_is_slug(character["secret_answer"])
                assert character["secret_answer"] == character["secret_answer"].lower()


        # MASTER and ANONYMOUS cases

        global_parameters = game_data["global_parameters"]

        utilities.check_is_slug(global_parameters["anonymous_login"])

        utilities.check_is_slug(global_parameters["master_login"])
        utilities.check_is_slug(global_parameters["master_password"])
        utilities.check_is_slug(global_parameters["master_email"])
        utilities.check_is_slug(global_parameters["master_real_life_email"])



    @readonly_method
    def get_available_logins(self):
        return ([self.get_global_parameter("anonymous_login")] +
                self.get_character_usernames() +
                [self.get_global_parameter("master_login")])


    @transaction_watcher(ensure_game_started=False)
    def logout_user(self):
        self._set_user(username=None, has_write_access=True)


    @readonly_method
    def can_impersonate(self, username, impersonation):
        """
        This method must play it safe, we're not sure username or impersonation is valid here!
        
        Returns True iff user *username* can temporarily take the identity of *impersonation*.
        """
        # FIXME - what about friendship ?? Todo ??
        assert username and impersonation

        if username == impersonation: # no sense - and also prevents master from impersonating master
            return False

        if username == SUPERUSER_SPECIAL_LOGIN or self.is_master(username):
            if impersonation in self.get_available_logins():
                return True # impersonation can be a character or anonymous (or even master for SUPERUSER_SPECIAL_LOGIN)

        return False


    @readonly_method
    def get_impersonation_targets(self, username):  #FIXME TODO? USELESS ??
        assert username
        possible_impersonations = [target for target in self.get_available_logins()
                                   if self.can_impersonate(username, target)]
        return possible_impersonations


    def _filter_impersonation_request(self,
                                       game_username,
                                       session_ticket,
                                       requested_impersonation_target,
                                       requested_impersonation_writability,
                                       django_user):

        assert session_ticket.get("game_instance_id") == self.game_instance_id

        # first, we compute the impersonation we actually want #
        if requested_impersonation_target == "": # special case "delete current impersonation target"
            requested_impersonation_target = None
        elif requested_impersonation_target is None: # means "use legacy one"
            requested_impersonation_target = session_ticket.get("impersonation_target", None)
        else:
            pass # we let submitted requested_impersonation_target continue

        requested_impersonation_writability = (requested_impersonation_writability
                                               if requested_impersonation_writability is not None
                                               else session_ticket.get("impersonation_writability", None))

        # then we filter out forbidden impersonation choices #
        if requested_impersonation_target:
            if django_user and (django_user.is_staff or django_user.is_superuser):
                game_username = SUPERUSER_SPECIAL_LOGIN # special django users can impersonate anyone
            elif game_username and self.can_impersonate(game_username, requested_impersonation_target):
                pass # user is game master, or a character with friendship rights
            else:
                requested_impersonation_target = requested_impersonation_writability = None # this stops impersonation completely
                self.user.add_error(_("Unauthorized user impersonation detected: %s") % requested_impersonation_target)

        return dict(game_username=game_username,
                    impersonation_target=requested_impersonation_target,
                    impersonation_writability=requested_impersonation_writability)



    @transaction_watcher(ensure_game_started=False)
    def authenticate_with_ticket(self,
                                 session_ticket,
                                 requested_impersonation_target=None,
                                 requested_impersonation_writability=None,
                                 django_user=None):
        """
        Allows a logged other to continue using his normal session,
        or to impersonate a lower-rank user (but in readonly mode, then).
        
        Raises UsageError if problem.
        """

        if not isinstance(session_ticket, dict):
            raise AbnormalUsageError(_("Invalid session ticket: %s") % session_ticket)

        game_instance_id = session_ticket.get("game_instance_id")
        if game_instance_id != self.game_instance_id:
            raise NormalUsageError(_("Session ticket doesn't belong to this instance"))

        game_username = session_ticket.get("game_username", None) # instance-local user set via login page

        # FIXME - todo, change username to master automatically if a django staff member ????

        new_impersonation_data = self._filter_impersonation_request(game_username=game_username,
                                                                   session_ticket=session_ticket,
                                                                   requested_impersonation_target=requested_impersonation_target,
                                                                   requested_impersonation_writability=requested_impersonation_writability,
                                                                   django_user=django_user)
        assert len(new_impersonation_data) == 3
        game_username = new_impersonation_data["game_username"]
        impersonation_target = new_impersonation_data["impersonation_target"]
        impersonation_writability = new_impersonation_data["impersonation_writability"]
        session_ticket.update(new_impersonation_data) # SAVED

        final_username = game_username # ALWAYS, can also be None if user is logged as staff in django but not logged in rpgweb
        final_has_write_access = True if not impersonation_target else bool(impersonation_writability) # game-authenticated users can always write
        final_impersonation = impersonation_target

        self._set_user(username=final_username, # can be SUPERUSER_SPECIAL_LOGIN (then it must impersonate someone), or None -> anonymous
                       has_write_access=final_has_write_access,
                       impersonation=final_impersonation)

        return session_ticket


    @transaction_watcher(ensure_game_started=False)
    def authenticate_with_credentials(self, username, password):
        """
        Tries to authenticate an user from its credentials, and raises an UsageError on failure,
        or returns a session ticket for that user.
        """
        username = username.strip()
        password = password.strip()
        if username == self.get_global_parameter("master_login"): # do not use is_master here, just in case...
            wanted_pwd = self.get_global_parameter("master_password")
        else:
            data = self.get_character_properties(username) # might raise UsageError
            wanted_pwd = data["password"]

        if password and password == wanted_pwd:
            self._set_user(username, has_write_access=True, impersonation=None) # when using credentials, it's always a real user
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
            if target_email not in self.get_user_contacts(self.get_global_parameter("master_login")): # all emails available
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
                                       date_or_delay_mn=self.get_global_parameter("password_recovery_delays"))

            self.log_game_event(_noop("Password of %(username)s has been recovered by %(target_email)s."),
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
        assert all((name.lower() == name and " " not in name) for name in names)
        cls.PERMISSIONS_REGISTRY.update(names) # SET operation, not dict


    def _load_initial_data(self, **kwargs):
        super(PermissionsHandling, self)._load_initial_data(**kwargs)

        game_data = self.data

        for (name, character) in game_data["character_properties"].items():
            character.setdefault("permissions", PersistentList())

        for (name, domain) in game_data["domains"].items():
            domain.setdefault("permissions", PersistentList())


    def _check_database_coherency(self, **kwargs):
        super(PermissionsHandling, self)._check_database_coherency(**kwargs)

        for permission in self.PERMISSIONS_REGISTRY: # check all available permissions
            utilities.check_is_slug(permission)
            assert permission.lower() == permission

        game_data = self.data

        ''' NIO - what if we deactivate a module !!!
        for (name, character) in game_data["character_properties"].items():
            for permission in character["permissions"]:
                assert permission in self.PERMISSIONS_REGISTRY

        for (name, domain) in game_data["domains"].items():
            for permission in domain["permissions"]:
                assert permission in self.PERMISSIONS_REGISTRY
        '''

    @transaction_watcher(ensure_game_started=False)
    def update_permissions(self, username=CURRENT_USER, permissions=None):
        username = self._resolve_username(username)
        assert self.is_character(username) and permissions

        data = self.get_character_properties(username)
        data["permissions"] = permissions


    @readonly_method
    def has_permission(self, username=CURRENT_USER, permission=None):
        assert permission
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

        delay = self.get_global_parameter("friendship_minimum_duration_h")
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
            assert (username2, username1) not in sealed_friendships # ensures both unicity and non-self-friendship
            assert (username1, username2) not in proposed_friendships
            assert (username2, username1) not in proposed_friendships
            assert username1 in character_names
            assert username2 in character_names
            template = {
                         "proposal_date": datetime,
                         "acceptance_date": datetime,
                        }
            utilities.check_dictionary_with_template(friendship_params, template, strict=strict)



    @readonly_method # TODO TEST THAT OVERRIDE
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
        assert self.is_character(username) and self.is_character(recipient)
        if username == recipient:
            raise AbnormalUsageError(_("User %s can't be friend with himself") % username)
        if self.are_friends(username, recipient):
            raise AbnormalUsageError(_("Already existing friendship between %s and %s") % (username, recipient))

        friendship_proposals = self.data["friendships"]["proposed"]
        friendships = self.data["friendships"]["sealed"]
        if (username, recipient) in friendship_proposals:
            raise AbnormalUsageError(_("%s has already requested the friendship of %s") % (username, recipient))

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

        # TODO - add game logging for both events
        return res


    @readonly_method
    def get_friendship_requests(self, username=CURRENT_USER):
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
                raise AbnormalUsageError(_("Unexisting friendship: %s<->%s") % (username1, username2))


    @readonly_method
    def are_friends(self, username1, username2):
        friendships = self.data["friendships"]["sealed"]
        if (username1, username2) in friendships or (username2, username1) in friendships:
            return True
        return False


    @readonly_method
    def get_friends(self, username=CURRENT_USER):
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
        friends = self.get_friends(username)

        recent_friend = []
        old_friend = []
        for friend in friends:
            __, friendship_data = self.get_friendship_params(username, friend)
            if self.is_friendship_too_young_to_be_terminated(friendship_data):
                recent_friend.append(friend)
            else:
                old_friend.append(friend)


        friendship_requests = self.get_friendship_requests(username)

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
        min_delay = self.get_global_parameter("friendship_minimum_duration_h")
        return (friendship_data["acceptance_date"] > datetime.utcnow() - timedelta(hours=min_delay))


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








@register_module
class LocationsHandling(BaseDataManager):

    def _load_initial_data(self, **kwargs):
        super(LocationsHandling, self)._load_initial_data(**kwargs)

        game_data = self.data
        for (name, properties) in game_data["locations"].items():
            properties.setdefault("spy_message", None)
            properties.setdefault("spy_audio", False)


    def _check_database_coherency(self, **kwargs):
        super(LocationsHandling, self)._check_database_coherency(**kwargs)

        game_data = self.data
        assert game_data["locations"]
        for (name, properties) in game_data["locations"].items():

            utilities.check_is_slug(name)

            if properties["spy_message"] is not None:
                utilities.check_is_string(properties["spy_message"])
            if properties["spy_audio"]:
                utilities.check_is_game_file(os.path.join("spy_reports", "spy_" + name.lower() + ".mp3"))


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
        if username in self.data["character_properties"]: # TODO improve
            self.set_online_status(username)


    def _set_online_status(self, username): # no fallback system here
        self.data["character_properties"][username]["last_online_time"] = datetime.utcnow()

    @transaction_watcher(ensure_game_started=False)
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


    def _load_initial_data(self, **kwargs):
        super(TextMessagingCore, self)._load_initial_data(**kwargs)

        game_data = self.data

        messaging = game_data.setdefault("messaging", PersistentList())

        messaging.setdefault("messages_dispatched", PersistentList())
        messaging.setdefault("messages_queued", PersistentList())

        for (index, msg) in enumerate(messaging["messages_dispatched"] + messaging["messages_queued"]):
            # we modify the dicts in place

            msg["sender_email"], msg["recipient_emails"] = self._normalize_message_addresses(msg["sender_email"], msg["recipient_emails"])

            msg["attachment"] = msg.get("attachment", None)
            msg["is_certified"] = msg.get("is_certified", False)

            if isinstance(msg["sent_at"], (long, int)): # offset in minutes
                msg["sent_at"] = self.compute_remote_datetime(msg["sent_at"])

            if not msg["id"]:
                msg["id"] = self._get_new_msg_id(index, msg["subject"] + msg["body"])

            if not msg.get("group_id"):
                msg["group_id"] = msg["id"]

        messaging["messages_dispatched"].sort(key=lambda msg: msg["sent_at"])
        messaging["messages_queued"].sort(key=lambda msg: msg["sent_at"])


    def _check_database_coherency(self, strict=False, **kwargs):
        super(TextMessagingCore, self)._check_database_coherency(strict=strict, **kwargs)

        messaging = self.messaging_data
        message_reference = {
                             "sender_email": basestring, # only initial one
                             "recipient_emails": PersistentList, # only initial, theoretical ones
                             "visible_by": PersistentDict, # mapping usernames (including master_login) to translatable (_noop'ed) string "reason of visibility" or None (if obvious)

                             "subject": basestring,
                             "body": basestring,
                             "attachment": (types.NoneType, basestring), # None or string

                             "sent_at": datetime,
                             "is_certified": bool, # for messages sent via automated processes

                             "id": basestring,
                             "group_id": basestring,
                             }

        def _check_message_list(msg_list):
            previous_sent_at = None
            for msg in msg_list:

                assert msg["subject"] # body can be empty, after all...

                if previous_sent_at:
                    assert previous_sent_at <= msg["sent_at"] # message lists are sorted by chronological order
                previous_sent_at = msg["sent_at"]

                utilities.check_dictionary_with_template(msg, message_reference, strict=False)

                utilities.check_is_email(msg["sender_email"])
                for recipient in msg["recipient_emails"]:
                    utilities.check_is_email(recipient)

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


    def _build_new_message(self, sender_email, recipient_emails, subject, body, attachment=None,
                           date_or_delay_mn=None, is_read=False, is_certified=False,
                           parent_id=None, **kwargs):
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
            sent_at = self.compute_remote_datetime(date_or_delay_mn) # date_or_delay_mn is None or number

        msg = PersistentDict({
                              "sender_email": sender_email,
                              "recipient_emails": recipient_emails,
                              "subject": subject,
                              "body": body,
                              "attachment": attachment, # None or string
                              "sent_at": sent_at,
                              "is_certified": is_certified,
                              "id": new_id,
                              "group_id": group_id if group_id else new_id,
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
        recipient_emails = PersistentList(set(recipient_emails)) # remove duplicates

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

    def _check_sender_email(self, sender_email):
        """
        Default : ALLOW ATM.
        
        To be overridden.
        """
        return # raise UsageError(_("Unknown sender address %r") % sender_email)

    def _check_recipient_email(self, recipient_email, sender_email):
        """
        Default : ALLOW ATM
        
        Only *sender_email* must be taken into account, not currently logged user,
        since some abilities might allow to send an email in the name of someone else.
        
        To be overridden.
        """
        return # raise UsageError(_("Unknown recipient address %r") % recipient_email)


    @transaction_watcher
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


    @transaction_watcher(ensure_game_started=False)
    def force_message_sending(self, msg_id):
        # immediately sends a queued message

        items = [item for item in enumerate(self.get_all_queued_messages()) if item[1]["id"] == msg_id]
        assert len(items) <= 1

        if not items:
            return False

        (index, msg) = items[0]

        del self.messaging_data["messages_queued"][index] # we remove the msg from queued list

        msg["sent_at"] = datetime.utcnow() # we force the timestamp to UTCNOW
        self._immediately_dispatch_message(msg)

        return True



    # manipulation of message lists #

    @staticmethod
    def _get_new_msg_id(index, content):
        md5 = hashlib.md5()
        md5.update(content.encode('ascii', 'ignore'))
        my_hash = md5.hexdigest()[0:4]
        return unicode(index) + "_" + my_hash

    @readonly_method
    def get_message_viewer_url(self, msg_id): # FIXME - where shall this method actually be ?
        return reverse('rpgweb.views.view_single_message',
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
            raise UsageError(_("Unknown message id"))
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

        TRANSLATABLE_ITEM_NAME = _lazy("contact")

        def _load_initial_data(self, **kwargs):
            for identifier, details in self._table.items():
                if details is None:
                    details = PersistentDict()
                    self._table[identifier] = details
                details.setdefault("immutable", True)
                details.setdefault("avatar", None)
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
                    assert username in all_usernames # this check could be removed in the future, if other kinds of tokens are used!!
            if value["description"]: # optional
                utilities.check_is_string(value["description"], multiline=False)
            if value["avatar"]: # optional
                utilities.check_is_slug(value["avatar"]) # FIXME improve that

        def _sorting_key(self, item_pair):
            return item_pair[0] # we sort by email, simply...

        def _get_table_container(self, root):
            return root["messaging"]["globally_registered_contacts"]

        def _item_can_be_edited(self, key, value):
            return (True if not value.get("immutable") else False)

    global_contacts = LazyInstantiationDescriptor(GloballyRegisteredContactsManager)


    @transaction_watcher
    def grant_private_contact_access_to_character(self, username=CURRENT_USER, contact_id=None, avatar=None, description=None):
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
                data["access_tokens"].append(username) # will fail if it was a public contact, i.e "None"
            else:
                pass # swallow "access already granted" error

    @transaction_watcher
    def revoke_private_contact_access_from_character(self, username=CURRENT_USER, contact_id=None):
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

        def _complete_messages_templates(msg_list):

            for msg in msg_list.values():

                msg["sender_email"], msg["recipient_emails"] = self._normalize_message_addresses(msg.get("sender_email", ""), msg.get("recipient_emails", []))

                msg["subject"] = msg.get("subject", "")
                msg["body"] = msg.get("body", "")
                msg["attachment"] = msg.get("attachment", None)
                msg["is_used"] = msg.get("is_used", False)

        # complete_messages_templates(game_data["automated_messages_templates"], is_manual=False)
        _complete_messages_templates(messaging["manual_messages_templates"])


    def _check_database_coherency(self, **kwargs):
        super(TextMessagingTemplates, self)._check_database_coherency(**kwargs)

        messaging = self.messaging_data
        # FIXME - check templates here


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

        for (name, character) in game_data["character_properties"].items():
            character.setdefault("has_new_messages", False)
            character.setdefault("external_contacts", []) # just for memory - will be overridden below

        pangea_network = game_data["global_parameters"]["pangea_network_domain"]

        for (index, msg) in enumerate(messaging["messages_dispatched"] + messaging["messages_queued"]):
            # we modify the dicts in place

            if "@" not in msg["sender_email"]:
                msg["sender_email"] = (msg["sender_email"] + "@" + pangea_network) # we allow short character usernames as sender/recipient

            msg["has_read"] = msg.get("has_read", PersistentList())
            msg["has_replied"] = msg.get("has_replied", PersistentList())

            msg["visible_by"] = msg.get("visible_by", PersistentDict())
            msg["visible_by"].update(self._determine_basic_visibility(msg)) # we might override here

        # we compute automatic external_contacts for the first time
        self._recompute_all_external_contacts_via_msgs()
        assert not self._recompute_all_external_contacts_via_msgs()

        # initial coherency check
        all_emails = self.get_user_contacts(self.master_login) # ALL available
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

        utilities.check_is_slug(game_data["global_parameters"]["global_email"]) # shortcut tag to send email to every character

        message_reference = {
                             "has_read": PersistentList,
                             "has_replied": PersistentList,
                             "is_certified": bool, # for messages sent via automated processes
                             }

        def _check_message_list(msg_list):

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
                # later, special script events might make it normal that even senders or recipients do NOT see the message anymore, but NOT NOW
                assert set(self._determine_basic_visibility(msg).keys()) <= set(msg["visible_by"].keys())


        # WARNING - we must check the two lists separately, because little incoherencies can appear at their junction due to the workflow
        # (the first queued messages might actually be younger than the last ones of the sent messages list)
        _check_message_list(messaging["messages_dispatched"])
        _check_message_list(messaging["messages_queued"])

        # new-message audio notification system
        all_msg_files = [self.data["audio_messages"][properties["new_messages_notification"]]["file"]
                         for properties in self.data["character_properties"].values()]
        utilities.check_no_duplicates(all_msg_files) # users must NOT have the same new-message audio notifications

        for character_set in self.data["character_properties"].values():
            utilities.check_no_duplicates(character_set["external_contacts"])
            for external_contact in character_set["external_contacts"]:
                utilities.check_is_email(external_contact) # FIXME - check that it exists and is authorized, too ???

        assert not self._recompute_all_external_contacts_via_msgs() # we recompute external_contacts, and check everything is coherent

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

        msg["visible_by"].update(self._determine_basic_visibility(msg))

        super(TextMessagingForCharacters, self)._immediately_dispatch_message(msg)

    def _message_dispatching_post_hook(self, frozen_msg):
        super(TextMessagingForCharacters, self)._message_dispatching_post_hook(frozen_msg)

        self._update_external_contacts(msg=frozen_msg)
        #print (">>>>>>>>>>>", frozen_msg["visible_by"])
        characters = set(self.get_character_usernames())
        target_characters = [username for username, reason in frozen_msg["visible_by"].items()
                                      if reason != VISIBILITY_REASONS.sender and username in characters] # thus we remove master_login and sender
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

        sender_username = self.get_character_or_none_from_email(msg["sender_email"])
        if sender_username:
            visibilities[sender_username] = VISIBILITY_REASONS.sender
        else:
            visibilities[self.master_login] = VISIBILITY_REASONS.sender

        for recipient_email in msg["recipient_emails"]:
            recipient_username = self.get_character_or_none_from_email(recipient_email)
            if recipient_username:
                visibilities[recipient_username] = VISIBILITY_REASONS.recipient # might override "sender" status for that user
            else:
                visibilities[self.master_login] = VISIBILITY_REASONS.recipient # might occur several times, we don't care

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
                                         for contact in character["external_contacts"]]
            return sorted(set(all_contacts))
        else:
            character = self.get_character_properties(username)
            return character["external_contacts"]
    

    @readonly_method
    def get_user_contacts(self, username=CURRENT_USER):
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

    @transaction_watcher(ensure_game_started=False)
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

    @transaction_watcher(ensure_game_started=False)
    def pop_received_messages(self, username=CURRENT_USER):
        """
        Also resets the 'new message' notification of concerner character, if any.
        """
        username = self._resolve_username(username)
        records = self.get_received_messages(username=username)
        if self.is_character(username):
            self.set_new_message_notification(concerned_characters=[username], new_status=False)
        return records

    @transaction_watcher(ensure_game_started=False)
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
        for msg in reversed(messages):
            groups.setdefault(msg["group_id"], [])
            groups[msg["group_id"]].append(msg)

        return groups.values()


    @readonly_method
    def get_unread_messages_count(self, username=CURRENT_USER):
        unread_msgs = [msg for msg in self.get_received_messages(username=username)
                           if username not in msg["has_read"]]
        return len(unread_msgs)



    @readonly_method
    def get_user_contacts(self, username=CURRENT_USER):
        username = self._resolve_username(username)
        if self.is_master(username=username):
            return self.get_character_emails() + sorted(self.global_contacts.keys())
        else:
            return self.get_character_emails() + self.get_character_external_contacts(username=username) # including user himself


    @readonly_method
    def get_character_external_contacts(self, username=CURRENT_USER):
        username = self._resolve_username(username)
        props = self.get_character_properties(username)
        return props["external_contacts"]


    def _recompute_all_external_contacts_via_msgs(self):
        external_contacts_changed = False
        for msg in self.messaging_data["messages_dispatched"]:
            new_contacts_added = self._update_external_contacts(msg)
            if new_contacts_added:
                #print("new_contacts_added", msg["subject"], new_contacts_added)
                external_contacts_changed = True
        return external_contacts_changed

    @transaction_watcher(ensure_game_started=False)
    def _update_external_contacts(self, msg):

        new_contacts_added = False

        (concerned_characters, external_emails) = self._get_external_contacts_updates(msg)

        for username in concerned_characters:
            props = self.get_character_properties(username)
            old_external_contacts = set(props["external_contacts"])
            new_external_contacts = old_external_contacts | external_emails
            assert set(props["external_contacts"]) <= new_external_contacts # that list can only grow - of course
            props["external_contacts"] = PersistentList(new_external_contacts) # no particular sorting here, but unicity is ensured

            new_contacts_added = new_contacts_added or (new_external_contacts != old_external_contacts) # SETS comparison

        return new_contacts_added

    @readonly_method
    def _get_external_contacts_updates(self, msg):
        """
        Retrieve info needed to update the *external_contacts* fields of character accounts,
        when they send/receive this single message.
        """
        all_characters_emails = set(self.get_character_emails())
        msg_emails = set(msg["recipient_emails"] + [msg["sender_email"]])
        external_emails = msg_emails - all_characters_emails

        master_login = self.master_login
        concerned_characters = {key: value for (key, value) in msg["visible_by"].items() if key != master_login} # can't use dict.copy() here because it modifies stuffs

        return (concerned_characters, external_emails)



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
        username = self._resolve_username(username)
        return self.data["character_properties"][username]["has_new_messages"] # boolean

    @transaction_watcher(ensure_game_started=False)
    def set_new_message_notification(self, concerned_characters, new_status):
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


    def _check_database_coherency(self, **kwargs):
        super(TextMessagingInterception, self)._check_database_coherency(**kwargs)

        game_data = self.data
        messaging = self.messaging_data

        character_names = self.get_character_usernames()
        for (name, data) in self.get_character_sets().items():
            for char_name in data["wiretapping_targets"]:
                assert char_name in character_names


    @transaction_watcher
    def _immediately_dispatch_message(self, msg):

        for username in self.get_character_usernames():
            wiretapping_targets_emails = [self.get_character_email(target)
                                          for target in self.get_wiretapping_targets(username)]
            if (msg["sender_email"] in wiretapping_targets_emails or
               any(True for recipient in msg["recipient_emails"] if recipient in wiretapping_targets_emails)):
                if username not in msg["visible_by"]: # if already sender or recipient, we skip interception
                    msg["visible_by"][username] = VISIBILITY_REASONS.interceptor # that character will see the message

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

        character_names = self.get_character_usernames()
        for name in target_names:
            if name not in character_names:
                raise AbnormalUsageError(_("Unknown target username %(target)s") % SDICT(target=name)) # we can show it

        data = self.get_character_properties(username)
        data["wiretapping_targets"] = PersistentList(target_names)

        self.log_game_event(_noop("Wiretapping targets set to (%(targets)s) for %(username)s."),
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




@register_module
class RadioMessaging(BaseDataManager): # TODO REFINE

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

        TRANSLATABLE_ITEM_NAME = _lazy("radio spots")

        def _load_initial_data(self, **kwargs):

            for identifier, details in self._table.items():
                details.setdefault("immutable", False) # we assume ANY radio spot is optional for the game, and can be edited/delete
                details.setdefault("file", None) # LOCAL file
                if details["file"]:
                    details["file"] = utilities.complete_game_file_path(details["file"], "audio_messages")
                details.setdefault("url", None) # LOCAL file

            audiofiles = [value["file"] for value in self._table.values()]
            utilities.check_no_duplicates(audiofiles) # only checked at load time, next game master can do whatever he wants


        def _preprocess_new_item(self, key, value):
            assert "immutable" not in value
            value["immutable"] = False
            return (key, PersistentDict(value))
            # other params are supposed to exist in "value"

        def _check_item_validity(self, key, value, strict=False):

            print ("RADIOSPOT IS", key, value)

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

    @transaction_watcher
    def set_radio_messages(self, audio_ids):
        """
        Allows duplicate audio messages.
        """
        self._check_audio_ids(audio_ids)
        self.data["global_parameters"]["pending_radio_messages"] = PersistentList(audio_ids)

    @transaction_watcher
    def reset_audio_messages(self):
        # note that the web radio might already have retrieved the whole playlist...
        self.data["global_parameters"]["pending_radio_messages"] = PersistentList()

    @readonly_method
    def get_all_audio_messages(self):
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
            character["last_chatting_time"] = character.get("last_chatting_time", None)

        game_data.setdefault("chatroom_messages", PersistentList())

        game_data["global_parameters"].setdefault("chatroom_presence_timeout_s", 20)
        game_data["global_parameters"].setdefault("chatroom_timestamp_display_threshold_s", 120)
        game_data.setdefault("user_color", PersistentDict())

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
            assert msg["username"] is None or msg["username"] in game_data["character_properties"].keys()

    @transaction_watcher
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

        message = escape(message.strip()) # we escape messages immediateley

        if not message:
            raise UsageError(_("Chat message can't be empty"))

        record = PersistentDict(time=datetime.utcnow(), username=self.user.username, message=message)
        self.data["chatroom_messages"].append(record)


    @readonly_method
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

        if self.user.is_character:
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
                evt["execute_at"] = self.compute_remote_datetime(evt["execute_at"])
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
            time = self.compute_remote_datetime(date_or_delay_mn)

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

    def _load_initial_data(self, **kwargs):
        super(PersonalFiles, self)._load_initial_data(**kwargs)


    def _check_database_coherency(self, **kwargs):
        super(PersonalFiles, self)._check_database_coherency(**kwargs)

        # common and personal file folders
        assert os.path.isdir(os.path.join(config.GAME_FILES_ROOT, "common_files"))
        for name in (self.data["character_properties"].keys() + [self.data["global_parameters"]["master_login"]]):
            assert os.path.isdir(os.path.join(config.GAME_FILES_ROOT, "personal_files", name)), name


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

        self.log_game_event(_noop("Encrypted folder '%(folder)s/%(password)s' accessed by user '%(username)s'."),
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

        common_folder_path = os.path.join(config.GAME_FILES_ROOT, "common_files")
        common_files = [game_file_url("common_files/" + filename) for filename in
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

    def _compute_gems_unit_cost(self, total_cost, num_gems):
        return int(math.ceil(float(total_cost / num_gems)))

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
            properties['unit_cost'] = self._compute_gems_unit_cost(total_cost=properties['total_price'], num_gems=properties['num_items'])
            properties['owner'] = properties.get('owner', None)
            properties["auction"] = properties.get('auction', None)

            if properties["is_gem"] and not properties['owner']: # we dont recount gems appearing in character["gems"]
                total_gems += [properties['unit_cost']] * properties["num_items"]


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
                total_gems.append(gem_value)
            # print ("---------", name, total_gems.count(500))

        assert game_data["game_items"]
        for (name, properties) in game_data["game_items"].items():

            utilities.check_is_slug(name)
            assert isinstance(properties['is_gem'], bool)
            assert utilities.check_is_positive_int(properties['num_items'])
            assert utilities.check_is_positive_int(properties['total_price'])
            assert utilities.check_is_positive_int(properties['unit_cost'])
            assert properties['unit_cost'] == self._compute_gems_unit_cost(total_cost=properties['total_price'], num_gems=properties['num_items'])

            assert properties['owner'] is None or properties['owner'] in game_data["character_properties"].keys()

            assert isinstance(properties['title'], basestring) and properties['title']
            assert isinstance(properties['comments'], basestring) and properties['comments']
            assert isinstance(properties['image'], basestring) and properties['image']

            # item might be out of auction
            assert properties['auction'] is None or isinstance(properties['auction'], basestring) and properties['auction']

            if properties["is_gem"] and not properties["owner"]:
                total_gems += [properties['unit_cost']] * properties["num_items"]
                # (">>>>>>>>>>", name, total_gems.count(500))

        old_total_gems = game_data["global_parameters"]["total_gems"]
        assert Counter(old_total_gems) == Counter(total_gems)
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

        self.log_game_event(_noop("Bank operation: %(amount)s kashes transferred from %(from_name)s to %(to_name)s."),
                             PersistentDict(amount=amount, from_name=from_name, to_name=to_name),
                             url=None)


    def _get_item_separate_gems(self, item_name):
        item = self.get_item_properties(item_name)
        assert item["is_gem"]
        return [(item["unit_cost"], item_name)] * item["num_items"] # tuples!


    def _free_item_from_character(self, item_name, item):
        assert self.get_item_properties(item_name) == item
        assert item["owner"]

        char_name = item["owner"]
        character = self.get_character_properties(char_name)
        if item["is_gem"]:
            # check that all single gems of the pack are still owned
            gems = self._get_item_separate_gems(item_name)
            remaining_gems = utilities.substract_lists(character["gems"], gems)
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
    def transfer_object_to_character(self, item_name, char_name):
        """
        Item might be free or not, and char_name may be a character 
        or None (i.e no more owner for the item).
        """
        ## FIXME - make this a character-method too !!!
        item = self.get_item_properties(item_name)
        from_name = item["owner"] if item["owner"] else _("no one") # must be done IMMEDIATELY
        to_name = char_name if char_name else _("no one") # must be done IMMEDIATELY

        if item["owner"] == char_name:
            raise NormalUsageError(_("Impossible to have same origin and destination for item transfer"))

        if item["owner"]:
            self._free_item_from_character(item_name, item)

        if char_name:
            self._assign_free_item_to_character(item_name=item_name, item=item, char_name=char_name)

        self.log_game_event(_noop("Item %(item_name)s transferred from %(from_name)s to %(char_name)s."),
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

        # todo - logging here ??
        '''


    @readonly_method
    def get_available_items_for_user(self, username=CURRENT_USER):
        username = self._resolve_username(username)
        if self.is_master(username):
            available_items = self.get_all_items()
        else:
            assert self.is_character(username)
            all_sharing_users = [username] # FIXME - which objects should we include?
            # user_domain = self.get_character_properties(username)["domain"]
            # all_domain_users = [name for (name, value) in self.get_character_sets().items() if
            #                    value["domain"] == user_domain]
            available_items = PersistentDict([(name, value) for (name, value)
                                              in self.get_all_items().items()
                                              if value['owner'] in all_sharing_users])
        return available_items



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

        self.log_game_event(_noop("Gems transferred from %(from_name)s to %(to_name)s : %(gems_choices)s."),
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

        if not view_class.ALWAYS_AVAILABLE:
            assert view_class.NAME not in cls.ACTIVABLE_VIEWS_REGISTRY
            cls.ACTIVABLE_VIEWS_REGISTRY[view_class.NAME] = view_class

        if view_class.PERMISSIONS:
            # auto registration of permission requirements brought by that view
            cls.register_permissions(view_class.PERMISSIONS)


    @transaction_watcher(ensure_game_started=False)
    def sync_game_view_data(self):
        """
        If we add/remove views to rpgweb without resetting the DB, a normal desynchronization occurs.
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
        return (view_name in self.data["views"]["activated_views"])


    @readonly_method
    def get_activated_game_views(self):
        return self.data["views"]["activated_views"]


    @transaction_watcher(ensure_game_started=False)
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
    def build_admin_widget_identifier(self, klass, form_name):
        assert isinstance(klass, type)
        assert isinstance(form_name, basestring)
        return "%s.%s" % (klass.NAME, form_name)

    @readonly_method
    def get_admin_widget_identifiers(self):
        """
        Gets a list of qualified names, each one targetting a single
        admin form widget.
        """
        ids = [self.build_admin_widget_identifier(klass, form_name)
               for klass in self.GAME_VIEWS_REGISTRY.values()
               for form_name in klass.ADMIN_FORMS]
        return ids

    @readonly_method
    def resolve_admin_widget_identifier(self, identifier):
        """
        Returns the (game_view_instance, form_name_string) tuple corresponding to that
        admin widget token (and its instantiation pmarams), or None. 
        """
        if identifier.count(".") == 1:
            klass_name, form_name = identifier.split(".")
            if klass_name in self.GAME_VIEWS_REGISTRY:
                klass = self.GAME_VIEWS_REGISTRY[klass_name]
                if form_name in klass.ADMIN_FORMS:
                    return (self.instantiate_game_view(klass), form_name)
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
    @transaction_watcher(ensure_game_started=False)
    def sync_ability_data(self):
        """
        NO - abilities cant be hot plugged!!
        If we add/remove abilities to rpgweb without resetting the DB, a normal desynchronization occurs.
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


    class StaticPagesManager(DataTableManager):

        TRANSLATABLE_ITEM_NAME = _lazy("static pages")

        def _load_initial_data(self, **kwargs):

            for identifier, details in self._table.items():
                details.setdefault("immutable", False) # we assume ANY static page is optional for the game, and can be edited/deleted

                details.setdefault("categories", []) # distinguishes possibles uses of static pages
                details["categories"] = [details["categories"]] if isinstance(details["categories"], basestring) else details["categories"]

                details.setdefault("keywords", []) # useful for encyclopedia articles mainly
                details["keywords"] = [details["keywords"]] if isinstance(details["keywords"], basestring) else details["keywords"]

                details.setdefault("description", "") # for gamemaster only
                details["description"] = details["description"].strip()

        def _preprocess_new_item(self, key, value):
            assert "immutable" not in value
            value["immutable"] = False
            return (key, PersistentDict(value))
            # other params are supposed to exist in "value"

        def _check_item_validity(self, key, value, strict=False):
            utilities.check_is_slug(key)
            assert key.lower() == key # handy

            utilities.check_has_keys(value, ["immutable", "categories", "content", "description", "keywords"], strict=strict)

            utilities.check_is_bool(value["immutable"],)
            utilities.check_is_restructuredtext(value["content"])

            utilities.check_is_list(value["categories"])
            for category in (value["categories"]):
                utilities.check_is_slug(category)

            utilities.check_is_list(value["keywords"])
            for keyword in (value["keywords"]):
                utilities.check_is_slug(keyword)

            if value["description"]: # optional
                utilities.check_is_string(value["description"], multiline=False)

        def _sorting_key(self, item_pair):
            return item_pair[0] # we sort by key, simply...

        def _get_table_container(self, root):
            return root["static_pages"]

        def _item_can_be_edited(self, key, value):
            return not value["immutable"]

    static_pages = LazyInstantiationDescriptor(StaticPagesManager)




@register_module
class HelpPages(BaseDataManager):
    """
    Help pages are static pagest that share their names with GameViews, 
    and they are meant to be displayed as help popups in the 
    template of each view.
    """

    HELP_CATEGORY = "help_pages"

    @readonly_method
    def get_help_page(self, name):
        """
        Returns the rst entry, or None.
        Fetching is case-insensitive.
        """
        key = name.lower().strip()
        if name not in self.static_pages:
            return None
        value = self.static_pages[key]
        if self.HELP_CATEGORY in value["categories"]:
            return value
        else:
            return None
        assert False


    @readonly_method
    def get_help_page_names(self):
        """
        Mainly for tests.
        """
        return [key for (key, value) in self.static_pages.get_all_data().items() if self.HELP_CATEGORY in value["categories"]]






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

        for (key, value) in self._get_encyclopedia_dict().items():
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
        article = self._get_encyclopedia_dict().get(key)
        return article["content"] if article else None


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


    def _get_encyclopedia_dict(self):
        return {key: value for (key, value) in self.static_pages.get_all_data().items() if self.ENCYCLOPEDIA_CATEGORY in value["categories"]}

    @readonly_method
    def get_encyclopedia_article_ids(self):
        return self._get_encyclopedia_dict().keys()


    @readonly_method
    def get_encyclopedia_keywords_mapping(self, excluded_link=None):
        """
        Returns a dict mapping keywords (which can be regular expressions) to lists 
        of targeted article ids.
        """
        mapping = {}
        for article_id, article in self._get_encyclopedia_dict().items():
            if article_id == excluded_link:
                continue # we skip links to the current article of course
            for keyword in article["keywords"]:
                mapping.setdefault(keyword, [])
                mapping[keyword].append(article_id)
        return mapping


    @readonly_method
    def get_character_known_article_ids(self, username=CURRENT_USER):
        username = self._resolve_username(username)
        return self.get_character_properties(username)["known_article_ids"]


    @transaction_watcher(ensure_game_started=False) # automatic action - not harmful
    def update_character_known_article_ids(self, username=CURRENT_USER, article_ids=None):
        username = self._resolve_username(username)
        assert article_ids is not None
        known_article_ids = self.get_character_properties(username)["known_article_ids"]
        for article_id in article_ids:
            if article_id not in known_article_ids:
                known_article_ids.append(article_id)


    @transaction_watcher(ensure_game_started=False) # admin action, actually
    def reset_character_known_article_ids(self, username=CURRENT_USER):
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
                utilities.check_is_game_file("captchas", value["image"])
            if value["explanation"]:
                utilities.check_is_restructuredtext(value["explanation"])

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

        normalized_attempt = attempt.strip().lower()
        normalized_answer = value["answer"].lower() # necessarily slug, but not always lowercase

        if normalized_attempt != normalized_answer:
            raise NormalUsageError(_("Incorrect captcha answer '%s'") % attempt)

        return value["explanation"]






@register_module
class NovaltyTracker(BaseDataManager):
    """
    Tracks the *resources* (references by a unique key) that each authenticated 
    player (and the game master) has, or not, already "accessed".
    
    Useful for new help pages, new radio playlists, new menu entries...
    
    Trocking objects are lazily created, only the first time a resource is accessed.
    """

    def _load_initial_data(self, **kwargs):
        super(NovaltyTracker, self)._load_initial_data(**kwargs)
        game_data = self.data
        game_data.setdefault("novalty_tracker", PersistentDict())


    def _check_database_coherency(self, strict=False, **kwargs):
        super(NovaltyTracker, self)._check_database_coherency(**kwargs)
        game_data = self.data

        allowed_usernames = self.get_character_usernames() + [self.get_global_parameter("master_login")]
        for item_key, usernames in game_data["novalty_tracker"].items():
            utilities.check_is_slug(item_key)
            for username in usernames:
                assert username in allowed_usernames

    @readonly_method
    def get_novelty_registry(self):
        """For tests..."""
        return copy.deepcopy(self.data["novalty_tracker"])

    @transaction_watcher
    def access_novelty(self, username=CURRENT_USER, item_key=None):
        """Returns True iff the user access that resource for the first time."""
        username = self._resolve_username(username)
        assert isinstance(item_key, basestring) and (" " not in item_key) and item_key
        assert username in (self.get_character_usernames() + [self.get_global_parameter("master_login")])
        tracker = self.data["novalty_tracker"]
        if item_key not in tracker:
            tracker[item_key] = PersistentList()
        if username not in tracker[item_key]:
            tracker[item_key].append(username)
            return True
        return False

    @readonly_method
    def has_accessed_novelty(self, username=CURRENT_USER, item_key=None):
        assert isinstance(item_key, basestring) and (" " not in item_key) and item_key
        assert username in (self.get_character_usernames() + [self.get_global_parameter("master_login")])
        username = self._resolve_username(username)
        tracker = self.data["novalty_tracker"]
        if item_key in tracker and username in tracker[item_key]:
            return True
        return False



