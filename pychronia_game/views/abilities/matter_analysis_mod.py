# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from pychronia_game.common import *

from pychronia_game.datamanager.abstract_ability import AbstractPartnershipAbility
from pychronia_game.forms import ArtefactForm, UninstantiableFormError
from pychronia_game.datamanager import readonly_method, \
    transaction_watcher

'''
class PersonalItemForm(AbstractGameForm):

    def __init__(self, datamanager, *args, **kwargs):
        super(PersonalItemForm, self).__init__(datamanager, *args, **kwargs)

        _objects = datamanager.get_available_items_for_user()
        _objects_choices = [("", _("Choose..."))] + [(item_name, _objects[item_name]["title"]) for item_name in sorted(_objects.keys())]

        self.fields["item_name"] = forms.ChoiceField(label=ugettext_lazy(u"Item"), choices=_objects_choices)

        assert self.fields.keyOrder # if reordering needed
'''


class MatterAnalysisAbility(AbstractPartnershipAbility):

    TITLE = ugettext_lazy("Biophysical Analysis")
    NAME = "matter_analysis"

    GAME_ACTIONS = dict(process_artefact=dict(title=ugettext_lazy("Process object analysis"),
                                                      form_class=ArtefactForm,
                                                      callback="process_object_analysis"))


    TEMPLATE = "abilities/matter_analysis.html"

    ACCESS = UserAccess.character
    REQUIRES_CHARACTER_PERMISSION = False
    REQUIRES_GLOBAL_PERMISSION = True


    def get_template_vars(self, previous_form_data=None):

        # for now we don't exclude objects already analysed, players just have to take care !
        try:
            item_form = self._instantiate_game_form(new_action_name="process_artefact",
                                                 hide_on_success=True,
                                                 previous_form_data=previous_form_data,
                                                 propagate_errors=True)
            specific_message = None
        except UninstantiableFormError, e:
            item_form = None
            specific_message = unicode(e)

        return {
                 'page_title': _("Deep Matter Analysis"),
                 'item_form': item_form,
                 'specific_message': specific_message, # TODO FIXME DISPLAY THIS
               }



    @readonly_method
    def _compute_analysis_result(self, item_name):
        assert not self.get_item_properties(item_name)["is_gem"], item_name
        report = self.settings["reports"].get(item_name, None)
        if report is None:
            raise NormalUsageError(_("Unfortunately this item can't be analyzed by our biophysical lab.")) # any payment will be aborted too
        return report


    @transaction_watcher
    def process_object_analysis(self, item_name, use_gems=()):

        assert item_name in self.datamanager.get_available_items_for_user(), item_name

        item_title = self.get_item_properties(item_name)["title"]

        user_email = self.get_character_email()

        # dummy request email, to allow wiretapping

        subject = "Deep Analysis Request - item \"%s\"" % item_title
        body = _("Please analyse the physical and biological properties of this item.")
        self.post_message(user_email, self.dedicated_email, subject, body, date_or_delay_mn=None, is_read=True)


        # answer from laboratory

        subject = _("<Deep Matter Analysis Report - %(item_title)s>") % SDICT(item_title=item_title)
        body = self._compute_analysis_result(item_name)

        msg_id = self.send_back_processing_result(user_email=user_email, subject=subject, body=body, attachment=None)

        self.log_game_event(ugettext_noop("Item '%(item_title)s' sent for deep matter analysis."),
                             PersistentDict(item_title=item_title),
                             url=self.get_message_viewer_url(msg_id))

        return _("Item '%s' successfully submitted, you'll receive the result by email") % item_title



    @classmethod
    def _setup_ability_settings(cls, settings):
        pass  # nothing to do

    def _setup_private_ability_data(self, private_data):
        pass  # nothing to do


    def _check_data_sanity(self, strict=False):

        settings = self.settings

        def reports_checker(reports):
            utilities.assert_set_smaller_or_equal(reports.keys(), self.get_non_gem_items().keys()) # some items might have no analysis data
            for body in reports.values():
                utilities.check_is_restructuredtext(body)
            return True

        _reference = dict(
                            reports=reports_checker,
                         )
        utilities.check_dictionary_with_template(settings, _reference, strict=False)


