# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

    OBSOLETE - ATTACKS WILL BE MANAGED BY EMAILS AT THE MOMENT

    @transaction_watcher
    def trigger_akarith_attack(self, username, city_name, message):
        # no special check is performed, as akarith agents are infiltrated about everywhere !
        user_email = self.get_character_email(username)
        recipient_emails = "acharis-army@special.com"

        subject = _("<Acharith Attack on %(city_name)s>") % SDICT(city_name=city_name.capitalize())

        local_finish_time = utilities.utc_to_local(self.compute_effective_remote_datetime(self.get_global_parameter("akarith_attack_delays")))
        local_finish_time_str = local_finish_time.strftime("%H:%M:%S")

        body = (_("*** termination planned at %(time)s ***") % SDICT(time=local_finish_time_str) + "\n\n" + message)
        attachment = None

        msg_id = self.post_message(user_email, recipient_emails, subject, body, attachment, date_or_delay_mn=0,
                                   is_certified=True)

        self.log_game_event(
            ugettext_noop("Acharith attack launched by %(username)s on %(city_name)s, terminating at %(time)s."),
            PersistentMapping(username=username, city_name=city_name, time=local_finish_time_str),
            url=self.get_message_viewer_url_or_none(msg_id))


    @transaction_watcher
    def trigger_teldorian_teleportation(self, username, city_name, message):
        if self.get_global_parameter("teldorian_teleportations_done") >= self.get_global_parameter(
            "max_teldorian_teleportations"):
            raise UsageError(
                _("Teleporters have exhausted all their energy, no more operations possible before two days."))

        is_scanned = (city_name in self.get_global_parameter("scanned_locations"))

        # IMPORTANT - we do not check that city_name is in scanned locations, as teldorians might arbitrarily teleport to save Cynthia too !

        user_email = self.get_character_email(username)
        recipient_emails = "teldorian-army@special.com"

        subject = _("<Teldorian Teleportation on %(scan_state)s location %(city_name)s>") % SDICT(
            scan_state=(_("scanned") if is_scanned else _("unscanned")), city_name=city_name.capitalize())

        local_finish_time = utilities.utc_to_local(self.compute_effective_remote_datetime(self.get_global_parameter("teldorian_teleportation_delays")))
        local_finish_time_str = local_finish_time.strftime("%H:%M:%S")

        body = _("*** termination planned at %(time)s ***") % SDICT(time=local_finish_time_str) + "\n\n" + message

        attachment = None

        msg_id = self.post_message(user_email, recipient_emails, subject, body, attachment, date_or_delay_mn=0,
                                   is_certified=True)

        self.data["global_parameters"]["teldorian_teleportations_done"] += 1 # IMPORTANT

        self.log_game_event(
            ugettext_noop("Teldorian teleportation launched by %(username)s on %(city_name)s, terminating at %(time)s."),
            PersistentMapping(username=username, city_name=city_name, time=local_finish_time_str),
            url=self.get_message_viewer_url_or_none(msg_id))


    @transaction_watcher
    def trigger_masslavian_mercenary_intervention(self, username, city_name, message):
        if not self.get_locations()[city_name]["has_mercenary"]:
            raise UsageError(_("You must first hire mercenaries for this city"))

        user_email = self.get_character_email(username)
        recipient_emails = "masslavian-army@special.com"

        subject = _("<Mercenary Intervention on %(city_name)s>") % SDICT(city_name=city_name.capitalize())

        local_finish_time = utilities.utc_to_local(self.compute_effective_remote_datetime(self.get_global_parameter("mercenary_intervention_delays")))
        local_finish_time_str = local_finish_time.strftime("%H:%M:%S")

        body = _("*** termination planned at %(time)s ***") % SDICT(time=local_finish_time_str) + "\n\n" + message

        attachment = None

        msg_id = self.post_message(user_email, recipient_emails, subject, body, attachment, date_or_delay_mn=0,
                                   is_certified=True)

        self.log_game_event(
            ugettext_noop("Mercenary intervention launched by %(username)s on %(city_name)s, terminating at %(time)s."),
            PersistentMapping(username=username, city_name=city_name, time=local_finish_time_str),
            url=self.get_message_viewer_url_or_none(msg_id))




