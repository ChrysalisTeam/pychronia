"""
PROD settings of the game site; deployment-specific values come from the environment or the untracked ".env" file
(see "_prod_base.py" and ".env.example"), Python-level overrides (eg. PASSWORDS_POOL, ACAPELA_CLIENT_ARGS) from the
untracked "config/settings/local_game.py".
"""

import importlib.util

from config.settings.game import *
from config.settings._prod_base import *
from config.settings._env import env

ROOT_URLCONF = "pychronia_game.urls"

DATABASES = {"default": env.db_url("GAME_DATABASE_URL")}  # eg. "mysql://user:password@localhost/dbname"

ZODB_URL = env.str("ZODB_URL")  # eg. "mysql://user:password@localhost?driver=MySQLdb#dbname" for RelStorage
ZODB_FILE = None

# root of the Chrysalis game data repository, if the game portal runs the Chrysalis scenarios
_chrysalis_data_dir = env.str("CHRYSALIS_DIR", default=None)
if _chrysalis_data_dir:
    GAME_FILES_ROOT = get_chrysalis_game_files_root(_chrysalis_data_dir)

    # the scenario (auction or mindstorm) is chosen when creating each game instance
    GAME_SCENARIOS = generate_chrysalis_scenarios(_chrysalis_data_dir)
    GAME_DEFAULT_SCENARIO = "auction"
else:
    GAME_FILES_ROOT = env.str("GAME_FILES_ROOT")  # folder of game assets (and of backups, thumbnails...)
    GAME_INITIAL_DATA_PATH = env.str("GAME_INITIAL_DATA_PATH")  # yaml fixture file, or folder of yaml files


# machine-specific Python-level overrides go in an UNTRACKED "local_game.py" module
if importlib.util.find_spec("config.settings.local_game"):
    from config.settings.local_game import *
