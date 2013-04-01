# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *
from .datamanager_tools import *



class BaseDataManager(utilities.TechnicalEventsMixin):


    def begin(self):

        if not self._in_transaction:
            self.check_no_pending_transaction()
            self._in_transaction = True
            #transaction.begin() # not really needed
            return None # value indicating top level
        else:
            return transaction.savepoint()

    def commit(self, savepoint=None):
        if savepoint:
            pass # savepoint needn't be committed, in ZODB
        else:
            self._in_transaction = False
            transaction.commit() # top level
            self.check_no_pending_transaction() # AFTER REAL COMMIT

    def rollback(self, savepoint=None):
        if savepoint:
            savepoint.rollback()
        else:
            self._in_transaction = False
            transaction.abort() # top level
            self.check_no_pending_transaction() # AFTER REAL ROLLBACK

    def check_no_pending_transaction(self):
        assert not self._in_transaction, self._in_transaction
        assert not self.connection._registered_objects, repr(self.connection._registered_objects)

    # no transaction manager - special case
    def __init__(self, game_instance_id, game_root=None, request=None, **kwargs):
        '''
        self.storage = FileStorage.FileStorage(config.ZODB_FILE)
        self.db = DB(self.storage)
        self.pack_database(days=1)
        self.connection = self.db.open()
        self.connection.root()

        '''
        assert game_root is not None

        super(BaseDataManager, self).__init__(**kwargs)

        self.notify_event("BASE_DATA_MANAGER_INIT_CALLED")

        self._in_transaction = False

        self.game_instance_id = game_instance_id

        self.logger = logging.getLogger("rpgweb.%s" % game_instance_id) #FIXME

        self._request = weakref.ref(request) if request else None # if None, user notifications won't work

        self.data = game_root # can be empty, here
        self.connection = game_root._p_jar # can be empty, for transient persistent objects

        self.is_initialized = bool(self.data) # empty or not

        if self.is_initialized:
            self._init_from_db()


    def _init_from_db(self):
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

            assert not self.connection or not self.connection._registered_objects # else problem, pending changes created by views!
            self.connection.close()
            self.connection = None
            self.data = None



    @transaction_watcher(always_writable=True) # might operate on broken data
    def reset_game_data(self, yaml_fixture=config.GAME_INITIAL_DATA_PATH):
        """
        This method might raise exceptions, and leave the datamanager uninitialized.
        """

        if self.data and not config.DB_RESET_ALLOWED:
            raise RuntimeError("Can't reset existing databases in this environment")

        #print "RESETTING DATABASE !"

        # ZODB reset - warning, we must replace content of dictionary "data",
        # not rebind the attribute "data", else we lose ZODB support
        self.data.clear()

        initial_data = utilities.load_yaml_fixture(yaml_fixture)
        self.data.update(initial_data)

        self._load_initial_data() # traversal of each core module

        # NOW only we normalize and check the object tree
        # normal python types are transformed to ZODB-persistent types
        for key in self.data.keys():
            self.data[key] = utilities.convert_object_tree(self.data[key], utilities.python_to_zodb_types)
            utilities.check_object_tree(self.data[key], allowed_types=utilities.allowed_zodb_types, path=["game_data"])

        self.is_initialized = True
        self._init_from_db()

        if config.GAME_INITIAL_FIXTURE_SCRIPT:
            self.logger.info("Performing setup via GAME_INITIAL_FIXTURE_SCRIPT")
            config.GAME_INITIAL_FIXTURE_SCRIPT(self)

        self.check_database_coherency()



    def _load_initial_data(self, **kwargs):
        """
        Overrides of this method can use standard python objects, 
        as everything will be converted to ZODB types before committing, 
        anyway.
        """
        self.notify_event("BASE_LOAD_INITIAL_DATA_CALLED")


    @transaction_watcher(always_writable=True) # that checking might lead to corrections
    def check_database_coherency(self, **kwargs):

        self.notify_event("BASE_CHECK_DB_COHERENCY_PUBLIC_CALLED")

        game_data = self.data

        # Heavy Check !
        utilities.check_object_tree(game_data, allowed_types=utilities.allowed_zodb_types, path=["game_data"])


        self._check_database_coherency()



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
            "spy_report_delays", "mercenary_intervention_delays", "acharith_attack_delays",
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
            acharith_attack_delays
            telecom_investigation_delays telecom_investigations_done max_telecom_investigations
            radio_is_on
            bots_answer_delays_ms bots_max_answers
            spy_cost_gems spy_cost_money mercenary_cost_gems mercenary_cost_money
        '''



    def _check_database_coherency(self, **kwargs):
        self.notify_event("BASE_CHECK_DB_COHERENCY_PRIVATE_CALLED")


    @transaction_watcher
    def process_periodic_tasks(self, **kwargs):
        """
        Each core module performs its periodic tasks, and appends to the common report.
        """
        report = PersistentDict()
        self._process_periodic_tasks(report)
        return report


    def _process_periodic_tasks(self, report):
        self.notify_event("BASE_PROCESS_PERIODIC_TASK_CALLED")


    @readonly_method
    def dump_zope_database(self, **kwargs):

        dump_args = dict(width=100, indent=4, # NO default_style nor canonical, else stuffs break
                            default_flow_style=False, allow_unicode=True)
        dump_args.update(kwargs)

        data_dump = copy.deepcopy(dict(self.data)) # beware - memory-intensive call

        # special, we remove info that is already well visible in messaging system
        for key in list(data_dump.keys()): # in case it'd be a "dict-view"
            if "message" in key:
                del data_dump[key]

        data_dump = utilities.convert_object_tree(data_dump, utilities.zodb_to_python_types)

        '''
        def coerce_to_ascii_if_possible(dumper, value):
            try:
                return dumper.represent_scalar(u'tag:yaml.org,2002:str', value.encode("ascii"))
            except UnicodeError:
                return dumper.represent_unicode(value)
        '''
        yaml.add_representer(unicode, lambda dumper, value: dumper.represent_scalar(u'tag:yaml.org,2002:str', value))

        # FIXME yaml.add_representer(unicode, lambda dumper, value: dumper.represent_scalar(u'tag:yaml.org,2002:str', value))
        string = yaml.dump(data_dump, **dump_args) # TODO fix safe_dump() to accept unicode in input!!

        return string









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
print [key for key in sys.modules.keys() if "rpgweb" in key]
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
