#!/usr/bin/env python3
"""Create once, or check, the copy-forward CPU policy seal."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILES = ('memory_plan.py', 'base-plan.json', 'measured-peaks.json', 'derive.py',
         'test_memory_plan.py', 'seal.py', 'README.md', 'CPU-CLOSEOUT.md', 'DO-NOT-REPEAT.md')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--create', action='store_true')
    args = parser.parse_args()
    if args.create:
        row = dict(schema='own-runtime.packet58u.seal.v1', device_executed=False,
                   scope='CPU module for future packets only; no existing window is modified',
                   files={n: hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in FILES})
        with (HERE/'seal.json').open('x') as stream:
            stream.write(json.dumps(row, indent=2, sort_keys=True)+'\n')
    else:
        import memory_plan
        memory_plan.verify_seal()
    print('packet58u seal verified' if not args.create else 'packet58u seal created')


if __name__ == '__main__':
    main()
