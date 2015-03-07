#!/usr/bin/env python

import os, sys

root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))) # CHRYSALIS/ root dir
sys.path.insert(0, root)
sys.path.insert(0, os.path.join(root, "dependencies"))
#print "SYS.PATH >>>", sys.path

os.environ["DJANGO_SETTINGS_MODULE"] = settings_module = "pychronia_common.tests.persistent_mode_settings" # with DB not in temp dir

from django.core.management import execute_from_command_line

if __name__ == "__main__":
    execute_from_command_line()
