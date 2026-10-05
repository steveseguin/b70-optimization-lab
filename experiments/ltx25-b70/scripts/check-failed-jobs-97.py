#!/usr/bin/env python3
"""Packet 97: report failed pipeline jobs from their on-disk receipts.

    check-failed-jobs-97.py --run R/<run> [--since <unix>] [--stage S] [--index I] [--lines N]

Every failed job of every pipeline stage in a packet 97 server writes
`pipeline-failed-<stage>-<index>-<ms>.json` (schema ltx.pipeline-failed-job.v1) into the run
directory (ltx_pipeline.record_failure). This lists the ones matching the filters (written at
or after --since; of --stage; of job index --index) and prints, for each, the stage, index,
worker, exception and the last N lines of the traceback (default 15).

Exit 0: none found. Exit 3: at least one found (printed). Exit 2: usage. Reads files only.
"""
import argparse
import json
import re
import sys
from pathlib import Path

NAME = re.compile(r'pipeline-failed-(?P<stage>[a-z]+)-(?P<index>[A-Za-z0-9_.-]+?)-(?P<ms>\d{10,})(?:-\d+)?\.json')


def find(run, since=None, stage=None, index=None):
    out = []
    for path in sorted(Path(run).glob('pipeline-failed-*.json')):
        m = NAME.fullmatch(path.name)
        if not m:
            continue
        if stage is not None and m['stage'] != stage:
            continue
        if index is not None and m['index'] != str(index):
            continue
        if since is not None and int(m['ms']) < int(float(since) * 1000):
            continue
        try:
            rec = json.loads(path.read_text())
        except (OSError, ValueError) as error:
            rec = {'unreadable': repr(error)}
        out.append((path, rec))
    return out


def describe(path, rec, lines=15):
    tb = (rec.get('traceback') or '').rstrip().splitlines()
    head = 'FAILED JOB %s: stage %s, index %s, worker %s, %s: %s' % (
        path.name, rec.get('stage'), rec.get('index'), rec.get('worker'), rec.get('exception_type'),
        (rec.get('exception_message') or '').splitlines()[0][:300] if rec.get('exception_message') else '')
    return '\n'.join([head] + ['    ' + line for line in tb[-lines:]])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', required=True)
    ap.add_argument('--since', type=float)
    ap.add_argument('--stage')
    ap.add_argument('--index')
    ap.add_argument('--lines', type=int, default=15)
    a = ap.parse_args(argv)
    found = find(a.run, a.since, a.stage, a.index)
    for path, rec in found:
        print(describe(path, rec, a.lines))
    return 3 if found else 0


if __name__ == '__main__':
    sys.exit(main())
