

from ._test_settings import *


# we override transient test DBs with persistent ones
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(TEST_DIR, "django.db")
    }
}
ZODB_FILE = os.path.join(TEST_DIR, "gamedata.fs")



def GAME_INITIAL_FIXTURE_SCRIPT(dm):
    """
    Called just before conversion of initial data tree, and coherency check.
    """
    
    # we activate ALL views
    dm.set_activated_game_views(dm.ACTIVABLE_VIEWS_REGISTRY.keys())

    # we give guy1 access to everything
    dm.update_permissions("guy1", list(dm.PERMISSIONS_REGISTRY))

    # we can't see all articles
    dm.set_encyclopedia_index_visibility(False)
