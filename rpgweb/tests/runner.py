#!/usr/bin/env python

import sys, os

os.environ["DJANGO_SETTINGS_MODULE"] = settings_module = "rpgweb.tests._persistent_settings" # with DB not in temp dir
from django.conf import settings
settings._wrapped = None # forces lazy reloading, in case settings were already loaded


from django.core.management import  execute_from_command_line

if __name__ == "__main__":
    
    if "reset" in sys.argv or "flush" in sys.argv:
        
        if os.path.exists(settings.ZODB_FILE):
            os.remove(settings.ZODB_FILE)
        sys.argv[1:] = ("syncdb --noinput --settings=%s" % settings_module).split()
        execute_from_command_line()
        sys.argv[1:] = ("flush --noinput --settings=%s" % settings_module).split()
        execute_from_command_line()
    
    elif "pack" in sys.argv:
        from rpgweb import utilities
        DB = utilities.open_zodb_file(utilities.config.ZODB_FILE)
        DB.pack(days=1)
        print "Successfully packed ZODB items older than 1 day in %s" % utilities.config.ZODB_FILE
        
    elif "runserver" in sys.argv:
        sys.argv[1:] = ("runserver 127.0.0.1:8000 --settings=%s" % settings_module).split()
        execute_from_command_line()
    
    else:
        print "Usage: python %s [reset|pack|runserver]" % sys.argv[0]
        print "- reset: reset django and ZODB databases to their initial state"
        print "- pack: cleans and compresses ZODB file, in case it gets too heavy (test server must not be running)"
        print "- runserver: run local django dev server, against persistent databases"
        sys.exit(1)