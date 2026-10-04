#!/usr/bin/env python3
"""Packet 94f: after the freeze, did the self-check prompts run the timed path without any
load refusal, capture refusal or residency failure? Reads files only.

    selfcheck-94f.py --root R --run R/<run> --prefix <request prefix> --since <unix time>

Exit 0: every prompt succeeded and nothing was refused. Exit 1: prints exactly which
model or graph was refused (from load-refused-*.json receipts and the prompts' own
execution errors).
"""
import argparse
import json
import re
from pathlib import Path

KINDS = (('Model load refused', 'load refused'),
         ('captures are frozen', 'sampler capture refused'),
         ('Resident models changed', 'resident set changed'),
         ('refused before execution', 'text-encoder graph missing (window/1024)'),
         ('serial capture pass required', 'pipelined request before the freeze'))


def classify(message):
    for needle, kind in KINDS:
        if needle in message:
            return kind
    return 'other error'


def check(root, run, prefix, since):
    problems = []
    for p in sorted(run.glob('load-refused-*.json')):
        try:
            d = json.loads(p.read_text())
        except ValueError:
            problems.append({'kind': 'load refused', 'file': p.name, 'detail': 'unreadable receipt'})
            continue
        if d.get('time', 0) >= since:
            problems.append({'kind': 'load refused', 'file': p.name, 'models': d.get('models'),
                             'reason': d.get('reason'), 'detail': d.get('detail')})
    prompts = 0
    for req in sorted((root / 'requests').glob(prefix + '-*')):
        if not re.fullmatch(re.escape(prefix) + r'-\d{2,}', req.name):
            continue
        prompts += 1
        hist = req / 'history.json'
        if not hist.is_file():
            problems.append({'kind': 'no history', 'prompt': req.name})
            continue
        status = json.loads(hist.read_text()).get('status', {})
        for m in status.get('messages', []):
            if m[0] == 'execution_error':
                msg = str((m[1] or {}).get('exception_message'))
                problems.append({'kind': classify(msg), 'prompt': req.name,
                                 'node': (m[1] or {}).get('node_type'), 'message': msg[:600]})
        if status.get('status_str') not in ('success', None) and not any(p.get('prompt') == req.name for p in problems):
            problems.append({'kind': 'not successful', 'prompt': req.name, 'status': status.get('status_str')})
    if prompts == 0:
        problems.append({'kind': 'no self-check prompts found', 'prefix': prefix})
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True, type=Path)
    ap.add_argument('--run', required=True, type=Path)
    ap.add_argument('--prefix', required=True)
    ap.add_argument('--since', required=True, type=float)
    a = ap.parse_args(argv)
    problems = check(a.root, a.run, a.prefix, a.since)
    print(json.dumps({'self_check': 'clean' if not problems else 'FAILED', 'problems': problems}, indent=1))
    return 0 if not problems else 1


if __name__ == '__main__':
    raise SystemExit(main())
