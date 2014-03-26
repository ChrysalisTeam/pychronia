 #!/usr/bin/env python
 # -*- coding: utf-8 -*-
import os
import sys
import logging
import setup_pychronia_env
import pychronia_game.models # initializes everything
from pychronia_game.datamanager.datamanager_administrator import backup_game_instance_data, get_all_instances_metadata      
 
 
def execute():
    for idx, metadata in enumerate(get_all_instances_metadata(), start=1):
        instance_id = metadata["instance_id"]
        backup_game_instance_data(instance_id, comment="nightly_autosave")
        logging.info("Game instance '%s' well autosaved", instance_id)

    logging.info("All %s game instances were well autosaved" % idx)
    return idx
 

if __name__ == "__main__":
    execute()
    
