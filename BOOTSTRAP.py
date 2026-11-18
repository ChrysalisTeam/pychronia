"""
Install dependencies and initialize zodb/django databases.
"""

import sys
import os
import subprocess

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
# dev settings (config.settings.game_dev), not the PROD settings of root manage.py
MANAGE = os.path.join(REPO_ROOT, "pychronia_game", "tests", "manage.py")

# "uv sync" also installs this project in editable mode, so that its folders are importable from anywhere
print(">>>>> Installing python/pip modules")
assert sys.prefix != sys.base_prefix, "Please launch this script with the python executable of a virtualenv"
# uv installs into the virtualenv of the current python, instead of its default ".venv" folder
uv_env = dict(os.environ, UV_PROJECT_ENVIRONMENT=sys.prefix)
retcode = subprocess.call(["uv", "sync", "--frozen", "--inexact"], env=uv_env, cwd=REPO_ROOT)
assert not retcode, (
    "Error when installing python/pip dependencies with uv (see https://docs.astral.sh/uv/ to install it)"
)

print(">>>>> Resetting sqlite django DB")
retcode = subprocess.call([sys.executable, MANAGE, "reset_django", "--noinput"])
assert not retcode, "Error when resetting django DB, please launch manage.py commands manually"

print(">>>>> Resetting demo game in zodb")
retcode = subprocess.call([sys.executable, MANAGE, "reset_zodb", "--noinput"])
assert not retcode, "Error when resetting zodb, please launch manage.py commands manually"

print(">>>>> ALL BOOTSTRAPPING TASKS COMPLETED")
