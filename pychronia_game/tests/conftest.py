"""
Pytest hooks of the game unit tests.

Django is set up by pytest-django, with the settings given in [tool.pytest.ini_options] of pyproject.toml
(config.settings.game_test). The e2e/ subfolder has its own pytest.ini and conftest.py, so this file doesn't apply to it.
"""

import pytest


def pytest_configure(config):
    # As early as possible: before tests are collected, before pytest-django creates its SQL test DB,
    # and before any test wipes the ZODB
    from pychronia_game.tests._safety import ensure_throwaway_databases

    try:
        ensure_throwaway_databases()
    except RuntimeError as exc:
        raise pytest.UsageError(str(exc)) from exc
