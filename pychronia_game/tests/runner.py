#!/usr/bin/env python

import sys, os, warnings

root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))  # CHRYSALIS/ root dir
sys.path.insert(0, root)
sys.path.insert(0, os.path.join(root, "dependencies"))
#print ">>>>>>>", sys.path

os.environ["DJANGO_SETTINGS_MODULE"] = settings_module = "pychronia_game.tests.persistent_mode_settings"  # with DB not in temp dir

import setup_pychronia_env

from django.core.management import execute_from_command_line
from django.conf import settings

""" COULD BE USEFUL
from django.core.management import call_command
call_command('my_command', 'foo', bar='baz')
"""

if __name__ == "__main__":

    arguments = [arg.lower() for arg in sys.argv]

    if any(help_key in arguments for help_key in ("help", "-h", "--help")):
        print "Usage: python %s [reset_django|reset_zodb|pack_file|runserver]" % sys.argv[0]
        print "- reset_zodb: reset ZODB databases (game data) to their initial state"
        print "- reset_django: reset django databases (authentication sessions) to their initial state"
        print "- pack_file: cleans and compresses ZODB file, in case it gets too heavy (test server must not be running)"
        print "- runserver: run local django dev server, against persistent databases"
        sys.exit(1)

    elif "reset_zodb" in arguments:
        if os.path.exists(settings.ZODB_FILE):
            os.remove(settings.ZODB_FILE)
        import pychronia_game.models  # initializes everything
        from pychronia_game.datamanager.datamanager_administrator import reset_zodb_structure, create_game_instance

        reset_zodb_structure()

        if "use_fixture" in arguments:
            skip_initializations = True
            skip_randomizations = True
            yaml_fixture = os.path.join(settings.GAME_FILES_ROOT, "script_fixtures", "_PROD_DUMP.yaml")
        else:
            skip_initializations = False
            skip_randomizations = False
            yaml_fixture = None
        create_game_instance(game_instance_id="DEMO",
                             creator_login="ze_creator",
                             skip_initializations=skip_initializations,
                             yaml_fixture=yaml_fixture,
                             skip_randomizations=skip_randomizations)

    elif "reset_django" in arguments:
        if not settings.DEBUG:
            raise RuntimeError("Can't reset django DB in non-DEBUG mode")
        sys.argv[1:] = ("migrate --noinput --settings=%s" % settings_module).split()
        execute_from_command_line()
        sys.argv[1:] = ("flush --noinput --settings=%s" % settings_module).split()
        execute_from_command_line()


    elif "pack_file" in arguments:
        from pychronia_game import utilities

        assert utilities.config.ZODB_FILE
        DB = utilities.open_zodb_file(utilities.config.ZODB_FILE)  # only works if we use a local ZODB file
        DB.pack(days=1)
        print "Successfully packed ZODB items older than 1 day in %s" % utilities.config.ZODB_FILE

    else:
        sys.argv[1:] = (
        "runserver 127.0.0.1:8000 --settings=%s" % settings_module).split()  # beware, with auto-reload this is applied twice...
        execute_from_command_line()
