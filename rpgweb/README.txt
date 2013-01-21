

Prerequisites
=================

- Ensure you have the rpgweb module in a folder of your PYTHONPATH
- Ensure you have installed proper dependencies (eg. run "pip install -r rpgweb/pip_requirements.txt")


Launching tests
==================

Tests are run with py.test against fake databases stored in temp directories::

	py.test -vl rpgweb/tests/ZODB_tests.py
	py.test -vl rpgweb/tests/test_game.py
	
	CF http://pytest.org/latest/usage.html#usage for more usage info
	
	
Utilities and servers
========================

Use the runner.py script to reset test DBs, pack persistent ZODB, and run django dev server against persistent DBs
located in the same directory::

	py.test rpgweb/tests/runner.py --help
	
..note::
	A standard manage.py script, pointing to the "persistent test DB" configuration, is
	also available to launch a dev server, or issue any other standard django command.

	
Sources Tree Overview
==========================

Most of the *rpgweb* package consists in standard django components, and other common python modules:

- urls.py: django url routing
- forms.py: django declarative web forms
- middlewares.py: django middlewares, for pre and post processing of request
- context_processors.py: add common game info in template contexts
- models.py: required by django, but empty here (we don't use django's SQL ORM for our data)
- default_settings.py: mainly a good reminder of available rpgweb settings
- locale/: standard gettext files, for site translation
- template/: standard django templates
- templatetags/: custom django template tags and filters
- tests/: unit-tests and web-tests for the site
- utilities/: misc. data types and handy functions

Rpgweb adds to these some layers dedicated to the game system:

- common.py: centralizes most useful variables of the application, to be imported as "from rpgweb.common import *"
- authentication.py: utilities to log in and out as a character or game master
- menu.py: dynamically builds nested menus for the page, depending on the permissions of the current user
- datamanager/: dynamic stack of classes, designed to wrap a ZODB and expose tons of getter/setter/utility methods, as well as powerful class-based views
- views/: unlike standard django views, these are not functions, neither singletons like class-based generic views, but "GameView" classes that must be instantiated on each request, and that perform a lot of work ; some of these gameviews are "abilities", that are linked more closely to the datamanager, in which they have a private storage area - they actually behave as "extensions" of the datamanager.


Summary of HTTP request processing
====================================

When a HTTP request reaches the site, the following tasks are performed:

- rpgweb middlewares determine which instance of the game is concerned
- they attach to the request a proper datamanager instance, perform user authentication, and process pending tasks that might remain (delayed actions, email sendings...)
- the targeted GameView is instantiated, and called on the request object
- the GameView performs access checks, returning HTTP error responses if needed
- depending on the kind of request (ajax or not), and the presence (or not) of POST data, the GameView modifies the content of the datamanager (via its public API) according to game rules
- the json or html response is built with templates and their associated data contexts
- middlewares perform some cleanup, and the response is returned to the user


Development tips
====================

- Only *persistent* versions of mutable types should be stored into the ZODB (and this is enforced by rpgweb's checking system), so use Persistent\* types instead of standard lists/dicts/sets.
- All public methods of the datamanager must have a decorator (readonly_method, transaction_watcher...) to take care of the ZODB transaction, depending on whether it may modify content or not.
- Gameviews offer a powerful API to process forms, and turn them into method calls - no need to manually validate forms anymore.
- *register_view* can be used to register a GameView, but also to turn a standard django view into a GameView.










