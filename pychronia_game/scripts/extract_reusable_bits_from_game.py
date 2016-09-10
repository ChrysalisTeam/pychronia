#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import pprint
import logging
import setup_pychronia_env

import pychronia_game.models  # initializes everything
from pychronia_game.datamanager.datamanager_administrator import UsageError, retrieve_game_instance
from pychronia_game.utilities import dump_data_tree_to_yaml


def execute():
    instance_id = sys.argv[1]  # please provide game instance id on cmd line
    dm = retrieve_game_instance(instance_id)

    msgs = dm.get_all_dispatched_messages()

    tpls = [dm.convert_msg_to_template(msg) for msg in msgs]
    #pprint.pprint(tpls)

    data = dump_data_tree_to_yaml(tpls, default_style=">", width=100)
    data = data.replace("\n-", "\n\n\n-")  # separate atomic templates

    filename = "%s_extracted_message_templates.yaml" % instance_id
    with open(filename, "wb") as f:
        f.write(data)

    #print(data)
    print(">> Extract file %s successfully created" % filename)


if __name__ == "__main__":
    execute()
