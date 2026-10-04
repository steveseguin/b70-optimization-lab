#!/usr/bin/env python3
"""Packet 94: should this candidate run the 160 extra prompts?

    decide-94.py <data/shard4-94 dir> <mode>

Yes (exit 0) when this mode's timed arm is all exact and its steady mean
interval is the lowest among the exact candidate arms run so far AND below the
control's (the control must have run and be all exact). Otherwise exit 10.
Reads files only.
"""
import json, sys
from pathlib import Path


def timed(base, mode):
    for p in sorted((base / mode).glob('f94*-*-timed-throughput.json')):
        return json.loads(p.read_text())
    return None


def decide(base, mode, candidates=('shard3-c', 'shard4-a')):
    ctl = timed(base, 'control')
    if ctl is None or not ctl.get('all_exact') or ctl.get('steady_mean_s') is None:
        return False, 'no exact control arm'
    me = timed(base, mode)
    if me is None or not me.get('all_exact') or me.get('steady_mean_s') is None:
        return False, 'this arm is missing or not all exact'
    if not me['steady_mean_s'] < ctl['steady_mean_s']:
        return False, 'not faster than control (%.4f vs %.4f s)' % (me['steady_mean_s'], ctl['steady_mean_s'])
    for other in candidates:
        if other == mode:
            continue
        o = timed(base, other)
        if o and o.get('all_exact') and o.get('steady_mean_s') is not None and o['steady_mean_s'] < me['steady_mean_s']:
            return False, '%s was faster (%.4f s)' % (other, o['steady_mean_s'])
    return True, 'best exact arm so far (%.4f s vs control %.4f s)' % (me['steady_mean_s'], ctl['steady_mean_s'])


if __name__ == '__main__':
    ok, why = decide(Path(sys.argv[1]), sys.argv[2])
    print(('yes: ' if ok else 'no: ') + why)
    sys.exit(0 if ok else 10)
