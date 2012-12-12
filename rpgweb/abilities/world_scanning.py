# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *
from ._abstract_ability import *
import functools
from rpgweb import utilities

# TODO - change "scanning" to "scan" everywhere!!!


@register_view
class WorldScanAbility(AbstractAbility):

    TITLE = _lazy("World Scan")

    NAME = "world_scan"

    #GAME_FORMS = {"artefact_form": (WiretappingTargetsForm, "change_current_user_wiretapping_targets")}
    ADMIN_FORMS = {}
    ACTION_FORMS = {}

    TEMPLATE = "abilities/world_scan.html"

    ACCESS = UserAccess.authenticated
    PERMISSIONS = ["world_scan", "messaging"]
    ALWAYS_AVAILABLE = False



    def get_template_vars(self, previous_form_data=None):

        """
        translation_form = self._instantiate_form(new_form_name="translation_form",
                                                  hide_on_success=False,
                                                  previous_form_data=previous_form_data)
        """
        return {
                 'page_title': _("World Scan"),

               }




    @classmethod
    def _setup_ability_settings(cls, settings):
        for (name, scan_set) in settings["scanning_sets"].items():
            if scan_set == "__everywhere__":
                settings["scanning_sets"][name] = self.get_locations().keys()


    def _setup_private_ability_data(self, private_data):
        pass # at the moment we don't care about the history of scans performed


    def _check_data_sanity(self, strict=False):

        settings = self.settings

        all_artefact_items = self.get_all_items().keys()
        all_locations = self.get_locations().keys()

        for (name, scan_set) in settings["scanning_sets"].items():
            utilities.check_is_slug(name)
            utilities.check_no_duplicates(scan_set)
            for location in scan_set:
                assert location in all_locations

        for (name, scan_set) in settings["item_locations"].items():
            assert
            utilities.check_no_duplicates(scan_set)
            for location in scan_set:
                assert location in all_locations


        if strict:
            utilities.check_num_keys(settings, 1)

            assert not any(self.all_private_data)



    @readonly_method
    def _compute_scanning_result(self, item_name):
        # Potential evolution - In the future, it might be possible to remove some locations depending on hints provided !
        item_properties = self.get_item_properties(item_name)
        scanning_set_name = item_properties["locations"]
        locations = self.settings["scanning_sets"][scanning_set_name]
        return locations # list of city names

    '''
    # WARNING - do not put inside a transaction manager, else too many levels of transaction when processing scheduled tasks...
    @transaction_watcher
    def _add_to_scanned_locations(self, locations):
        self.data["global_parameters"]["scanned_locations"] = PersistentList(set(self.data["global_parameters"][
                                                                                 "scanned_locations"] + locations)) # we let the _check_coherency system ensure it's OK
    '''


    @transaction_watcher
    def process_scanning_submission(self, username, item_name):

        # here input checking has already been done by form system

        remote_email = "scanner-robot@hightech.com"  # dummy domain too
        local_email = self.get_character_email(username)


        # dummy request email, to allow wiretapping

        subject = "Scanning Request - item \"%s\"" % item_name
        body = _("Please scan the world according to the features of this object.")
        self.post_message(local_email, remote_email, subject, body, date_or_delay_mn=0, is_read=True)


        # answer email

        scanning_delay = self.get_global_parameter("scanning_delays")

        item_title = self.get_item_properties(item_name)["title"]

        locations = self._compute_scanning_result(item_name)

        locations_found = ", ".join(locations) #, additional_hints))

        subject = "<World Scan Result - %(item)s>" % SDICT(item=item_title)

        body = dedent("""
                Below is the result of the scanning operation which has been performed according to the documents you sent.
                Please note that these results might be incomplete or erroneous, depending on the accuracy of the information available.

                Potential locations of similar items: "%(locations_found)s"
                """) % SDICT(locations_found=locations_found)

        attachment = None

        ## USELESS self.schedule_delayed_action(scanning_delay, "_add_to_scanned_locations", locations) # pickling instance method

        msg_id = self.post_message(remote_email, local_email, subject, body, attachment=attachment,
                                   date_or_delay_mn=scanning_delay)

        self.log_game_event(_noop("Automated scanning request sent by %(username)s for item '%(item_title)s'."),
                             PersistentDict(username=username, item_title=item_title),
                             url=self.get_message_viewer_url(msg_id))

        return msg_id

        """ Canceled for now - manual resposne by gamemaster, following a description of the object...
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
