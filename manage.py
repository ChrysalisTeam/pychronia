#!/usr/bin/env python

"""
Django manage.py script intended for use in PREVIEW/PROD environments: the site is chosen by DJANGO_SETTINGS_MODULE,
taken from the real environment or else from the untracked ".env" file (eg. "config.settings.prod_cms" or
"config.settings.prod_game"), else the legacy "pychronia_settings" module is used.

In DEV environments, use the "pychronia-game" and "pychronia-cms" commands instead.
"""

import sys

if __name__ == "__main__":
    from config.settings._env import configure_settings_module

    configure_settings_module(default="pychronia_settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
