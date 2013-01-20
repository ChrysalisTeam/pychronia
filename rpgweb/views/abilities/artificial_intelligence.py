# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals



## INIT

for props in game_data["AI_bots"]["bot_properties"].values():
    props["bot_sessions"]["_inputStack"] = [] # always empty between bot requests !
    props["bot_sessions"]["_inputHistory"] = props["bot_sessions"].get("_inputHistory", [])
    props["bot_sessions"]["_outputHistory"] = props["bot_sessions"].get("_outputHistory", [])

            if name in "bots_max_answers".split():
                assert isinstance(value, (long, int)) and value > 0



## CHECK


    bots = game_data["AI_bots"]
    assert isinstance(bots, PersistentDict)
    assert set(bots.keys()) == set("common_properties bot_properties bot_terminal_answers".split())
    for (name, value) in bots["common_properties"].items():
        assert isinstance(name, basestring)
        assert isinstance(value, basestring)
    for (name, value) in bots["bot_properties"].items():
        assert isinstance(name, basestring)
        assert len(value) == 2
        assert isinstance(value["gems_required"], (int, long)) and value["gems_required"] > 0
        #for aiml in value["specific_aiml"]: # NOT USED ANYMORE, 1 AIML for all djinns now !
        #    assert os.path.isfile(config.GAME_FILES_ROOT, "AI", "specific_aiml", aiml)
        assert isinstance(value["bot_sessions"], PersistentDict)
        for predicate in "_inputHistory _inputStack _outputHistory".split():
            assert predicate in value["bot_sessions"].keys()
            assert isinstance(value["bot_sessions"][predicate], PersistentList)
    for value in bots["bot_terminal_answers"]:
        assert isinstance(value, basestring) and value












    def get_bots_properties(self):
        return self.data["AI_bots"]["bot_properties"]

    def get_bot_names(self):
        return self.data["AI_bots"]["bot_properties"].keys()

    def is_bot_accessible(self, bot_name, domain):
        WRONG - gems_owned = self.get_team_gems_count(domain)
        gems_required = self.get_bots_properties()[bot_name]["gems_required"]

        return (gems_owned >= gems_required)


    @transaction_watcher
    def get_bot_response(self, username, bot_name, input):
        # TIP : say "startup xml" to the bot, to list its main predicates !!

        # we use only the "global session" of bot kernel, in the following calls !

        bot_properties = self.data["AI_bots"]["bot_properties"][bot_name] # we load previous session
        djinn_proxy.setSessionData(bot_properties["bot_sessions"])

        # heavy, we override the personality of the target bot
        for (predicate, value) in self.data["AI_bots"]["common_properties"].items():
            djinn_proxy.setBotPredicate(predicate, value) # hobbies and tastes

        djinn_proxy.setBotPredicate("name", bot_name) # we change the bot personality
        djinn_proxy.setPredicate("name", username) # who is talking to him ?
        if "?" in input:
            djinn_proxy.setPredicate("topic",
                                     "")  # WARNING - TODO - Hack to help the bot get away from its "persistent ideas", as long as A.I. don't work very well...
            djinn_proxy.setPredicate("orbType", "")

        (inputs, outputs) = self.get_bot_history(bot_name)

        if len(outputs) > self.get_global_parameter("bots_max_answers"):
            res = random.choice(self.data["AI_bots"]["bot_terminal_answers"])
            # these persistent lists will keep the history OK
            inputs.append(input)
            outputs.append(res)

        else:
            res = djinn_proxy.respond(input)
            bot_properties["bot_sessions"] = djinn_proxy.getSessionData() # we save current session


        # we simulate answer delay
        delay_ms = self.get_global_parameter("bots_answer_delays_ms")
        if not isinstance(delay_ms, (int, long, float)):
            delay_ms = random.randint(delay_ms[0], delay_ms[1])
        time.sleep(float(delay_ms) / 1000)

        return res


    def get_bot_history(self, bot_name):
        data = self.data["AI_bots"]["bot_properties"][bot_name]["bot_sessions"]
        return (data["_inputHistory"], data["_outputHistory"])






















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

            import aimllib

            kernel = aimllib.Kernel()
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
        self.bot_kernel.setPredicate(key, value) # we change the bot personality

    def getPredicate(self, key):
        return self.bot_kernel.getPredicate(key)


# singleton
djinn_proxy = DjinnProxy()



