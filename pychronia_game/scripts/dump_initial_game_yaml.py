#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import logging

import setup_pychronia_env   # NOW ONLY

from pychronia_game import utilities
from pychronia_game.datamanager import GameDataManager, PersistentMapping



def execute(output_file):
    """
    Dumping initial game data is especially useful for murder-party sheet generators
    which rely on some data from it (encyclopedia articles, text messages, objects...)
    """

    print(">> Generating transient game data manager instance")

    dm = GameDataManager(game_instance_id="temp_dumper_instance",
                         game_root=PersistentMapping(),
                         request=None)  # no user messages possible here

    assert not dm.is_initialized
    dm.reset_game_data(strict=False,
                       skip_randomizations=True,
                       skip_initializations=False,
                       skip_coherence_check=False,
                       yaml_fixture=False)

    json_bytes_str = utilities.dump_data_tree_to_yaml(dm.data,
                                                      convert=True,  # should be output in UTF8
                                                      default_style="|")  # will output very long lines

    print((">> Dumping whole initial data to file %r" % output_file))

    with open(output_file, "wb") as f:
        f.write(json_bytes_str)



if __name__ == "__main__":
    output_file = "initial_data_dump.yaml"
    if len(sys.argv) > 1:
        output_file = sys.argv[1]
    execute(output_file)
