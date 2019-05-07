"""
Install dependencies and initialize zodb/django databases.
"""

import sys, os, subprocess

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.join(REPO_ROOT, "pychronia_game", "tests", "runner.py")

#print(sys.path)
if REPO_ROOT not in sys.path and REPO_ROOT + os.sep not in sys.path:
   print("""-------> WARNING, it seems you don't have the folder "%s" in your python paths, please add it (eg. via the PYTHONPATH environment variable) so that all scripts in this project manage to bootstrap themselves.""" % REPO_ROOT)

print("Installing python/pip modules")
retcode = subprocess.call("python -m pip install -r pip_requirements.txt", shell=True)
assert not retcode, "Error when installing python/pip dependencies (if problems with compiled extensions like MysqlDB, on windows, see docs)"

print("Resetting sqlite django DB")
retcode = subprocess.call("python \"%s\" reset_django" % RUNNER, shell=True)
assert not retcode, "Error when resetting django DB, please launch runner.py commands manually"

print("Resetting demo game in zodb")
retcode = subprocess.call("python \"%s\" reset_zodb" % RUNNER, shell=True)
assert not retcode, "Error when resetting zodb, please launch runner.py commands manually"

print("ALL BOOTSTRAPPING TASKS COMPLETED")
