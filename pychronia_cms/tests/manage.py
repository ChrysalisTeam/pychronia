#!/usr/bin/env python

"""
Django manage.py script for the DEV environment of pychronia_cms, with its DB not in a temp dir.

A --settings option (eg. --settings=pychronia_cms.tests.transient_mode_settings) overrides these default settings.
"""

import os
import sys

if __name__ == "__main__":
    os.environ["DJANGO_SETTINGS_MODULE"] = "pychronia_cms.tests.persistent_mode_settings"
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
