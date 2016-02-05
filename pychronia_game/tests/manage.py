#!/usr/bin/env python

import os, sys, warnings

#warnings.resetwarnings() # SHOW ALL

# equivalent of " set DJANGO_SETTINGS_MODULE=pychronia_game.tests.persistent_mode_settings " on windows shell
os.environ["DJANGO_SETTINGS_MODULE"] = settings_module = "pychronia_game.tests.persistent_mode_settings" # with DB not in temp dir
import setup_pychronia_env  # only AFTER setting this DJANGO_SETTINGS_MODULE

from django.core.management import execute_from_command_line

if __name__ == "__main__":
    execute_from_command_line()
