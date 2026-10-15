# -*- coding: utf-8 -*-

import os, sys

from pychronia_cms.common_settings import *

from pychronia_common.tests.persistent_mode_settings import *  # simple overrides

ROOT_URLCONF = 'pychronia_cms.tests._test_urls'

_curdir = os.path.dirname(os.path.abspath(__file__))
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'chryscms_local',  # TEMPORARY (do not commit): local MariaDB sandbox
        'USER': 'root',
        'PASSWORD': '',
        'HOST': 'localhost',
    }
}

# fields.E903 (cmsplugin_zinnia's LatestEntriesPlugin.featured NullBooleanField) and
# admin.E012 (cmsplugin_zinnia.admin.EntryPlaceholderAdmin's repeated fieldset field) both
# dropped from this list: no longer fire now that zinnia/cmsplugin_zinnia has been removed
# (entries migrated to djangocms-stories, see cms4_data_fix_migrate_zinnia_to_stories.py).
#
# treebeard.E001 (rung 9, re-verified at rung 11/cms 5.0.13): originally raised against
# cmsplugin_filer_utils.FilerPluginManager (cmsplugin-filer 1.1.3, abandoned - since removed
# entirely from this stack); still fires post-upgrade, now against django-cms's OWN
# cms.models.managers.PageManager, which likewise predates django-treebeard's modern
# MP_NodeManager base class requirement. No upstream fix available on django-cms 5.0.13.
#
# admin.E013 (rung 9) no longer fires as of the django-filer 1.5.0->3.6.0 bump (rung 11
# Stage B) - filer.admin.clipboardadmin.ClipboardAdmin's M2M/filter_horizontal issue was
# fixed upstream somewhere in that range - so it has been dropped from this list.
SILENCED_SYSTEM_CHECKS = ['treebeard.E001']
