# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *
from rpgweb.datamanager.abstract_ability import AbstractAbility
from rpgweb.datamanager.abstract_game_view import register_view
from rpgweb.datamanager import readonly_method, \
    transaction_watcher


@register_view
class ArtificialIntelligenceAbility(AbstractAbility):

    NAME = "artificial_intelligence"

    GAME_FORMS = {}

    ACTIONS = dict()

    TEMPLATE = "abilities/artificial_intelligence.html"

    ACCESS = UserAccess.character
    PERMISSIONS = []
    ALWAYS_AVAILABLE = True


    @classmethod
    def _setup_ability_settings(cls, settings):
        pass

    def _setup_private_ability_data(self, private_data):
        settings = self.settings

        for bot_name in settings["specific_bot_properties"].keys():
            bot_session = private_data.setdefault(bot_name, {})
            bot_session.setdefault("_inputStack", []) # always empty between bot requests !
            bot_session.setdefault("_inputHistory", [])
            bot_session.setdefault("_outputHistory", [])

    def _check_data_sanity(self, strict=False):
        settings = self.settings


        utilities.check_is_range_or_num(settings["bots_answer_delays_ms"])
        utilities.check_is_int(settings["bot_max_answers"])

        for value in settings["terminal_answers"]:
            utilities.check_is_string(value)

        for key, value in settings["common_bot_properties"].items():
            utilities.check_is_string(key)
            utilities.check_is_string(value)

        for bot_name, bot_props in settings["specific_bot_properties"].items():
            utilities.check_is_string(bot_name)
            utilities.check_is_dict(bot_props) # nothing precise about what's here ATM


        for bot_session in self.all_private_data.values():
            utilities.check_has_keys(bot_session, ["_inputStack", "_inputHistory", "_outputHistory"], strict=strict)
            for val in bot_session.values():
                utilities.check_is_list(val) # let's not check further that data



    def get_template_vars(self, previous_form_data=None):
        return {
                'page_title': _("Djinns Chatroom"),
               }

    @readonly_method
    def get_bot_names(self):
        return self.settings["specific_bot_properties"].keys()

    @readonly_method
    def get_bot_session(self, bot_name):
        return self.settings["specific_bot_properties"][bot_name]

    @readonly_method
    def get_bot_history(self, bot_name):
        bot_session = self.get_bot_session(bot_name)
        return (bot_session["_inputHistory"], bot_session["_outputHistory"])



    @transaction_watcher
    def get_bot_response(self, username, bot_name, input):
        # TIP : say "startup xml" to the bot, to list its main predicates !!

        # we use only the "global session" of bot kernel, in the following calls !

        djinn_proxy = DJINN_PROXY # SINGLETON instance ATM

        bot_session = self.get_bot_session(bot_name) # we load previous session
        djinn_proxy.setSessionData(bot_session)

        # heavy, we override the personality of the target bot
        for (predicate, value) in self.settings["common_bot_properties"].items():
            djinn_proxy.setBotPredicate(predicate, value) # hobbies and tastes

        djinn_proxy.setBotPredicate("name", bot_name) # we change the bot personality

        djinn_proxy.setPredicate("name", self.username) # who is talking to him ?

        if "?" in input:
            djinn_proxy.setPredicate("topic", "")  # WARNING - a hack to help the bot get away from its "persistent ideas", as long as A.I. doesn't work very well...
            djinn_proxy.setPredicate("orbType", "")

        (inputs, outputs) = self.get_bot_history(bot_name)

        if len(outputs) > self.settings["bot_max_answers"]:
            res = random.choice(self.settings["terminal_answers"])
            # then let's manually update history
            inputs.append(input)
            outputs.append(res)
        else:
            res = djinn_proxy.respond(input)
            self.private_data.update(djinn_proxy.getSessionData()) # we save current session

        # we simulate answer delay
        delay_ms = self.settings["bots_answer_delays_ms"]
        if not isinstance(delay_ms, (int, long, float)):
            delay_ms = random.randint(delay_ms[0], delay_ms[1])
        time.sleep(float(delay_ms) / 1000)

        return res









class DjinnProxy(object):
    """
    Abstraction layer, redirecting either to a local PyAiml bot,
    or an external bot server.
    """

    def __init__(self):
        # Note : setBotPredicate can only be accessed from python code,
        # whereas setPredicate can be set from AIML and is stored in the bot session !
        # we do not use session IDs, so that we keep an unique history for all chats with a specific bot !
        self.bot_kernel = None

        if config.ACTIVATE_AIML_BOTS: # in prod we shall NOT use bots, too memory-consuming !

            import aiml

            kernel = aiml.Kernel()
            kernel.verbose(False) # DEBUG OUTPUT
            kernel.bootstrap(
                brainFile=os.path.join(config.GAME_FILES_ROOT, "AI", "botbrain.brn"),
                learnFiles=glob.glob(os.path.join(config.GAME_FILES_ROOT, "AI", "djinn_specific_aiml", "*.aiml"))
            )
            self.bot_kernel = kernel

        else:
            logging.debug("AI bots not initialized to preserve memory")

            """
            print "INITIALIZED SESSION  for %s : " % name, self.data["AI_bots"]["bot_properties"][name]["bot_sessions"]
            props["bot_sessions"] = kernel.getSessionData() # IMPORTANT - initialized values, with I/O history etc.
            print "COMMITTING DATA for %s :" % name, self.data["AI_bots"]["bot_properties"][name]
            """

    def respond(self, input):
        return self.bot_kernel.respond(input)

    def setSessionData(self, data):
        self.bot_kernel.setSessionData(data)

    def getSessionData(self):
        return self.bot_kernel.getSessionData()

    def setBotPredicate(self, key, value):
        self.bot_kernel.setBotPredicate(key, value) # we change the bot personality

    def getBotPredicate(self, key):
        return self.bot_kernel.getBotPredicate(key)

    def setPredicate(self, key, value):
        self.bot_kernel.setPredicate(key, value) # we change the context of conversation

    def getPredicate(self, key):
        return self.bot_kernel.getPredicate(key)


# singleton
DJINN_PROXY = DjinnProxy()



