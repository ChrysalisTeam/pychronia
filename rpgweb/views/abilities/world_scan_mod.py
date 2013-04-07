# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *
from rpgweb.datamanager.abstract_ability import AbstractAbility
import functools
from rpgweb import utilities
from rpgweb.forms import ArtefactForm, UninstantiableFormError
from rpgweb.datamanager.datamanager_tools import transaction_watcher, \
    readonly_method
from rpgweb.datamanager.abstract_game_view import register_view

# TODO - change "scanning" to "scan" everywhere!!!




@register_view
class WorldScanAbility(AbstractAbility):

    TITLE = _lazy("World Scan")

    NAME = "world_scan"

    GAME_ACTIONS = dict(scan_form=dict(title=_lazy("Choose wiretapping targets"),
                                              form_class=None,
                                              callback="process_world_scan_submission"))

    TEMPLATE = "abilities/world_scan.html"

    ACCESS = UserAccess.character
    PERMISSIONS = ["world_scan", "messaging"]
    ALWAYS_AVAILABLE = True



    def get_template_vars(self, previous_form_data=None):

        try:
            scan_form = self._instantiate_form(new_action_name="scan_form",
                                                      hide_on_success=True,
                                                      previous_form_data=previous_form_data)
            specific_message = None
        except UninstantiableFormError, e:
            scan_form = None
            specific_message = unicode(e)

        return {
                 'page_title': _("World Scan"),
                 'scan_form': scan_form,
                 'specific_message': specific_message,
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

        assert utilities.check_is_range_or_num(settings["result_delay"])

        for (name, scan_set) in settings["scanning_sets"].items():
            utilities.check_is_slug(name)
            utilities.check_no_duplicates(scan_set)
            for location in scan_set:
                assert location in all_locations

        assert  set(all_artefact_items) < set(settings["item_locations"].keys())  # more might be defined in this ability
        for (item_name, scan_set_name) in settings["item_locations"].items():
            utilities.check_is_slug(item_name)  # in case it's NOT a valid item name, in unstrict mode...
            assert scan_set_name in settings["scanning_sets"].keys()

        if strict:
            assert set(settings["item_locations"].keys()) == set(all_locations)
            utilities.check_num_keys(settings, 3)

            assert not any(self.all_private_data)



    @readonly_method
    def _compute_scanning_result(self, item_name):
        assert not self.get_item_properties(item_name)["is_gem"], item_name
        # Potential evolution - in the future, it might be possible to remove some locations depending on hints provided !
        scanning_set_name = self.settings["item_locations"][item_name]
        locations = self.settings["scanning_sets"][scanning_set_name]
        return locations  # list of city names

    '''
    # WARNING - do not put inside a transaction manager, else too many levels of transaction when processing scheduled tasks...
    @transaction_watcher
    def _add_to_scanned_locations(self, locations):
        self.data["global_parameters"]["scanned_locations"] = PersistentList(set(self.data["global_parameters"][
                                                                                 "scanned_locations"] + locations)) # we let the _check_coherency system ensure it's OK
    '''


    @transaction_watcher
    def process_world_scan_submission(self, item_name):

        # here input checking has already been done by form system (item_name is required=True) #
        assert item_name, item_name

        item_title = self.get_item_properties(item_name)["title"]

        remote_email = "scanner-robot@hightech.com"  # dummy domain too
        local_email = self.get_character_email()

        # dummy request email, to allow wiretapping

        subject = "Scanning Request - \"%s\"" % item_title
        body = _("Please scan the world according to the features of this object.")
        self.post_message(local_email, remote_email, subject, body, date_or_delay_mn=0, is_read=True)


        # answer email

        scanning_delay = self.settings["result_delay"]

        locations = self._compute_scanning_result(item_name)

        locations_found = ", ".join(locations) if locations else _("None")

        item_title = self.get_item_properties(item_name)["title"]
        subject = "<World Scan Result - %(item)s>" % SDICT(item=item_title)

        body = dedent("""
                Below is the result of the scanning operation which has been performed according to the documents you sent.
                Please note that these results might be incomplete or erroneous, depending on the accuracy of the information available.

                Potential locations of similar items: "%(locations_found)s"
                """) % SDICT(locations_found=locations_found)

        attachment = None

        # # USELESS self.schedule_delayed_action(scanning_delay, "_add_to_scanned_locations", locations) # pickling instance method

        msg_id = self.post_message(remote_email, local_email, subject, body, attachment=attachment,
                                   date_or_delay_mn=scanning_delay)

        self.log_game_event(_noop("Automated scanning request sent for item '%(item_title)s'."),
                             PersistentDict(item_title=item_title),
                             url=self.get_message_viewer_url(msg_id))

        return _("World scan submission in progress, the result will be emailed to you.")

        """ Canceled for now - manual response by gamemaster, from a description of the object...
        else:
            subject = _("Scanning Request - CF description")
            body = _("Please scan the world according to this description.")
            body += "\n\n" + description
            msg_id = self.post_message(local_email, remote_email, subject, body, date_or_delay_mn=0, is_read=False,
                                       is_certified=True)
    
            self.log_game_event(_noop("Manual scanning request sent by %(username)s with description."),
                                 PersistentDict(username=username),
                                 url=self.get_message_viewer_url(msg_id)))
    
        """
