# -*- coding: utf-8 -*-
from django.utils.translation import ugettext_lazy

from pychronia_game.common import *
from .runic_translation_mod import RunicTranslationAbility
from ...datamanager import register_view, transaction_watcher


@register_view
class OpenRunicTranslationAbility(RunicTranslationAbility):
    TITLE = ugettext_lazy("Open Runic Translation")
    NAME = "runic_translation_open"

    ACCESS = UserAccess.anonymous
    REQUIRES_CHARACTER_PERMISSION = False
    REQUIRES_GLOBAL_PERMISSION = False

    TEMPLATE = "abilities/runic_translation_open.html"

    # HACKS
    result_message = None
    transcription = None

    def get_template_vars(self, previous_form_data=None):
        res = super().get_template_vars(previous_form_data=previous_form_data)
        res["result_message"] = self.result_message
        return res

    @transaction_watcher
    def process_translation(self, transcription="", use_gems=()):
        """
        Parameter target_item may be None (auto detection).
        """
        transcription = transcription.strip() if transcription else transcription
        if not transcription:
            raise UsageError(_("The transcription submitted is empty."))

        item_name = self._get_closest_item_name_or_none(
            decoding_attempt=transcription)  # will always return non-None, unless no objects are translatable

        if not item_name:
            raise UsageError(_("No matching runic pattern found."))

        translation = self._translate_rune_message(item_name=item_name, rune_transcription=transcription)
        del item_name

        result_message = dedent(_("""
                        Below is the output of the automated translation process for the runes of the targeted object.
                        Please note that any error in the decoding of runes may lead to important errors in the translation result.

                        Runes transcription: "%(original)s"

                        Translation result: "%(translation)s"
                      """)) % SDICT(original=transcription, translation=translation)

        # HACKS to transmit data to TEMPLATE and FORM!
        self.transcription = transcription
        self.result_message = result_message

        return _("Runic transcription successfully submitted, see results below.")
