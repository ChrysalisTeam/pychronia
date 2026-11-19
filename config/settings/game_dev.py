"""
DEV settings of the game site, with persistent DBs: by default a sqlite "django.db" and a ZODB "gamedata.fs"
in pychronia_game/tests/, unless the untracked ".env.game" or ".env" file (see ".env.example") provides GAME_DATABASE_URL
and ZODB_URL. Python-level overrides go in the untracked "config/settings/local_game.py".

Used by the "pychronia-game" command and by pychronia_game/tests/manage.py.
"""

import importlib.util
import os

from config.settings.game import *
from config.settings._dev_base import *
from config.settings._game_dev_base import *
from config.settings._game_dev_base import _game_tests_dir
from config.settings._env import env, read_dotenv

read_dotenv("game")

if "GAME_DATABASE_URL" in os.environ:
    DATABASES = {"default": env.db_url("GAME_DATABASE_URL")}
else:
    DATABASES = {
        "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": os.path.join(_game_tests_dir, "django.db")}
    }

ZODB_URL = env.str("ZODB_URL", default=None)  # eg. "mysql://root@localhost?driver=MySQLdb#mydbname" for RelStorage
ZODB_FILE = None if ZODB_URL else os.path.join(_game_tests_dir, "gamedata.fs")


## OVERRIDES FOR INTEGRATION OF REAL CHRYSALIS FIXTURES, if they're in ../Chrysalis relatively to this depot's root ##
_chrysalis_data_dir = os.path.join(os.path.dirname(ROOT_PATH), "Chrysalis")
if os.path.exists(_chrysalis_data_dir):
    GAME_FILES_ROOT = get_chrysalis_game_files_root(_chrysalis_data_dir)

    # the scenario (auction or mindstorm) is chosen when creating each game instance
    GAME_SCENARIOS = generate_chrysalis_scenarios(_chrysalis_data_dir)
    GAME_DEFAULT_SCENARIO = "auction"


# machine-specific Python-level overrides go in an UNTRACKED "local_game.py" module
if importlib.util.find_spec("config.settings.local_game"):
    from config.settings.local_game import *
