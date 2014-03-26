 #!/usr/bin/env python
 # -*- coding: utf-8 -*-
import os
import sys

import setup_pychronia_env
import pychronia_game.models # initializes everything
from pychronia_game.datamanager.datamanager_administrator import delete_game_instance, create_game_instance, \
        change_game_instance_status, UsageError


DEMO_NAME = "DEMO"

def execute():
    try:
        change_game_instance_status(DEMO_NAME, new_status="terminated")
        delete_game_instance(DEMO_NAME)
    except UsageError, e:
        print "Exception swallowed:", e
    create_game_instance(game_instance_id=DEMO_NAME, creator_login="dummy_creator")


if __name__ == "__main__":
    execute()

