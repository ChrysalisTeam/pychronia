# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *


##INIT

for (name, scan_set) in new_data["scanning_sets"].items():
    if scan_set == "__everywhere__":
        new_data["scanning_sets"][name] = new_data["locations"].keys()


            elif name == "scanned_locations": # not used at the moment, but well...
                for city in value:
                    assert city in game_data["locations"].keys()
""" # at the moment we don't care about the number of scans performed
assert len(game_data["scanned_items"]) <= game_data["global_parameters"]["max_world_scans"]
for item_name in game_data["scanned_items"]:
    assert item_name in game_data["items_for_sale"].keys(), item_name
"""

@readonly_method
def _compute_scanning_result(self, item_name, additional_hints=None):
    item_properties = self.get_item_properties(item_name)

    locations = self.data["scanning_sets"][item_properties["locations"]]

    """ # Potential evolution - In the future, it might be possible to remove some locations depending on hints provided !

    orbs_locations = self.get_global_parameter("orbs_locations").values()
    removable_locations = set(locations) - set(orbs_locations)
    secret_features = item_properties["secret_features"]
    """
    return locations # list of city names


# WARNING - do not put inside a transaction manager, else too many levels of transaction when processing scheduled tasks...
@transaction_watcher
def _add_to_scanned_locations(self, locations):
    self.data["global_parameters"]["scanned_locations"] = PersistentList(set(self.data["global_parameters"][
                                                                             "scanned_locations"] + locations)) # we let the _check_coherency system ensure it's OK


@transaction_watcher
def process_scanning_submission(self, username, item_name, description): # additional_hints unused at the moment

    if not item_name and not description:
        raise UsageError(_("You must at least provide an object or its description to launch a scan."))

    remote_email = "scanner-robot@hightech.com"  # dummy domain too
    local_email = self.get_character_email(username)

    if item_name:
        ## WARNING - At the moment, 'description' is ignored in automated scanning process !! ##

        # request email, to allow interception

        subject = "Scanning Request - item \"%s\"" % item_name
        body = _("Please scan the world according to the features of this object.")
        if description:
            body += "\n\n" + description
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

        common_date = self.compute_remote_datetime(scanning_delay)

        self.schedule_delayed_action(common_date, "_add_to_scanned_locations", locations) # pickling instance method

        msg_id = self.post_message(remote_email, local_email, subject, body, attachment=attachment,
                                   date_or_delay_mn=common_date)

        self.log_game_event(_noop("Automated scanning request sent by %(username)s for item '%(item_title)s'."),
                             PersistentDict(username=username, item_title=item_title),
                             url=self.get_message_viewer_url(msg_id)))

    else:
        subject = _("Scanning Request - CF description")
        body = _("Please scan the world according to this description.")
        body += "\n\n" + description
        msg_id = self.post_message(local_email, remote_email, subject, body, date_or_delay_mn=0, is_read=False,
                                   is_certified=True)

        self.log_game_event(_noop("Manual scanning request sent by %(username)s with description."),
                             PersistentDict(username=username),
                             url=self.get_message_viewer_url(msg_id)))

    return msg_id
