#!/usr/bin/env python3
"""Build a ladder suite from the prompts that actually diverge.

Divergence is concentrated: on the 4B c64 ladder 16 prompts out of 64 carry every event, with per-pass
rates from 5% to 95%. A full-suite ladder therefore spends most of its card time on prompts that never
diverge. Filling the batch with the fragile prompts instead buys roughly an order of magnitude more
events for the same card time, which is what separating two interventions needs.

The suite harness expands N base prompts to fill C slots by appending a case suffix, so the fragile
prompt is `<base text>` + `\\n\\n[Independent validation case NNN; variant VV]` - a specific string, not
the base prompt. This reconstructs those exact texts and emits them as base prompts of a new suite,
meant to be run with `--verbatim-prompts` so the copies stay byte-identical and the site survives.

Reconstruction is verified against the `prompt_sha256` recorded for each request; a mismatch is fatal
rather than silently producing a suite of near-miss prompts that no longer sit on the site.

usage: build-fragile-suite.py ROOT --base-suite SUITE --out SUITE_OUT
                              [--lane ladder] [--concurrency 64] [--min-rate 0.05]
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path


def expanded_text(base_text: str, base_count: int, index: int) -> str:
    variant = index // base_count
    return base_text + f"\n\n[Independent validation case {index:03d}; variant {variant:02d}]"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    ap.add_argument("--base-suite", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--lane", default="ladder")
    ap.add_argument("--concurrency", type=int, default=64)
    ap.add_argument("--min-rate", type=float, default=0.05)
    a = ap.parse_args()

    base = json.loads(a.base_suite.read_text())
    base_prompts = {p["id"]: p["prompt"] for p in base["prompts"]}
    base_count = len(base["prompts"])

    d = json.loads((a.root / a.lane / "ladder.json").read_text())
    oracle = {r["prompt_id"]: r.get("token_ids") or [] for r in (d.get("oracle") or {}).get("rows", [])}
    hashes = {r["prompt_id"]: r.get("prompt_sha256") for b in d["batches"] for r in b["rows"]}

    passes, counts = 0, collections.Counter()
    for b in d["batches"]:
        if b["concurrency"] != a.concurrency:
            continue
        passes += 1
        for r in b["rows"]:
            ref, got = oracle.get(r["prompt_id"]), r.get("token_ids") or []
            if ref and got and ref != got:
                counts[r["prompt_id"]] += 1
    if not passes:
        raise SystemExit(f"no c{a.concurrency} batches in {a.root}/{a.lane}")

    prompts, rates = [], {}
    for pid, hits in counts.most_common():
        rate = hits / passes
        if rate < a.min_rate:
            continue
        stem, _, idx = pid.rpartition("-c")
        if stem not in base_prompts or not idx.isdigit():
            raise SystemExit(f"cannot reconstruct {pid} from {a.base_suite}")
        text = expanded_text(base_prompts[stem], base_count, int(idx))
        want = hashes.get(pid)
        got = hashlib.sha256(text.encode()).hexdigest()
        if want and want != got:
            raise SystemExit(f"{pid}: reconstructed text hash {got[:12]} != recorded {want[:12]}")
        prompts.append({"id": pid, "prompt": text})
        rates[pid] = round(rate, 3)

    if not prompts:
        raise SystemExit("no prompt met --min-rate")

    out = {
        "suite_id": f"fragile-{a.root.name}-c{a.concurrency}",
        "version": 1,
        "description": (
            f"Prompts that diverged in at least {a.min_rate:.0%} of {passes} c{a.concurrency} passes of "
            f"{a.root.name}/{a.lane}. Texts reconstructed from {a.base_suite.name} expansion and verified "
            f"against the recorded prompt_sha256. Run with --verbatim-prompts."
        ),
        "metric": base.get("metric"),
        "source": {"root": str(a.root), "lane": a.lane, "passes": passes, "rates": rates},
        "prompts": prompts,
    }
    a.out.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"{len(prompts)} fragile prompt(s) from {passes} passes -> {a.out}")
    for p in prompts:
        print(f"   {p['id']:<20} rate={rates[p['id']]:.0%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
