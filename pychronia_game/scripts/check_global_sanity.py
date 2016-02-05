 #!/usr/bin/env python
 # -*- coding: utf-8 -*-
import os
import sys
import logging
import setup_pychronia_env

import pychronia_game.models # initializes everything
from pychronia_game.datamanager.datamanager_administrator import delete_game_instance, create_game_instance, \
     change_game_instance_status, UsageError, retrieve_game_instance, get_all_instances_metadata


def execute():
    result = True
    for idx, metadata in enumerate(get_all_instances_metadata(), start=1):
        instance_id = metadata["instance_id"]
        dm = retrieve_game_instance(instance_id)
        try:
            dm.check_database_coherence(strict=True)
        except Exception, e:
            result = False
            logging.critical("Error during checking of game instance '%s'", instance_id, exc_info=True)
        else:
            logging.info("Game instance '%s' is OK", instance_id)
    return (idx, result)


if __name__ == "__main__":
    execute()

