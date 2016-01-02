# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from django import forms

from pychronia_game.common import *
from pychronia_game.datamanager.abstract_ability import AbstractPartnershipAbility
from pychronia_game.datamanager import readonly_method, \
    transaction_watcher
from pychronia_game.datamanager import readonly_method, \
    transaction_watcher
from pychronia_game.forms import AbstractGameForm
from pychronia_game.datamanager.abstract_game_view import register_view


class TranslationForm(AbstractGameForm):
    def __init__(self, ability, *args, **kwargs):
        super(TranslationForm, self).__init__(ability, *args, **kwargs)

        ''' No need to specify object anymore - auto detect!!
        
        _translatable_items_ids = ability.get_translatable_items().keys()
        _translatable_items_pretty_names = [ability.get_all_items()[item_name]["title"] for item_name in _translatable_items_ids]
        _translatable_items_choices = zip(_translatable_items_ids, _translatable_items_pretty_names)
        _translatable_items_choices.sort(key=lambda double: double[1])
        # WARNING - we always put ALL runic items, even before they have been sold at auction - it's OK !
        self.fields["target_item"] = forms.ChoiceField(label=_("Object"), choices=_translatable_items_choices)
        '''

        self.fields["transcription"] = forms.CharField(label=_("Transcription"), required=True, widget=forms.Textarea(attrs={'rows': '5', 'cols':'30'}))


@register_view
class RunicTranslationAbility(AbstractPartnershipAbility):

    TITLE = ugettext_lazy("Runic Translation")
    NAME = "runic_translation"

    GAME_ACTIONS = dict(translation_form=dict(title=ugettext_lazy("Translate runes"),
                                              form_class=TranslationForm,
                                              callback="process_translation"))

    TEMPLATE = "abilities/runic_translation.html"

    ACCESS = UserAccess.character # game master not welcome!
    REQUIRES_CHARACTER_PERMISSION = True
    REQUIRES_GLOBAL_PERMISSION = True

    def get_template_vars(self, previous_form_data=None):

        translation_form = self._instantiate_game_form(new_action_name="translation_form",
                                                  hide_on_success=False,
                                                  previous_form_data=previous_form_data)

        translation_delay = self.get_ability_parameter("result_delay")  # TODO - translate this

        return {
                 'page_title': _("Runic translations"),
                 "translation_form": translation_form,
                 'min_delay_mn': translation_delay[0],
                 'max_delay_mn': translation_delay[1],
               }



    @staticmethod
    def _normalize_string(string):
        # removes exceeding spaces, newlines and tabs in the string
        return " ".join(string.replace("\t", " ").replace("\n", " ").split())


    @readonly_method
    def get_translatable_items(self):
        return self.settings["references"]

    @classmethod
    def _tokenize_rune_message(cls, string):  # , left_to_right=True, top_to_bottom=True
        # parses a string of tokens separated by '#' (clauses) and '|' (word groups)

        string = cls._normalize_string(string)

        clauses = string.split("#")

        # if not top_to_bottom:
        #    clauses.reverse()

        clauses = [clause.split("|") for clause in clauses]  # list of lists

        # if not left_to_right:
        #    for clause in clauses:
        #        clause.reverse()

        words = [word.strip() for clause in clauses for word in clause if word.strip()]  # flattened list of 'words' (actually, groups of tokens)

        return words

    @classmethod
    def _build_translation_dictionary(cls, real_rune_string, translated_string):

        real_rune_tokens = cls._tokenize_rune_message(real_rune_string)
        translated_tokens = cls._tokenize_rune_message(translated_string)

        assert len(real_rune_tokens) == len(translated_tokens), "Mismatch between runes and real tokens"
        assert len(set(real_rune_tokens)) == len(real_rune_tokens), "No unicity of real rune tokens"  # rune phrases must be unique in the message, to allow proper translation

        translator = PersistentMapping(zip(real_rune_tokens, translated_tokens))
        return translator

    @classmethod
    def _try_translating_runes(cls, decoded_rune_string, translator, random_words, random_seed=None):
        """
        Returns an array of guessed word groups.
        
        Parameter random_seed, if not None, is used to initialize the random generator.
        """

        assert len(random_words) >= 5, random_words

        my_random = random.Random(x=random_seed)

        # we remove characters that could interfere with the parsing
        punctuation_chars = list(".,?!;:|#")
        for punctuation_char in punctuation_chars:
            decoded_rune_string = decoded_rune_string.replace(punctuation_char, " ")

        decoded_rune_string = cls._normalize_string(decoded_rune_string)

        keywords = None
        for token in translator.keys():
            """
            if not token:
                print ">>>>>>>>", translator
                traceback.print_stack()
            """
            new_keyword = pyparsing.Keyword(token)
            if keywords is None:
                keywords = new_keyword
            else:
                keywords = keywords ^ new_keyword

        # if not a keyword, it's a random word
        default_tokens = pyparsing.Word(pyparsing.printables)
        if keywords is None:
            all_tokens = default_tokens
        else:
            all_tokens = keywords ^ default_tokens

        parser = pyparsing.ZeroOrMore(all_tokens)

        parsed_decoded_rune = parser.parseString(decoded_rune_string)

        translated_tokens = []
        for token in parsed_decoded_rune:
            if translator.has_key(token):
                translated_tokens.append(translator[token])
            else:
                translated_tokens.append(my_random.choice(random_words))

        return translated_tokens


    @readonly_method
    def _get_closest_item_name_or_none(self, decoding_attempt):
        """
        Used to determine object which is most likely to carry these runes,
        for when user doesn't (or can't) explicitly select one (eg. he doesn't 
        own the object).
        
        Returns an item name or None (if no object is translatable).
        """
        all_translation_settings = self.get_ability_parameter("references")

        if not all_translation_settings:
            return None

        results = dict((utilities.string_similarity(decoding_attempt, translation_settings["decoding"]), item_name)
                        for item_name, translation_settings in all_translation_settings.items())

        best_score = min(results.keys())

        return results[best_score] # positive integer, 0 <=> equality of compared strings


    @readonly_method
    def _translate_rune_message(self, item_name, rune_transcription):
        assert item_name is None or item_name # may be unknown
        assert rune_transcription

        if not item_name or item_name not in self.get_ability_parameter("references").keys():
            translator = {}  # we let random words translation deal with that
        else:
            translation_settings = self.get_ability_parameter("references")[item_name]
            translator = self._build_translation_dictionary(translation_settings["decoding"],
                                                            translation_settings["translation"])

        random_words = self.get_ability_parameter("random_translation_words").split()
        translated_tokens = self._try_translating_runes(rune_transcription, translator=translator,
                                                        random_words=random_words, random_seed=self.get_global_parameter("game_random_seed"))

        return " ".join(translated_tokens)


    @transaction_watcher
    def process_translation(self, transcription="", use_gems=()):
        """
        Parameter target_item may be None (auto detection).
        """
        transcription = transcription.strip() if transcription else transcription
        if not transcription:
            raise UsageError(_("The transcription submitted is empty."))

        # dummy request email, to allow wiretapping
        subject = _('Translation Request')
        body = _("Runes: ") + transcription
        request_msg_data = dict(subject=subject,
                                body=body)
        del subject, body

        # answer from laboratory
        response_msg_data = None
        item_title = None
        item_name = self._get_closest_item_name_or_none(decoding_attempt=transcription)  # will always return non-None, unless no objects are translatable
        if item_name:
            translation = self._translate_rune_message(item_name=item_name, rune_transcription=transcription)
            item_title = item_name or _("unknown")
            del item_name

            subject = "<Rune Translation Result>"
            body = dedent("""
                            Below is the output of the automated translation process for the runes of the targeted object.
                            Please note that any error in the decoding of runes may lead to important errors in the translation result.
    
                            Runes transcription: "%(original)s"
    
                            Translation result: "%(translation)s"
                          """) % SDICT(original=transcription, translation=translation)

            response_msg_data = dict(subject=subject,
                                     body=body,
                                     attachment=None)
            del subject, body

        best_msg_id = self._process_standard_exchange_with_partner(request_msg_data=request_msg_data,
                                                                   response_msg_data=response_msg_data)

        self.log_game_event(ugettext_noop("Translation request submitted (presumably for item '%(item_title)s')."),
                              PersistentMapping(item_title=item_title),
                              url=self.get_message_viewer_url_or_none(best_msg_id),  # best_msg_id might be None
                              visible_by=[self.username])

        return _("Runic transcription successfully submitted, the result will be emailed to you.")


    @classmethod
    def _setup_ability_settings(cls, settings):
        pass  # Nothing to do, all translation data must be fully present in initial fixture

    def _setup_private_ability_data(self, private_data):
        pass  # nothing stored here at the moment


    def _check_data_sanity(self, strict=False):

        settings = self.settings

        utilities.check_is_string(settings["random_translation_words"])
        references = settings["references"]

        if strict:
            utilities.check_num_keys(settings, 3)

        for (name, properties) in references.items():
            if strict:
                utilities.check_num_keys(properties, 2)
            assert name in self.get_all_items().keys(), name
            utilities.check_is_string(properties["decoding"])
            utilities.check_is_string(properties["translation"])
            assert self._build_translation_dictionary(properties["decoding"], properties["translation"])  # we ensure tokens are well matching

        if strict:
            assert not any(self.all_private_data)

