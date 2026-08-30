#!/usr/bin/env python3
"""Run Qwen3.8 exact-answer quality canaries at real HTTP concurrency.

This complements the sequential text-quality suite.  It deliberately repeats
the same seven exact cases while requests are active together, because a
quantized kernel can cross a numerical boundary only at throughput-sized batch
shapes.  Results are measured, never extrapolated.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import importlib.util
import json
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Any


def load_quality_module() -> Any:
    repo_root = Path(__file__).resolve().parents[3]
    source = repo_root / "scripts" / "qwen38-text-quality-suite.py"
    spec = importlib.util.spec_from_file_location("qwen38_text_quality_suite", source)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load quality suite: {source}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--model", required=True)
    parser.add_argument("--concurrency", type=int, default=64)
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--seed", type=int, default=20260609)
    parser.add_argument("--request-id-prefix", default="qwen38-concurrent-quality")
    parser.add_argument(
        "--speculative-n-max",
        type=int,
        choices=(0, 1, 2),
        help="explicit per-request speculative depth; omitted preserves server default",
    )
    parser.add_argument(
        "--chat-template-kwargs-json", default='{"enable_thinking":false}'
    )
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()
    if args.concurrency < 1 or args.rounds < 1:
        parser.error("--concurrency and --rounds must be positive")
    return args


def main() -> int:
    args = parse_args()
    quality = load_quality_module()
    cases = quality.make_exact_cases()
    template_kwargs = json.loads(args.chat_template_kwargs_json)
    request_extra = (
        {"speculative.n_max": args.speculative_n_max}
        if args.speculative_n_max is not None
        else None
    )
    all_rounds: list[dict[str, Any]] = []

    for round_index in range(args.rounds):
        release = threading.Event()
        ready = threading.Barrier(args.concurrency + 1)

        def run_one(slot: int) -> dict[str, Any]:
            case_index = slot % len(cases)
            case = cases[case_index]
            ready.wait()
            release.wait()
            result = quality.chat_completion(
                args.base_url,
                args.model,
                case["messages"],
                case["max_tokens"],
                args.timeout,
                seed=args.seed + case_index,
                chat_template_kwargs=template_kwargs,
                request_id=(
                    f"{args.request_id_prefix}-r{round_index:02d}-"
                    f"s{slot:03d}-{case['name']}"
                ),
                request_extra=request_extra,
            )
            if "expected" in case:
                passed = result["normalized"] == case["expected"]
                parsed = None
            else:
                parsed = quality.extract_json_object(result["content"])
                passed = isinstance(parsed, dict) and all(
                    str(parsed.get(key)) == expected
                    for key, expected in case["json_expected_fields"].items()
                )
            cached = (
                ((result.get("usage") or {}).get("prompt_tokens_details") or {})
                .get("cached_tokens")
            )
            return {
                "slot": slot,
                "case": case["name"],
                **result,
                "expected": case.get("expected"),
                "json_expected_fields": case.get("json_expected_fields"),
                "json_parsed": parsed,
                "cached_tokens": cached,
                "pass": passed,
            }

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=args.concurrency
        ) as executor:
            futures = [executor.submit(run_one, slot) for slot in range(args.concurrency)]
            ready.wait()
            started = time.perf_counter()
            release.set()
            results = [future.result() for future in futures]
            elapsed = time.perf_counter() - started

        counts = Counter(item["case"] for item in results)
        failures = [item for item in results if not item["pass"]]
        cached_nonzero = [
            item for item in results if item["cached_tokens"] not in (None, 0)
        ]
        all_rounds.append(
            {
                "round": round_index + 1,
                "concurrency": args.concurrency,
                "elapsed_s": elapsed,
                "case_counts": dict(sorted(counts.items())),
                "passed": len(results) - len(failures),
                "failed": len(failures),
                "cached_tokens_nonzero": len(cached_nonzero),
                "pass": not failures and not cached_nonzero,
                "results": results,
            }
        )

    document = {
        "schema_version": 1,
        "classification": "measured-concurrent-exact-answer-quality-canary",
        "base_url": args.base_url,
        "model": args.model,
        "concurrency": args.concurrency,
        "rounds": args.rounds,
        "total_requests": args.concurrency * args.rounds,
        "speculative_n_max": args.speculative_n_max,
        "pass_all": all(row["pass"] for row in all_rounds),
        "no_extrapolation": True,
        "results": all_rounds,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output_json": str(args.output_json),
                "pass_all": document["pass_all"],
                "rounds": [
                    {
                        "round": row["round"],
                        "passed": row["passed"],
                        "failed": row["failed"],
                        "elapsed_s": row["elapsed_s"],
                    }
                    for row in all_rounds
                ],
            },
            sort_keys=True,
        )
    )
    return 0 if document["pass_all"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
