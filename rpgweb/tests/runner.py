#!/usr/bin/env python

import sys, os
os.environ["DJANGO_SETTINGS_MODULE"] = settings_module = "rpgweb.tests._persistent_settings" # with DB not in temp dir

from django.core.management import execute_from_command_line
from django.conf import settings

if __name__ == "__main__":
    
    arguments = [arg.lower() for arg in sys.argv]
    
    if any(help_key in arguments for help_key in ("help", "-h", "--help")):
        print "Usage: python %s [reset_django|reset_zodb|pack|runserver]" % sys.argv[0]
        print "- reset_zodb: reset ZODB databases (game data) to their initial state"
        print "- reset_django: reset django databases (authentication sessions) to their initial state"
        print "- pack: cleans and compresses ZODB file, in case it gets too heavy (test server must not be running)"
        print "- runserver: run local django dev server, against persistent databases"
        sys.exit(1)
          
    elif "reset_zodb" in arguments:
        if os.path.exists(settings.ZODB_FILE):
            os.remove(settings.ZODB_FILE)
        import rpgweb.views # initialize everything
        from rpgweb.datamanager.datamanager_administrator import reset_zodb_structure, create_game_instance
        reset_zodb_structure()
        create_game_instance(game_instance_id="DEMO", master_email="dummy@dummy.fr", master_login="master", master_password="ultimate")
                    

    elif "reset_django" in arguments:
        sys.argv[1:] = ("syncdb --noinput --settings=%s" % settings_module).split()
        execute_from_command_line()
        sys.argv[1:] = ("flush --noinput --settings=%s" % settings_module).split()
        execute_from_command_line()
    
    elif "pack" in arguments:
        from rpgweb import utilities
        DB = utilities.open_zodb_file(utilities.config.ZODB_FILE)
        DB.pack(days=1)
        print "Successfully packed ZODB items older than 1 day in %s" % utilities.config.ZODB_FILE
        
    else:
        sys.argv[1:] = ("runserver 127.0.0.1:8000 --settings=%s" % settings_module).split() # beware, with auto-reload this is applied twice...
        execute_from_command_line()
    
 

