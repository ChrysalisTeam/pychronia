import os

import environ

ROOT_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

env = environ.Env()


def read_dotenv():
    """Load the untracked ".env" file of the repository root, if any (real environment variables take precedence)."""
    dotenv_path = os.path.join(ROOT_PATH, ".env")
    if os.path.exists(dotenv_path):
        env.read_env(dotenv_path)
