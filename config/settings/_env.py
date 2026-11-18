import os

import environ

ROOT_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

env = environ.Env()


def read_dotenv():
    """Load the untracked ".env" file of the repository root, if any (real environment variables take precedence)."""
    dotenv_path = os.path.join(ROOT_PATH, ".env")
    if os.path.exists(dotenv_path):
        env.read_env(dotenv_path)


def configure_settings_module(default):
    """
    Set DJANGO_SETTINGS_MODULE for the PROD entry points (root manage.py, config/wsgi.py...): the value of the
    real environment, else the one of the ".env" file (eg. "config.settings.prod_cms"), else the given default.
    """
    if "DJANGO_SETTINGS_MODULE" not in os.environ:
        read_dotenv()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", default)
