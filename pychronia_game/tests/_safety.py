"""
Safety net of the test suites (unit and e2e): they wipe the ZODB and create/flush the SQL DB, so they must refuse to
run unless both are throwaway DBs - eg. if pytest was given DEV settings (via --ds or DJANGO_SETTINGS_MODULE), or if
test settings were edited to point to a real DB.

It's called by the pytest_configure() hooks of the conftest.py files, ie. before any test is collected or run, and
before pytest-django creates its SQL test DB (which, for non-sqlite engines, would live on the real DB server).
"""

import os
import tempfile

from django.conf import settings


def _is_temp_path(path):
    if not path:
        return False
    temp_root = os.path.normcase(os.path.realpath(tempfile.gettempdir()))
    return os.path.normcase(os.path.realpath(path)).startswith(temp_root + os.sep)


def _is_throwaway_sqlite_name(name):
    """
    A sqlite file of the temp folder, or an in-memory sqlite DB, like the default test DB of Django (once pytest-django
    has created it, settings.DATABASES[alias]["NAME"] becomes eg. "file:memorydb_default?mode=memory&cache=shared").
    """
    if isinstance(name, str) and (name == ":memory:" or "mode=memory" in name):
        return True
    return _is_temp_path(name)


def get_non_throwaway_databases():
    """Return descriptions of the DBs of current settings that aren't throwaway DBs."""
    problems = []

    zodb_url = getattr(settings, "ZODB_URL", None)
    zodb_file = getattr(settings, "ZODB_FILE", None)
    if zodb_url:
        problems.append("ZODB_URL %r" % zodb_url)
    elif not _is_temp_path(zodb_file):
        problems.append("ZODB_FILE %r" % zodb_file)

    for alias, db in settings.DATABASES.items():
        test_name = (db.get("TEST") or {}).get("NAME")  # the SQL DB that tests actually use, if explicitly set
        if (
            db["ENGINE"] != "django.db.backends.sqlite3"
            or not _is_throwaway_sqlite_name(db["NAME"])
            or (test_name and not _is_throwaway_sqlite_name(test_name))
        ):
            problem = "DATABASES[%r] %s %r" % (alias, db["ENGINE"], db.get("NAME"))
            if test_name:
                problem += " (test DB %r)" % test_name
            problems.append(problem)

    return problems


def ensure_throwaway_databases():
    problems = get_non_throwaway_databases()
    if problems:
        raise RuntimeError(
            "Refusing to run tests with settings %r, which use real databases (tests would wipe them): %s"
            % (settings.SETTINGS_MODULE, "; ".join(problems))
        )
