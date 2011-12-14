#!/usr/bin/env python

import os
os.environ["DJANGO_SETTINGS_MODULE"] = settings_module = "rpgweb.tests._persistent_settings" # with DB not in temp dir

from django.core.management import execute_from_command_line

if __name__ == "__main__":
    execute_from_command_line()
    
