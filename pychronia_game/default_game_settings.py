import pytz

GAME_LOCAL_TZ = pytz.timezone("Europe/Paris")  # for now...

GAME_FILES_URL = "/files/"  # must end with /
GAME_FILES_ROOT = None  # MUST be overridden
GAME_INITIAL_DATA_PATH = None  # MUST be overridden
GAME_INITIAL_FIXTURE_SCRIPT = None  # must be a callable taking a datamanager as unique parameter

# Languages in which game CONTENT may be available (fixture files suffixed "_<language>.yaml"), and the
# language of game instances created before game languages existed (all their fixtures were French)
GAME_LANGUAGES = ("fr", "en")
GAME_DEFAULT_LANGUAGE = "fr"

# Scenarios selectable at game creation, as {scenario_id: (initial_data_path, initial_fixture_script)}, eg. built
# by generate_chrysalis_scenarios() of config/settings/game.py. If unset, a single "default" scenario uses
# GAME_INITIAL_DATA_PATH and GAME_INITIAL_FIXTURE_SCRIPT.
GAME_SCENARIOS = None
GAME_DEFAULT_SCENARIO = None  # scenario of instances created before scenarios existed; None means the first one

GAME_ALLOW_ENFORCED_LOGIN = False
GAME_ENFORCED_LOGIN_TOKEN_MAX_AGE = None  # in seconds; None for permanent login links (eg. of DEMO, or observers)
GAME_ACTIVATION_TOKEN_MAX_AGE = 7 * 24 * 3600  # in seconds, validity of the links mailed to game creators
ACTIVATE_AIML_BOTS = False
ZODB_RESET_ALLOWED = False

# at least one of these must be set, URL takes precedence over file
ZODB_FILE = None
ZODB_URL = None

BUG_REPORT_EMAIL = None

PASSWORDS_POOL = None  # must be a list of strings

ACAPELA_CLIENT_ARGS = None  # must be filled to use TTS

GAME_BACKUPS_PATH = "savegames"  # relative to GAME_FILES_ROOT
