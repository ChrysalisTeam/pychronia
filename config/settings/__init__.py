"""
Settings modules of the two Pychronia sites:

- base.py: settings shared by both sites; game.py and cms.py: complete settings of each site, without
  any deployment-specific value (DB, secrets...)
- game_dev.py / cms_dev.py: DEV servers, with persistent DBs (see "pychronia-game" and "pychronia-cms" commands)
- game_test.py / cms_test.py: unit tests, with throwaway DBs in a temp folder
- e2e.py: Playwright end-to-end tests of the game site
- prod_game.py / prod_cms.py: PROD servers, with deployment-specific values (secrets, DBs...) read from the
  environment or from the untracked ".env" file, which also picks the site via DJANGO_SETTINGS_MODULE
  (see the root manage.py and config/wsgi.py)

Machine-specific values of DEV settings (DB urls...) are read from the untracked ".env" file at the root of
the repository (see ".env.example"), and Python-level overrides from the untracked "local_game.py" and
"local_cms.py" modules of this folder (used by both DEV and PROD settings). Test settings ignore all of these,
to never touch real DBs.

Underscore-prefixed modules are fragments shared by the modules above.
"""
