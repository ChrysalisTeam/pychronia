
import os, sys

root = os.path.dirname(os.path.realpath(__file__))
if root not in sys.path:
    sys.path.insert(0, root)

dependencies = os.path.join(root, "dependencies")
if dependencies not in sys.path:
    sys.path.insert(0, dependencies)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pychronia_settings")  # not erased if already set, eg. for tests

#warnings.resetwarnings() # UNCOMMENT TO SHOW ALL WARNINGS (even deprecation stuffs)

import django_compat_patcher
from django_compat_patcher import default_settings as dcp_default_settings
dcp_settings = dict(DCP_ENABLE_WARNINGS=False,
                    DCP_LOGGING_LEVEL="WARNING",
                    # callable User.is_authenticated/is_anonymous trigger CRITICAL system checks in recent Django versions
                    DCP_EXCLUDE_FIXER_IDS=dcp_default_settings.DCP_EXCLUDE_FIXER_IDS + [
                        "fix_behaviour_contrib_auth_user_is_anonymous_is_authenticated_callability"])
django_compat_patcher.patch(dcp_settings)

import django
django.setup()
