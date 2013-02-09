# -*- coding: utf-8 -*-
import os, sys

GAME_ROOT = os.path.dirname(os.path.realpath(__file__))
GAME_FILES_ROOT = os.path.join(os.path.dirname(GAME_ROOT), "game_files")
GAME_FILES_URL = "/files/" # must end with /
GAME_INITIAL_DATA_PATH = os.path.join(GAME_FILES_ROOT, "game_initial_data.yaml")
GAME_INITIAL_FIXTURE_SCRIPT = None
ACTIVATE_AIML_BOTS = False
DB_RESET_ALLOWED = False
MOBILE_HOST_NAMES = []
ROOT_URLCONF_MOBILE = None
