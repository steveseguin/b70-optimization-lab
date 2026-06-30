#!/usr/bin/env python3
"""Summarize Gemma single-decode prefill / context ladder runs.

Input files are the `summary.json` files produced by
`scripts/run-gemma4-26b-first-baseline.sh` in synthetic diagnostic mode.
The output is intentionally service-lane oriented; it is not a LocalMaxxing
headline metric.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def first_number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        for key in ("median", "mean", "min", "max"):
            if isinstance(value.get(key), (int, float)):
                return float(value[key])
    return None


def cached_tokens_valid(summary: dict[str, Any]) -> bool | None:
    validity = summary.get("fresh_response_validity")
    if not isinstance(validity, dict):
        return None
    value = validity.get("cached_tokens_all_zero")
    return value if isinstance(value, bool) else None


def summarize(path: Path) -> dict[str, Any]:
    summary = json.loads(path.read_text())
    bench = summary.get("bench_summary") or {}
    launcher = summary.get("launcher_identity") or {}
    run_identity = summary.get("bench_run_identity") or {}
    prompt_tokens = first_number(bench.get("prompt_tokens"))
    completion_tokens = first_number(bench.get("completion_tokens"))
    ttft_s = first_number(bench.get("ttft_s"))
    prompt_tok_s = None
    if prompt_tokens is not None and ttft_s is not None and ttft_s > 0:
        prompt_tok_s = prompt_tokens / ttft_s

    return {
        "label": summary.get("label") or path.parent.name,
        "path": str(path),
        "gpu_index": launcher.get("gpu_index"),
        "prompt_tokens_requested": run_identity.get("prompt_tokens_requested"),
        "prompt_tokens_actual": prompt_tokens,
        "completion_tokens": completion_tokens,
        "ttft_s": ttft_s,
        "prefill_tok_s_approx": prompt_tok_s,
        "tok_s_after_ttft": first_number(bench.get("tok_s_after_ttft")),
        "tok_s_wall": first_number(bench.get("tok_s_wall")),
        "cached_tokens_all_zero": cached_tokens_valid(summary),
        "canary_pass_all": summary.get("canary_pass_all"),
        "ctx_size": launcher.get("ctx_size"),
        "batch_size": launcher.get("batch_size"),
        "ubatch_size": launcher.get("ubatch_size"),
        "flash_attn": launcher.get("flash_attn"),
        "vmm": launcher.get("ggml_sycl_enable_vmm"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("summary", nargs="+", type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    rows = [summarize(path) for path in args.summary]
    rows.sort(key=lambda row: (
        row["prompt_tokens_actual"] if row["prompt_tokens_actual"] is not None else -1,
        row["label"],
    ))

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps({"rows": rows}, indent=2, sort_keys=True) + "\n")

    headers = [
        "prompt",
        "actual",
        "ttft_s",
        "prefill_tok_s",
        "decode_tok_s",
        "wall_tok_s",
        "cached0",
        "canary",
        "label",
    ]
    print("\t".join(headers))
    for row in rows:
        def fmt(value: Any) -> str:
            if value is None:
                return ""
            if isinstance(value, float):
                return f"{value:.3f}"
            return str(value)

        print("\t".join([
            fmt(row["prompt_tokens_requested"]),
            fmt(row["prompt_tokens_actual"]),
            fmt(row["ttft_s"]),
            fmt(row["prefill_tok_s_approx"]),
            fmt(row["tok_s_after_ttft"]),
            fmt(row["tok_s_wall"]),
            fmt(row["cached_tokens_all_zero"]),
            fmt(row["canary_pass_all"]),
            row["label"],
        ]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
