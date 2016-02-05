 #!/usr/bin/env python
 # -*- coding: utf-8 -*-
import os
import sys
import logging
import setup_pychronia_env

import pychronia_game.models # initializes everything
from pychronia_game.datamanager.datamanager_administrator import get_all_instances_metadata, \
     retrieve_game_instance
from django.conf import settings
from smtplib import SMTPException
from django.core.mail import send_mail


SUBJECT = "Notification - Portail Anthropia"

TEMPLATE = """\
Cher(ère) %(username)s,

de nouveaux contenus sont apparus sur votre compte depuis votre dernier passage.

%(novelties)s

Bien à vous,
Le Portail Anthropia
"""

def execute():

    for idx, metadata in enumerate(get_all_instances_metadata(), start=1):

        successes = 0
        errors = 0

        instance_id = metadata["instance_id"]

        if metadata["status"] != "active":
            logging.info("Skipping external notifications on obsolete game instance '%s'", instance_id)
            continue

        assert metadata["status"] == "active"

        try:

            dm = retrieve_game_instance(instance_id)

            all_notifications = dm.get_characters_external_notifications()
            master_email = dm.get_global_parameter("master_real_email")

            if all_notifications:
                logging.info("Starting notification of novelties, by emails, for players of game instance '%s'", instance_id)

            for pack in all_notifications:
                username, real_email = pack["username"], pack["real_email"]
                signal_new_radio_messages, signal_new_text_messages = pack["signal_new_radio_messages"], pack["signal_new_text_messages"]

                novelties = ""
                if signal_new_radio_messages:
                    novelties += "- la liste de lecture de la webradio a été mise à jour.\n"
                if signal_new_text_messages:
                    novelties += "- vous avez reçu %s nouveaux messages textuels.\n" % signal_new_text_messages

                if not novelties:
                    continue # no news for the player

                assert novelties
                content_dict = dict(username=username,
                                    novelties=novelties)
                message = TEMPLATE % content_dict

                params = dict(subject=SUBJECT,
                              message=message,
                              from_email=settings.SERVER_EMAIL,
                              recipient_list=[real_email] + ([master_email] if master_email else []),
                              fail_silently=False)

                try:
                    logging.info("""Sending novelty notification from '%(from_email)s' to %(recipient_list)r : "%(subject)s"\n%(message)s""", params)
                    send_mail(**params)
                except (SMTPException, EnvironmentError), e:
                    logging.error("Couldn't send external notification email to %s", real_email, exc_info=True)
                    errors += 1
                else:
                    logging.info("Properly sent external notification email to %s", real_email)
                    successes += 1

        except Exception, e:
            logging.critical("Pathological error during external notifications processing on game instance '%s'", instance_id, exc_info=True)

    return (idx, successes, errors)


if __name__ == "__main__":
    execute()



