"""
Translatable strings of the settings in config/settings/ (they're displayed through gettext() at runtime), listed
here so that "makemessages", run from this package folder, keeps them in its message catalogs.
"""

from django.utils.translation import gettext_noop

SETTINGS_STRINGS = [
    gettext_noop("French"),  # LANGUAGES
    gettext_noop("English"),
]
