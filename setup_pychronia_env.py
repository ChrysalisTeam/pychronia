
import os, sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pychronia_settings")  # not erased if already set, eg. for tests

import django
django.setup()

root = os.path.dirname(os.path.realpath(__file__))
if root not in sys.path:
    sys.path.insert(0, root)
    
dependencies = os.path.join(root, "dependencies")
if dependencies not in sys.path:
    sys.path.insert(0, dependencies)
