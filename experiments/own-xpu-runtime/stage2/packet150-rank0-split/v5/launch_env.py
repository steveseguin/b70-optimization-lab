"""Closed environment from the vendored ops/launch_env.py authority."""
import os
from p150_ops_launch_env import environment
def apply():
 row=environment();os.environ.clear();os.environ.update(row);return row
