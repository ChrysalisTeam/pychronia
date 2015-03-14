PYCHRONIA README
#############################


Prerequisites
=================

- Ensure you have the root of this depot in your PYTHONPATH (eg. via your ~/.bashrc, or a virtualenv's activate script...)
- Ensure you have installed proper dependencies, for example:

On a debian/ubuntu, run:
$ sudo apt-get install python python-dev python-pip libjpeg8-dev libmysqlclient-dev"

And then, with or without sudo (depending on whether you use a system python or a virtualenv):
$ pip install -r  pip_requirements.txt


Launching tests
==================

Tests are run with py.test against fake databases stored in temp directories::

	py.test -vl pychronia_game/tests/ZODB_tests.py
	py.test -vl pychronia_game/tests/test_game.py

	CF http://pytest.org/latest/usage.html#usage for more usage info

WARNING - if you use a virtualenv, "python -m pytest" might be safer to use, so that you're sure to use the proper python executable.


Utilities and servers
========================

Use the runner.py script of pychronia_game package to reset test DBs, pack persistent ZODB, and run django dev server against persistent DBs
located in the same directory::

	python pychronia_game/tests/runner.py --help

..note::
	Standard manage.py scripts, pointing to the "persistent test DB" configuration, are
	also available in /test folders, so as to launch dev servers or issue any other standard django command.


Sources Tree Overview for pychronia_game package
===================================================

Most of the *pychronia_game* package consists of standard django components, and other common python modules:

- xxx_urls.py: django url routing files
- common_settings.py: default settinsg for all deployments using pychronia_game
- context_processors.py: to add variables to default contexts of template rendering
- forms.py: django declarative web forms
- middlewares.py: django middlewares, for pre and post processing of request
- context_processors.py: add common game info in template contexts
- models.py: required by django, but empty here (we don't use django's SQL ORM for our data)
- locale/: standard gettext files, for site translation
- template/: standard django templates
- templatetags/: custom django template tags and filters
- tests/: unit-tests and web-tests for the site
- utilities/: misc. data types and handy functions
- views/: not standard django function-views, these are similar to django class-based
  generic views: "GameView" classes that must be instantiated on each request, and that perform a lot of work ;
  some of these gameviews are "abilities", that are linked more closely to the datamanager, in which they have
  a private storage area - they actually behave as "extensions" of the datamanager.

Pychronia adds to these some layers dedicated to the game system:

- authentication.py: utilities to log in and out as a character or game master
- common.py: centralizes most useful variables of the application, to be imported as "from pychronia_game.common import *"
- default_game_settings.py: mainly a good reminder of available pychronia_game settings
- menus.py: dynamically builds nested menus for the page, depending on the permissions of the current user
- datamanager/: dynamic stack of classes, designed to wrap a ZODB and expose tons of getter/setter/utility methods, as well as powerful class-based views
- scripts/: scripts to help maintain a pychronia_game deployment


Summary of HTTP request processing in pychronia_game
========================================================

When a HTTP request reaches the site, the following tasks are performed:

- pychronia_game middlewares determine which instance of the game is concerned
- they attach to the request a proper datamanager instance, perform user authentication, and process
  pending tasks that might remain (delayed actions, email sendings...)
- the targeted GameView is instantiated, and called with the request object as parameter
- the GameView performs access checks, returning HTTP error responses if needed
- depending on the kind of request (ajax or not), and the presence (or not) of POST data, the
  GameView modifies the content of the datamanager (via its public API) according to game rules, and action mixins
- the json or html response is built with templates and their associated data contexts
- middlewares perform some cleanup, and the response is returned to the user


Development tips
====================

- Only *persistent* versions of mutable types should be stored into the ZODB
  (and this is enforced by pychronia_game's checking system),
  so use Persistent\* types instead of standard lists/dicts/sets.
- All public methods of the datamanager must have a decorator (readonly_method, transaction_watcher...)
  to take care of ZODB transactions, depending on whether it may modify content or not.
- If webdesign gets broken, ensure you have well your {% extends %} tags at the TOP of your template
- Gameviews offer a powerful API to process forms, and turn them into method calls - no need to manually validate forms anymore.
- *register_view* can be used to to turn a standard django view into a GameView.
- An old Django debug toolbar might require a fix in django core/handlers/base.py to work with custom urlconfs::

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







