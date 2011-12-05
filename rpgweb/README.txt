

Prerequisites
=================

- Ensure you have the rpgweb module in a folder of your PYTHONPATH

- Ensure you have installed proper dependencies (eg. run "pip install -r rpgweb/install/pip_requirements.txt")

Launching tests
==================

Tests are run against fake databases, from temp directories, using py.test::

	py.test -v rpgweb/tests/ZODB_tests.py
	py.test -v test_game.py
	
Launching dev server
========================

Use the rpgweb/tests/runner.py script to reset test DBs, pack test ZODB, and run django dev server against persistent DBs
located in the same directory. 

