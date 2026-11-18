#!/usr/bin/env python

"""
Django manage.py script for the DEV environment of pychronia_cms, with its DB not in a temp dir.

A --settings option (eg. --settings=config.settings.cms_test) overrides these default settings.
"""

import os
import sys

if __name__ == "__main__":
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.cms_dev"
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
