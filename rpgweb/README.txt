

Prerequisites
=================

- Ensure you have the rpgweb module in a folder of your PYTHONPATH

- Ensure you have installed proper dependencies (eg. run "pip install -r rpgweb/pip_requirements.txt")

Launching tests
==================

Tests are run with py.test against fake databases stored in temp directories::

	py.test -v rpgweb/tests/ZODB_tests.py
	py.test -v rpgweb/tests/test_game.py
	
Utilities and servers
========================

Use the runner.py script to reset test DBs, pack persistent ZODB, and run django dev server against persistent DBs
located in the same directory::

	py.test rpgweb/tests/runner.py --help
	
..note::
	A standard manage.py script, pointing to the "persistent test DB" configuration, is
	also available to launch a dev server, or issue any other standard django command.
