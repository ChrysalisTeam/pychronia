#!/usr/bin/env python

import os, sys

root = os.path.dirname(os.path.realpath(__file__))
if root not in sys.path:
    sys.path.insert(0, root)
sys.path.insert(0, os.path.join(root, "dependencies"))

from django.core.management import execute_from_command_line

if __name__ == "__main__":
    execute_from_command_line()
