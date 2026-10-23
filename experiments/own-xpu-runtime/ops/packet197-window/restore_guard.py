#!/usr/bin/env python3
"""Run pinned p196 restore/validator with p197's guard before every operation."""
from pathlib import Path
import runpy
import subprocess
import sys

sys.dont_write_bytecode = True
import helpers as H
import window  # parent sources import window.faults_clear; p197 exports clear there


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    H.verify(); window.clear()
    validator = H.PARENT / 'validate.py'
    original = subprocess.run

    def dispatch(command, *a, **kw):
        # Preserve every original operation; only route its validator child
        # through this same p197 guard adapter, without changing request args.
        if len(command) > 1 and command[0] == '/usr/bin/python3' and Path(command[1]) == validator:
            command = ['/usr/bin/python3', '-B', str(Path(__file__).resolve()), '--validate', *command[2:]]
        return original(command, *a, **kw)

    validate = bool(args and args[0] == '--validate')
    target = validator if validate else H.RESTORE
    sys.argv = [str(target), *(args[1:] if validate else args)]
    subprocess.run = dispatch
    try:
        runpy.run_path(str(target), run_name='__main__')
    finally:
        subprocess.run = original
        window.clear()


if __name__ == '__main__': main()
