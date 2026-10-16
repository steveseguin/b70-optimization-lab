#!/usr/bin/env python3
"""Prefix cache + drafting, one user (2026-10-16): does a cached answer depend on which request ran before it, or on
requests following each other with no pause?

Q3 (notes/2026-10-04-fp8-multiuser-prereg.md) sent all 64 long prompts at once to a one-sequence server: 37-39 of 64
equal to the paused one-at-a-time pass, and the three passes disagree with each other too. Runs the same 64 expanded
prompts (same suffixes as scripts/bench-openai-concurrency-oracle.py) in one of these orders against a live server:

  seq        one at a time, waiting for each answer plus --gap-s, in suite order (what the oracle pass does)
  shuffle    one at a time with the gap, in a seeded random order
  burst      all submitted --stagger-ms apart in suite order, so they queue and run back to back in that order
  burst-shuffle   as burst, seeded random order

Writes one JSON file per run: per prompt id the token ids, cached tokens, start/end times and the order index.
--compare A.json B.json prints, per prompt, equal or the first differing token, and the family summary.
"""
import argparse
import concurrent.futures
import importlib.util
import json
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[2]


def load_base():
    spec = importlib.util.spec_from_file_location('bench_base', LAB / 'scripts/bench-openai-realistic-suite.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def expand(base_prompts, count):
    out = []
    for index in range(count):
        base = base_prompts[index % len(base_prompts)]
        variant = index // len(base_prompts)
        out.append({'id': f"{base['id']}-c{index:03d}",
                    'prompt': base['prompt'] + f"\n\n[Independent validation case {index:03d}; variant {variant:02d}]"})
    return out


def run(args):
    B = load_base()
    _, base_prompts = B.load_suite(args.suite)
    items = expand(base_prompts, args.count)
    order = list(range(len(items)))
    if 'shuffle' in args.mode:
        random.Random(args.seed_order).shuffle(order)

    def one(pos, idx):
        item = items[idx]
        t0 = time.time()
        row = B.post_stream(base_url=args.base_url, model=args.model, prompt=item['prompt'], max_tokens=args.max_tokens,
                            timeout=args.timeout, api_mode='completions', seed=42, request_extra={},
                            return_token_ids=True, system_prompt=None,
                            request_id=f"probe-{args.label}-{pos:03d}-{idx:03d}")
        return item['id'], {'order': pos, 'token_ids': row.get('token_ids'), 'cached': B.cached_tokens(row),
                            'start': t0, 'end': time.time(), 'prompt_tokens': row.get('prompt_tokens')}

    rows = {}
    t_start = time.time()
    if args.mode in ('seq', 'shuffle'):
        for pos, idx in enumerate(order):
            pid, r = one(pos, idx)
            rows[pid] = r
            time.sleep(args.gap_s)
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(order)) as pool:
            futs = []
            for pos, idx in enumerate(order):
                futs.append(pool.submit(one, pos, idx))
                time.sleep(args.stagger_ms / 1000.0)
            for f in futs:
                pid, r = f.result()
                rows[pid] = r
    out = {'mode': args.mode, 'label': args.label, 'seed_order': args.seed_order, 'gap_s': args.gap_s,
           'stagger_ms': args.stagger_ms, 'elapsed_s': time.time() - t_start, 'order': [items[i]['id'] for i in order],
           'rows': rows}
    Path(args.out).write_text(json.dumps(out))
    print(f"{args.label}: {args.mode} {len(rows)} answers in {out['elapsed_s']:.0f} s -> {args.out}")


def compare(a_path, b_path):
    a, b = json.loads(Path(a_path).read_text()), json.loads(Path(b_path).read_text())
    equal, fam_diff, fam_total = 0, {}, {}
    for pid in sorted(a['rows']):
        x, y = a['rows'][pid], b['rows'].get(pid)
        fam = pid.rsplit('-c', 1)[0]
        fam_total[fam] = fam_total.get(fam, 0) + 1
        if y is None:
            continue
        if x['token_ids'] == y['token_ids']:
            equal += 1
            continue
        fam_diff[fam] = fam_diff.get(fam, 0) + 1
        k = next((i for i, (p, q) in enumerate(zip(x['token_ids'], y['token_ids'])) if p != q),
                 min(len(x['token_ids']), len(y['token_ids'])))
        print(f"  {pid:<16} cached {x['cached']}/{y['cached']} order {x['order']}/{y['order']} first diff at {k}")
    print(f"{a['label']} vs {b['label']}: {equal}/{len(a['rows'])} equal; differing by family:",
          {f: f"{fam_diff.get(f, 0)}/{n}" for f, n in sorted(fam_total.items())})


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--base-url', default='http://127.0.0.1:18196')
    p.add_argument('--model', default='qwen38-27b-fp8')
    p.add_argument('--suite', default=str(HERE.parent / 'data/2026-10-04-fp8-multiuser/long-prompt-suite.json'))
    p.add_argument('--mode', choices=['seq', 'shuffle', 'burst', 'burst-shuffle'])
    p.add_argument('--count', type=int, default=64)
    p.add_argument('--max-tokens', type=int, default=128)
    p.add_argument('--timeout', type=int, default=3600)
    p.add_argument('--gap-s', type=float, default=1.0)
    p.add_argument('--stagger-ms', type=float, default=30.0)
    p.add_argument('--seed-order', type=int, default=7)
    p.add_argument('--label', default='run')
    p.add_argument('--out')
    p.add_argument('--compare', nargs=2)
    args = p.parse_args()
    if args.compare:
        compare(*args.compare)
    else:
        if not args.mode or not args.out:
            p.error('--mode and --out are required unless --compare')
        run(args)


if __name__ == '__main__':
    sys.exit(main())
