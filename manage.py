#!/usr/bin/env python

"""
Django manage.py script intended for use in PREVIEW/PROD environments, with a custom pychronia_settings.py file.

See /tests subfolders to manage DEV environments.
"""

import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pychronia_settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
