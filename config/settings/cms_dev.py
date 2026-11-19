"""
DEV settings of the CMS site, with a persistent SQL DB: by default a local MySQL "chrysaliscms_dev" DB, unless the
untracked ".env.cms" or ".env" file (see ".env.example") provides CMS_DATABASE_URL. Python-level overrides go in the untracked
"config/settings/local_cms.py".

Used by the "pychronia-cms" command and by pychronia_cms/tests/manage.py.
"""

import importlib.util
import os

from config.settings.cms import *
from config.settings._dev_base import *
from config.settings._env import env, read_dotenv

read_dotenv("cms")

ROOT_URLCONF = "pychronia_cms.tests._test_urls"

if "CMS_DATABASE_URL" in os.environ:
    DATABASES = {"default": env.db_url("CMS_DATABASE_URL")}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": "chrysaliscms_dev",
            "USER": "root",
            "PASSWORD": "root",
            "HOST": "127.0.0.1",
            "PORT": "3306",
        }
    }

# machine-specific Python-level overrides go in an UNTRACKED "local_cms.py" module
if importlib.util.find_spec("config.settings.local_cms"):
    from config.settings.local_cms import *
