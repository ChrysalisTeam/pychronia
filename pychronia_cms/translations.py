"""
Translatable strings of the settings in config/settings/ (they're displayed through gettext() at runtime), listed
here so that "makemessages", run from this package folder, keeps them in its message catalogs.
"""

from django.utils.translation import gettext_noop

SETTINGS_STRINGS = [
    gettext_noop("French"),  # LANGUAGES, CMS_LANGUAGES
    gettext_noop("English"),
    gettext_noop("One column"),  # CMS_TEMPLATES
    gettext_noop("Two columns"),
]
