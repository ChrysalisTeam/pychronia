#!/usr/bin/env python

"""
Django manage.py script for the DEV environment of pychronia_common, with its DB not in a temp dir.

A --settings option (eg. --settings=pychronia_common.tests.transient_mode_settings) overrides these default settings.
"""

import os
import sys

if __name__ == "__main__":
    os.environ["DJANGO_SETTINGS_MODULE"] = "pychronia_common.tests.persistent_mode_settings"
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
