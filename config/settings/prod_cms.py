"""
PROD settings of the CMS site; deployment-specific values come from the environment or the untracked ".env" file
(see "_prod_base.py" and ".env.example"), Python-level overrides from the untracked "config/settings/local_cms.py".
"""

import importlib.util

from config.settings.cms import *
from config.settings._prod_base import *
from config.settings._env import env

ROOT_URLCONF = "pychronia_cms.urls"

DATABASES = {"default": env.db_url("CMS_DATABASE_URL")}  # eg. "mysql://user:password@localhost/dbname"


# machine-specific Python-level overrides go in an UNTRACKED "local_cms.py" module
if importlib.util.find_spec("config.settings.local_cms"):
    from config.settings.local_cms import *
