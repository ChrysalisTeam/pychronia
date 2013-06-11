PYCHRONIA README
#############################


Prerequisites
=================

- Ensure you have this folder in your PYTHONPATH (not mandatory)
- Ensure you have installed proper dependencies (eg. run "pip install -r pip_requirements.txt") in each subpackage


Launching tests
==================

Tests are run with py.test against fake databases stored in temp directories::

	py.test -vl pychronia_game/tests/ZODB_tests.py
	py.test -vl pychronia_game/tests/test_game.py

	CF http://pytest.org/latest/usage.html#usage for more usage info


Utilities and servers
========================

Use the runner.py script of pychronia_game package to reset test DBs, pack persistent ZODB, and run django dev server against persistent DBs
located in the same directory::

	py.test pychronia_game/tests/runner.py --help

..note::
	Standard manage.py scripts, pointing to the "persistent test DB" configuration, are
	also available in /test folders, so as to launch dev servers or issue any other standard django command.


Sources Tree Overview for pychronia_game package
==========================================

Most of the *pychronia_game* package consists in standard django components, and other common python modules:

- urls.py: django url routing
- forms.py: django declarative web forms
- middlewares.py: django middlewares, for pre and post processing of request
- context_processors.py: add common game info in template contexts
- models.py: required by django, but empty here (we don't use django's SQL ORM for our data)
- default_game_settings.py: mainly a good reminder of available pychronia_game settings
- locale/: standard gettext files, for site translation
- template/: standard django templates
- templatetags/: custom django template tags and filters
- tests/: unit-tests and web-tests for the site
- utilities/: misc. data types and handy functions

Pychronia adds to these some layers dedicated to the game system:

- common.py: centralizes most useful variables of the application, to be imported as "from pychronia_game.common import *"
- authentication.py: utilities to log in and out as a character or game master
- menu.py: dynamically builds nested menus for the page, depending on the permissions of the current user
- datamanager/: dynamic stack of classes, designed to wrap a ZODB and expose tons of getter/setter/utility methods, as well as powerful class-based views
- views/: unlike standard django views, these are not functions, neither singletons like class-based generic views, but "GameView" classes that must be instantiated on each request, and that perform a lot of work ; some of these gameviews are "abilities", that are linked more closely to the datamanager, in which they have a private storage area - they actually behave as "extensions" of the datamanager.


Summary of HTTP request processing in pychronia_game
==============================================

When a HTTP request reaches the site, the following tasks are performed:

- pychronia_game middlewares determine which instance of the game is concerned
- they attach to the request a proper datamanager instance, perform user authentication, and process pending tasks that might remain (delayed actions, email sendings...)
- the targeted GameView is instantiated, and called on the request object
- the GameView performs access checks, returning HTTP error responses if needed
- depending on the kind of request (ajax or not), and the presence (or not) of POST data, the GameView modifies the content of the datamanager (via its public API) according to game rules
- the json or html response is built with templates and their associated data contexts
- middlewares perform some cleanup, and the response is returned to the user


Development tips
====================

- Only *persistent* versions of mutable types should be stored into the ZODB (and this is enforced by pychronia_game's checking system), so use Persistent\* types instead of standard lists/dicts/sets.
- All public methods of the datamanager must have a decorator (readonly_method, transaction_watcher...) to take care of ZODB transactions, depending on whether it may modify content or not.
- If webdesign gets broken, ensure you have well your {% extends %} tags at the TOP of your template
- Gameviews offer a powerful API to process forms, and turn them into method calls - no need to manually validate forms anymore.
- *register_view* can be used to to turn a standard django view into a GameView.
- Django debug toolbar requires a fix in django core/handlers/base.py to work with custom urlconfs::

  SEE https://code.djangoproject.com/ticket/19784#ticket::

		...

            try:
                # Apply response middleware, regardless of the response
                for middleware_method in self._response_middleware:
                    response = middleware_method(request, response)
                response = self.apply_response_fixes(request, response)
            except: # Any exception should be gathered and handled
                signals.got_request_exception.send(sender=self.__class__, request=request)
                response = self.handle_uncaught_exception(request, resolver, sys.exc_info())

            return response

        finally:
            # Reset URLconf for this thread on the way out for complete
            # isolation of request.urlconf
            urlresolvers.set_urlconf(None)







