import os

import environ

ROOT_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

env = environ.Env()


def read_dotenv(site=None):
    """
    Load into os.environ the untracked env files of the repository root, if they exist: the ".env.<site>" file of the
    given site ("game" or "cms") if any, then the ".env" file shared by both sites.

    Already set variables are never overwritten, so real environment variables take precedence over the site file,
    which takes precedence over the shared file.
    """
    filenames = ([".env." + site] if site else []) + [".env"]
    for filename in filenames:
        dotenv_path = os.path.join(ROOT_PATH, filename)
        if os.path.exists(dotenv_path):
            env.read_env(dotenv_path)


def configure_settings_module(default):
    """
    Set DJANGO_SETTINGS_MODULE for the PROD entry points (root manage.py, config/wsgi.py...): the value of the
    real environment, else the one of the shared ".env" file (eg. "config.settings.prod_cms"), else the given default.

    When both sites are served from the same checkout, DJANGO_SETTINGS_MODULE must come from the real environment
    (web server config, crontab...), since the site-specific ".env.<site>" files can only be chosen once it's known.
    """
    if "DJANGO_SETTINGS_MODULE" not in os.environ:
        # only this variable is taken from the file here, the settings module then loads the env files itself,
        # so that values of ".env" don't shadow those of the ".env.<site>" file
        class _FileOnlyEnv(environ.Env):
            ENVIRON = {}

        dotenv_path = os.path.join(ROOT_PATH, ".env")
        if os.path.exists(dotenv_path):
            _FileOnlyEnv.read_env(dotenv_path)
        os.environ["DJANGO_SETTINGS_MODULE"] = _FileOnlyEnv.ENVIRON.get("DJANGO_SETTINGS_MODULE", default)
