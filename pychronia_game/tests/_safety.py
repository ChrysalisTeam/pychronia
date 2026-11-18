"""
Safety net of the test suites (unit and e2e): they wipe the ZODB and flush the SQL DB, so they must refuse to run
unless both are throwaway files in the temp folder - eg. if Django was set up with DEV settings before the test
settings could be selected, or if test settings were edited to point to a real DB.
"""

import os
import tempfile

from django.conf import settings


def _is_temp_path(path):
    if not path:
        return False
    temp_root = os.path.normcase(os.path.realpath(tempfile.gettempdir()))
    return os.path.normcase(os.path.realpath(path)).startswith(temp_root + os.sep)


def get_non_throwaway_databases():
    """Return descriptions of the DBs of current settings that aren't throwaway files of the temp folder."""
    problems = []

    zodb_url = getattr(settings, "ZODB_URL", None)
    zodb_file = getattr(settings, "ZODB_FILE", None)
    if zodb_url:
        problems.append("ZODB_URL %r" % zodb_url)
    elif not _is_temp_path(zodb_file):
        problems.append("ZODB_FILE %r" % zodb_file)

    for alias, db in settings.DATABASES.items():
        if db["ENGINE"] != "django.db.backends.sqlite3" or not _is_temp_path(db["NAME"]):
            problems.append("DATABASES[%r] %s %r" % (alias, db["ENGINE"], db.get("NAME")))

    return problems


def ensure_throwaway_databases():
    problems = get_non_throwaway_databases()
    if problems:
        raise RuntimeError(
            "Refusing to run tests with settings %r, which use real databases (tests would wipe them): %s"
            % (settings.SETTINGS_MODULE, "; ".join(problems))
        )
