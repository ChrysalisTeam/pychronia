#!/usr/bin/env python

"""
Django manage.py script for the DEV environment of pychronia_common, with its DB not in a temp dir.

A --settings option (eg. --settings=config.settings._transient) overrides these default settings.
"""

import os
import sys

if __name__ == "__main__":
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings._dev_base"  # minimal settings, eg. for makemessages
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
