# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from pychronia_game.common import *
from .datamanager_tools import *



class BaseDataManager(utilities.TechnicalEventsMixin):


    # utilities for WRITING transactions (readonly ones are implicit) #

    def begin(self):
        if not self._in_writing_transaction:
            self.check_no_pending_transaction()
            self._in_writing_transaction = True
            begin_transaction_with_autoreconnect() # not really needed
            return None # value indicating top level
        else:
            return transaction.savepoint()

    def commit(self, savepoint=None):
        if savepoint:
            pass # savepoint needn't be committed, in ZODB
        else:
            self._in_writing_transaction = False
            transaction.commit() # top level
            self.check_no_pending_transaction() # AFTER REAL COMMIT

    def rollback(self, savepoint=None):
        if savepoint:
            savepoint.rollback()
        else:
            self._in_writing_transaction = False
            transaction.abort() # top level
            self.check_no_pending_transaction() # AFTER REAL ROLLBACK

    def is_in_writing_transaction(self):
        return self._in_writing_transaction

    def check_no_pending_transaction(self):
        assert self.connection  # else, connectionless mode, we shouldn't be using transaction API
        assert not self._in_writing_transaction, self._in_writing_transaction
        assert not self.connection._registered_objects, repr(self.connection._registered_objects)



    # utilities for toplevel handling of transactions (writing or not) #

    def begin_top_level_wrapping(self):
        if self._in_top_level_handler:
            raise RuntimeError("begin_top_level_wrapping() called twice in same transaction")
        self._in_top_level_handler = True

    def end_top_level_wrapping(self):
        if not self._in_top_level_handler:
            raise RuntimeError("end_top_level_wrapping() called out of workflow")
        self._in_top_level_handler = False

    def is_under_top_level_wrapping(self):
        return self._in_top_level_handler


    # no transaction manager - special case
    def __init__(self, game_instance_id, game_root=None, request=None, **kwargs):

        assert game_root is not None # it's actually game DATA, no METADATA is included here!

        super(BaseDataManager, self).__init__(**kwargs)

        self.notify_event("BASE_DATA_MANAGER_INIT_CALLED")

        self._in_writing_transaction = False # for WRITING transactions only
        self._in_top_level_handler = False # for both readonly and writing transactions, top-level conflict handler

        self.game_instance_id = game_instance_id

        # workaround to have DYNAMIC extra values in logger
        datamanager_instance = self
        class DynamicDatamanagerLoggerAdapter(dict):
            EXTRA_FIELDS = ["game_instance_id", "real_username", "username", "is_observer"]
            def __getitem__(self, name):
                if name not in self.EXTRA_FIELDS:
                    raise KeyError("DynamicDatamanagerLoggerAdapter doesn't support DM attribute %s" % name)
                try:
                    return getattr(datamanager_instance.user, name)
                except AttributeError:
                    try:
                        return getattr(datamanager_instance, name)
                    except AttributeError as e:
                        return "<none>"
            def __iter__(self):
                return iter(self.EXTRA_FIELDS)
        dm_logger_adapter = DynamicDatamanagerLoggerAdapter()

        self._inner_logger = logging.getLogger("pychronia_game") #FIXME
        self.logger = logging.LoggerAdapter(self._inner_logger, dm_logger_adapter)

        self._request = weakref.ref(request) if request else None # if None, user notifications won't work

        self.data = game_root # can be empty, here
        self.connection = game_root._p_jar # can be empty, for transient persistent objects

        self.is_initialized = bool(self.data) # empty or not

        if self.is_initialized:
            self.do_init_from_db()

    @transaction_watcher(always_writable=True)
    def do_init_from_db(self):
        self._init_from_db()

    def _init_from_db(self):
        """
        To be overridden.
        """
        self.notify_event("BASE_DATA_MANAGER_INIT_FROM_DB_CALLED")

    @property
    def request(self):
        return self._request() if self._request else None


    # NO transaction_watcher here!
    def close(self):
        """
        Should be called before terminating the server, to prevent any DB trouble.
        """

        if self.data is not None:
            # we close the ZODB connection attached to our data root
            assert not self.connection or not self.connection._registered_objects  # else problem, pending changes created by views!
            self.data = None
        if self.connection:
            self.connection.close()
            self.connection = None
            



    @transaction_watcher(always_writable=True) # might operate on broken data
    def reset_game_data(self,
                        yaml_fixture=None,
                        skip_randomizations=False,  # randomize some values in dm.data
                        skip_initializations=False,  # used when an already-initialized fixture is used
                        skip_coherence_check=False,
                        strict=False):
        """
        This method might raise exceptions, and leave the datamanager uninitialized.
        """

        if self.data and not config.ZODB_RESET_ALLOWED:
            raise RuntimeError("Can't reset existing databases in this environment")

        if not yaml_fixture:
            yaml_fixture = config.GAME_INITIAL_DATA_PATH

        self.logger.info("Resetting game data for instance '%s' with fixture '%s'",
                         self.game_instance_id, yaml_fixture if isinstance(yaml_fixture, basestring) else "<data-tree>")
        #print "RESETTING DATABASE !"

        # ZODB reset - warning, we must replace content of dictionary "data",
        # not rebind the attribute "data", else we lose ZODB support
        self.data.clear()

        if isinstance(yaml_fixture, basestring):
            initial_data = utilities.load_yaml_fixture(yaml_fixture)
        else:
            assert isinstance(yaml_fixture, PersistentMapping), yaml_fixture  # a preloaded data tree was provided
            initial_data = yaml_fixture

        self.data.update(initial_data)

        if not skip_initializations:
            self._load_initial_data(skip_randomizations=skip_randomizations) # traversal of each core module
        else:
            assert skip_randomizations == True

        # NOW only we normalize and check the object tree
        # normal python types are transformed to ZODB-persistent types
        for key in self.data.keys():
            self.data[key] = utilities.convert_object_tree(self.data[key], utilities.python_to_zodb_types)
            utilities.check_object_tree(self.data[key], allowed_types=utilities.allowed_zodb_types, path=["game_data"])

        self.is_initialized = True
        self._init_from_db()

        if config.GAME_INITIAL_FIXTURE_SCRIPT and not skip_initializations:
            self.logger.info("Performing setup via GAME_INITIAL_FIXTURE_SCRIPT")
            config.GAME_INITIAL_FIXTURE_SCRIPT(self)
        else:
            self.logger.info("Skipping setup via GAME_INITIAL_FIXTURE_SCRIPT")

        if not skip_coherence_check:
            self.check_database_coherence(strict=strict)



    def _load_initial_data(self, **kwargs):
        """
        Overrides of this method can use standard python objects, 
        as everything will be converted to ZODB types before committing, 
        anyway.
        """
        self.notify_event("BASE_LOAD_INITIAL_DATA_CALLED")


    @transaction_watcher(always_writable=True) # that checking might lead to corrections
    def check_database_coherence(self, **kwargs):

        self.notify_event("BASE_CHECK_DB_COHERENCE_PUBLIC_CALLED")

        game_data = self.data

        # Heavy Check !
        utilities.check_object_tree(game_data, allowed_types=utilities.allowed_zodb_types, path=["game_data"])


        self._check_database_coherence(**kwargs)



        ''' # TO BE REDISPATCHED #

        _expected_game_params = set("""
                                    anonymous_login
                                    master_login master_password master_email master_real_life_email
                                    """.split())

        _actual_game_params = set(game_data["global_parameters"].keys())

        assert _expected_game_params <= _actual_game_params, ("Missing global params", _expected_game_params - _actual_game_params)

        
        for name, value in game_data["global_parameters"].items():

            elif name == "opening_music":
                assert os.path.isfile(os.path.join(config.GAME_FILES_ROOT, "musics", value))
            elif name == "orbs_locations":
                assert len(value) == 3 # 3 orbs...
                for (orb_name, city) in value.items():
                    assert city in game_data["locations"].keys()

            elif name == "cynthia_abduction_location":
                assert value in game_data["locations"].keys()
            elif name in (
            "password_recovery_delays", "scanning_delays", "teldorian_teleportation_delays",
            "spy_report_delays", "mercenary_intervention_delays", "akarith_attack_delays",
            "telecom_investigation_delays", "bots_answer_delays_ms"):
                utilities.check_is_range_or_num(value) # can be floats too !
            elif name in ["global_introduction", "history_summary"]:
                assert isinstanceXX(value, basestring) and value
            elif name in ["game_is_started"]:
                assert isinstanceXX(value, bool)

            else:
                # default : positive integer
                assert (isinstanceXX(value, (int, long)) and value >= 0), "Value is %s" % value

        # reserved character names
        assert game_data["global_parameters"]["anonymous_login"] not in game_data["character_properties"].keys()
        assert game_data["global_parameters"]["master_login"] not in game_data["character_properties"].keys()


            spy_report_delays mercenary_intervention_delays
            password_recovery_delays
            scanned_locations scanning_delays
            orbs_locations    cynthia_abduction_location
            teldorian_teleportation_delays max_teldorian_teleportations teldorian_teleportations_done
            akarith_attack_delays
            telecom_investigation_delays telecom_investigations_done max_telecom_investigations
            radio_is_on
            bots_answer_delays_ms bots_max_answers
            spy_cost_gems spy_cost_money mercenary_cost_gems mercenary_cost_money
        '''



    def _check_database_coherence(self, **kwargs):
        self.notify_event("BASE_CHECK_DB_COHERENCE_PRIVATE_CALLED")


    @transaction_watcher
    def process_periodic_tasks(self, **kwargs):
        """
        Each core module performs its periodic tasks, and appends to the common report.
        
        Note that none of these tasks should rely on current user, which could be anything...
        """
        assert self.is_game_writable()
        report = PersistentMapping()
        self._process_periodic_tasks(report)
        return report


    def _process_periodic_tasks(self, report):
        self.notify_event("BASE_PROCESS_PERIODIC_TASK_CALLED")


    @readonly_method
    def dump_zope_database(self, **kwargs):

        data_tree = copy.deepcopy(dict(self.data)) # beware - memory-intensive call

        """ TODO FIXME REPUT THAT ??
        # special, we remove info that is already well visible in messaging system and chatroom
        for key in list(data_tree.keys()): # in case it'd be a "dict-view"
            if "message" in key:
                del data_tree[key]
        """

        string = utilities.dump_data_tree_to_yaml(data_tree,
                                                  default_style=">", # prevents too long lines and double "'" quotes
                                                  ** kwargs)

        return string


    @transaction_watcher
    def load_zope_database_from_string(self, string, strict=True):

        data_tree = utilities.load_data_tree_from_yaml(string, convert=True)
        assert isinstance(data_tree, PersistentMapping)

        try:
            old_data = self.data
            self.data = data_tree
            self.check_database_coherence(strict=strict)
        except Exception:
            self.data = old_data # security about mishandlings
            raise

        return self.data


'''

    def _check_dictionary_with_template(self, hash, template): #TO BE REMOVED
        # checks that the keys and value types of a dictionary matches a reference one
        assert set(hash.keys()) == set(template.keys()), (hash.keys(), template.keys())
        for (key, value) in hash.items():
            assert isinstanceXX(value, template[key]), unicode((key, value, template[key]))



    def _load_and_normalize_yaml_data(self, yaml_file):
        """
        
        """

        # We initialize runtime parameters #


        game_data["global_parameters"]["total_gems_number"] = total_gems_number
        game_data["global_parameters"]["total_digital_money"] = total_digital_money
        game_data["global_parameters"]["teldorian_teleportations_done"] = 0
        game_data["global_parameters"]["telecom_investigations_done"] = 0
        game_data["global_parameters"]["scanned_locations"] = []
   

        ##game_data["wiretapping_targets"] = game_data.get("wiretapping_targets", [])


        # IMPORTANT - NOW we can convert basic types !

        return game_data


'''
"""
import traceback
traceback.print_stack()
print "\n"
print [key for key in sys.modules.keys() if "pychronia_game" in key]
print "\n\n"
"""

"""
try:

    mydatamanager = DataManager()

    import atexit
    atexit.register(mydatamanager.shutdown) # it should work !

    '''
    # dangerous asynchronous code - but we can't do differently... #
    # we cleanup on signal reception - atexit() is not called soon enough for this case !
    import signal
    curr_sigint_handler = signal.getsignal(signal.SIGINT)
    def sigint_handler(*args, **kswargs):
        mydatamanager.close()
        curr_sigint_handler(*args, **kswargs)
    signal.signal(signal.SIGINT, sigint_handler)
    signal.signal(signal.SIGTERM, sigint_handler)
    if getattr(signal, "SIGBREAK", None) is not None:
        signal.signal(signal.SIGBREAK, sigint_handler)
    '''

    #if config.DEBUG: # TODO REMOVE
    #    mydatamanager.reset_game_data() #reset_all_databases() # for local debugging only
except Exception:
    raise


    #def get_wiretapping_targets(self):
    #    return self.data["wiretapping_targets"]


    def get_processed_translation_attempts(self):
        res = [attempt for attempt in self.data["rune_translations"]["translation_attempts"] if utilities.is_past_datetime(attempt["activation_datetime"])]
        return res

 # translation_attempts: [] # TO BE REMOVED, BAD ! let this empty, it will be filled with hashes having keys [activation_datetime, item_name, decoded_runes, proposed_translation]



    # Warning - use the CRON instead !!

"""

"""     DEPRECATED - hard-code messages for translation instead
    def _build_robot_message_content(self, template_name, subject_dict, body_dict):

        # for YAML message templates :
        # warning - double all normal "%" in these messages, and use keyword-style placeholder
        # like "%(name)s" instead of positional placeholders like "%s"

        template = self.data["automated_messages_templates"][template_name]

        subject_tpl = template["subject"]
        body_tpl = template["body"]

        subject = ""
        body = ""

        attachment = template["attachment"]

        with exception_swallower():
            subject = self._try_filling_message_template(subject_tpl, subject_dict, part_name="subject", tpl_name=template_name)
            body = self._try_filling_message_template(body_tpl, body_dict, part_name="body", tpl_name=template_name)

        return (subject, body, attachment)
    """
