#!/usr/bin/env python3
"""Measure the logit margin at the token where a concurrent request diverges.

The lane's identity work has assumed for weeks that high-concurrency flips are near-ties, and the
2026-09-09 bidirectional-site census supports that reading indirectly. Nothing has measured the
margin, because no ladder ever captured logprobs: the shared harness parses only the chat shape
(`choice.logprobs.content`) while the ladders run `--api-mode completions`, whose logprobs arrive as
parallel arrays, so the field came back empty in all 170 ladder files on disk.

This does not fix that harness. `scripts/bench-openai-realistic-suite.py` is pinned by SHA256 in
several qualification gates and a published record gate, and editing shared pinned tooling in place
is the exact failure recorded in `notes/2026-09-08-a-good-tooling-change-broke-a-record-gate.md`.
This is a separate, unpinned probe that talks to the endpoint directly.

Method: generate a sequential oracle for each prompt (concurrency 1), then issue the same prompts at
concurrency C and compare. For every divergent request, report the top-k logprobs at the first
differing index, from both the oracle pass and the concurrent pass, and the top1-top2 margin in each.

A near-tie predicts a margin near zero in both. A margin of several nats predicts something other
than tie-breaking is moving the token.

usage: probe-tie-margin.py --base-url URL --model NAME --suite SUITE [--concurrency 64]
                           [--repeats 5] [--max-tokens 128] [--logprobs 5] [--out OUT.json]
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import threading
import urllib.request


def post(base_url: str, model: str, prompt: str, max_tokens: int, logprobs: int, timeout: int) -> dict:
    payload = {
        "model": model,
        "prompt": prompt,
        "max_tokens": max_tokens,
        "temperature": 0,
        "top_p": 1,
        "seed": 42,
        "logprobs": logprobs,
        "stream": False,
        "ignore_eos": True,
    }
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        d = json.loads(resp.read())
    ch = d["choices"][0]
    lp = ch.get("logprobs") or {}
    return {
        "text": ch.get("text", ""),
        "tokens": lp.get("tokens") or [],
        "token_logprobs": lp.get("token_logprobs") or [],
        "top_logprobs": lp.get("top_logprobs") or [],
        "finish_reason": ch.get("finish_reason"),
    }


def margin(top: dict | None) -> float | None:
    """top1 - top2 in nats from one position's top_logprobs map."""
    if not isinstance(top, dict) or len(top) < 2:
        return None
    vals = sorted(top.values(), reverse=True)
    return round(vals[0] - vals[1], 6)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--suite", required=True)
    ap.add_argument("--concurrency", type=int, default=64)
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--max-tokens", type=int, default=128)
    ap.add_argument("--logprobs", type=int, default=5)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--out")
    a = ap.parse_args()

    suite = json.loads(open(a.suite).read())
    base = suite["prompts"]
    # Fill the slots by cycling the suite verbatim, so the exact text that sits on a site is preserved.
    slots = [{"id": f"{base[i % len(base)]['id']}-s{i:03d}", "prompt": base[i % len(base)]["prompt"]}
             for i in range(a.concurrency)]

    print(f"oracle: {len(slots)} sequential requests")
    oracle = {}
    for s in slots:
        oracle[s["id"]] = post(a.base_url, a.model, s["prompt"], a.max_tokens, a.logprobs, a.timeout)
    if not any(o["tokens"] for o in oracle.values()):
        raise SystemExit("no logprobs returned; the server may not support logprobs on /v1/completions")

    events = []
    for rep in range(1, a.repeats + 1):
        barrier = threading.Barrier(a.concurrency)

        def run(s):
            barrier.wait()
            return s["id"], post(a.base_url, a.model, s["prompt"], a.max_tokens, a.logprobs, a.timeout)

        with concurrent.futures.ThreadPoolExecutor(max_workers=a.concurrency) as pool:
            got = dict(pool.map(run, slots))
        n = 0
        for pid, r in got.items():
            o = oracle[pid]
            if o["tokens"] == r["tokens"]:
                continue
            n += 1
            i = next((k for k, (x, y) in enumerate(zip(o["tokens"], r["tokens"])) if x != y),
                     min(len(o["tokens"]), len(r["tokens"])))
            ot = o["top_logprobs"][i] if i < len(o["top_logprobs"]) else None
            rt = r["top_logprobs"][i] if i < len(r["top_logprobs"]) else None
            events.append({
                "repeat": rep, "prompt_id": pid, "index": i,
                "oracle_token": o["tokens"][i] if i < len(o["tokens"]) else None,
                "run_token": r["tokens"][i] if i < len(r["tokens"]) else None,
                "oracle_logprob": o["token_logprobs"][i] if i < len(o["token_logprobs"]) else None,
                "run_logprob": r["token_logprobs"][i] if i < len(r["token_logprobs"]) else None,
                "oracle_margin": margin(ot), "run_margin": margin(rt),
                "oracle_top": ot, "run_top": rt,
            })
        print(f"  pass {rep}: {n}/{a.concurrency} divergent")

    print(f"\n{len(events)} divergence(s)")
    margins = [e["oracle_margin"] for e in events if e["oracle_margin"] is not None]
    for e in events[:40]:
        print(f"  rep{e['repeat']} {e['prompt_id'][:26]:28}@{e['index']:<4} "
              f"{e['oracle_token']!r} -> {e['run_token']!r}  "
              f"oracle margin={e['oracle_margin']}  run margin={e['run_margin']}")
    if margins:
        margins.sort()
        print(f"\noracle top1-top2 margin at divergence points, {len(margins)} samples:")
        print(f"  min={margins[0]}  median={margins[len(margins)//2]}  max={margins[-1]}")
        print(f"  at or below 1e-3: {sum(1 for m in margins if m <= 1e-3)}/{len(margins)}")
        print(f"  at or below 1e-2: {sum(1 for m in margins if m <= 1e-2)}/{len(margins)}")
    if a.out:
        json.dump({"config": vars(a), "events": events}, open(a.out, "w"), indent=1)
        print(f"\nwrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
