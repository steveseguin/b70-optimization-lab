#!/usr/bin/env python3
"""Bitwise gate between two census/multirow runs (research/multirow-verify-2026-10-30). CPU only.
  compare_state.py RUN_A RUN_B [--modes d,2,...]
Compares the full target state dump (state.json buffer hashes of the DUMP that ends each run's last request), and, for
every mode both runs have, the per-position output-row hashes, rank-1 tokens and rank-0 draft guesses. Runs whose last
requests read the same rows in the same way (e.g. both end with a mode-4 request) are comparable even if their earlier
requests differ: every request starts from RESET."""
import argparse, json, sys
from pathlib import Path


def state(run):
    d = next(Path(run).glob('rank*/state-2147483647'))
    return json.loads((d / 'state.json').read_text())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('a'); ap.add_argument('b'); ap.add_argument('--out')
    x = ap.parse_args()
    sa, sb = state(x.a), state(x.b)
    ba, bb = sa['buffers'], sb['buffers']
    keys = sorted(ba.keys() & bb.keys())
    diff = [k for k in keys if ba[k] != bb[k]]
    only = sorted(ba.keys() ^ bb.keys())
    other = {k: (sa[k], sb[k]) for k in sa if k != 'buffers' and sa.get(k) != sb.get(k)}
    ra = {r['mode']: r for r in json.loads((Path(x.a) / 'summary.json').read_text())['requests']}
    rb = {r['mode']: r for r in json.loads((Path(x.b) / 'summary.json').read_text())['requests']}
    modes = {m: dict(rows_equal=ra[m]['rows_sha256'] == rb[m]['rows_sha256'], tokens_equal=ra[m]['tokens'] == rb[m]['tokens'],
                     guesses_equal=ra[m]['guesses'] == rb[m]['guesses']) for m in sorted(ra.keys() & rb.keys())}
    last_a = json.loads((Path(x.a) / 'summary.json').read_text())['modes'][-1]
    last_b = json.loads((Path(x.b) / 'summary.json').read_text())['modes'][-1]
    ok = not (diff or only or other) and all(all(v.values()) for v in modes.values()) and last_a == last_b
    r = dict(passed=ok, a=x.a, b=x.b, last_mode=[last_a, last_b], compared=len(keys), differ=diff[:40], differ_count=len(diff),
             only_one_side=only[:20], other_fields_differ=other, per_mode=modes)
    print(json.dumps(r))
    if x.out:
        Path(x.out).write_text(json.dumps(r, indent=1))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
