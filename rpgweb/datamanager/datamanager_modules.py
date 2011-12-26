# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *

from .datamanager_user import GameUser
from .datamanager_core import *


PLACEHOLDER = object()


MODULES_REGISTRY = []  # IMPORTANT



def register_module(Klass):
    MODULES_REGISTRY.append(Klass)
    return Klass



@register_module
class GameGlobalParameters(BaseDataManager):


    @readonly_method
    def check_database_coherency(self, **kwargs):
        super(GameGlobalParameters, self)._check_database_coherency(**kwargs)
        
        game_data = self.data

        utilities.check_is_bool(game_data["global_parameters"]["game_is_started"])

        assert os.path.isfile(os.path.join(config.GAME_FILES_ROOT, "musics", game_data["global_parameters"]["opening_music"]))
  


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







@register_module
class GameEvents(BaseDataManager): # TODO REFINE


    def _load_initial_data(self, **kwargs):
        super(GameEvents, self)._load_initial_data(**kwargs)

        new_data = self.data
        new_data.setdefault("events_log", PersistentList())
        for evt in new_data["events_log"]:
            if isinstance(evt["time"], (long, int)): # offset in minutes
                evt["time"] = utilities.compute_remote_datetime(evt["time"])
        new_data["events_log"].sort(key=lambda evt: evt["time"])

    def _check_database_coherency(self, **kwargs):
        super(GameEvents, self)._check_database_coherency(**kwargs)

        event_reference = {
            "time": datetime,
            "message": basestring,
            "substitutions": (types.NoneType, PersistentDict),
            "url": (types.NoneType, basestring),
            "username": basestring
        }
        previous_time = None
        for event in self.data["events_log"]:
            assert event["message"]
            if previous_time:
                assert previous_time <= event["time"] # event lists are sorted by chronological order
            previous_time = event["time"]
            utilities.check_dictionary_with_template(event, event_reference)
            username = event["username"]
            assert username in self.get_character_names() or username == self.get_global_parameter("master_login") or username is None

    @transaction_watcher
    def log_game_event(self, message, substitutions=None, url=None, is_master_action=False):
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

            utilities.check_is_string(character["description"])
            utilities.check_is_string(character["official_name"])
            utilities.check_is_string(character["real_life_identity"])
            utilities.check_is_email(character["real_life_email"])

            identities = [char["official_name"].replace(" ", "").lower() for char in
                          game_data["character_properties"].values()]
            utilities.check_no_duplicates(identities)

    @readonly_method
    def get_character_sets(self):
        return self.data["character_properties"]

    @readonly_method
    def get_character_usernames(self):
        return sorted(self.data["character_properties"].keys())

    @readonly_method
    def get_character_official_names(self):
        return sorted([char["official_name"] for char in self.data["character_properties"].values()])

    @readonly_method
    def get_official_name_from_username(self, username):
        properties = self.data["character_properties"][username]
        return properties["official_name"]

    @readonly_method
    def get_username_from_official_name(self, official_name):
        matches = [name for (name, value) in self.data["character_properties"].items() if
                   value["official_name"] == official_name]
        return matches[0] # may raise error

    @readonly_method
    def get_character_properties(self, username):
        # for normal characters only
        try:
            return self.data["character_properties"][username]
        except KeyError:
            raise UsageError(_("Unknown username %s") % username)

    @readonly_method
    def __get_fellow_usernames(self, username):
        # returns team mates only, doesn't work for game master
        domain = self.get_character_properties(username)["domain"]
        fellows = [name for (name, props) in self.get_character_sets().items() if
                   props["domain"] == domain and name != username]
        return fellows

    @readonly_method
    def get_other_usernames(self, username):
        # also works for game master : returns ALL players
        others = [name for name in self.get_character_usernames() if name != username]
        return others

    @readonly_method
    def build_select_choices_from_usernames(self, usernames):
        official_names = sorted([self.get_official_name_from_username(username) for username in usernames])
        character_choices = zip(usernames, official_names)
        return character_choices

    @transaction_watcher
    def update_real_life_data(self, username, real_life_identity=None, real_life_email=None):
        
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
            assert os.path.isfile(os.path.join(config.GAME_FILES_ROOT, "musics", content["prologue_music"]))

            utilities.check_is_bool(content["show_official_identities"])


    @readonly_method
    def get_domain_names(self):
        return sorted(self.data["domains"].keys())

    @readonly_method
    def get_domain_properties(self, domain_name):
        return self.data["domains"][domain_name]

    @transaction_watcher(ensure_game_started=False)
    def update_allegiances(self, username, allegiances):
        
        assert len(set(allegiances)) == len(allegiances)
        
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


    def __init__(self, **kwargs):
        super(PlayerAuthentication, self).__init__(**kwargs)
        self.user = None
        self._set_user(username=None) # TODO - improve by doing player authentication at init time !

    def _load_initial_data(self, **kwargs):
        super(PlayerAuthentication, self)._load_initial_data(**kwargs)


    def _check_database_coherency(self, **kwargs):
        super(PlayerAuthentication, self)._check_database_coherency(**kwargs)

        utilities.check_is_slug(self.get_global_parameter("master_login"))
        utilities.check_is_slug(self.get_global_parameter("master_password"))

        for character in self.get_character_sets().values():
            utilities.check_is_slug(character["password"])
            utilities.check_is_string(character["secret_question"])
            assert not character["secret_answer"] or utilities.check_is_slug(character["secret_answer"])
            
        
        # MASTER and ANONYMOUS cases

        global_parameters = game_data["global_parameters"]

        utilities.check_is_slug(global_parameters["anonymous_login"])
        utilities.check_is_slug(global_parameters["master_login"])
        utilities.check_is_slug(global_parameters["master_password"])
        utilities.check_is_slug(global_parameters["master_email"])
        utilities.check_is_slug(global_parameters["master_real_life_email"])





    def _notify_user_change(self, username, **kwargs):
        assert not hasattr(super(PlayerAuthentication, self), "_notify_user_change") # we're well top-level here
        
        
    @transaction_watcher(ensure_game_started=False)
    def _set_user(self, username):

        self.user = GameUser(datamanager=self, username=username, previous_user=self.user)

        self._notify_user_change(username=username)

        return self.user
 

    @transaction_watcher(ensure_game_started=False)
    def logout_user(self):
        self._set_user(username=None)


    @transaction_watcher(ensure_game_started=False)
    def authenticate_with_ticket(self, session_ticket):
        """Raises Exception if problem."""
        (game_instance_id, username) = session_ticket
        self._set_user(username)
        #if not player.is_master:
        #    self.set_online_status(username)
        return None


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
            data = self.get_character_properties(username)
            wanted_pwd = data["password"]

        if password == wanted_pwd:
            self._set_user(username)

            session_ticket = (self.game_instance_id, username)

            return session_ticket

        else:
            raise UsageError(_("Wrong password"))

        assert False


    @readonly_method
    def get_secret_question(self, username):
        return self.get_character_properties(username)["secret_question"]


    @transaction_watcher # requires game started mode
    def process_secret_answer_attempt(self, username, secret_answer_attempt, target_email):
        user_properties = self.get_character_properties(username)

        secret_answer_attempt = secret_answer_attempt.lower().strip()
        expected_answer = user_properties["secret_answer"].lower().strip()

        # WARNING - if no answer is actually expected, attempts must ALWAYS fail
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

            msg_id = self.post_message(sender_email, target_email, subject, body, attachment=attachment,
                                       date_or_delay_mn=self.get_global_parameter("password_recovery_delays"))

            self.log_game_event(_noop("Password of %(username)s has been recovered by %(target_email)s."),
                                 PersistentDict(username=username, target_email=target_email),
                                 url=self.get_message_viewer_url(msg_id))

            return password

        else:
            raise UsageError(_("Wrong answer supplied."))



    # Utility functions for tests on other usernames than current player's one #

    def is_anonymous(self, username=PLACEHOLDER):
        if username is PLACEHOLDER:
            username = self.user.username
        return (username == None)

    def is_master(self, username=PLACEHOLDER):
        if username is PLACEHOLDER:
            username = self.user.username
        return (username == self.get_global_parameter("master_login"))

    def is_character(self, username=PLACEHOLDER):
        if username is PLACEHOLDER:
            username = self.user.username
        return (username in self.get_character_usernames())




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
        cls.PERMISSIONS_REGISTRY.update(names)


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

        for (name, character) in game_data["character_properties"].items():
            for permission in character["permissions"]:
                assert permission in self.PERMISSIONS_REGISTRY

        for (name, domain) in game_data["domains"].items():
            for permission in domain["permissions"]:
                assert permission in self.PERMISSIONS_REGISTRY


    @transaction_watcher(ensure_game_started=False)
    def update_permissions(self, username, permissions):
        
        assert self.is_character(username)
        
        data = self.get_character_properties(username)
        data["permissions"] = permissions


    def has_permission(self, permission):

        if not self.user.is_character:
            return False # anonymous and master must be handled differently

        props = self.user.character_properties()

        if permission in props["permissions"]:
            return True

        for domain_name in props["domains"]:
            domain = self.get_domain_properties(domain_name)
            if permission in domain["permissions"]:
                return True

        return False
    

    def build_permission_select_choices(self):
        return [(perm, perm) for perm in sorted(self.PERMISSIONS_REGISTRY)]



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
            assert isinstance(content["prologue_music"], basestring)
            assert os.path.isfile(os.path.join(config.GAME_FILES_ROOT, "musics", content["prologue_music"]))
            assert isinstance(content["instructions"], (types.NoneType, basestring)) # can be empty


    @readonly_method
    def get_game_instructions(self, username):
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
            prologue_music = config.GAME_FILES_URL + "musics/" + domain["prologue_music"]
        '''

        return PersistentDict(prologue_music=prologue_music,
                              global_introduction=global_introduction,
                              team_introduction=team_introduction)








@register_module
class LocationsHandling(BaseDataManager):

    def _load_initial_data(self, **kwargs):
        super(LocationsHandling, self)._load_initial_data(**kwargs)

        new_data = self.data
        for (name, properties) in new_data["locations"].items():
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
                assert os.path.isfile(os.path.join(config.GAME_FILES_ROOT, "spy_reports", "spy_" + name.lower() + ".mp3")), name


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

        utilities.check_positive_int(self.get_global_parameter("online_presence_timeout_s"))


    def _notify_user_change(self, username, **kwargs):
        super(OnlinePresence, self)._notify_user_change(username=username, **kwargs)

        if username in self.data["character_properties"]: # TODO improve
            self.set_online_status(username)

    @transaction_watcher(ensure_game_started=False)
    def set_online_status(self, username):
        self.data["character_properties"][username]["last_online_time"] = datetime.utcnow()

    @readonly_method
    def get_online_status(self, username):
        timestamp = self.data["character_properties"][username]["last_online_time"]
        return timestamp and timestamp >= (datetime.utcnow() - timedelta(seconds=self.get_global_parameter("online_presence_timeout_s")))

    @readonly_method
    def get_online_users(self):
        return [username for username in self.get_character_usernames() if self.get_online_status(username)]









@register_module
class TextMessaging(BaseDataManager): # TODO REFINE

    def _recompute_all_external_contacts_via_msgs(self):
        external_contacts_changed = False
        for msg in self.data["messages_sent"]:
            res = self._update_external_contacts(msg)
            if res: 
                external_contacts_changed = True
        return external_contacts_changed
    
    def _load_initial_data(self, **kwargs):
        super(TextMessaging, self)._load_initial_data(**kwargs)

        new_data = self.data

        pangea_network = new_data["global_parameters"]["pangea_network_domain"]

        for (name, character) in new_data["character_properties"].items():
            character.setdefault("has_new_messages", False)

        new_data.setdefault("messages_sent", PersistentList())
        new_data.setdefault("messages_queued", PersistentList())
        
        for (name, data) in new_data["character_properties"].items():
            data.setdefault("wiretapping_targets", PersistentList())

        for (index, msg) in enumerate(new_data["messages_sent"] + new_data["messages_queued"]):
            # we modify the dicts in place

            msg["recipient_emails"] = self._normalize_recipient_emails(msg["recipient_emails"])

            if "@" not in msg["sender_email"]:
                msg["sender_email"] = (msg["sender_email"] + "@" + pangea_network)
                                       # we allow short username as sender/recipient

            msg["attachment"] = msg.get("attachment", None)
            msg["is_certified"] = msg.get("is_certified", False)

            if isinstance(msg["sent_at"], (long, int)): # offset in minutes
                msg["sent_at"] = utilities.compute_remote_datetime(msg["sent_at"])

            msg["intercepted_by"] = msg.get("intercepted_by", PersistentList())
            msg["has_read"] = msg.get("has_read", PersistentList())
            msg["has_replied"] = msg.get("has_replied", PersistentList())

            if not msg["id"]:
                msg["id"] = self._get_new_msg_id(index, msg["subject"] + msg["body"])

        new_data["messages_sent"].sort(key=lambda msg: msg["sent_at"])
        new_data["messages_queued"].sort(key=lambda msg: msg["sent_at"])


        def complete_messages_templates(msg_list, is_manual):
            for msg in msg_list.values():
                if is_manual:
                    msg["recipient_emails"] = self._normalize_recipient_emails(msg.get("recipient_emails", []))
                    msg["sender_email"] = msg.get("sender_email", "")
                    if msg["sender_email"] and "@" not in msg["sender_email"]: # email could be empty
                        msg["sender_email"] = msg["sender_email"] + "@" + pangea_network # we allow short username as sender/recipient

                msg["subject"] = msg.get("subject", "")
                msg["body"] = msg.get("body", "")
                msg["attachment"] = msg.get("attachment", None)
                msg["is_used"] = msg.get("is_used", False)

        #complete_messages_templates(new_data["automated_messages_templates"], is_manual=False)
        complete_messages_templates(new_data["manual_messages_templates"], is_manual=True)

        # we compute automatic external_contacts for the first time
        self._recompute_all_external_contacts_via_msgs()


    def _check_database_coherency(self, **kwargs):
        super(TextMessaging, self)._check_database_coherency(**kwargs)

        game_data = self.data

        utilities.check_is_slug(game_data["global_parameters"]["global_email"]) # shortcut tag to send email to everyone
         
        character_names = self.get_character_usernames()
        for (name, data) in self.get_character_sets().items():
            for char_name in data["wiretapping_targets"]:
                assert char_name in character_names
                
        message_reference = {# the ids of emails are simply their location in the global message list !
                             "sender_email": basestring,
                             "recipient_emails": PersistentList,
                             "subject": basestring,
                             "body": basestring,
                             "attachment": (types.NoneType, basestring), # None or string
                             "sent_at": datetime,
                             "intercepted_by": PersistentList,
                             "has_read": PersistentList,
                             "has_replied": PersistentList,
                             "is_certified": bool, # for messages sent via automated processes
                             "id": basestring
                             }

        def check_message_list(msg_list):
            previous_sent_at = None
            for msg in msg_list:

                assert msg["subject"] # body can be empty, after all...
                if previous_sent_at:
                    assert previous_sent_at <= msg["sent_at"] # message lists are sorted by chronological order
                previous_sent_at = msg["sent_at"]
                utilities.check_dictionary_with_template(msg, message_reference)

                utilities.check_is_email(msg["sender_email"])
                for recipient in msg["recipient_emails"]:
                    utilities.check_is_email(recipient)

                all_chars = game_data["character_properties"].keys()
                for username in msg["intercepted_by"]:
                    assert username in all_chars
                utilities.check_no_duplciates(msg["intercepted_by"])
                    
                all_users = all_chars + [game_data["global_parameters"]["master_login"]]
                assert all((char in all_users) for char in msg["has_read"]), msg["has_read"]
                assert all((char in all_users) for char in msg["has_replied"]), msg["has_replied"]
                
            all_ids = [msg["id"] for msg in msg_list]
            utilities.check_no_duplicates(all_ids)

        # WARNING - we must separate the two lists, because little incoherencies can appear at their junction due to the workflow
        # (the first queued messages might actually be younger than the last ones of the sent messages list)
        check_message_list(game_data["messages_sent"])
        check_message_list(game_data["messages_queued"])

        #TODO CHECK THAT !!
        all_msg_files = [self.data["audio_messages"][properties["new_messages_notification"]]["file"] for properties in
                         self.data["character_properties"].values()]
        #all_msg_files += [self.data["audio_messages"][properties["request_for_report"]]["file"] for properties in self.data["domains"].values()]
        assert len(set(all_msg_files)) == len(self.data["character_properties"]) # + len(self.data["domains"])# users must NOT share new-message audio notifications

        # we recompute external_contacts, and check everything is coherent
        assert not self._recompute_all_external_contacts_via_msgs()

        for character_set in self.data["character_properties"].values():
            utilities.check_no_duplicates(character_set["external_contacts"])
            for external_contact in character_set["external_contacts"]:
                utilities.check_is_email(external_contact)
                
                
    def _process_periodic_tasks(self, report):
        super(TextMessaging, self)._process_periodic_tasks(report)

        # WE SEND DELAYED MESSAGES #

        last_index_processed = None
        utcnow = datetime.utcnow()

        for (index, msg) in enumerate(self.data["messages_queued"]):
            if msg["sent_at"] <= utcnow:
                try:
                    self._immediately_send_message(msg)
                except:
                    if __debug__: self.notify_event("DELAYED_MESSAGE_ERROR")
                    logging.critical("Delayed message couldn't be sent : %s" % msg, exc_info=True)
                last_index_processed = index # even if error, we remove the msg from list
            else:
                break # since messages are queued in CHRONOLOGICAL order...

        if last_index_processed is not None:
            self.data["messages_queued"] = self.data["messages_queued"][last_index_processed + 1:]
            report["messages_sent"] = last_index_processed + 1
        else:
            report["messages_sent"] = 0



    def _normalize_recipient_emails(self, recipient_emails):
        # accepts any form of argument as "recipients_lists", and converts short names to full emails

        data = self.data

        pangea_domain = data["global_parameters"]["pangea_network_domain"]

        if isinstance(recipient_emails, basestring):
            recipient_emails = recipient_emails.replace(",", ";")
            recipient_emails = recipient_emails.split(";")

        recipient_emails = [stripped for stripped in (email.strip() for email in recipient_emails) if stripped]

        normalized_emails = set() # unicity !
        for (index, chunk) in enumerate(recipient_emails):
            if "@" in chunk:
                values = [chunk]
            elif chunk == data["global_parameters"]["global_email"]:
                values = [chunk]
            elif chunk == data["global_parameters"]["master_login"]:
                values = [data["global_parameters"]["master_email"]]
            elif chunk in data["character_properties"].keys():
                values = [chunk + "@" + pangea_domain] # we allow short usernames
            else:
                print(data["character_properties"].keys())
                raise UsageError(_("Unknown user login '%s' in recipients list") % chunk) # surely an input error of user!
            normalized_emails.update(values)

        recipient_emails = PersistentList(normalized_emails) # important !
        return recipient_emails

    @staticmethod
    def _sort_and_join_contact_parts(contact_parts):
        contact_parts = list(set(contact_parts)) # we remove duplicates...
        contact_parts.sort(key=lambda parts: parts[1] + parts[0])
        contacts = ["@".join(parts) for parts in contact_parts]
        return contacts

    @transaction_watcher
    def post_message(self, sender_email, recipient_emails, subject, body, attachment=None,
                     date_or_delay_mn=None, is_read=False, is_certified=False,
                     reply_to=None, use_template=None):
        sender_email = sender_email.strip()
        recipient_emails = self._normalize_recipient_emails(recipient_emails)
        subject = subject.strip()
        body = body.strip()
        if attachment:
            attachment = attachment.strip()

        if not all([sender_email, recipient_emails, subject, body]):
            raise UsageError(_("Sender, recipient, subject and body of the message mustn't be empty"))

        # sender and recipient can be the same !
        # we don't check sender email or recipient email more than that

        """
        all_emails = self.get_user_contacts(self.get_global_parameter("master_login"))
        assert (recipient_emails in all_emails), \
                "Invalid emails provided : %s and %s VS %s" % (sender_email, recipient_emails, all_emails)

        no_reply= False
        if sender_email not in all_emails:
            no_reply = True # we consider it's a no-reply robot which has sent the mail
        """

        if reply_to:
            try:
                msg = self.get_sent_message_by_id(reply_to)
                self._set_message_reply_state(self.get_username_from_email(sender_email), msg, True)
                self._set_message_read_state(self.get_username_from_email(sender_email), msg, True)
            except UsageError, e:
                logging.error(e, exc_info=True)

        if use_template:
            try:
                msg = self.get_message_template(use_template)
                msg["is_used"] = True
            except UsageError, e:
                logging.error(e, exc_info=True)

        new_id = self._get_new_msg_id(len(self.data["messages_sent"]) + len(self.data["messages_queued"]),
                                      subject + body) # unicity more than guaranteed

        # NO - let them relative if needed...
        #if attachment and attachment.startswith("/"):
        #    attachment = config.SITE_DOMAIN + attachment

        if isinstance(date_or_delay_mn, datetime):
            sent_at = date_or_delay_mn
        else:
            sent_at = utilities.compute_remote_datetime(date_or_delay_mn) # date_or_delay_mn is None or number

        msg = PersistentDict({# the ids of emails are simply their location in the global message list !
                              "sender_email": sender_email,
                              "recipient_emails": recipient_emails,
                              "subject": subject,
                              "body": body,
                              "attachment": attachment, # None or string
                              "sent_at": sent_at,
                              "intercepted_by": PersistentList(), # by default...
                              "has_read": PersistentList(), # for dummy automated messages
                              "has_replied": PersistentList(),
                              "is_certified": is_certified,
                              "id": new_id,
                              })
        if is_read: # workaround : we add ALL players to the "has read" list !
            msg["has_read"] = PersistentList(
                self.get_character_usernames() + [self.get_global_parameter("master_login")])

        if sent_at > datetime.utcnow():
            self.data["messages_queued"].append(msg)
            self.data["messages_queued"].sort(key=lambda msg: msg["sent_at"]) # python sorting is stable !
        else:
            self._immediately_send_message(msg)

        return new_id

    @staticmethod
    def _get_new_msg_id(index, content):
        md5 = hashlib.md5()
        md5.update(content.encode('ascii', 'ignore'))
        my_hash = md5.hexdigest()[0:4]
        return unicode(index) + "_" + my_hash

    @readonly_method
    def get_character_email(self, username):
        assert self.is_character(username)
        return username + "@" + self.get_global_parameter("pangea_network_domain")

    @readonly_method
    def get_character_or_none_from_email(self, email):
        """
        Returns the character username corresponding to that email, or None.
        """
        username = email.split("@")[0]
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
            return self.get_global_parameter("master_login")

    @readonly_method
    def get_players_emails(self):
        pangea_network_domain = self.get_global_parameter("pangea_network_domain")
        return [username + "@" + pangea_network_domain for username in self.get_character_usernames()]

    @readonly_method
    def get_external_emails(self, username):
        # should NOT be called for anonymous users
        if self.is_master(username):
            char_sets = self.get_character_sets()
            all_contacts = [contact for (name, character) in char_sets.items()
                                         for contact in character["external_contacts"]]
            return sorted(set(all_contacts))
        else:
            character = self.get_character_properties(username)
            return character["external_contacts"]


    @readonly_method
    def get_user_contacts(self, username):
        # should NOT be called for anonymous users
        return self.get_players_emails() + self.get_external_emails(username)

    @readonly_method
    def get_message_viewer_url(self, msg_id):
        return reverse('rpgweb.views.view_single_message',
                       kwargs=dict(msg_id=msg_id, game_instance_id=self.game_instance_id))

    @readonly_method
    def get_all_queued_messages(self):
        return self.data["messages_queued"]

    @readonly_method
    def get_all_sent_messages(self):
        return self.data["messages_sent"]

    @readonly_method
    def get_sent_messages(self, sender_email):
        records = [record for record in self.data["messages_sent"] if record["sender_email"] == sender_email]
        return records # chronological order

    @readonly_method
    def get_messages_templates(self):
        return self.data["manual_messages_templates"]

    @readonly_method
    def get_message_template(self, tpl_id):
        return self.data["manual_messages_templates"][tpl_id]



    @readonly_method
    def get_game_master_messages(self):
        # returns all emails sent to external contacts or robots
        all_messages = self.get_all_sent_messages()

        normal_emails = self.get_players_emails()
        messages = []
        for message in all_messages:
            for recipient in message["recipient_emails"]:
                if recipient not in normal_emails:
                    messages.append(message)
                    break

        return messages


    @transaction_watcher(ensure_game_started=False)
    def get_received_messages(self, recipient_email, reset_notification=True):
        records = [record for record in self.data["messages_sent"] if recipient_email in record["recipient_emails"]]

        if reset_notification:
            self.set_new_message_notification(PersistentList([recipient_email]), False)

        return records # chronological order

    @readonly_method
    def get_intercepted_messages(self, username=None): # for wiretapping
        if username is not None and not self.is_master(username):
            assert username in self.get_character_usernames()
            records = [record for record in self.data["messages_sent"] if username in record["intercepted_by"]]
        else:
            records = [record for record in self.data["messages_sent"] if record["intercepted_by"]] # intercepted by anyone
        return records # chronological order

    @readonly_method
    def get_sent_message_by_id(self, msg_id):
        msgs = [message for message in self.data["messages_sent"] if message["id"] == msg_id]
        assert len(msgs) <= 1, "len(msgs) must be < 1"
        if not msgs:
            raise UsageError(_("Unknown message id"))
        return msgs[0]

    @readonly_method
    def get_unread_messages_count(self, username):
        # user_email == None -> unread messages of external contacts (i.e game master)
        if self.is_master(username):
            unread_msgs = [message for message in self.get_game_master_messages()
                           if username not in message["has_read"]]
        else:
            user_email = self.get_character_email(username)
            unread_msgs = [message for message in self.get_received_messages(user_email, reset_notification=False)
                           if username not in message["has_read"]]

        return len(unread_msgs)

    @transaction_watcher(ensure_game_started=False)
    def force_message_sending(self, msg_id):
        # immediately sends a queued message

        items = [item for item in enumerate(self.get_all_queued_messages()) if item[1]["id"] == msg_id]
        assert len(items) <= 1

        if not items:
            return False

        (index, msg) = items[0]

        del self.data["messages_queued"][index] # we remove the msg from queued list

        msg["sent_at"] = datetime.utcnow() # we force the timestamp to NOW
        self._immediately_send_message(msg)

        return True


    @transaction_watcher(ensure_game_started=False)
    def _set_message_read_state(self, username, msg, is_read):
        assert username
        if is_read and username not in msg["has_read"]:
            msg["has_read"].append(username)
        elif not is_read and username in msg["has_read"]:
            msg["has_read"].remove(username) # we don't care whether he had the right to view it or not - it doesn't matter

    @transaction_watcher
    def _set_message_reply_state(self, username, msg, is_read):
        assert username
        if is_read and username not in msg["has_replied"]:
            msg["has_replied"].append(username)
        elif not is_read and username in msg["has_replied"]:
            msg["has_replied"].remove(
                username) # we don't care whether he had the right to view it or not - it doens't matter

    @transaction_watcher(ensure_game_started=False)
    def set_message_read_state(self, username, msg_id, is_read):
        # username can be master login here !
        msg = self.get_sent_message_by_id(msg_id)
        self._set_message_read_state(username, msg, is_read)

    @readonly_method
    def get_pending_new_message_notifications(self):
        # returns users that must be notified, with corresponding message audio_id

        notifications = PersistentDict((username, properties["new_messages_notification"])
        for (username, properties) in self.get_character_sets().items()
        if properties["has_new_messages"])
        return notifications

    @readonly_method
    def get_all_new_message_notification_sounds(self):
        return [char["new_messages_notification"] for char in self.get_character_sets().values()]

    @readonly_method
    def has_new_message_notification(self, username):
        return self.data["character_properties"][username]["has_new_messages"] # boolean

    @transaction_watcher(ensure_game_started=False)
    def set_new_message_notification(self, recipient_emails, new_status):
        assert isinstance(recipient_emails, PersistentList), (recipient_emails, type(recipient_emails))
        for username in self.get_character_usernames():
            email = self.get_character_email(username)
            if email in recipient_emails:
                self.data["character_properties"][username]["has_new_messages"] = new_status
                # thus, "invented" emails are simply ignored in this process


    @transaction_watcher
    def set_wiretapping_targets(self, username, target_names):

        target_names = sorted(list(set(target_names))) # renormalization, just in case

        character_names = self.get_character_usernames()
        for name in target_names:
            if name not in character_names:
                raise AbnormalUsageError(_("Unknown target username %(target)s") % SDICT(target=name)) # we can show it

        data = self.get_character_properties(username)
        data["wiretapping_targets"] = PersistentList(target_names)

        self.log_game_event(_noop("Wiretapping targets set to (%(targets)s) for %(username)s."),
                             PersistentDict(targets="[%s]"%(", ".join(target_names)), username=username),
                             url=None)
    
    def get_wiretapping_targets(self, username):
        return self.get_character_properties(username)["wiretapping_targets"]


    @readonly_method
    def _get_external_contacts_updates(self, msg):
        """
        Retrieve info needed to update the *external_contacts* fields of character accounts,
        when they send/receive this single message.
        """
        all_characters_emails = set(self.get_players_emails())
        msg_emails = set(msg["recipient_emails"] + [msg["sender_email"]])

        external_emails = msg_emails - all_characters_emails

        msg_characters_emails = all_characters_emails & msg_emails
        concerned_characters = [self.get_character_or_none_from_email(email) for email in msg_characters_emails]
        assert all(concerned_characters) # no None value here

        return (concerned_characters, external_emails)

    @transaction_watcher
    def _update_external_contacts(self, msg):

        (concerned_characters, external_emails) = self._get_external_contacts_updates(msg)

        for username in concerned_characters:
            props = self.get_character_properties(username)
            old_external_contacts = set(props["external_contacts"])
            new_external_contacts = old_external_contacts | external_emails
            assert set(props["external_contacts"]) <= new_external_contacts # that list can only grow - of course
            props["external_contacts"] = PersistentList(new_external_contacts) # no particular sorting here, but unicity is ensured
            
            new_contacts_added = (new_external_contacts != old_external_contacts)
            return new_contacts_added

    @transaction_watcher
    def _immediately_send_message(self, msg):

        # wiretapping
        for username in self.get_character_usernames():
                
            wiretapping_targets_emails = [self.get_character_email(target) 
                                          for target in self.get_wiretapping_targets(username)]
            
            if (msg["sender_email"] in wiretapping_targets_emails or
                any(True for recipient in msg["recipient_emails"] if recipient in wiretapping_targets_emails)):
                msg["intercepted_by"].append(username)

        # audio_notification = self.get_global_parameter("message_intercepted_audio_id")
        # NO NOTIFICATION - self.add_radio_message(audio_notification)

        self._update_external_contacts(msg)
        self.set_new_message_notification(msg["recipient_emails"], new_status=True)

        self.data["messages_sent"].append(msg)
        self.data["messages_sent"].sort(key=lambda msg: msg["sent_at"]) # python sorting is stable !


    @transaction_watcher
    def _try_filling_message_template(self, template, values, part_name, tpl_name):
        try:
            return template % values
        except:
            pass

        if __debug__: self.notify_event("MSG_TEMPLATE_FORMATTING_ERROR_1")
        logging.error("Impossible to format %s of automated message %s, retrying with defaultdict", part_name, tpl_name,
                      exc_info=True)

        try:
            new_values = collections.defaultdict(lambda: "<unknown>", values)
            return template % new_values
        except:
            if __debug__: self.notify_event("MSG_TEMPLATE_FORMATTING_ERROR_2")
            logging.critical("Definitely impossible to format %s of automated message %s, returning original value",
                             part_name, tpl_name, exc_info=True)
            return template








@register_module
class RadioMessaging(BaseDataManager): # TODO REFINE

    def _load_initial_data(self, **kwargs):
        super(RadioMessaging, self)._load_initial_data(**kwargs)

        new_data = self.data
        for (audio_id, audio_properties) in new_data["audio_messages"].items():
            audio_properties["url"] = config.GAME_FILES_URL + "audio_messages/" + audio_properties["file"]


    def _check_database_coherency(self, **kwargs):
        super(RadioMessaging, self)._check_database_coherency(**kwargs)

        game_data = self.data

        value = game_data["global_parameters"]["pending_radio_messages"]
        utilities.check_is_list(value) # must be ordered, we can't use a set !
        for audio_id in value:
            assert audio_id in game_data["audio_messages"].keys()

        utilities.check_is_slug(game_data["global_parameters"]["pangea_radio_frequency"])
        utilities.check_is_bool(game_data["global_parameters"]["radio_is_on"])


        assert game_data["audio_messages"]
        assert game_data["audio_messages"]["intro_audio_messages"]
        for (name, properties) in game_data["audio_messages"].items():
            utilities.check_is_slug(name)
            assert properties["text"] and isinstance(properties["text"], basestring)
            assert properties["file"] and isinstance(properties["file"], basestring)
            assert properties["url"] and isinstance(properties["url"], basestring)

            assert os.path.isfile(os.path.join(config.GAME_FILES_ROOT,
                                  "audio_messages", properties["file"])), properties["file"]

        utilities.check_no_duplicates(game_data["audio_messages"])

        audiofiles = [value["file"] for value in game_data["audio_messages"].values()]
        utilities.check_no_duplicates(audiofiles)



    @transaction_watcher
    def add_radio_message(self, audio_id):
        if audio_id not in self.data["audio_messages"].keys():
            raise UsageError(_("Unknown radio message identifier - %(audio_id)s") % SDICT(audio_id=audio_id))

        queue = self.data["global_parameters"]["pending_radio_messages"]
        if audio_id not in queue:
            queue.append(audio_id)


    @transaction_watcher
    def reset_audio_messages(self):
        # note that the web radio might already have retrieved the whole playlist...
        self.data["global_parameters"]["pending_radio_messages"] = PersistentList()

    @readonly_method
    def get_all_audio_messages(self):
        return self.data["audio_messages"]

    @readonly_method
    def check_radio_frequency(self, frequency):
        if frequency != self.get_global_parameter("pangea_radio_frequency"):
            raise UsageError(_("Unknown radio frequency"))

    @readonly_method
    def get_all_next_audio_messages(self):
        queue = self.data["global_parameters"]["pending_radio_messages"]
        return queue

    @readonly_method
    def get_next_audio_message(self):
        queue = self.data["global_parameters"]["pending_radio_messages"]
        if queue:
            return queue[0] # we let the audio message in the queue anyway !
        else:
            return None

    @readonly_method
    def get_audio_message_properties(self, audio_id):
        audio_properties = self.data["audio_messages"][audio_id]
        return audio_properties


    @transaction_watcher
    def notify_audio_message_termination(self, audio_id):
        queue = self.data["global_parameters"]["pending_radio_messages"]

        res = False

        if audio_id in queue: # in case several radio run simultaneously or if a reset occurred inbetween...
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

        new_data = self.data

        for (name, character) in new_data["character_properties"].items():
            character["last_chatting_time"] = character.get("last_chatting_time", None)

        new_data.setdefault("chatroom_messages", PersistentList())

        new_data["global_parameters"].setdefault("chatroom_presence_timeout_s", 20)
        new_data["global_parameters"].setdefault("chatroom_timestamp_display_threshold_s", 120)



    def _check_database_coherency(self, **kwargs):
        super(Chatroom, self)._check_database_coherency(**kwargs)

        game_data = self.data

        utilities.check_positive_int(self.get_global_parameter("chatroom_presence_timeout_s"))
        utilities.check_positive_int(self.get_global_parameter("chatroom_timestamp_display_threshold_s"))

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
    def _set_chatting_status(self, username):
        self.data["character_properties"][username]["last_chatting_time"] = datetime.utcnow()

    @readonly_method
    def get_chatting_status(self, username):
        timestamp = self.data["character_properties"][username]["last_chatting_time"]
        return timestamp and timestamp >= (datetime.utcnow() - timedelta(
            seconds=self.get_global_parameter("chatroom_presence_timeout_s")))

    @readonly_method
    def get_chatting_users(self):
        return [username for username in self.get_character_usernames() if self.get_chatting_status(username)]

    @transaction_watcher
    def send_chatroom_message(self, message):
        """
        Master can chat too, as "system" talker.
        """

        if not self.user.is_authenticated:
            raise AbnormalUsageError(_("Only authenticated users may chat"))

        if self.user.is_character:
            self._set_chatting_status(self.user.username)

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

        return (new_slice_index, previous_msg_timestamp, new_messages)





@register_module
class ActionScheduling(BaseDataManager):

    def _load_initial_data(self, **kwargs):
        super(ActionScheduling, self)._load_initial_data(**kwargs)

        new_data = self.data

        new_data.setdefault("scheduled_actions", PersistentList())

        for evt in new_data["scheduled_actions"]:
            if isinstance(msg["execute_at"], (long, int)): # offset in minutes
                msg["execute_at"] = utilities.compute_remote_datetime(msg["execute_at"])
        new_data["scheduled_actions"].sort(key=lambda evt: evt["execute_at"])



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
                    #print "executed ", function
                except:
                    if __debug__: self.notify_event("DELAYED_ACTION_ERROR")
                    logging.critical("Delayed action raised an error when executing : %s" % action, exc_info=True)
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

        #print >>sys.stderr, "REGISTERING ONE SHOT  ", function

        if isinstance(function, basestring):
            #print ("SEARCHING", function, "IN", sorted(dir(self)))
            if not hasattr(self, function) or not hasattr(getattr(self, function), '__call__'):
                raise TypeError(_("Only strings representing DataManager methods can be scheduled as delayed actions, not %(function)s") % SDICT(
                                    function=function))
        elif not hasattr(function, '__call__'):
            raise TypeError(_("You can only register a callable object as a delayed action, not a %(function)r") % SDICT(
                              function=function))

        if isinstance(date_or_delay_mn, datetime):
            time = date_or_delay_mn
        else:
            time = utilities.compute_remote_datetime(date_or_delay_mn)

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
    def get_encrypted_files(self, username, folder, password, absolute_urls=False):
        """
        Might raise environment errors if older/password incorrect.
        Username is used just for event logging.
        """

        if not self.encrypted_folder_exists(folder):
            raise UsageError(_("This encrypted archive doesn't exist."))

        decrypted_folder = os.path.join(config.GAME_FILES_ROOT, "encrypted", folder,
                                        password.strip().lower()) # warning, password directory must always be lowercase !!
        if not os.path.isdir(decrypted_folder):
            raise UsageError(_("Wrong password for this encrypted folder."))

        # there , we shouldn't have environment errors, theoretically
        decrypted_files = sorted(
            [config.GAME_FILES_URL + "encrypted/" + folder + "/" + password + "/" + item for item in
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
    def get_personal_files(self, username=None, absolute_urls=False):
        """
        'username == None' -> game master !

        Might raise environment errors.
        """

        if username is None:
            username = self.get_global_parameter("master_login") # reserved folder with game administration files

            """ # ACTUALLY NO ! Game master has its own files !!
            # DEPRECATED !!!!!!!!!!!!
            # we list all the files of users
            root_folder = os.path.join(config.GAME_FILES_ROOT, personal_files)
            #print "ROOT FOLDER: ", root_folder
            personal_folders = sorted([dir for dir in os.listdir(root_folder)
                                          if os.path.isdir(os.path.join(root_folder, dir))])
            #print "personal_folders: ", personal_folders
            personal_files = [("/filespersonal_files/"+folder+"/"+filename) for folder in personal_folders
                                                            for filename in sorted(os.listdir(os.path.join(root_folder, folder)))  # None is a separator here
                                                            if filename and os.path.isfile(os.path.join(root_folder, folder, filename))]
            """

        common_folder_path = os.path.join(config.GAME_FILES_ROOT, "common_files")
        common_files = [(config.GAME_FILES_URL + "common_files/" + filename) for filename in
                        os.listdir(common_folder_path)
                        if os.path.isfile(os.path.join(common_folder_path, filename))
                           and not filename.startswith(".") and not filename.startswith("~")] # hidden files removed

        personal_folder_path = os.path.join(config.GAME_FILES_ROOT, "personal_files", username)
        personal_files = [(config.GAME_FILES_URL + "personal_files/" + username + "/" + filename) for filename in
                          os.listdir(personal_folder_path)
                          if os.path.isfile(os.path.join(personal_folder_path, filename))
                             and not filename.startswith(".") and not filename.startswith("~")] # hidden files removed

        all_files = sorted(common_files + personal_files)

        if absolute_urls:
            domain = config.SITE_DOMAIN  #"http://%s" % Site.objects.get_current().domain
            all_files = [domain + user_file for user_file in all_files]

        return all_files







@register_module
class MoneyItemsOwnership(BaseDataManager):



    def _load_initial_data(self, **kwargs):
        super(MoneyItemsOwnership, self)._load_initial_data(**kwargs)

        new_data = self.data

        new_data["global_parameters"].setdefault("bank_name", "bank")
        new_data["global_parameters"].setdefault("bank_account", 0) # can be negative
        new_data["global_parameters"].setdefault("spent_gems", []) # gems used in abilities

        total_digital_money = new_data["global_parameters"]["bank_account"]
        total_gems = new_data["global_parameters"]["spent_gems"][:] # COPY

        for (name, character) in new_data["character_properties"].items():
            character["items"] = character.get("items", [])
            character["account"] = character.get("account", 0)
            character["gems"] = character.get("gems", [])

            total_gems += character["gems"]
            total_digital_money += character["account"]

        for (name, properties) in new_data["items_for_sale"].items():
            properties['unit_cost'] = int(math.ceil(float(properties['total_price']) / properties['num_items']))
            properties['owner'] = properties.get('owner', None)

            if properties["is_gem"] and not properties['owner']: # we dont recount gems appearing in character["gems"]
                total_gems += [properties['unit_cost']] * properties["num_items"]

        for (name, scan_set) in new_data["scanning_sets"].items():
            if scan_set == "__everywhere__":
                new_data["scanning_sets"][name] = new_data["locations"].keys()

        # We initialize some runtime checking parameters #
        new_data["global_parameters"]["total_digital_money"] = total_digital_money # integer
        new_data["global_parameters"]["total_gems"] = sorted(total_gems) # sorted list of integer values



    def _check_database_coherency(self, **kwargs):
        super(MoneyItemsOwnership, self)._check_database_coherency(**kwargs)

        game_data = self.data

        total_digital_money = game_data["global_parameters"]["bank_account"]
        total_gems = game_data["global_parameters"]["spent_gems"][:] # COPY!
        print ("^^^^^^^^^^^^", "spent_gems", total_gems.count(500))
        assert game_data["scanning_sets"]
        for (name, scan_set) in game_data["scanning_sets"].items():
            utilities.check_is_slug(name)
            for city in scan_set:
                assert city in game_data["locations"].keys(), "Wrong city : %s" % city

        for (name, character) in game_data["character_properties"].items():
            total_digital_money += character["account"]
            total_gems += character["gems"]
            print ("---------", name, total_gems.count(500))

        assert game_data["items_for_sale"]
        for (name, properties) in game_data["items_for_sale"].items():

            utilities.check_is_slug(name)
            assert isinstance(properties['is_gem'], bool)
            assert utilities.check_positive_int(properties['num_items'])
            assert utilities.check_positive_int(properties['total_price'])
            assert utilities.check_positive_int(properties['unit_cost'])

            assert properties['locations'] in game_data["scanning_sets"].keys()

            assert properties['owner'] is None or properties['owner'] in game_data["character_properties"].keys()

            assert isinstance(properties['title'], basestring) and properties['title']
            assert isinstance(properties['comments'], basestring) and properties['comments']
            assert isinstance(properties['image'], basestring) and properties['image']
            assert isinstance(properties['auction'], basestring) and properties['auction']

            if properties["is_gem"] and not properties["owner"]:
                total_gems += [properties['unit_cost']] * properties["num_items"]
                print (">>>>>>>>>>", name, total_gems.count(500))

        old_total_gems = game_data["global_parameters"]["total_gems"]
        assert Counter(old_total_gems) == Counter(total_gems)
        assert old_total_gems == sorted(total_gems), "%s != %s" % (old_total_gems, total_gems)

        old_total_digital_money = game_data["global_parameters"]["total_digital_money"]
        assert old_total_digital_money == total_digital_money, "%s != %s" % (old_total_digital_money, total_digital_money)



    @readonly_method
    def get_items_for_sale(self):
        return self.data["items_for_sale"]

    @readonly_method
    def get_item_properties(self, item_name):
        return self.data["items_for_sale"][item_name]

    @readonly_method
    def get_team_gems_count(self, domain):
        total_gems = 0
        for props in self.get_character_sets().values():
            if props["domain"] == domain:
                total_gems += len(props["gems"])
        return total_gems


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
            from_char = self.data["character_properties"][from_name] # may raise key error
            if from_char["account"] < amount:
                raise UsageError(_("Sender doesn't have enough money"))
            from_char["account"] -= amount

        if to_name == bank_name: # special case
            self.data["global_parameters"]["bank_account"] += amount
        else:
            to_char = self.data["character_properties"][to_name] # may raise key error
            to_char["account"] += amount

        self.log_game_event(_noop("Bank operation: %(amount)s kashes transferred from %(from_name)s to %(to_name)s."),
                             PersistentDict(amount=amount, from_name=from_name, to_name=to_name),
                             url=None)


    @transaction_watcher
    def transfer_object_to_character(self, item_name, char_name):
        # only admin may do that

        obj = self.get_item_properties(item_name)

        if obj["owner"]:
            raise UsageError(_("%(item_name)s has already been sold to %(char_name)s !") % SDICT(item_name=item_name,
                                                                                                 char_name=char_name))

        character = self.data["character_properties"][char_name] # might raise error

        character["items"].append(item_name)
        if obj["is_gem"]: # pack of gems
            character["gems"] += [obj["unit_cost"]] * obj["num_items"] #we add each gem separately
        obj["owner"] = char_name

        # todo - logging here ??


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

        self.data["items_for_sale"][item_name]["owner"] = None # we reset the owner tag of the object

        # todo - logging here ??



    @readonly_method
    def get_available_items_for_user(self, username):
        if username is None or self.is_master(username):
            available_items = self.get_items_for_sale()
        else:
            all_sharing_users = [username] # FIXME - which objects should we include?
            # user_domain = self.get_character_properties(username)["domain"]
            # all_domain_users = [name for (name, value) in self.get_character_sets().items() if
            #                    value["domain"] == user_domain]
            available_items = PersistentDict([(name, value) for (name, value)
                                              in self.get_items_for_sale().items()
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
        else:
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
            {
            'steps': (int, long),
            'total': (int, long),
            'levels': (int, long),
            'startlevel': (int, long),
            'filedir': basestring,
            'filename': basestring,
            'suffix': basestring,
            'imagewidth': (int, long),
            'imageheight': (int, long),
            'mode': basestring,
            'x_coefficient': (int, long),
            'y_coefficient': (int, long),
            }

        for (name, properties) in game_data["item_3d_settings"].items():
            assert name in game_data["items_for_sale"].keys(), name
            utilities.check_dictionary_with_template(properties, item_viewer_reference)



    @readonly_method
    def get_items_3d_settings(self):
        return self.data["item_3d_settings"]








@register_module
class SpecialAbilities(BaseDataManager):

    ABILITIES_REGISTRY = {}  # abilities automatically register themselves with this dict, thanks to their metaclass

    def __init__(self, **kwargs):
        super(SpecialAbilities, self).__init__(**kwargs)

        self.abilities = SpecialAbilities.AbilityLazyLoader(self)


    def _load_initial_data(self, **kwargs):
        super(SpecialAbilities, self)._load_initial_data(**kwargs)

        new_data = self.data

        new_data.setdefault("abilities", {})
        for (key, klass) in self.ABILITIES_REGISTRY.items():
            ability_data = new_data["abilities"].setdefault(key, {})
            self.logger.debug("Setting up main settings for ability %s" % key) #TODO
            klass.setup_main_ability_data(ability_data) # each ability fills its default values


    def _check_database_coherency(self, **kwargs):
        super(SpecialAbilities, self)._check_database_coherency(**kwargs)

        game_data = self.data

        for (name, value) in game_data["abilities"].items():
            ability = getattr(self.abilities, name) # lazy loading forced
            ability.check_data_sanity()


    def _notify_user_change(self, username, **kwargs):
        super(SpecialAbilities, self)._notify_user_change(username, **kwargs)

        self.abilities = SpecialAbilities.AbilityLazyLoader(self) # important - because of weak refs to old data!!


    @readonly_method
    def get_ability_data(self, ability_name):
        return self.data["abilities"][ability_name]


    class AbilityLazyLoader:

        def __init__(self, datamanager):
            self.__datamanager = weakref.ref(datamanager)

        @property
        def _datamanager(self):
            return self.__datamanager() # could be None

        def __getattr__(self, ability_name):

            registry = SpecialAbilities.ABILITIES_REGISTRY

            try:

                ability_class = registry[ability_name]

                # instantiation performs lazy init of private ability data too
                ability = ability_class(self._datamanager, self._datamanager.get_ability_data(ability_name))

                setattr(self, ability_name, ability) # ability now cached
                return ability

            except Exception, e:
                #print "error", e, traceback.print_exc() # TODO REMOVE
                raise

















