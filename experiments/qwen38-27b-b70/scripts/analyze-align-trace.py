#!/usr/bin/env python3
"""Read a b70-align-trace log (overlays/b70-align-trace) next to probe-pc-order-vs-timing.py results (2026-10-16).

For every prompt whose answer differs between two traced probe runs (e.g. BT and ST), print both runs' per-step
align decisions for that request (tokens computed, scheduled, previous/current state column, pre-copy source column
and bias, accepted count) up to the first decode steps, and for the first step the recurrent-state block the
pre-copy reads from, with the last step before it in which any request could have written that block:
  - a row's current state block (pre-copy target, and where the step's kernels leave the state),
  - a decoding row's next num_spec blocks (the draft positions' states).
A hit block written after the request that filled it, by another request, is the leftover the probe looks for.

  analyze-align-trace.py TRACE.jsonl --runs BT ST --results DIR [--nsb 5] [--limit 12]
  analyze-align-trace.py RANK0.jsonl RANK1.jsonl --by-rank --runs BT ST --results DIR
    (one file per TP rank, B70_ALIGN_TRACE_ALL_RANKS=1: first-step bias of each request on every rank)
"""
import argparse
import gzip
import json
import re
from collections import defaultdict
from pathlib import Path

RID = re.compile(r'probe-(?P<label>[A-Za-z0-9]+)-(?P<pos>\d{3})-(?P<idx>\d{3})')


def load(trace_paths):
    steps = []
    for p in trace_paths:
        text = gzip.open(p, 'rt').read() if str(p).endswith('.gz') else Path(p).read_text()
        for line in text.splitlines():
            if line.strip():
                steps.append(json.loads(line))
    steps.sort(key=lambda s: s['step'])
    return steps


def key(rid):
    m = RID.search(rid)
    return (m['label'], int(m['idx'])) if m else (None, None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('trace', nargs='+')
    ap.add_argument('--runs', nargs=2, required=True)
    ap.add_argument('--results', required=True, help='folder with the probe JSON files')
    ap.add_argument('--nsb', type=int, default=5)
    ap.add_argument('--limit', type=int, default=12, help='steps per request to print')
    ap.add_argument('--max-prompts', type=int, default=8)
    ap.add_argument('--by-rank', action='store_true', help='one trace file per rank; table only')
    a = ap.parse_args()
    if a.by_rank:
        return by_rank(a)
    steps = load(a.trace)
    res = {r: json.loads((Path(a.results) / f'{r}.json').read_text()) for r in a.runs}
    ids = sorted(res[a.runs[0]]['rows'])
    idx_of = {pid: int(pid.rsplit('-c', 1)[1]) for pid in ids}

    per_req = defaultdict(list)          # (label, idx) -> [(step, row)]
    writes = defaultdict(list)           # block id -> [(step, label, idx, why)]
    new_info = {}
    for s in steps:
        so = s.get('so') or {}
        for n in so.get('new', ()):
            new_info[key(n['rid'])] = n
        spec = so.get('spec', {})
        for row in s['rows']:
            k = key(row['rid'])
            per_req[k].append((s['step'], row))
            for gid, blocks in row.get('mamba_blocks', {}).items():
                curr = row.get('curr')
                if curr is None or curr >= len(blocks):
                    continue
                writes[blocks[curr]].append((s['step'], k, f'state col {curr}'))
                if spec.get(row['rid']):
                    for j in range(1, a.nsb + 1):
                        if curr + j < len(blocks):
                            writes[blocks[curr + j]].append((s['step'], k, f'draft col {curr + j}'))

    # First step of every request in run B (the second --runs label): the pre-copy bias against whether its answer
    # differs from run A. The mechanism predicts: differing exactly when a hit request's first bias is above 0.
    table = defaultdict(int)
    for pid in ids:
        k = (a.runs[1], idx_of[pid])
        first = per_req.get(k, [(None, {})])[0][1]
        differs = res[a.runs[0]]['rows'][pid]['token_ids'] != res[a.runs[1]]['rows'].get(pid, {}).get('token_ids')
        hit = (new_info.get(k) or {}).get('computed', 0) > 0
        table[(hit, (first.get('bias') or 0) > 0, differs)] += 1
    print(f'first steps of {a.runs[1]} (hit, bias>0, answer differs from {a.runs[0]}): count')
    for kk in sorted(table):
        print(f'  hit={kk[0]!s:<5} bias>0={kk[1]!s:<5} differs={kk[2]!s:<5} {table[kk]}')
    differing = [pid for pid in ids
                 if res[a.runs[0]]['rows'][pid]['token_ids'] != res[a.runs[1]]['rows'].get(pid, {}).get('token_ids')]
    print(f'{len(differing)} prompts differ between {a.runs[0]} and {a.runs[1]}; traced steps {len(steps)}')
    for pid in differing[:a.max_prompts]:
        idx = idx_of[pid]
        print(f'\n=== {pid}')
        for label in a.runs:
            k = (label, idx)
            n = new_info.get(k)
            print(f'  [{label}] new: computed {n and n["computed"]} prompt {n and n["prompt_len"]} '
                  f'blocks {n and [len(g) for g in n["blocks"]]}')
            for j, (step, row) in enumerate(per_req.get(k, ())[:a.limit]):
                blocks = next(iter(row.get('mamba_blocks', {}).values()), [])
                src = row.get('src_col', -1)
                srcb = blocks[src + row.get('bias', 0)] if 0 <= src < len(blocks) else None
                line = (f'    step {step}: computed {row["computed"]} sched {row["sched"]} prev {row["prev"]} '
                        f'curr {row.get("curr")} src {src} bias {row.get("bias")} count {row["count"]} '
                        f'src_block {srcb}')
                if j == 0 and srcb is not None:
                    before = [w for w in writes.get(srcb, ()) if w[0] < step]
                    last = before[-3:]
                    line += f' | last writes of block {srcb}: ' + ', '.join(
                        f'step {w[0]} {w[1][0]}:{w[1][1]:03d} {w[2]}' for w in last)
                print(line)


def by_rank(a):
    res = {r: json.loads((Path(a.results) / f'{r}.json').read_text()) for r in a.runs}
    ids = sorted(res[a.runs[0]]['rows'])
    idx_of = {pid: int(pid.rsplit('-c', 1)[1]) for pid in ids}
    first_bias, hit = [], {}
    for p in a.trace:
        seen = {}
        for s in load([p]):
            for n in (s.get('so') or {}).get('new', ()):
                hit[key(n['rid'])] = n['computed'] > 0
            for row in s['rows']:
                seen.setdefault(key(row['rid']), row.get('bias') or 0)
        first_bias.append(seen)
    table = defaultdict(list)
    for pid in ids:
        k = (a.runs[1], idx_of[pid])
        biases = tuple(fb.get(k) for fb in first_bias)
        differs = res[a.runs[0]]['rows'][pid]['token_ids'] != res[a.runs[1]]['rows'].get(pid, {}).get('token_ids')
        table[(hit.get(k, False), tuple((b or 0) > 0 for b in biases), differs)].append(f'{pid}{list(biases)}')
    print(f'first steps of {a.runs[1]} per rank file {[Path(p).name for p in a.trace]}: '
          f'(hit, bias>0 per rank, differs from {a.runs[0]}): count')
    for kk in sorted(table):
        print(f'  hit={kk[0]!s:<5} bias>0={kk[1]} differs={kk[2]!s:<5} {len(table[kk])}'
              + (f'  {" ".join(table[kk][:12])}' if kk[2] != any(kk[1]) else ''))


if __name__ == '__main__':
    main()
