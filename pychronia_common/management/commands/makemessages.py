# -*- coding: utf-8 -*-
"""
Django's makemessages, extended with the legacy "ugettext*" aliases (still provided by django-compat-patcher),
which recent Django versions no longer pass to xgettext as keywords.
"""

from django.core.management.commands import makemessages


class Command(makemessages.Command):
    xgettext_options = makemessages.Command.xgettext_options + [
        "--keyword=ugettext",
        "--keyword=ugettext_lazy",
        "--keyword=ugettext_noop",
        "--keyword=ungettext:1,2",
        "--keyword=ungettext_lazy:1,2",
    ]
