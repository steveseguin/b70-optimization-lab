#!/usr/bin/env python3
"""End-to-end c1 repeat-determinism probe at chosen prompt lengths.

Operator/endpoint diagnostic only. The CR1 kernel sweep found the oneDNN
`fp8_gemm_w8a16` kernel run-to-run nondeterministic for 168-256 input rows on
four production shapes. This probe asks whether that surfaces at the endpoint:
it builds prompts whose `usage.prompt_tokens` hits requested lengths, sends each
prompt sequentially N times at temperature 0 with top logprobs, and compares
token IDs and the returned logprob floats bitwise across repeats.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.request
from pathlib import Path

WORDS = (
    "The B70 lab records every measurement with its model identity, runtime "
    "commit, environment, flags, prompt hash, output hash, and logs so that a "
    "later reader can reproduce or reject the number without trusting the "
    "author. Determinism is checked by repeating requests on a fresh server and "
    "comparing complete token arrays rather than decoded text. Speed and quality "
    "are independent gates; a fast result never substitutes for an exact one. "
).split()


def post(base_url: str, payload: dict, timeout: int) -> dict:
    req = urllib.request.Request(
        f"{base_url}/v1/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def prompt_of_words(n: int) -> str:
    out = []
    while len(out) < n:
        out.extend(WORDS)
    return "Summarize the following lab policy in one paragraph:\n" + " ".join(out[:n])


def build_prompt(base_url, model, target_tokens, timeout) -> tuple[str, int]:
    lo, hi = 1, target_tokens * 3
    best = None
    while lo <= hi:
        mid = (lo + hi) // 2
        text = prompt_of_words(mid)
        r = post(base_url, {"model": model, "prompt": text, "max_tokens": 1,
                            "temperature": 0}, timeout)
        n = int(r["usage"]["prompt_tokens"])
        if n == target_tokens:
            return text, n
        if best is None or abs(n - target_tokens) < abs(best[1] - target_tokens):
            best = (text, n)
        if n < target_tokens:
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18127")
    parser.add_argument("--model", required=True)
    parser.add_argument("--lengths", default="100,168,200,224,250,300")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--max-tokens", type=int, default=64)
    parser.add_argument("--logprobs", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    results = []
    for target in [int(x) for x in args.lengths.split(",")]:
        text, n = build_prompt(args.base_url, args.model, target, args.timeout)
        rows = []
        for i in range(args.repeats):
            t0 = time.perf_counter()
            r = post(args.base_url, {
                "model": args.model, "prompt": text,
                "max_tokens": args.max_tokens, "temperature": 0, "seed": 42,
                "logprobs": args.logprobs, "ignore_eos": True,
                "return_token_ids": True,
            }, args.timeout)
            choice = r["choices"][0]
            token_ids = choice.get("token_ids") or (r.get("token_ids") or [])
            lp = choice.get("logprobs") or {}
            rows.append({
                "repeat": i + 1,
                "prompt_tokens": r["usage"]["prompt_tokens"],
                "cached_tokens": (r["usage"].get("prompt_tokens_details") or {}).get("cached_tokens"),
                "completion_tokens": r["usage"]["completion_tokens"],
                "text_sha256": hashlib.sha256(choice["text"].encode()).hexdigest(),
                "token_ids_sha256": digest(token_ids),
                "token_logprobs_sha256": digest(lp.get("token_logprobs")),
                "top_logprobs_sha256": digest(lp.get("top_logprobs")),
                "first_token_logprobs": (lp.get("token_logprobs") or [])[:4],
                "wall_s": round(time.perf_counter() - t0, 3),
            })
        ids = {r["token_ids_sha256"] for r in rows}
        tlp = {r["token_logprobs_sha256"] for r in rows}
        top = {r["top_logprobs_sha256"] for r in rows}
        results.append({
            "target_prompt_tokens": target,
            "actual_prompt_tokens": n,
            "repeats": args.repeats,
            "token_ids_identical": len(ids) == 1,
            "token_logprobs_identical": len(tlp) == 1,
            "top_logprobs_identical": len(top) == 1,
            "distinct_token_id_streams": len(ids),
            "distinct_token_logprob_arrays": len(tlp),
            "cached_tokens_all_zero": all((r["cached_tokens"] or 0) == 0 for r in rows),
            "rows": rows,
        })
        print(f"[probe] prompt_tokens={n} ids_identical={len(ids)==1} logprobs_identical={len(tlp)==1} top_identical={len(top)==1}", flush=True)
    args.out.write_text(json.dumps({
        "schema": "neural.download.qwen38-fp8-c1-prefill-length-determinism-probe.v1",
        "base_url": args.base_url, "model": args.model,
        "max_tokens": args.max_tokens, "logprobs": args.logprobs,
        "results": results,
    }, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
