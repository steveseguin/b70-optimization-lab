#!/usr/bin/env python3
"""Are two agent-campaign call logs the same run apart from time and cache hits?

  python3 compare-campaign-calls.py calls-c26a-K32.jsonl calls-c27a-K32.jsonl

Compares the rows of two `ctxkeeper --log-calls` files in order, on every field but time (`s`, `at`, `timings`) and
the cached count, and prints the cached-count gain and the time change. Exit 1 on any difference. CPU only.
"""
import json
import sys

SKIP = {'s', 'at', 'timings', 'cached'}


def rows(path):
    return [json.loads(line) for line in open(path) if line.strip()]


def main():
    a, b = rows(sys.argv[1]), rows(sys.argv[2])
    diff = [i for i, (x, y) in enumerate(zip(a, b))
            if {k: v for k, v in x.items() if k not in SKIP} != {k: v for k, v in y.items() if k not in SKIP}]
    gained = [(y.get('cached') or 0) - (x.get('cached') or 0) for x, y in zip(a, b)]
    ta, tb = sum(r['s'] for r in a), sum(r['s'] for r in b)
    print(f'calls {len(a)} / {len(b)}; equal apart from time and cache {len(a) - len(diff) if len(a) == len(b) else "n/a"}'
          f'; first differences {diff[:5]}')
    print(f'cached: +{sum(gained)} tokens in all; calls gaining {sum(g > 0 for g in gained)}, losing '
          f'{sum(g < 0 for g in gained)}; gains seen {sorted(set(gained))[:8]}')
    print(f'model time {ta:.1f} s -> {tb:.1f} s ({(tb / ta - 1) * 100:+.1f} %)')
    for kind in sorted({r['kind'] for r in a}):
        sa = sum(r['s'] for r in a if r['kind'] == kind)
        sb = sum(r['s'] for r in b if r['kind'] == kind)
        print(f'  {kind}: {sa:.1f} s -> {sb:.1f} s ({(sb / sa - 1) * 100:+.1f} %)')
    return 1 if diff or len(a) != len(b) else 0


if __name__ == '__main__':
    raise SystemExit(main())
