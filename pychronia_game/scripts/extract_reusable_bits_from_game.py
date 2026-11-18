#!/usr/bin/env python
import sys
import setup_pychronia_env  # noqa: F401

from pychronia_game.datamanager.datamanager_administrator import retrieve_game_instance
from pychronia_game import utilities


def execute(instance_id):
    dm = retrieve_game_instance(instance_id)

    msgs = dm.get_all_dispatched_messages()

    tpls = [dm.convert_msg_to_template(msg) for msg in msgs]
    # pprint.pprint(tpls)

    yaml_str = utilities.dump_data_tree_to_yaml(tpls, default_style=">", width=100)
    yaml_str = yaml_str.replace("\n-", "\n\n\n-")  # separate atomic templates

    output_file = "%s_extracted_message_templates.yaml" % instance_id
    utilities.write_to_file(output_file, content=yaml_str)

    # print(data)
    print(">> Extract file %s successfully created" % output_file)


if __name__ == "__main__":
    execute(sys.argv[1])  # please provide game instance id on cmd line
