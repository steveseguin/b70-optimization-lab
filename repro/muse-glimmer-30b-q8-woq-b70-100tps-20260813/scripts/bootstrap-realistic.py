#!/usr/bin/env python3
import argparse
import json
import random
import statistics

parser = argparse.ArgumentParser()
parser.add_argument("result")
parser.add_argument("--resamples", type=int, default=200000)
parser.add_argument("--seed", type=int, default=20260813)
args = parser.parse_args()

payload = json.load(open(args.result))
values = [row["tok_s_1_100_intervals_after_ttft"] for row in payload["rows"]]
if len(values) != 15:
    raise SystemExit(f"expected 15 rows, got {len(values)}")
rng = random.Random(args.seed)
medians = sorted(statistics.median(rng.choices(values, k=len(values))) for _ in range(args.resamples))
lower = medians[max(0, int(0.05 * args.resamples) - 1)]
print(json.dumps({
    "schema": "prompt-bootstrap-median-v1",
    "metric": "tok_s_1_100_intervals_after_ttft",
    "resamples": args.resamples,
    "seed": args.seed,
    "one_sided_95_lower_tok_s": lower,
}, indent=2))
