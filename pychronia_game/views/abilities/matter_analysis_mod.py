# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from pychronia_game.common import *

from pychronia_game.datamanager.abstract_ability import AbstractAbility
from pychronia_game.forms import ArtefactForm, UninstantiableFormError
from pychronia_game.datamanager import readonly_method, \
    transaction_watcher

'''
class PersonalItemForm(AbstractGameForm):

    def __init__(self, datamanager, *args, **kwargs):
        super(PersonalItemForm, self).__init__(datamanager, *args, **kwargs)

        _objects = datamanager.get_available_items_for_user()
        _objects_choices = [("", _("Choose..."))] + [(item_name, _objects[item_name]["title"]) for item_name in sorted(_objects.keys())]

        self.fields["item_name"] = forms.ChoiceField(label=_lazy(u"Item"), choices=_objects_choices)

        assert self.fields.keyOrder # if reordering needed
'''


class MatterAnalysisAbility(AbstractAbility):

    TITLE = _lazy("Biophysical Analysis")
    NAME = "matter_analysis"

    GAME_ACTIONS = dict(process_artefact=dict(title=_lazy("Process artefact analysis"),
                                                      form_class=ArtefactForm,
                                                      callback="process_artefact_analysis"))


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
        report = self.settings["reports"][item_name]
        return report


    @transaction_watcher
    def process_artefact_analysis(self, item_name):

        assert item_name in self.datamanager.get_available_items_for_user(), item_name

        item_title = self.get_item_properties(item_name)["title"]

        remote_email = self.settings["sender_email"]
        local_email = self.get_character_email()

        # dummy request email, to allow wiretapping

        subject = "Deep Analysis Request - item \"%s\"" % item_title
        body = _("Please analyse the physical and biological properties of this item.")
        self.post_message(local_email, remote_email, subject, body, date_or_delay_mn=0, is_read=True)


        # answer from laboratory

        subject = _("<Deep Matter Analysis Report - %(item_title)s>") % SDICT(item_title=item_title)
        body = self._compute_analysis_result(item_name)

        self.post_message(remote_email, local_email, subject, body=body, attachment=None,
                          date_or_delay_mn=self.settings["result_delay"])

        self.log_game_event(_noop("Item '%(item_title)s' sent for deep matter analysis."),
                             PersistentDict(item_title=item_title),
                             url=None)

        return _("Item '%s' successfully submitted, you'll receive the result by email") % item_title



    @classmethod
    def _setup_ability_settings(cls, settings):
        pass  # nothing to do

    def _setup_private_ability_data(self, private_data):
        pass  # nothing to do


    def _check_data_sanity(self, strict=False):

        settings = self.settings

        def reports_checker(reports):
            utilities.assert_sets_equal(reports.keys(), self.get_non_gem_items().keys())
            for body in reports.values():
                utilities.check_is_restructuredtext(body)
            return True

        _reference = dict(
                            sender_email=utilities.check_is_email,
                            result_delay=utilities.check_is_range_or_num,
                            reports=reports_checker,
                         )
        utilities.check_dictionary_with_template(settings, _reference, strict=strict)


