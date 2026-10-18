"""Pinned v4 screens: micro-qualified grid, then exact other-lane winner."""
import json
import math
import sys
from pathlib import Path

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
WRAPPER = P.parent / 'screen/v4-lanes'
sys.path.insert(0, str(WRAPPER))
from common import read, require, sha, verify_map
from cpu_seal import verify as verify_wrapper

from micro_gate import CANDIDATES
VIEWS=('production',*CANDIDATES)
DIRECTIONS = ('B-grid',)  # record host A is always the deciding confirmation


def verify():
    verify_wrapper()
    row = read(P / 'screen-jobs-seal.json')
    verify_map(ROOT, row['sources'])
    require(row['wrapper_seal_sha256'] == sha(WRAPPER / 'wrapper-seal.json'),
            'shared wrapper changed')
    return row


def qualified_candidates():
    import micro_gate
    return candidates(micro_gate.require_qualified(P))


def candidates(qualified=None):
    selected = tuple(VIEWS[1:] if qualified is None else qualified)
    require(bool(selected) and selected == tuple(c for c in VIEWS[1:] if c in selected),
            'nonempty ordered unique micro-qualified candidates required')
    return selected


def lanes(direction='B-grid'):
    require(direction in DIRECTIONS, 'direction')
    return ('A', 'B') if direction == 'A-grid' else ('B', 'A')


def jobs(lane, choice=None, direction='B-grid', qualified=None):
    require(lane in ('A', 'B'), 'lane')
    selected = candidates(qualified)
    require(len(selected)==1, 'one candidate per bracket required')
    source, confirm = lanes(direction)
    views = ('production', *selected, 'production') if lane == source else (
        'production', choice or selected[0], 'production')
    require(lane == source or views[1] in selected, 'confirmation candidate did not qualify')
    result = []
    for index, view in enumerate(views):
        root = P / 'compat/packet64-record-bundle/selections' / view
        result.append(dict(out=f'p102-{selected[0]}-{direction}-{lane}-{index}-{view}', choice=view,
                           lineage=str(root), seal=str(root / 'screen-seal.json'),
                           binary=str(root / 'build/device/own-rt-iq3'),
                           dispatch=str(root / 'dispatch-speed6.json'), placement='1'))
    return result


def command(row, lane, review=None, plan=False):
    cmd = ['/usr/bin/python3', '-B', str(WRAPPER / 'screen.py'), '--profile', 'tp2',
           '--lane', lane, '--placement', '1', '--timing', 'token']
    for key in ('lineage', 'seal', 'binary', 'dispatch'):
        cmd += ['--' + key, row[key]]
    cmd += ['--output', str(WRAPPER / 'evidence' / row['out'])]
    return cmd + (['--plan'] if plan else ['--fault-review', str(review), '--authorized-device-window'])


def choose(rows, qualified=None):
    selected = candidates(qualified)
    require([r['choice'] for r in rows] == ['production', *selected, 'production'],
            'complete ordered micro-qualified source-lane grid required')
    require(all(r['exact'] for r in rows), 'all 13 requests on every grid screen must match packet49')
    require(all(math.isfinite(r['rate']) and r['rate'] > 0 for r in rows), 'invalid rate')
    require(all(r['acceptance_counts'] == rows[0]['acceptance_counts'] for r in rows),
            'per-prompt target/draft acceptance changed; no winner')
    best = max(rows[1:-1], key=lambda row: row['rate'])
    require(best['rate'] > max(rows[0]['rate'], rows[-1]['rate']),
            'no candidate beats both fresh controls; confirmation withheld')
    return best


def winner(direction='B-grid', qualified=None):
    from compare import load
    selected = qualified_candidates() if qualified is None else candidates(qualified)
    source, _ = lanes(direction)
    return choose([load(row, source) for row in jobs(source, direction=direction, qualified=selected)], selected)
