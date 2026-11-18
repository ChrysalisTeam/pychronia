"""
Entry points of the "pychronia-game" and "pychronia-cms" commands (see [project.scripts] in pyproject.toml).

They behave like "django-admin", with the DEV settings of their site by default (eg. "uv run pychronia-game runserver"),
and a "--settings" option to use other settings (eg. "--settings=config.settings.game_test").
"""

import os
import sys


def _execute(settings_module):
    os.environ["DJANGO_SETTINGS_MODULE"] = settings_module
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


def game():
    _execute("config.settings.game_dev")


def cms():
    _execute("config.settings.cms_dev")
