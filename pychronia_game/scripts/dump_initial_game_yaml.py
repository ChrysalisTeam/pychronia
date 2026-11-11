#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys

import setup_pychronia_env   # NOW ONLY

from pychronia_game import utilities
from pychronia_game.datamanager import GameDataManager, PersistentMapping


def execute(output_file, game_language=None):
    """
    Dumping initial game data is especially useful for murder-party sheet generators
    which rely on some data from it (encyclopedia articles, text messages, objects...)

    The game_language (eg. "en") selects the translated fixtures, it defaults to GAME_DEFAULT_LANGUAGE.
    """

    print(">> Generating transient game data manager instance")

    dm = GameDataManager(game_instance_id="temp_dumper_instance",
                         game_root=PersistentMapping(),
                         request=None)  # no user messages possible here

    assert not dm.is_initialized
    dm.reset_game_data(strict=False,
                       game_language=game_language,
                       skip_randomizations=True,
                       skip_initializations=False,
                       skip_coherence_check=False,
                       yaml_fixture=False)

    yaml_str = utilities.dump_data_tree_to_yaml(dm.data,
                                                convert_types=True,  # should be output in UTF8
                                                default_style="|")  # will output very long lines

    print((">> Dumping whole initial data to file %r" % output_file))

    utilities.write_to_file(output_file, content=yaml_str)


if __name__ == "__main__":
    output_file = "initial_data_dump.yaml"
    game_language = None
    if len(sys.argv) > 1:
        output_file = sys.argv[1]
    if len(sys.argv) > 2:
        game_language = sys.argv[2]
    execute(output_file, game_language=game_language)
