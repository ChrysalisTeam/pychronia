
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
dcp_settings = dict(DCP_ENABLE_WARNINGS=False,
                    DCP_LOGGING_LEVEL="INFO")
django_compat_patcher.patch(dcp_settings)

import django
django.setup()
