"""
Settings modules of the two Pychronia sites:

- base.py: settings shared by both sites; game.py and cms.py: complete settings of each site, without
  any deployment-specific value (DB, secrets...)
- game_dev.py / cms_dev.py: DEV servers, with persistent DBs (see "pychronia-game" and "pychronia-cms" commands)
- game_test.py / cms_test.py: unit tests, with throwaway DBs in a temp folder
- e2e.py: Playwright end-to-end tests of the game site
- prod_game.py / prod_cms.py: PROD servers, with deployment-specific values (secrets, DBs...) read from the
  environment or from the untracked env files below; the site is picked by DJANGO_SETTINGS_MODULE, taken from the
  environment or the ".env" file (see the root manage.py and config/wsgi.py)

Machine-specific values of DEV and PROD settings (DB urls...) are read from untracked env files at the root of
the repository (see ".env.example"): ".env.game" or ".env.cms" for the values of a single site, then ".env" for
values shared by both sites (eg. the DB urls of all DEV sites); real environment variables take precedence over
the site file, which takes precedence over ".env". Python-level overrides come from the untracked "local_game.py" and
"local_cms.py" modules of this folder (used by both DEV and PROD settings). Test settings ignore all of these,
to never touch real DBs.

Underscore-prefixed modules are fragments shared by the modules above.
"""
