# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from pychronia_game.common import *
from pychronia_game.datamanager.abstract_ability import AbstractPartnershipAbility
import functools
from pychronia_game import utilities
from pychronia_game.forms import ArtefactForm, UninstantiableFormError
from pychronia_game.datamanager.datamanager_tools import transaction_watcher, \
    readonly_method
from pychronia_game.datamanager.abstract_game_view import register_view


# TODO - change "scanning" to "scan" everywhere!!!




@register_view
class WorldScanAbility(AbstractPartnershipAbility):
    TITLE = ugettext_lazy("World Scan")

    NAME = "world_scan"

    GAME_ACTIONS = dict(scan_form=dict(title=ugettext_lazy("Choose world scan model"),
                                       form_class=ArtefactForm,
                                       callback="process_world_scan_submission"))

    TEMPLATE = "abilities/world_scan.html"

    ACCESS = UserAccess.character
    REQUIRES_CHARACTER_PERMISSION = True
    REQUIRES_GLOBAL_PERMISSION = True

    def get_template_vars(self, previous_form_data=None):

        try:
            scan_form = self._instantiate_game_form(new_action_name="scan_form",
                                                    hide_on_success=False,
                                                    previous_form_data=previous_form_data,
                                                    propagate_errors=True, )
            specific_message = None
        except UninstantiableFormError, e:
            scan_form = None
            specific_message = unicode(e)

        return {
            'page_title': _("World Scan"),
            'scan_form': scan_form,
            'specific_message': specific_message,  # TODO FIXME DISPLAY THIS
        }

    @classmethod
    def _setup_ability_settings(cls, settings):
        pass
        '''
        for (name, scan_set) in settings["scanning_sets"].items():
            if scan_set == "__everywhere__":
                settings["scanning_sets"][name] = self.get_locations().keys()
        '''

    def _setup_private_ability_data(self, private_data):
        pass  # at the moment we don't care about the history of scans performed

    def _check_data_sanity(self, strict=False):

        settings = self.settings

        all_artefact_items = self.get_non_gem_items().keys()
        all_locations = self.get_locations().keys()

        for (name, scan_set) in settings["scanning_sets"].items():
            utilities.check_is_slug(name)
            utilities.check_no_duplicates(scan_set)
            utilities.usage_assert(scan_set, comment=name)  # NOT EMPTY
            for location in scan_set:
                assert location in all_locations, location

        # for now items can't be deleted, so we're OK
        utilities.assert_set_smaller_or_equal(settings["item_locations"].keys(),
                                              all_artefact_items)  # some items might have no scanning locations

        for (item_name, scan_set_details) in settings["item_locations"].items():
            utilities.check_is_slug(item_name)  # in case it's NOT a valid item name, in unstrict mode...

            if strict:
                utilities.check_num_keys(scan_set_details, 2)  # fields must be present even if None

            if scan_set_details["message"] is not None:
                utilities.check_is_string(scan_set_details["message"])
            if scan_set_details["scanning_set"] is not None:
                assert scan_set_details["scanning_set"] in settings["scanning_sets"].keys()

            # at least SOME data must be available
            assert scan_set_details["message"] or scan_set_details["scanning_set"], scan_set_details

        if strict:
            utilities.check_num_custom_settings(settings, 4)  # with dedicated email

        assert not any(x for x in self.all_private_data.values()
                       if set(x.keys()) - set(["middlewares"]))

    @readonly_method
    def _compute_scanning_result_or_none(self, item_name):
        assert not self.get_item_properties(item_name)["is_gem"], item_name
        # Potential evolution - in the future, it might be possible to remove some locations depending on hints provided !
        scanning_set_details = self.settings["item_locations"].get(item_name, None)
        if scanning_set_details is None:
            return None

        message = scanning_set_details["message"]  # might be None

        scanning_set_name = scanning_set_details["scanning_set"]  # might be None
        locations = self.settings["scanning_sets"][scanning_set_name] if scanning_set_name else None  # list of city names

        return (message, locations)  # one of them might be None

    '''
    # WARNING - do not put inside a transaction manager, else too many levels of transaction when processing scheduled tasks...
    @transaction_watcher
    def _add_to_scanned_locations(self, locations):
        self.data["global_parameters"]["scanned_locations"] = PersistentList(set(self.data["global_parameters"][
                                                                                 "scanned_locations"] + locations)) # we let the _check_coherence system ensure it's OK
    '''


    @staticmethod
    def _format_scanning_result(scanning_result):
        """
        Returns a string message suitable for inclusion in an email.
        """
        (message, locations) = scanning_result
        assert message or locations, scanning_result  # sanity check
        assert not isinstance(locations, basestring), locations  # prevent dumb bug

        locations_found = ", ".join(locations) if locations else ""

        if message:
            locations_found += "\n\n" + message

        return locations_found


    @transaction_watcher
    def process_world_scan_submission(self, item_name, use_gems=()):

        # here input checking has already been done by form system (item_name is required=True)
        assert item_name, item_name

        item_title = self.get_item_properties(item_name)["title"]

        # dummy request email, to allow wiretapping
        subject = _('<Scanning Request - "%s">') % item_title
        body = _("Please scan the world according to the features of this object.")
        request_msg_data = dict(subject=subject,
                                body=body)
        del subject, body

        # answer email
        response_msg_data = None
        scanning_result = self._compute_scanning_result_or_none(item_name)

        if scanning_result:

            locations_found_msg = self._format_scanning_result(scanning_result)

            subject = _("<World Scan Result - %(item)s>") % SDICT(item=item_title)

            body = dedent(_("""
                    Below is the result of the scanning operation which has been performed according to the documents you sent.
                    Please note that these results might be incomplete or erroneous, depending on the accuracy of the information available.
    
                    Potential locations of similar items: 
                    
                    %(locations_found)s
                    """)) % SDICT(locations_found=locations_found_msg)

            response_msg_data = dict(subject=subject,
                                     body=body,
                                     attachment=None)
            del subject, body

        best_msg_id = self._process_standard_exchange_with_partner(request_msg_data=request_msg_data,
                                                                   response_msg_data=response_msg_data)

        self.log_game_event(ugettext_noop("Automated scanning request sent for item '%(item_title)s'."),
                            PersistentMapping(item_title=item_title),
                            url=self.get_message_viewer_url_or_none(best_msg_id),  # best_msg_id might be None
                            visible_by=[self.username])

        return _("World scan submission in progress, the result will be emailed to you.")

        """ Canceled for now - manual response by gamemaster, from a description of the object...
        else:
            subject = _("Scanning Request - CF description")
            body = _("Please scan the world according to this description.")
            body += "\n\n" + description
            msg_id = self.post_message(local_email, remote_email, subject, body, date_or_delay_mn=0, is_read=False,
                                       is_certified=True)
    
            self.log_game_event(ugettext_noop("Manual scanning request sent by %(username)s with description."),
                                 PersistentMapping(username=username),
                                 url=self.get_message_viewer_url_or_none(msg_id))) # msg_id might be None
    
        """
