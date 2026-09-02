#!/usr/bin/env python3
"""Same-server output-determinism probe across prompt depths (A57 diagnostic).

Against the healthy A57 endpoint (identical to A56: tuned M1 W13-N32 map,
twoshots, full decode graph, external checkpoint), send `--repeats` identical
greedy completions at each prompt depth taken as the first N token ids of the
frozen 2048-token exact-depth fixture case, and record per depth:

- the set of distinct 128-token output hashes across repeats;
- the first output position at which any repeat diverges from the first;
- cached-token usage (must be 0 on every request);
- the conventional decode rate from the streamed timestamps is not needed
  here, so requests are non-streaming with `return_token_ids`.

The probe changes nothing on the server. It verifies the live server's
environment carries exactly the A57 tuned-map folder, writes one JSON summary
into the run directory, and on exit writes the supervisor stop file so the
host wrapper tears the server down (the stop is recorded as invalid because
the frozen lossless client did not run; that is expected for this diagnostic).
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
MAX_TOKENS = 128


def token_ids_sha256(ids: list[int]) -> str:
    """Same canonical JSON encoding as scripts/bench-openai-token-depth-suite.py,
    so probe hashes are comparable with the battery's output_token_ids_sha256."""
    canonical = json.dumps(
        ids, allow_nan=False, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


def load_prompt() -> list[int]:
    fixture = json.loads(FIXTURE.read_text())
    case = next(c for c in fixture["cases"] if c.get("depth") == 2048)
    ids = [int(x) for x in case["prompt_token_ids"]]
    assert len(ids) == 2048
    assert case["prompt_token_ids_sha256"] == FIXTURE_CASE_SHA
    return ids


def request(
    base_url: str, model: str, prompt: list[int], request_id: str, timeout: int
) -> dict:
    payload = {
        "model": model,
        "prompt": prompt,
        "max_tokens": MAX_TOKENS,
        "temperature": 0,
        "seed": 1,
        "ignore_eos": True,
        "return_token_ids": True,
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
    usage = body["usage"]
    return {
        "output_token_ids": ids,
        "output_sha256": token_ids_sha256(ids),
        "finish_reason": choice.get("finish_reason"),
        "prompt_tokens": usage["prompt_tokens"],
        "completion_tokens": usage["completion_tokens"],
        "cached_tokens": (usage.get("prompt_tokens_details") or {}).get(
            "cached_tokens"
        ),
        "wall_seconds": round(elapsed, 3),
    }


def first_divergence(a: list[int], b: list[int]) -> int | None:
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i
    return None if len(a) == len(b) else min(len(a), len(b))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:19729")
    parser.add_argument("--model", default="qwen38-flash-next-fp8-tp4")
    parser.add_argument(
        "--server-pid-file",
        type=Path,
        default=Path("/tmp/q38-mtp0-ple-only-a57.server.pid"),
    )
    parser.add_argument(
        "--stop-file", type=Path, default=Path("/tmp/q38-mtp0-ple-only-a57.stop")
    )
    parser.add_argument("--depths", default="256,512,1024,1536,2048")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--no-stop", action="store_true")
    args = parser.parse_args()

    pid = int(args.server_pid_file.read_text().strip())
    environ = Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
    folders = [e for e in environ if e.startswith(b"VLLM_TUNED_CONFIG_FOLDER=")]
    if folders != [f"VLLM_TUNED_CONFIG_FOLDER={FOLDER}".encode()]:
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
            rows = []
            for r in range(1, args.repeats + 1):
                rid = f"q38-a57-depth{depth}-r{r}"
                row = request(args.base_url, args.model, sub, rid, args.timeout)
                row["repeat"] = r
                rows.append(row)
                print(
                    f"depth={depth} r{r} sha={row['output_sha256'][:16]} cached={row['cached_tokens']} "
                    f"prompt={row['prompt_tokens']} out={row['completion_tokens']} wall={row['wall_seconds']}s",
                    flush=True,
                )
            hashes = [row["output_sha256"] for row in rows]
            first = rows[0]["output_token_ids"]
            divergences = [
                first_divergence(first, row["output_token_ids"]) for row in rows[1:]
            ]
            results[str(depth)] = {
                "prompt_sha256": token_ids_sha256(sub),
                "repeats": rows,
                "distinct_output_hashes": sorted(set(hashes)),
                "deterministic": len(set(hashes)) == 1,
                "first_divergence_vs_repeat1": divergences,
                "all_cached_zero": all(row["cached_tokens"] == 0 for row in rows),
                "all_full_length": all(
                    row["completion_tokens"] == MAX_TOKENS for row in rows
                ),
            }
            print(
                f"depth={depth}: deterministic={results[str(depth)]['deterministic']} "
                f"divergence={divergences}",
                flush=True,
            )
    finally:
        summary = {
            "schema_version": 1,
            "classification": "qwen38_flash_next_a57_depth_determinism_probe",
            "server_pid": pid,
            "tuned_config_folder": FOLDER,
            "fixture_case_sha256": FIXTURE_CASE_SHA,
            "max_tokens": MAX_TOKENS,
            "repeats": args.repeats,
            "depths": depths,
            "results": results,
            "boundary": {
                "largest_deterministic_depth": max(
                    (int(d) for d, v in results.items() if v["deterministic"]),
                    default=None,
                ),
                "smallest_nondeterministic_depth": min(
                    (int(d) for d, v in results.items() if not v["deterministic"]),
                    default=None,
                ),
            },
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        print(f"summary: {args.out}", flush=True)
        if not args.no_stop:
            args.stop_file.write_text(
                "STOP after A57 depth-determinism probe (diagnostic)\n"
            )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (urllib.error.URLError, OSError, AssertionError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(2)
