#!/usr/bin/env python3
"""Logprob-resolution determinism probe (A59 diagnostic).

Against a healthy endpoint, for each prompt depth:

1. `--first-step-repeats` identical greedy requests with `max_tokens=1` and
   `logprobs=5`: are the first decode step's top-5 token ids and logprobs
   bitwise identical across repeats? This isolates prefill plus one decode
   step from the graph-replayed continuation.
2. `--repeats` identical greedy requests with `max_tokens=128` and
   `logprobs=2`: per position, the chosen token and the top-2 logprobs.
   Reports the first divergence index, the maximum absolute top-1 logprob
   difference across repeats over the positions before the divergence, and
   the top-1/top-2 gap at the divergence position in repeat 1.

Prompts are the first N token ids of the frozen 2048-token exact-depth
fixture case. Requests are non-streaming `/v1/completions` with
`return_token_ids`, `temperature=0`, `seed=1`, `ignore_eos`. The probe
changes nothing on the server, writes one JSON summary, and on exit writes
the supervisor stop file unless `--no-stop`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

FIXTURE = Path(
    "/home/steve/llm-optimizations/data/qwen27-exact-depth/"
    "qwen38-flash-next-bcd9f01-exact-depth-v1.json"
)
FIXTURE_CASE_SHA = "a173e60e5047c0f080e0ea45680eecbb533d30946cfc2ae0e028c684bf18d1ba"
FOLDER = "/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/configs/moe-m1-w13-n32"


def token_ids_sha256(ids: list[int]) -> str:
    canonical = json.dumps(
        ids, allow_nan=False, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


def load_prompt() -> list[int]:
    fixture = json.loads(FIXTURE.read_text())
    case = next(c for c in fixture["cases"] if c.get("depth") == 2048)
    ids = [int(x) for x in case["prompt_token_ids"]]
    assert len(ids) == 2048 and case["prompt_token_ids_sha256"] == FIXTURE_CASE_SHA
    return ids


def request(
    base_url: str,
    model: str,
    prompt: list[int],
    request_id: str,
    max_tokens: int,
    logprobs: int,
    timeout: int,
) -> dict:
    payload = {
        "model": model,
        "prompt": prompt,
        "max_tokens": max_tokens,
        "temperature": 0,
        "seed": 1,
        "ignore_eos": True,
        "return_token_ids": True,
        "logprobs": logprobs,
        "stream": False,
    }
    req = urllib.request.Request(
        f"{base_url}/v1/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "X-Request-Id": request_id},
    )
    started = time.monotonic()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.load(resp)
    elapsed = time.monotonic() - started
    choice = body["choices"][0]
    ids = [int(x) for x in choice["token_ids"]]
    lp = choice.get("logprobs") or {}
    # per position: list of (token_str, logprob) sorted by logprob descending
    tops = []
    for entry in lp.get("top_logprobs") or []:
        tops.append(sorted(entry.items(), key=lambda kv: -kv[1]))
    usage = body["usage"]
    return {
        "output_token_ids": ids,
        "output_sha256": token_ids_sha256(ids),
        "token_logprobs": lp.get("token_logprobs"),
        "top_logprobs": tops,
        "cached_tokens": (usage.get("prompt_tokens_details") or {}).get(
            "cached_tokens"
        ),
        "completion_tokens": usage["completion_tokens"],
        "wall_seconds": round(elapsed, 3),
    }


def first_divergence(a: list[int], b: list[int]) -> int | None:
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i
    return None if len(a) == len(b) else min(len(a), len(b))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", default="qwen38-flash-next-fp8-tp4")
    parser.add_argument("--server-pid-file", type=Path, required=True)
    parser.add_argument("--stop-file", type=Path, required=True)
    parser.add_argument("--depths", default="256,2048")
    parser.add_argument("--first-step-repeats", type=int, default=8)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--no-stop", action="store_true")
    parser.add_argument(
        "--expect-no-tuned-folder",
        action="store_true",
        help="server identity must carry no VLLM_TUNED_CONFIG_FOLDER (A63 old-head control)",
    )
    args = parser.parse_args()

    pid = int(args.server_pid_file.read_text().strip())
    environ = Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
    folders = [e for e in environ if e.startswith(b"VLLM_TUNED_CONFIG_FOLDER=")]
    expected = [] if args.expect_no_tuned_folder else [f"VLLM_TUNED_CONFIG_FOLDER={FOLDER}".encode()]
    if folders != expected:
        print(f"FAIL: server {pid} tuned folder is {folders!r}", file=sys.stderr)
        return 1
    with urllib.request.urlopen(f"{args.base_url}/health", timeout=20) as resp:
        assert resp.status == 200

    prompt = load_prompt()
    depths = [int(d) for d in args.depths.split(",")]
    results: dict[str, dict] = {}
    try:
        for depth in depths:
            sub = prompt[:depth]
            first_steps = []
            for r in range(1, args.first_step_repeats + 1):
                row = request(
                    args.base_url,
                    args.model,
                    sub,
                    f"q38-a59-d{depth}-first-r{r}",
                    1,
                    5,
                    args.timeout,
                )
                first_steps.append(row)
                print(
                    f"depth={depth} first-step r{r} token={row['output_token_ids']} "
                    f"top={[(t, round(p, 6)) for t, p in row['top_logprobs'][0][:3]] if row['top_logprobs'] else None} "
                    f"cached={row['cached_tokens']} wall={row['wall_seconds']}s",
                    flush=True,
                )
            first_sigs = [
                json.dumps(r["top_logprobs"], sort_keys=True) for r in first_steps
            ]
            first_tokens = [r["output_token_ids"] for r in first_steps]
            first_lps = [(r["token_logprobs"] or [None])[0] for r in first_steps]
            first_identical = len(set(first_sigs)) == 1
            print(
                f"depth={depth}: first-step logits identical across {len(first_steps)} repeats: {first_identical}; "
                f"tokens={first_tokens}; logprob spread={max(x for x in first_lps if x is not None) - min(x for x in first_lps if x is not None) if all(x is not None for x in first_lps) else None}",
                flush=True,
            )

            rows = []
            for r in range(1, args.repeats + 1):
                row = request(
                    args.base_url,
                    args.model,
                    sub,
                    f"q38-a59-d{depth}-full-r{r}",
                    128,
                    2,
                    args.timeout,
                )
                rows.append(row)
                print(
                    f"depth={depth} full r{r} sha={row['output_sha256'][:16]} cached={row['cached_tokens']} wall={row['wall_seconds']}s",
                    flush=True,
                )
            base = rows[0]
            analyses = []
            for row in rows[1:]:
                div = first_divergence(
                    base["output_token_ids"], row["output_token_ids"]
                )
                upto = (
                    div
                    if div is not None
                    else min(
                        len(base["token_logprobs"] or []),
                        len(row["token_logprobs"] or []),
                    )
                )
                max_lp_diff = None
                if base["token_logprobs"] and row["token_logprobs"] and upto > 0:
                    max_lp_diff = max(
                        abs(a - b)
                        for a, b in zip(
                            base["token_logprobs"][:upto], row["token_logprobs"][:upto]
                        )
                    )
                gap = None
                if (
                    div is not None
                    and base["top_logprobs"]
                    and len(base["top_logprobs"]) > div
                ):
                    top = base["top_logprobs"][div]
                    if len(top) >= 2:
                        gap = top[0][1] - top[1][1]
                analyses.append(
                    {
                        "first_divergence": div,
                        "positions_compared_before_divergence": upto,
                        "max_abs_top1_logprob_diff_before_divergence": max_lp_diff,
                        "top1_top2_gap_at_divergence_repeat1": gap,
                    }
                )
            results[str(depth)] = {
                "prompt_sha256": token_ids_sha256(sub),
                "first_step": {
                    "repeats": first_steps,
                    "identical_top5": first_identical,
                    "tokens": first_tokens,
                },
                "full": {
                    "repeats": rows,
                    "analyses": analyses,
                    "distinct_output_hashes": sorted(
                        {r["output_sha256"] for r in rows}
                    ),
                },
            }
            print(f"depth={depth}: full-run analyses={analyses}", flush=True)
    finally:
        summary = {
            "schema_version": 1,
            "classification": "qwen38_flash_next_a59_logprob_determinism_probe",
            "server_pid": pid,
            "tuned_config_folder": FOLDER,
            "fixture_case_sha256": FIXTURE_CASE_SHA,
            "depths": depths,
            "first_step_repeats": args.first_step_repeats,
            "repeats": args.repeats,
            "results": results,
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        print(f"summary: {args.out}", flush=True)
        if not args.no_stop:
            args.stop_file.write_text(
                "STOP after A59 logprob-determinism probe (diagnostic)\n"
            )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (urllib.error.URLError, OSError, AssertionError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(2)
