# -*- coding: utf-8 -*-



import threading
from pychronia_game.common import *
from pychronia_game.datamanager import readonly_method, transaction_watcher, register_view, AbstractAbility, AbstractGameForm
from pychronia_game.datamanager.abstract_form import autostrip_form_charfields
from django import forms
from django.http import Http404
from configparser import ConfigParser

""" DEPRECATED
class DjinnContactForm(AbstractGameForm):

    def __init__(self, ability, *args, **kwargs):
        super(DjinnContactForm, self).__init__(*args, **kwargs)
        available_djinns_choices = zip(available_djinns, available_djinns)
        self.fields["djinn"] = forms.ChoiceField(label=_("Djinn"), choices=available_djinns_choices)

"""

djinn_singleton_lock = threading.Lock()  # cfor oncurrent access to singleton


@autostrip_form_charfields
class DjinnContactForm(AbstractGameForm):
    djinn_name = forms.CharField(label=ugettext_lazy("Djinn"), required=True)


@register_view
class ArtificialIntelligenceAbility(AbstractAbility):
    TITLE = ugettext_lazy("Chat with Djinns")
    NAME = "artificial_intelligence"

    GAME_ACTIONS = dict(process_user_sentence=dict(title=ugettext_lazy("Respond to user input"),
                                                   form_class=None,
                                                   callback="process_user_sentence"))

    TEMPLATE = "abilities/artificial_intelligence.html"

    ACCESS = UserAccess.character
    REQUIRES_CHARACTER_PERMISSION = True
    REQUIRES_GLOBAL_PERMISSION = True

    @classmethod
    def _setup_ability_settings(cls, settings):
        pass

    def _setup_private_ability_data(self, private_data):
        settings = self.settings

        for bot_name in list(settings["specific_bot_properties"].keys()):
            bot_session = private_data.setdefault(bot_name, PersistentMapping())
            bot_session.setdefault("_inputStack", PersistentList())  # always empty between bot requests !
            bot_session.setdefault("_inputHistory", PersistentList())
            bot_session.setdefault("_outputHistory", PersistentList())

    def _check_data_sanity(self, strict=False):
        settings = self.settings

        utilities.check_is_range_or_num(settings["bots_answer_delays_ms"])
        utilities.check_is_int(settings["bot_max_answers"])

        for value in settings["terminal_answers"]:
            utilities.check_is_string(value)

        for key, value in list(settings["common_bot_properties"].items()):
            utilities.check_is_string(key)
            if value:  # may be empty
                utilities.check_is_string(value)

        for bot_name, bot_props in list(settings["specific_bot_properties"].items()):
            utilities.check_is_string(bot_name)
            assert bot_name.strip() == bot_name, bot_name
            utilities.check_is_dict(bot_props)  # nothing precise about what's here ATM

        for data in list(self.all_private_data.values()):
            for bot_name in list(settings["specific_bot_properties"].keys()):
                bot_session = data[bot_name]
                utilities.check_has_keys(bot_session, ["_inputStack", "_inputHistory", "_outputHistory"],
                                         strict=False)  # other session values may exist

    def _process_html_post_data(self):
        """We prevent default form handling and error reporting."""
        assert not self.request.is_ajax()
        assert self.request.method == "POST"
        return dict(result=None, form_data=None)

    def _get_entrance_template_vars(self):
        return {
            'page_title': _("Djinns' Temple"),
            'selected_djinn': None,
            'bot_max_answers': self.settings["bot_max_answers"],
        }

    def _get_djinn_template_vars(self, selected_bot):

        history = self.get_bot_history(bot_name=selected_bot)
        sentences = []
        for i in range(max(len(history[0]), len(history[1]))):
            if i < len(history[0]):
                sentences.append(history[0][i])  # input
            if i < len(history[1]):
                sentences.append(history[1][i])  # output

        return {
            'page_title': _("%s's Shrine") % selected_bot,
            'selected_djinn': selected_bot,
            'history': sentences,
        }

    def get_template_vars(self, previous_form_data=None):
        selected_bot = self.request.POST.get("target_djinn_name", None)
        if selected_bot is not None:  # post var was sent
            selected_bot = selected_bot.strip()  # normalize
            if selected_bot in self.get_bot_names():
                return self._get_djinn_template_vars(selected_bot=selected_bot)  # success, talk with a djinn
            else:
                self.user.add_error(_("Unknown djinn name '%s'") % selected_bot)
        return self._get_entrance_template_vars()  # page to choose wanted djinn

    @readonly_method
    def get_bot_names(self):
        return list(self.settings["specific_bot_properties"].keys())

    @readonly_method
    def get_bot_session(self, bot_name):
        return self.private_data[bot_name]  # specific to the current user

    @readonly_method
    def get_bot_history(self, bot_name):
        bot_session = self.get_bot_session(bot_name)
        return (bot_session["_inputHistory"], bot_session["_outputHistory"])

    @transaction_watcher
    def get_bot_response(self, bot_name, input):
        # TIP : say "startup xml" to the bot, to list its main predicates !!
        # TODO - use loadSubs to make proper substitutions
        # we use only the "global session" of bot kernel, in the following calls !

        if not DJINN_PROXY_IS_INITIALIZED:
            _activate_djinn_proxy()  # might still remain None, though
            assert DJINN_PROXY_IS_INITIALIZED

        djinn_proxy = DJINN_PROXY  # SINGLETON instance ATM

        if not djinn_proxy:
            return _("[DJINN IS OFFLINE]")

        with djinn_singleton_lock:

            bot_session = self.get_bot_session(bot_name)  # we load previous session
            djinn_proxy.setSessionData(bot_session)

            # heavy, we override the personality of the target bot
            for (predicate, value) in list(self.settings["common_bot_properties"].items()):
                djinn_proxy.setBotPredicate(predicate, value)  # hobbies and tastes

            # we change the bot personality #
            djinn_proxy.setBotPredicate("name", bot_name)  # to use <bot name="name"/>
            djinn_proxy.setPredicate("botName", bot_name)  # to use in <condition> tag

            djinn_proxy.setPredicate("name", self.username)  # who is talking to him ?

            if "?" in input:
                djinn_proxy.setPredicate("topic",
                                         "")  # WARNING - a hack to help the bot get away from its "persistent ideas", as long as A.I. doesn't work very well...
                djinn_proxy.setPredicate("orbType", "")

            (inputs, outputs) = self.get_bot_history(bot_name)

            if len(outputs) > self.settings["bot_max_answers"]:
                res = random.choice(self.settings["terminal_answers"])
                # then let's manually update history
                inputs.append(input)
                outputs.append(res)
            else:
                res = djinn_proxy.respond(input)
                # print ("DJINN REQUEST %r => %r" % (input, res))
                data = djinn_proxy.getSessionData()
                data = utilities.convert_object_tree(data,
                                                     utilities.python_to_zodb_types)  # FIXME, is it really useful ??
                self.private_data.update(data)  # we save current session in ZODB

            # we simulate answer delay
            delay_ms = self.settings["bots_answer_delays_ms"]
            if not isinstance(delay_ms, (int, float)):
                delay_ms = random.randint(delay_ms[0], delay_ms[1])
            time.sleep(float(delay_ms) / 1000)

            return res

    def process_user_sentence(self, djinn_name, message, use_gems=()):

        if djinn_name not in self.get_bot_names():
            raise Http404  # pathological

        res = self.get_bot_response(bot_name=djinn_name,
                                    input=message)  # in case of error, a "500" code will be returned
        return dict(response=res)

        '''

        def chat_with_djinn(request, template_name='specific_operations/chat_with_djinn.html'):

            bot_name = request.POST.get("djinn", None)

            # TODO BAD - add security here !!!!!!!!!!

            if not request.datamanager.is_game_started():
                return HttpResponse(_("Game is not yet started"))

            if bot_name not in request.datamanager.get_bot_names():
                raise Http404



            return render(request,
                          template_name,
                            {
                             'page_title': _("Djinn Communication"),
                             'bot_name': bot_name,
                             'history': sentences
                            })


        def ajax_consult_djinns(request):
            user = request.datamanager.user
            message = request.REQUEST.get("message", "")
            bot_name = request.REQUEST.get("djinn", None)

            if bot_name not in request.datamanager.get_bot_names():
                raise Http404

            res = request.datamanager.get_bot_response(bot_name, message)
            return HttpResponse(escape(res))  # IMPORTANT - escape xml entities !!

            # in case of error, a "500" code will be returned


        def contact_djinns(request, template_name='specific_operations/contact_djinns.html'):

            user = request.datamanager.user

            bots_properties = request.datamanager.get_bots_properties()

            if user.is_master:  # FIXME
                available_bots = bots_properties.keys()
                # team_gems = None
            else:
                domain = request.datamanager.get_character_properties()["domain"]
                available_bots = [bot_name for bot_name in bots_properties.keys() if request.datamanager.is_bot_accessible(bot_name, domain)]
                # team_gems = request.datamanager.get_team_gems_count(domain)

            if available_bots:
                djinn_form = forms.DjinnContactForm(available_bots)
            else:
                djinn_form = None

            all_bots = bots_properties.items()
            all_bots.sort(key=lambda t: t[1]["gems_required"])

            return render(request,
                          template_name,
                            {
                             'page_title': _("Shrine of Oracles"),
                             'djinn_form': djinn_form,
                             'all_bots': all_bots,
                             # 'team_gems': team_gems,
                             'bots_max_answers': request.datamanager.get_global_parameter("bots_max_answers")
                            })
            '''


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

        import aiml  # lazily loaded

        # MONKEY PATCHING #
        def setSessionData(self, data, sessionID="_global"):
            self._sessions[sessionID] = data

        aiml.Kernel.setSessionData = setSessionData

        kernel = aiml.Kernel()
        kernel.verbose(False)  # DEBUG OUTPUT
        kernel.bootstrap(
            brainFile=os.path.join(config.GAME_FILES_ROOT, "AI", "botbrain.brn"),
            learnFiles=glob.glob(os.path.join(config.GAME_FILES_ROOT, "AI", "djinn_specific_aiml", "*.aiml"))
        )

        self.bot_kernel = kernel

        substitutions_file = os.path.join(config.GAME_FILES_ROOT, "AI", "substitutions.ini")
        self._update_substitutions(substitutions_file)

        """
        print ("INITIALIZED SESSION  for %s : " % name, self.data["AI_bots"]["bot_properties"][name]["bot_sessions"])
        props["bot_sessions"] = kernel.getSessionData() # IMPORTANT - initialized values, with I/O history etc.
        print ("COMMITTING DATA for %s :" % name, self.data["AI_bots"]["bot_properties"][name])
        """

    def _update_substitutions(self, substitutions_file):

        """ OBSOLETE
        subbers = self.bot_kernel._subbers
        for section_name, section in subbers.items():
            assert section_name in subbers, section_name
            for k, v in section.items():
        """
        subbers = self.bot_kernel._subbers
        del self
        with open(substitutions_file, "rb") as inFile:
            parser = ConfigParser()
            parser.readfp(inFile, substitutions_file)
            inFile.close()
            for s in parser.sections():
                assert s in subbers, (s, list(subbers.keys()))
                # iterate over the key,value pairs and add them to the subber
                for k, v in parser.items(s):
                    subbers[s][k] = v

    def respond(self, input):
        return self.bot_kernel.respond(input)

    def setSessionData(self, data):
        self.bot_kernel.setSessionData(data)

    def getSessionData(self):
        return self.bot_kernel.getSessionData()

    def setBotPredicate(self, key, value):
        self.bot_kernel.setBotPredicate(key, value)  # we change the bot personality

    def getBotPredicate(self, key):
        return self.bot_kernel.getBotPredicate(key)

    def setPredicate(self, key, value):
        self.bot_kernel.setPredicate(key, value)  # we change the context of conversation

    def getPredicate(self, key):
        return self.bot_kernel.getPredicate(key)


DJINN_PROXY_IS_INITIALIZED = False
DJINN_PROXY = None


def _activate_djinn_proxy():
    global DJINN_PROXY, DJINN_PROXY_IS_INITIALIZED, _activate_djinn_proxy
    # singleton instance #
    if config.ACTIVATE_AIML_BOTS:
        DJINN_PROXY = DjinnProxy()  # beware in prod, memory-consuming !
    else:
        DJINN_PROXY = None
        logging.warning("AI bots not initialized, so as to preserve memory")
    DJINN_PROXY_IS_INITIALIZED = True
    del _activate_djinn_proxy  # SECURITY
