#!/usr/bin/env python3
"""Throughput measurement for the community PR #9 recipe.

Mirrors the shape of the contributor's own table: five prompt lengths, 256
output tokens each. One request in flight at a time, so this is single-session
decode throughput and never aggregate.

Each prompt is unique and freshly generated, and the server runs with prefix
caching disabled, so `cached_tokens` should be 0 on every row. That is asserted
rather than assumed -- a nonzero value invalidates the row.
"""

import json
import sys
import time
import urllib.request

ROOT = "http://127.0.0.1:8001"
BASE = ROOT + "/v1"
MODEL = "qwen36-27b-fp8"
OUTPUT_TOKENS = 256
TARGET_PROMPT_TOKENS = [10, 50, 200, 500, 2000]
REPEATS = 3

# Unique filler so no two runs, and no two rows, share a prefix.
STAMP = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


_TOKENIZE_URL = None


def count_tokens(text: str) -> int:
    """Exact prompt token count from the server's own tokenizer."""
    global _TOKENIZE_URL
    candidates = [_TOKENIZE_URL] if _TOKENIZE_URL else [ROOT + "/tokenize",
                                                        BASE + "/tokenize"]
    last = None
    for url in candidates:
        req = urllib.request.Request(
            url,
            data=json.dumps({"model": MODEL, "prompt": text}).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                _TOKENIZE_URL = url
                return json.load(resp)["count"]
        except Exception as exc:  # try the next candidate endpoint
            last = exc
    raise RuntimeError(f"no working tokenize endpoint: {last}")


# Token-dense but natural filler; each word is roughly one token.
_WORDS = (
    "the quick brown fox jumps over a lazy dog while cold rain falls on green "
    "hills near the old stone bridge where ships pass slowly toward open sea"
).split()


def make_prompt(target_tokens: int, idx: int) -> str:
    """Build a fresh prompt whose real token count is close to `target_tokens`.

    Calibrated against the server tokenizer rather than estimated, because a
    word-count approximation was off by roughly 10x on the first attempt and
    made the rows incomparable to the contributor's table.
    """
    head = f"S{STAMP[-6:]}r{idx}. "
    tail = "\nSummarize the above in one sentence."
    budget = target_tokens - count_tokens(head + tail)
    if budget <= 0:
        return (head + tail)[:target_tokens * 4]

    # Grow to just under budget, then trim word by word to land on target.
    body = []
    while count_tokens(head + " ".join(body) + tail) < target_tokens:
        body.append(_WORDS[(len(body) + idx) % len(_WORDS)])
        if len(body) > target_tokens * 3:
            break
    while body and count_tokens(head + " ".join(body) + tail) > target_tokens:
        body.pop()
    return head + " ".join(body) + tail


def post(path: str, payload: dict, stream: bool):
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    return urllib.request.urlopen(req, timeout=900)


def run_row(target_tokens: int, idx: int) -> dict:
    prompt = make_prompt(target_tokens, idx)
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": OUTPUT_TOKENS,
        "stream": True,
        "stream_options": {"include_usage": True},
    }

    t0 = time.perf_counter()
    ttft = None
    completion_tokens = 0
    prompt_tokens = 0
    cached_tokens = None

    with post("/chat/completions", payload, stream=True) as resp:
        for raw in resp:
            line = raw.decode("utf-8").strip()
            if not line.startswith("data: "):
                continue
            body = line[6:]
            if body == "[DONE]":
                break
            chunk = json.loads(body)
            choices = chunk.get("choices") or []
            if choices:
                delta = choices[0].get("delta") or {}
                # First token = first chunk carrying any payload beyond the
                # opening role marker. Checking named fields missed it,
                # because this build streams thinking output under a
                # different key than plain content.
                if ttft is None and any(
                    k != "role" and v for k, v in delta.items()
                ):
                    ttft = time.perf_counter() - t0
            usage = chunk.get("usage")
            if usage:
                completion_tokens = usage.get("completion_tokens", 0)
                prompt_tokens = usage.get("prompt_tokens", 0)
                details = usage.get("prompt_tokens_details") or {}
                cached_tokens = details.get("cached_tokens")

    total = time.perf_counter() - t0
    decode_time = total - (ttft or 0.0)
    # Decode throughput excludes prefill, matching how the lab reports tok/s.
    decode_tps = (completion_tokens - 1) / decode_time if decode_time > 0 else 0.0
    overall_tps = completion_tokens / total if total > 0 else 0.0

    return {
        "target_prompt_tokens": target_tokens,
        "prompt_tokens": prompt_tokens,
        "cached_tokens": cached_tokens,
        "completion_tokens": completion_tokens,
        "ttft_s": round(ttft or 0.0, 4),
        "total_s": round(total, 4),
        "decode_tok_s": round(decode_tps, 4),
        "overall_tok_s": round(overall_tps, 4),
    }


def main() -> int:
    # Warmup: the first request after load pays one-time kernel/JIT cost and
    # is not representative. Discarded, never reported.
    print("warmup request (discarded)...")
    w = run_row(64, 99)
    print(f"  warmup: {w['completion_tokens']} tok in {w['total_s']:.2f}s\n")

    rows = []
    print(
        f"{'pass':>4} {'prompt':>8} {'actual':>8} {'cached':>7} {'out':>5} "
        f"{'ttft_s':>8} {'total_s':>8} {'decode':>9} {'overall':>9}"
    )
    # Three passes so dispersion is reported rather than a single lucky row.
    for rep in range(REPEATS):
        for idx, target in enumerate(TARGET_PROMPT_TOKENS):
            row = run_row(target, rep * 100 + idx)
            row["pass"] = rep + 1
            rows.append(row)
            print(
                f"{rep + 1:>4} {row['target_prompt_tokens']:>8} "
                f"{row['prompt_tokens']:>8} "
                f"{str(row['cached_tokens']):>7} {row['completion_tokens']:>5} "
                f"{row['ttft_s']:>8.3f} {row['total_s']:>8.3f} "
                f"{row['decode_tok_s']:>9.3f} {row['overall_tok_s']:>9.3f}"
            )

    bad = [r for r in rows if r["cached_tokens"] not in (0, None)]
    if bad:
        print(f"\nINVALID: {len(bad)} row(s) had nonzero cached_tokens")

    import statistics
    decodes = sorted(r["decode_tok_s"] for r in rows)
    overalls = sorted(r["overall_tok_s"] for r in rows)
    mid = len(decodes) // 2
    summary = {
        "stamp": STAMP,
        "rows": rows,
        "decode_tok_s_median": decodes[mid],
        "decode_tok_s_min": decodes[0],
        "decode_tok_s_max": decodes[-1],
        "overall_tok_s_median": overalls[mid],
        "overall_tok_s_min": overalls[0],
        "overall_tok_s_max": overalls[-1],
        "decode_tok_s_stdev": round(statistics.stdev([r["decode_tok_s"] for r in rows]), 4),
        "repeats": REPEATS,
        "cache_zero_rows": sum(1 for r in rows if r["cached_tokens"] in (0, None)),
        "total_rows": len(rows),
    }
    print(
        f"\ndecode  tok/s: median {summary['decode_tok_s_median']:.3f}  "
        f"range {summary['decode_tok_s_min']:.3f}-{summary['decode_tok_s_max']:.3f}"
    )
    print(
        f"overall tok/s: median {summary['overall_tok_s_median']:.3f}  "
        f"range {summary['overall_tok_s_min']:.3f}-{summary['overall_tok_s_max']:.3f}"
    )

    out = sys.argv[1] if len(sys.argv) > 1 else f"bench-{STAMP}.json"
    with open(out, "w") as fh:
        json.dump(summary, fh, indent=2)
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
