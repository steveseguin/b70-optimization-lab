#!/usr/bin/env python3
"""Convert Qwen3.6 live-ABI deferred samples into route JSONL rows.

The graph-capture census hook can emit small deferred samples after XPU graph
capture. This tool extracts complete top-k ID samples and converts them into
the same compact route JSONL format used by the route-class AOT planner.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_CONFIG = (
    "/mnt/fast-ai/llm-cache/hf/"
    "models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/"
    "snapshots/cced56592e8c8935f8220836b4baa04dfd389118/config.json"
)


def load_model_shape(
        config_path: str, *, fallback_topk: int,
        fallback_num_experts: int) -> dict[str, int]:
    try:
        cfg = json.loads(Path(config_path).read_text(encoding="utf-8"))
        text_config = cfg.get("text_config") or {}
        return {
            "topk": int(text_config.get("num_experts_per_tok") or fallback_topk),
            "num_experts": int(
                text_config.get("num_experts") or fallback_num_experts),
        }
    except Exception:
        return {
            "topk": fallback_topk,
            "num_experts": fallback_num_experts,
        }


def read_jsonl(
        paths: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records = []
    errors = []
    for raw_path in paths:
        path = Path(raw_path)
        lines = path.read_text(encoding="utf-8").splitlines()
        for lineno, line in enumerate(lines, 1):
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


def layer_index(layer: str) -> int | None:
    match = re.search(r"layers[.](\d+)[.]", layer)
    if not match:
        return None
    return int(match.group(1))


def stable_route_hash(topk_rows: list[list[int]]) -> str:
    payload = "|".join(",".join(str(item) for item in row) for row in topk_rows)
    return hashlib.blake2s(payload.encode("utf-8"), digest_size=8).hexdigest()


def reshape_topk(
        values: Any, topk: int,
        sample_limit: int) -> tuple[list[list[int]], bool, bool]:
    if not isinstance(values, list) or not values:
        return [], False, False
    flat = []
    for item in values:
        if isinstance(item, list):
            flat.extend(int(value) for value in item)
        else:
            flat.append(int(item))
    complete = len(flat) >= topk and len(flat) % topk == 0
    may_be_truncated = len(flat) >= sample_limit
    usable = flat[:len(flat) - (len(flat) % topk)]
    rows = [
        usable[index:index + topk]
        for index in range(0, len(usable), topk)
    ]
    return rows, complete, may_be_truncated


def build_route_record(
        record: dict[str, Any], *, topk: int, num_experts_default: int,
        sample_limit: int) -> tuple[dict[str, Any] | None, str | None]:
    if record.get("capture_observation") != "deferred_post_capture_sample":
        return None, "not_deferred_sample"
    samples = record.get("samples")
    if not isinstance(samples, dict):
        return None, "missing_samples"
    topk_rows, complete, may_be_truncated = reshape_topk(
        samples.get("topk_ids"), topk, sample_limit)
    if not topk_rows:
        return None, "missing_complete_topk_ids"

    num_experts = num_experts_default
    context = record.get("context")
    if isinstance(context, dict):
        shape = context.get("shape")
        if isinstance(shape, dict) and shape.get("num_experts"):
            num_experts = int(shape["num_experts"])
    counts = [0] * num_experts
    for row in topk_rows:
        for expert in row:
            if 0 <= expert < num_experts:
                counts[expert] += 1

    layer = str(record.get("layer") or "")
    idx = layer_index(layer)
    route = {
        "source_kind": "live_abi_deferred_route_sample",
        "source_path": record.get("_source_path"),
        "source_line": record.get("_source_line"),
        "rank": str(record.get("rank", "")),
        "local_rank": str(record.get("local_rank", "")),
        "call": record.get("call"),
        "event_id": record.get("call"),
        "layer": layer,
        "layer_index": idx,
        "stage": "deferred_post_capture_sample",
        "is_pure_decode": len(topk_rows) == 1,
        "topk": topk,
        "topk_ids": topk_rows,
        "num_tokens": len(topk_rows),
        "num_experts": num_experts,
        "counts": counts,
        "active_experts": sum(1 for count in counts if count),
        "total_assignments": sum(counts),
        "route_hash": stable_route_hash(topk_rows),
        "topk_sample_complete": complete,
        "topk_sample_may_be_truncated": may_be_truncated,
        "checksums": (
            record.get("checksums")
            if isinstance(record.get("checksums"), dict) else {}
        ),
    }
    if not complete:
        return route, "topk_sample_partial"
    if may_be_truncated:
        return route, "topk_sample_hit_limit_may_be_truncated"
    return route, None


def summarize(routes: list[dict[str, Any]],
              skipped: Counter[str],
              parse_errors: list[dict[str, Any]]) -> dict[str, Any]:
    by_layer = Counter(str(route.get("layer", "")) for route in routes)
    by_rank = Counter(str(route.get("rank", "")) for route in routes)
    route_classes = Counter(str(route.get("route_hash", "")) for route in routes)
    decode_routes = [route for route in routes if route.get("is_pure_decode")]
    return {
        "status": "pass" if routes and not parse_errors else "fail",
        "routes_emitted": len(routes),
        "pure_decode_routes": len(decode_routes),
        "unique_route_classes": len(route_classes),
        "layers": dict(sorted(by_layer.items())),
        "ranks": dict(sorted(by_rank.items())),
        "skipped": dict(sorted(skipped.items())),
        "parse_errors": parse_errors,
        "interpretation": (
            "This converts deferred diagnostic route samples only. It is a "
            "route-planning artifact, not a speed or quality proof."
        ),
    }


def write_markdown(path: str, summary: dict[str, Any]) -> None:
    lines = [
        "# Qwen3.6 Live-ABI Route Ledger",
        "",
        f"- Status: `{summary['status']}`.",
        f"- Routes emitted: `{summary['routes_emitted']}`.",
        f"- Pure decode routes: `{summary['pure_decode_routes']}`.",
        f"- Unique route classes: `{summary['unique_route_classes']}`.",
        "",
        "## Skipped Records",
        "",
    ]
    if summary["skipped"]:
        for key, value in summary["skipped"].items():
            lines.append(f"- `{key}`: `{value}`")
    else:
        lines.append("- none")
    lines.extend(["", "## Layers", ""])
    for layer, count in summary["layers"].items():
        lines.append(f"- `{layer}`: `{count}`")
    lines.extend(["", "## Interpretation", "", summary["interpretation"], ""])
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("jsonl", nargs="+", help="Live ABI JSONL log(s).")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--topk", type=int, default=8)
    parser.add_argument("--num-experts", type=int, default=256)
    parser.add_argument("--sample-limit", type=int, default=32)
    parser.add_argument("--output-jsonl", required=True)
    parser.add_argument("--summary-json")
    parser.add_argument("--markdown-out")
    args = parser.parse_args()

    model_shape = load_model_shape(
        args.config,
        fallback_topk=args.topk,
        fallback_num_experts=args.num_experts,
    )
    records, errors = read_jsonl(args.jsonl)
    routes = []
    skipped: Counter[str] = Counter()
    for record in records:
        route, reason = build_route_record(
            record,
            topk=model_shape["topk"],
            num_experts_default=model_shape["num_experts"],
            sample_limit=args.sample_limit,
        )
        if route is None:
            skipped[reason or "unknown"] += 1
            continue
        if reason:
            skipped[reason] += 1
        routes.append(route)

    out = Path(args.output_jsonl)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "".join(json.dumps(route, sort_keys=True) + "\n" for route in routes),
        encoding="utf-8",
    )
    summary = summarize(routes, skipped, errors)
    text = json.dumps(summary, indent=2, sort_keys=True)
    if args.summary_json:
        Path(args.summary_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.summary_json).write_text(text + "\n", encoding="utf-8")
    if args.markdown_out:
        Path(args.markdown_out).parent.mkdir(parents=True, exist_ok=True)
        write_markdown(args.markdown_out, summary)
    print(text)
    return 0 if summary["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
