# -*- coding: utf-8 -*-
import os, sys, pytz

GAME_LOCAL_TZ = pytz.timezone('Europe/Paris')  # for now...

GAME_FILES_URL = "/files/"  # must end with /
GAME_FILES_ROOT = None  # MUST be overridden
GAME_INITIAL_DATA_PATH = None  # MUST be overridden
GAME_INITIAL_FIXTURE_SCRIPT = None  # must be a callable taking a datamanager as unique parameter

GAME_ALLOW_ENFORCED_LOGIN = False
ACTIVATE_AIML_BOTS = False
ZODB_RESET_ALLOWED = False

# at least one of these must be set, URL takes precedence over file
ZODB_FILE = None
ZODB_URL = None

BUG_REPORT_EMAIL = None

PASSWORDS_POOL = None  # must be a list of strings

ACAPELA_CLIENT_ARGS = None  # must be filled to use TTS

GAME_BACKUPS_PATH = "savegames"  # relative to GAME_FILES_ROOT
