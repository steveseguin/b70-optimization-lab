#!/usr/bin/env python3
"""Create a concurrency oracle from one unconditioned same-shape batch.

This is deliberately a pilot, not a publishable benchmark.  Unlike
bench-openai-concurrency-oracle.py without --oracle-digests, it sends no
sequential oracle requests before the measured cohort.  The cohort can then be
compacted by qualify-openai-concurrency-attempt.py --pilot-from-batch and used
as the frozen oracle for fresh validation servers.
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
from pathlib import Path
from typing import Any


_HERE = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location(
    "bench_openai_concurrency_oracle",
    _HERE / "bench-openai-concurrency-oracle.py",
)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError("cannot load bench-openai-concurrency-oracle.py")
_CONCURRENCY = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_CONCURRENCY)
_BASE = _CONCURRENCY._BASE


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18088")
    parser.add_argument("--model", required=True)
    parser.add_argument(
        "--api-mode", choices=("chat", "completions", "native"), default="completions"
    )
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--concurrency", type=int, required=True)
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--launch-stagger-ms", type=int, default=0)
    parser.add_argument("--pin-slots", action="store_true")
    parser.add_argument("--request-extra-json", default="{}")
    parser.add_argument("--request-id-prefix", default="concurrency-batch-oracle-pilot")
    parser.add_argument("--return-token-ids", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.concurrency < 1 or args.max_tokens < 1 or args.launch_stagger_ms < 0:
        raise SystemExit("concurrency/max-tokens must be positive and stagger nonnegative")
    request_extra = json.loads(args.request_extra_json)
    if not isinstance(request_extra, dict):
        raise SystemExit("--request-extra-json must be an object")
    request_id_prefix = _BASE.safe_request_id(args.request_id_prefix)
    if not request_id_prefix:
        raise SystemExit("--request-id-prefix must contain a safe request-ID character")

    suite_meta, base_prompts = _BASE.load_suite(args.suite)
    prompts = _CONCURRENCY.expand_prompts(base_prompts, args.concurrency)
    system_prompt = suite_meta.get("system_prompt")

    def request(
        item: dict[str, str], request_id: str, slot_id: int = -1
    ) -> dict[str, Any]:
        request_options = dict(request_extra)
        if slot_id >= 0:
            request_options["id_slot"] = slot_id
        return _BASE.post_stream(
            base_url=args.base_url,
            model=args.model,
            prompt=item["prompt"],
            max_tokens=args.max_tokens,
            timeout=args.timeout,
            api_mode=args.api_mode,
            seed=args.seed,
            request_extra=request_options,
            return_token_ids=args.return_token_ids,
            system_prompt=system_prompt,
            request_id=request_id,
        )

    elapsed, rows = _CONCURRENCY.run_group(
        prompts=prompts,
        concurrency=args.concurrency,
        request=request,
        request_prefix=f"{request_id_prefix}-c{args.concurrency}-r1",
        launch_stagger_ms=args.launch_stagger_ms,
        pin_slots=args.pin_slots,
    )
    oracle_by_id = {row["prompt_id"]: row for row in rows}
    batch = _CONCURRENCY.summarize_batch(
        concurrency=args.concurrency,
        repeat=1,
        elapsed_s=elapsed,
        rows=rows,
        oracle_by_id=oracle_by_id,
    )
    cached_tokens_all_zero = all(_BASE.cached_tokens(row) == 0 for row in rows)
    result = {
        "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
        "classification": "same-shape-batch-oracle-pilot",
        "aggregate_metric": "sum(completion_tokens) / batch wall time",
        "reporting_boundary": (
            "Oracle-generation pilot only. The first and only user workload was "
            "the measured same-shape concurrent batch; no sequential oracle, "
            "warmup, prompt cache, interpolation, or extrapolation was used."
        ),
        "config": {
            "base_url": args.base_url,
            "model": args.model,
            "api_mode": args.api_mode,
            "suite_path": str(args.suite),
            "suite": suite_meta,
            "concurrency": [args.concurrency],
            "repeats": 1,
            "max_tokens": args.max_tokens,
            "seed": args.seed,
            "request_extra": request_extra,
            "request_id_prefix": request_id_prefix,
            "launch_stagger_ms": args.launch_stagger_ms,
            "pin_slots": args.pin_slots,
            "return_token_ids": args.return_token_ids,
            "oracle_source": "first-and-only-same-shape-batch",
        },
        # The qualifier in --pilot-from-batch mode intentionally exports from
        # batches[0].rows.  Mirroring the rows here keeps the shared result
        # schema self-contained without issuing another request.
        "oracle": {
            "request_count": len(rows),
            "cached_tokens_all_zero": cached_tokens_all_zero,
            "rows": rows,
        },
        "batches": [batch],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "classification": result["classification"],
                "output": str(args.out),
                "aggregate_tok_s_wall": batch["aggregate_tok_s_wall"],
                "request_count": batch["request_count"],
                "completion_tokens_complete": batch["completion_tokens_complete"],
                "cached_tokens_all_zero": batch["cached_tokens_all_zero"],
                "cross_base_oracle_collision_count": batch[
                    "cross_base_oracle_collision_count"
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
