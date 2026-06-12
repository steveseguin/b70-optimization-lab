#!/usr/bin/env python3
"""Validate Qwen3.6 XPU MoE live-ABI graph-capture evidence.

This parser is intentionally narrow. It checks JSONL emitted by the opt-in
`VLLM_XPU_MOE_LIVE_ABI_*` diagnostics and distinguishes three evidence classes:

- eager/post-capture live ABI records with tensor checksums,
- stream-capture visits where synchronous tensor copies were skipped,
- deferred post-capture samples from static graph tensors.

It does not claim model quality or speed by itself. It is a promotion gate input
for future kernel candidates.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def read_records(paths: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for raw_path in paths:
        path = Path(raw_path)
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append({
                    "path": str(path),
                    "line": lineno,
                    "error": str(exc),
                })
                continue
            record["_source_path"] = str(path)
            record["_source_line"] = lineno
            records.append(record)
    return records, errors


def observation(record: dict[str, Any]) -> str:
    value = record.get("capture_observation")
    if value:
        return str(value)
    if record.get("stream_capture_active") is True:
        return "stream_capture_active_unspecified"
    if record.get("checksums"):
        return "eager_or_post_capture_checksum"
    return "metadata_only"


def tensor_meta_complete(record: dict[str, Any]) -> bool:
    tensors = record.get("tensors")
    if not isinstance(tensors, dict):
        return False
    required = ("hidden_states", "topk_ids", "output", "rows_per_expert")
    for name in required:
        meta = tensors.get(name)
        if not isinstance(meta, dict):
            return False
        if "shape" not in meta or "dtype" not in meta or "device" not in meta:
            return False
    return True


def checksum_complete(record: dict[str, Any]) -> bool:
    checksums = record.get("checksums")
    if not isinstance(checksums, dict):
        return False
    return checksums.get("output_sample_sum") is not None


def summarize(
    records: list[dict[str, Any]],
    errors: list[dict[str, Any]],
    *,
    layer_regex: str | None,
    rank: str | None,
    require_capture_skip: bool,
    require_deferred_sample: bool,
) -> dict[str, Any]:
    layer_pattern = re.compile(layer_regex) if layer_regex else None
    filtered: list[dict[str, Any]] = []
    skipped_by_filter = 0
    for record in records:
        layer = str(record.get("layer", ""))
        if layer_pattern and not layer_pattern.search(layer):
            skipped_by_filter += 1
            continue
        if rank is not None and rank not in {
            str(record.get("rank", "")),
            str(record.get("local_rank", "")),
        }:
            skipped_by_filter += 1
            continue
        filtered.append(record)

    obs_counts = Counter(observation(record) for record in filtered)
    by_layer: dict[str, Counter[str]] = defaultdict(Counter)
    by_rank: dict[str, Counter[str]] = defaultdict(Counter)
    tensor_meta_failures = []
    checksum_failures = []
    for record in filtered:
        obs = observation(record)
        layer = str(record.get("layer", ""))
        rank_key = f"rank={record.get('rank', '')}/local={record.get('local_rank', '')}"
        by_layer[layer][obs] += 1
        by_rank[rank_key][obs] += 1
        if obs == "stream_capture_skip_no_tensor_copy" and not tensor_meta_complete(record):
            tensor_meta_failures.append({
                "path": record.get("_source_path"),
                "line": record.get("_source_line"),
                "layer": layer,
                "reason": "missing required capture-safe tensor metadata",
            })
        if obs == "deferred_post_capture_sample" and not checksum_complete(record):
            checksum_failures.append({
                "path": record.get("_source_path"),
                "line": record.get("_source_line"),
                "layer": layer,
                "reason": "missing output_sample_sum checksum",
            })

    has_capture_skip = obs_counts["stream_capture_skip_no_tensor_copy"] > 0
    has_deferred_sample = obs_counts["deferred_post_capture_sample"] > 0
    failures = []
    if errors:
        failures.append("json_parse_errors")
    if require_capture_skip and not has_capture_skip:
        failures.append("missing_stream_capture_skip_record")
    if require_deferred_sample and not has_deferred_sample:
        failures.append("missing_deferred_post_capture_sample")
    if tensor_meta_failures:
        failures.append("capture_skip_tensor_metadata_incomplete")
    if checksum_failures:
        failures.append("deferred_sample_checksum_incomplete")

    status = "pass" if not failures else "fail"
    return {
        "status": status,
        "failures": failures,
        "records_total": len(records),
        "records_filtered": len(filtered),
        "records_skipped_by_filter": skipped_by_filter,
        "parse_errors": errors,
        "observation_counts": dict(obs_counts),
        "has_stream_capture_skip": has_capture_skip,
        "has_deferred_post_capture_sample": has_deferred_sample,
        "tensor_meta_failures": tensor_meta_failures,
        "checksum_failures": checksum_failures,
        "by_layer": {
            layer: dict(counter)
            for layer, counter in sorted(by_layer.items())
        },
        "by_rank": {
            rank_key: dict(counter)
            for rank_key, counter in sorted(by_rank.items())
        },
        "requirements": {
            "layer_regex": layer_regex,
            "rank": rank,
            "require_capture_skip": require_capture_skip,
            "require_deferred_sample": require_deferred_sample,
        },
        "interpretation": (
            "Passing this gate proves the diagnostic log saw the requested "
            "graph-capture evidence. It does not prove model quality, endpoint "
            "speed, or full graph/eager tensor parity by itself."
        ),
    }


def write_markdown(path: str, summary: dict[str, Any]) -> None:
    lines = [
        "# Qwen3.6 MoE Live-ABI Graph Capture Gate",
        "",
        f"- Status: `{summary['status']}`.",
        f"- Records total: `{summary['records_total']}`.",
        f"- Records after filters: `{summary['records_filtered']}`.",
        f"- Failures: `{', '.join(summary['failures']) if summary['failures'] else 'none'}`.",
        f"- Has stream-capture skip: `{summary['has_stream_capture_skip']}`.",
        f"- Has deferred post-capture sample: `{summary['has_deferred_post_capture_sample']}`.",
        "",
        "## Observation Counts",
        "",
    ]
    for name, count in sorted(summary["observation_counts"].items()):
        lines.append(f"- `{name}`: `{count}`")
    lines.extend(["", "## Requirements", ""])
    for key, value in summary["requirements"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Interpretation", "", summary["interpretation"], ""])
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("jsonl", nargs="+", help="Live ABI JSONL log(s).")
    parser.add_argument("--layer-regex")
    parser.add_argument("--rank")
    parser.add_argument("--require-capture-skip", action="store_true")
    parser.add_argument("--require-deferred-sample", action="store_true")
    parser.add_argument("--output-json")
    parser.add_argument("--markdown-out")
    args = parser.parse_args()

    records, errors = read_records(args.jsonl)
    summary = summarize(
        records,
        errors,
        layer_regex=args.layer_regex,
        rank=args.rank,
        require_capture_skip=args.require_capture_skip,
        require_deferred_sample=args.require_deferred_sample,
    )
    text = json.dumps(summary, indent=2, sort_keys=True)
    if args.output_json:
        Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output_json).write_text(text + "\n", encoding="utf-8")
    if args.markdown_out:
        Path(args.markdown_out).parent.mkdir(parents=True, exist_ok=True)
        write_markdown(args.markdown_out, summary)
    print(text)
    return 0 if summary["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
