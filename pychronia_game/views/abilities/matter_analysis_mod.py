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

        assert self.fields.keyOrder # if reordering needed OBSOLETE
'''


class MatterAnalysisAbility(AbstractPartnershipAbility):

    TITLE = ugettext_lazy("Biophysical Analysis")
    NAME = "matter_analysis"

    GAME_ACTIONS = dict(process_artefact=dict(title=ugettext_lazy("Process object analysis"),
                                                      form_class=ArtefactForm,
                                                      callback="process_object_analysis"))


    TEMPLATE = "abilities/matter_analysis.html"

    ACCESS = UserAccess.character
    REQUIRES_CHARACTER_PERMISSION = True
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
                 'specific_message': specific_message,
               }



    @readonly_method
    def _compute_analysis_result_or_none(self, item_name):
        assert not self.get_item_properties(item_name)["is_gem"], item_name

        if self.get_global_parameter("disable_automated_ability_responses"):
            return _("Result will be sent to you in a short while...") # should actually NOT be sent to user

        report = self.settings["reports"].get(item_name, None)

        return report  # might be None



    @transaction_watcher
    def process_object_analysis(self, item_name, use_gems=()):

        # here input checking has already been done by form system (item_name is required=True)
        assert item_name, item_name

        item_title = self.get_item_properties(item_name)["title"]

        # dummy request email, to allow wiretapping
        subject = "Deep Analysis Request - item \"%s\"" % item_title
        body = _("Please analyse the physical and biological properties of this item.")
        request_msg_data = dict(subject=subject,
                                body=body)
        del subject, body

        # answer from laboratory
        response_msg_data = None
        result = self._compute_analysis_result_or_none(item_name)
        if result:
            subject = _("<Deep Matter Analysis Report - %(item_title)s>") % SDICT(item_title=item_title)
            body = result  # as is
            response_msg_data = dict(subject=subject,
                                     body=body,
                                     attachment=None)
            del subject, body

        best_msg_id = self._process_standard_exchange_with_partner(request_msg_data=request_msg_data,
                                                                   response_msg_data=response_msg_data)

        self.log_game_event(ugettext_noop("Item '%(item_title)s' sent for deep matter analysis."),
                             PersistentMapping(item_title=item_title),
                             url=self.get_message_viewer_url_or_none(best_msg_id))  # best_msg_id might be None

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


