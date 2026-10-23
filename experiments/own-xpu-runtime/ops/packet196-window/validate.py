#!/usr/bin/env python3
"""Run the existing endpoint validator with a fault gate before every HTTP call."""
import hashlib
from pathlib import Path
import runpy
import urllib.request
from window import faults_clear
SOURCE = Path('/home/steve/inference/validate_endpoint.py')
SHA256 = '9b679f044d110a806f7d6b6f42b232b641236eeac35f1236fca3724c98ed04a5'

def main():
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SHA256:
        raise SystemExit('endpoint validator changed: review before use')
    original = urllib.request.urlopen
    def guarded(*args, **kwargs):
        faults_clear()
        return original(*args, **kwargs)
    urllib.request.urlopen = guarded
    try:
        faults_clear()
        runpy.run_path(str(SOURCE), run_name='__main__')
    finally:
        urllib.request.urlopen = original
        faults_clear()

if __name__ == '__main__':
    main()
