#!/usr/bin/env python3
"""Measure endpoint concurrency against per-prompt sequential output oracles."""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import importlib.util
import json
import re
import statistics
import threading
import time
from pathlib import Path
from typing import Any, Callable


_HERE = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location(
    "bench_openai_realistic_suite", _HERE / "bench-openai-realistic-suite.py"
)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError("cannot load bench-openai-realistic-suite.py")
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)


def parse_counts(value: str) -> list[int]:
    counts = [int(item) for item in value.split(",")]
    if not counts or any(item < 1 for item in counts):
        raise argparse.ArgumentTypeError("counts must be positive integers")
    if counts != sorted(set(counts)):
        raise argparse.ArgumentTypeError("counts must be unique and ascending")
    return counts


def expand_prompts(
    base_prompts: list[dict[str, str]], count: int
) -> list[dict[str, str]]:
    if not base_prompts:
        raise ValueError("suite has no prompts")
    expanded = []
    for index in range(count):
        base = base_prompts[index % len(base_prompts)]
        variant = index // len(base_prompts)
        suffix = f"\n\n[Independent validation case {index:03d}; variant {variant:02d}]"
        expanded.append(
            {
                "id": f"{base['id']}-c{index:03d}",
                "prompt": base["prompt"] + suffix,
            }
        )
    return expanded


def output_identity_match(
    row: dict[str, Any], oracle: dict[str, Any]
) -> tuple[bool, str]:
    """Prefer complete token IDs; otherwise retain the text-hash fallback."""
    row_ids = row.get("token_ids")
    oracle_ids = oracle.get("token_ids")
    row_count = row.get("completion_tokens")
    oracle_count = oracle.get("completion_tokens")
    token_ids_complete = (
        isinstance(row_ids, list)
        and isinstance(oracle_ids, list)
        and isinstance(row_count, int)
        and isinstance(oracle_count, int)
        and row_count > 0
        and row_count == len(row_ids)
        and oracle_count == len(oracle_ids)
    )
    if token_ids_complete:
        return row_ids == oracle_ids, "complete_token_ids"
    if (
        isinstance(row_ids, list)
        and isinstance(row_count, int)
        and row_count > 0
        and row_count == len(row_ids)
        and isinstance(oracle.get("token_ids_sha256"), str)
    ):
        return (
            token_ids_sha256(row_ids) == oracle["token_ids_sha256"],
            "complete_token_ids_sha256",
        )
    return row.get("sha256") == oracle.get("sha256"), "text_sha256"


def base_prompt_id(prompt_id: str) -> str:
    return re.sub(r"-c\d+$", "", prompt_id)


def token_ids_sha256(token_ids: list[int]) -> str:
    payload = json.dumps(token_ids, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def select_pinned_oracle_rows(
    oracle_rows: list[dict[str, Any]], prompts: list[dict[str, str]]
) -> list[dict[str, Any]]:
    """Select an exact prompt prefix from a pinned oracle, allowing a superset."""
    rows_by_id: dict[str, dict[str, Any]] = {}
    for row in oracle_rows:
        prompt_id = row.get("prompt_id")
        if not isinstance(prompt_id, str):
            raise ValueError("pinned oracle row is missing a string prompt_id")
        if prompt_id in rows_by_id:
            raise ValueError(f"pinned oracle contains duplicate prompt_id: {prompt_id}")
        rows_by_id[prompt_id] = row

    selected = []
    for item in prompts:
        expected_hash = hashlib.sha256(item["prompt"].encode("utf-8")).hexdigest()
        row = rows_by_id.get(item["id"])
        if row is None or row.get("prompt_sha256") != expected_hash:
            raise ValueError(
                "oracle digest prompt IDs/hashes do not contain the exact expanded suite"
            )
        selected.append(row)
    return selected


def summarize_batch(
    *,
    concurrency: int,
    repeat: int,
    elapsed_s: float,
    rows: list[dict[str, Any]],
    oracle_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    completion_tokens = [row.get("completion_tokens") for row in rows]
    completion_tokens_complete = all(isinstance(v, int) for v in completion_tokens)
    total_tokens = sum(v for v in completion_tokens if isinstance(v, int))
    identity = [
        output_identity_match(row, oracle_by_id[row["prompt_id"]])
        for row in rows
    ]
    exact = [matched for matched, _ in identity]
    identity_methods = [method for _, method in identity]
    complete_token_ids = all(
        method in {"complete_token_ids", "complete_token_ids_sha256"}
        for method in identity_methods
    )
    cross_base_oracle_collisions = 0
    if complete_token_ids:
        oracle_tokens: dict[str, set[str]] = {}
        for prompt_id, oracle in oracle_by_id.items():
            token_ids = oracle.get("token_ids")
            digest = (
                token_ids_sha256(token_ids)
                if isinstance(token_ids, list)
                else oracle.get("token_ids_sha256")
            )
            if isinstance(digest, str):
                oracle_tokens.setdefault(digest, set()).add(
                    oracle.get("base_prompt_id", base_prompt_id(prompt_id))
                )
        for row in rows:
            bases = oracle_tokens.get(token_ids_sha256(row["token_ids"]), set())
            if any(base != base_prompt_id(row["prompt_id"]) for base in bases):
                cross_base_oracle_collisions += 1
    cached = [_BASE.cached_tokens(row) for row in rows]
    request_wall_rates = [
        float(row["tok_s_wall_full"])
        for row in rows
        if isinstance(row.get("tok_s_wall_full"), (int, float))
    ]
    return {
        "concurrency": concurrency,
        "repeat": repeat,
        "elapsed_s": elapsed_s,
        "request_count": len(rows),
        "completion_tokens": completion_tokens,
        "completion_tokens_complete": completion_tokens_complete,
        "total_completion_tokens": total_tokens,
        "aggregate_tok_s_wall": total_tokens / elapsed_s if elapsed_s > 0 else None,
        "per_request_tok_s_wall_median": (
            statistics.median(request_wall_rates) if request_wall_rates else None
        ),
        "oracle_exact_count": sum(exact),
        "oracle_exact_total": len(exact),
        "oracle_exact_all": all(exact),
        "oracle_identity_methods": sorted(set(identity_methods)),
        "complete_token_id_identity_all": complete_token_ids,
        "cross_base_oracle_collision_count": cross_base_oracle_collisions,
        "cached_tokens": cached,
        "cached_tokens_all_zero": all(v == 0 for v in cached),
        "rows": rows,
    }


def run_group(
    *,
    prompts: list[dict[str, str]],
    concurrency: int,
    request: Callable[[dict[str, str], str, int], dict[str, Any]],
    request_prefix: str,
    launch_stagger_ms: int = 0,
    pin_slots: bool = False,
) -> tuple[float, list[dict[str, Any]]]:
    barrier = threading.Barrier(concurrency)

    def one(index: int, item: dict[str, str]) -> dict[str, Any]:
        barrier.wait()
        # Preserve a concurrent cohort while making prompt-to-server-slot
        # ordering reproducible. The server's admission window must exceed
        # (concurrency - 1) * launch_stagger_ms.
        if launch_stagger_ms:
            time.sleep(index * launch_stagger_ms / 1000.0)
        # The server normally assigns slots by HTTP arrival order. At high
        # concurrency that order is timing-dependent even with staggered
        # clients, and some optimized TP paths are not bit-equivalent across
        # slots. Pinning makes a correctness replay compare the same prompt in
        # the same slot while preserving a fully concurrent cohort.
        slot_id = concurrency - 1 - index if pin_slots else -1
        row = request(item, f"{request_prefix}-{index:03d}", slot_id)
        row["prompt_id"] = item["id"]
        row["prompt_sha256"] = hashlib.sha256(
            item["prompt"].encode("utf-8")
        ).hexdigest()
        return row

    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(one, i, item) for i, item in enumerate(prompts)]
        rows = [future.result() for future in futures]
    return time.perf_counter() - started, rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18088")
    parser.add_argument("--model", required=True)
    parser.add_argument(
        "--api-mode", choices=("chat", "completions", "native"), default="completions"
    )
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--concurrency", type=parse_counts, default=parse_counts("1,2,4,8"))
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--launch-stagger-ms", type=int, default=0)
    parser.add_argument(
        "--pin-slots",
        action="store_true",
        help="Pin expanded prompt i to slot concurrency-1-i for deterministic replay.",
    )
    parser.add_argument("--request-extra-json", default="{}")
    parser.add_argument(
        "--request-id-prefix",
        default="concurrency-oracle",
        help="Stable prefix for X-Request-Id values used by this run.",
    )
    parser.add_argument("--return-token-ids", action="store_true")
    parser.add_argument(
        "--require-output-identity",
        action="store_true",
        help=(
            "Fail when any concurrent complete output differs from its "
            "sequential oracle. Output isolation alone is not a quality-"
            "equivalence gate."
        ),
    )
    parser.add_argument(
        "--oracle-digests",
        type=Path,
        help="Use a pinned compact sequential token-ID oracle instead of regenerating it.",
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.repeats < 1 or args.max_tokens < 1 or args.launch_stagger_ms < 0:
        raise SystemExit("--repeats/max-tokens must be positive and --launch-stagger-ms nonnegative")
    request_extra = json.loads(args.request_extra_json)
    if not isinstance(request_extra, dict):
        raise SystemExit("--request-extra-json must be an object")
    request_id_prefix = _BASE.safe_request_id(args.request_id_prefix)
    if not request_id_prefix:
        raise SystemExit("--request-id-prefix must contain a safe request-ID character")

    suite_meta, base_prompts = _BASE.load_suite(args.suite)
    prompts = expand_prompts(base_prompts, max(args.concurrency))
    system_prompt = suite_meta.get("system_prompt")

    def request(item: dict[str, str], request_id: str, slot_id: int = -1) -> dict[str, Any]:
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

    oracle_digest_sha256 = None
    if args.oracle_digests:
        oracle_digest_bytes = args.oracle_digests.read_bytes()
        oracle_digest_sha256 = hashlib.sha256(oracle_digest_bytes).hexdigest()
        oracle_doc = json.loads(oracle_digest_bytes)
        try:
            oracle_rows = select_pinned_oracle_rows(oracle_doc["rows"], prompts)
        except (KeyError, TypeError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc
        oracle_fresh = oracle_doc.get("cached_tokens_zero") is True
    else:
        oracle_rows = []
        for index, item in enumerate(prompts):
            row = request(item, f"{request_id_prefix}-oracle-{index:03d}")
            row["prompt_id"] = item["id"]
            row["prompt_sha256"] = hashlib.sha256(
                item["prompt"].encode("utf-8")
            ).hexdigest()
            oracle_rows.append(row)
        oracle_fresh = all(_BASE.cached_tokens(row) == 0 for row in oracle_rows)
    oracle_by_id = {row["prompt_id"]: row for row in oracle_rows}

    batches = []
    for repeat in range(1, args.repeats + 1):
        for concurrency in args.concurrency:
            selected = prompts[:concurrency]
            elapsed, rows = run_group(
                prompts=selected,
                concurrency=concurrency,
                request=request,
                request_prefix=(
                    f"{request_id_prefix}-c{concurrency}-r{repeat}"
                ),
                launch_stagger_ms=args.launch_stagger_ms,
                pin_slots=args.pin_slots,
            )
            batches.append(
                summarize_batch(
                    concurrency=concurrency,
                    repeat=repeat,
                    elapsed_s=elapsed,
                    rows=rows,
                    oracle_by_id=oracle_by_id,
                )
            )

    all_exact = all(batch["oracle_exact_all"] for batch in batches)
    all_fresh = oracle_fresh and all(
        batch["cached_tokens_all_zero"] for batch in batches
    )
    all_counts = all(batch["completion_tokens_complete"] for batch in batches)
    output_isolation_qualified = (
        all_fresh
        and all_counts
        and all(batch["complete_token_id_identity_all"] for batch in batches)
        and all(batch["cross_base_oracle_collision_count"] == 0 for batch in batches)
    )
    classification = (
        "output-identity-qualified"
        if all_exact and all_fresh and all_counts
        else (
            "output-isolation-qualified-shape-variant"
            if output_isolation_qualified
            else "measured-output-variant"
        )
    )
    output_identity_qualified = all_exact and all_fresh and all_counts
    result = {
        "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
        "classification": classification,
        "aggregate_metric": "sum(completion_tokens) / batch wall time",
        "reporting_boundary": (
            "Measured endpoint batches with per-prompt sequential oracle comparison. "
            "No interpolation or extrapolation. Output isolation proves that requests "
            "did not cross-contaminate one another; it does not prove output identity "
            "or quality equivalence. A shape-variant result must not be presented as "
            "quality-equivalent to its sequential oracle."
        ),
        "identity_qualification": {
            "complete_outputs_exact_vs_sequential_oracle": all_exact,
            "fresh_and_complete": all_fresh and all_counts,
            "public_quality_equivalence_eligible": output_identity_qualified,
            "output_isolation_only": (
                output_isolation_qualified and not output_identity_qualified
            ),
            "require_output_identity": args.require_output_identity,
        },
        "config": {
            "base_url": args.base_url,
            "model": args.model,
            "api_mode": args.api_mode,
            "suite_path": str(args.suite),
            "suite": suite_meta,
            "concurrency": args.concurrency,
            "repeats": args.repeats,
            "max_tokens": args.max_tokens,
            "seed": args.seed,
            "request_extra": request_extra,
            "request_id_prefix": request_id_prefix,
            "launch_stagger_ms": args.launch_stagger_ms,
            "pin_slots": args.pin_slots,
            "return_token_ids": args.return_token_ids,
            "require_output_identity": args.require_output_identity,
            "oracle_digests": str(args.oracle_digests) if args.oracle_digests else None,
            "oracle_digests_sha256": oracle_digest_sha256,
        },
        "oracle": {
            "request_count": len(oracle_rows),
            "cached_tokens_all_zero": oracle_fresh,
            "rows": oracle_rows,
        },
        "batches": batches,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "classification": result["classification"],
        "output_identity_qualified": output_identity_qualified,
        "output": str(args.out),
        "batches": [
            {
                "concurrency": row["concurrency"],
                "repeat": row["repeat"],
                "aggregate_tok_s_wall": row["aggregate_tok_s_wall"],
                "oracle_exact": f"{row['oracle_exact_count']}/{row['oracle_exact_total']}",
            }
            for row in batches
        ],
    }, indent=2))
    if args.require_output_identity and not output_identity_qualified:
        return 4
    return 0 if classification != "measured-output-variant" else 3


if __name__ == "__main__":
    raise SystemExit(main())
