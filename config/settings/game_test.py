"""TEST settings of the game site: throwaway SQL DB and ZODB in a temp folder (used by unit tests)."""

from config.settings.game import *
from config.settings._transient import *
from config.settings._game_dev_base import *

ZODB_FILE = os.path.join(TEMP_DIR, "gamedata.fs.%s" % UNICITY_STRING)
ZODB_URL = None
