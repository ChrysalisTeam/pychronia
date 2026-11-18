import os
import sys

# "uv sync" installs the project in editable mode, which already puts these folders in sys.path;
# this is only a fallback for environments where the project itself isn't installed
root = os.path.dirname(os.path.realpath(__file__))
for path in (os.path.join(root, "vendor"), root):
    if path not in sys.path:
        sys.path.insert(0, path)

from config.settings._env import configure_settings_module  # noqa: E402

# not erased if already set, eg. for tests; else taken from the ".env" file, else the legacy "pychronia_settings"
configure_settings_module(default="pychronia_settings")

# warnings.resetwarnings() # UNCOMMENT TO SHOW ALL WARNINGS (even deprecation stuffs)

import django

django.setup()
