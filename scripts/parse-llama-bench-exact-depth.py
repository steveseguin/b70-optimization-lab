#!/usr/bin/env python3
"""Validate llama-bench JSON and build exact-depth raw-engine receipts.

The default mode is an inert plan. ``--create`` is the only mode that writes a
receipt and it refuses to overwrite an existing path. ``--check`` rebuilds the
receipt from the two source artifacts and compares it byte-for-byte.

Metadata is deliberately separate from llama-bench output because llama-bench
does not report the executable digest, complete argv/environment, or reliable
graph capture/replay evidence. A requested graph flag is never promoted to a
verified graph-on selector without positive capture *and* replay counts.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
import json
import math
from pathlib import Path
import re
import sys
from typing import Any

import qwen27_exact_depth_common as exact_depth


SCHEMA = "llama-bench-exact-depth-receipt-v1"
METADATA_SCHEMA = "llama-bench-exact-depth-metadata-v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ContractError(RuntimeError):
    """Raised when an input cannot satisfy the exact-depth contract."""


def _plain_int(value: object, field: str) -> int:
    if type(value) is not int:
        raise ContractError(f"{field} must be a plain integer")
    return value


def _finite(value: object, field: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError(f"{field} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ContractError(f"{field} must be a finite number")
    if positive and result <= 0:
        raise ContractError(f"{field} must be positive")
    return result


def _mapping(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractError(f"{field} must be a JSON object")
    result = dict(value)
    if any(type(key) is not str for key in result):
        raise ContractError(f"{field} keys must be strings")
    try:
        exact_depth.canonical_json_bytes(result)
    except ValueError as exc:
        raise ContractError(f"{field} is not canonical JSON: {exc}") from exc
    return result


def _nonempty_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{field} must be a non-empty string")
    return value


def _sha256(value: object, field: str) -> str:
    result = _nonempty_string(value, field)
    if not SHA256_RE.fullmatch(result):
        raise ContractError(f"{field} must be a lowercase SHA-256 digest")
    return result


def load_json(path: Path, field: str) -> Any:
    if not path.is_file():
        raise ContractError(f"{field} does not exist: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"{field} is not valid UTF-8 JSON: {path}") from exc


def _declared_depths(value: object) -> tuple[int, ...]:
    if not isinstance(value, list) or not value:
        raise ContractError("metadata.declared_depths must be a non-empty list")
    depths: list[int] = []
    for index, item in enumerate(value):
        try:
            depth = exact_depth.validate_depth(item)
        except ValueError as exc:
            raise ContractError(
                f"metadata.declared_depths[{index}] is invalid: {exc}"
            ) from exc
        if depth in depths:
            raise ContractError(f"metadata.declared_depths repeats depth {depth}")
        depths.append(depth)
    if 0 not in depths:
        raise ContractError("metadata.declared_depths must include true depth 0")
    return tuple(depth for depth in exact_depth.DECLARED_DEPTHS if depth in depths)


def _identity(value: object, field: str) -> dict[str, Any]:
    identity = _mapping(value, field)
    _nonempty_string(identity.get("path"), f"{field}.path")
    _sha256(identity.get("sha256"), f"{field}.sha256")
    return identity


def _argv(value: object, binary_path: str, model_path: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ContractError("metadata.argv must be a non-empty string list")
    argv: list[str] = []
    for index, item in enumerate(value):
        argv.append(_nonempty_string(item, f"metadata.argv[{index}]"))
    if argv[0] != binary_path:
        raise ContractError("metadata.argv[0] must exactly match metadata.binary.path")

    model_values: list[str] = []
    for index, item in enumerate(argv):
        if item in {"-m", "--model"}:
            if index + 1 >= len(argv):
                raise ContractError(f"metadata.argv {item} has no value")
            model_values.append(argv[index + 1])
        elif item.startswith("--model="):
            model_values.append(item.split("=", 1)[1])
    if model_values != [model_path]:
        raise ContractError(
            "metadata.argv must select metadata.model.path exactly once with "
            "-m, --model, or --model=PATH"
        )
    return argv


def _environment(value: object) -> dict[str, str]:
    environment = _mapping(value, "metadata.env")
    for key, item in environment.items():
        _nonempty_string(key, "metadata.env key")
        if not isinstance(item, str):
            raise ContractError(f"metadata.env[{key!r}] must be a string")
    return dict(sorted(environment.items()))


def _evidence_count(value: object, field: str) -> tuple[dict[str, Any], int]:
    evidence = _mapping(value, field)
    count = _plain_int(evidence.get("count"), f"{field}.count")
    if count < 0:
        raise ContractError(f"{field}.count must be non-negative")
    return evidence, count


def _graph_contract(value: object) -> dict[str, Any]:
    graph = _mapping(value, "metadata.graph")
    requested = graph.get("requested")
    if type(requested) is not bool:
        raise ContractError("metadata.graph.requested must be boolean")
    capture, capture_count = _evidence_count(
        graph.get("capture"), "metadata.graph.capture"
    )
    replay, replay_count = _evidence_count(graph.get("replay"), "metadata.graph.replay")
    positive = capture_count > 0 and replay_count > 0
    if not requested and (capture_count or replay_count):
        raise ContractError(
            "graph capture/replay counts must be zero when graph was not requested"
        )
    if not requested:
        classification = "off"
        selector: str | None = "off"
    elif positive:
        classification = "verified-capture-and-replay"
        selector = "on"
    else:
        classification = "requested-unverified"
        selector = None
    return {
        "requested": requested,
        "classification": classification,
        "positive_capture_and_replay_evidence": positive,
        "cell_selector_graph_mode": selector,
        "capture": capture,
        "replay": replay,
        "evidence_sha256": exact_depth.canonical_json_sha256(
            {"capture": capture, "replay": replay}
        ),
    }


def validate_metadata(value: object) -> dict[str, Any]:
    metadata = _mapping(value, "metadata")
    if metadata.get("schema") != METADATA_SCHEMA:
        raise ContractError(f"metadata.schema must be {METADATA_SCHEMA!r}")
    receipt_id = _nonempty_string(metadata.get("receipt_id"), "metadata.receipt_id")
    depths = _declared_depths(metadata.get("declared_depths"))
    binary = _identity(metadata.get("binary"), "metadata.binary")
    model = _identity(metadata.get("model"), "metadata.model")
    argv = _argv(metadata.get("argv"), binary["path"], model["path"])
    environment = _environment(metadata.get("env"))
    selectors = _mapping(metadata.get("cell_selectors"), "metadata.cell_selectors")
    if not selectors:
        raise ContractError("metadata.cell_selectors must not be empty")
    forbidden = {"active_context_tokens", "graph", "graph_mode"} & selectors.keys()
    if forbidden:
        fields = ", ".join(sorted(forbidden))
        raise ContractError(
            f"metadata.cell_selectors must not predeclare derived fields: {fields}"
        )
    graph = _graph_contract(metadata.get("graph"))
    return {
        "schema": METADATA_SCHEMA,
        "receipt_id": receipt_id,
        "declared_depths": list(depths),
        "binary": binary,
        "model": model,
        "argv": argv,
        "env": environment,
        "cell_selectors": selectors,
        "graph": graph,
        "metadata_sha256": exact_depth.canonical_json_sha256(metadata),
    }


def _raw_metrics(row: Mapping[str, Any], field: str) -> dict[str, Any]:
    avg_ts = _finite(row.get("avg_ts"), f"{field}.avg_ts", positive=True)
    stddev_ts = _finite(row.get("stddev_ts"), f"{field}.stddev_ts")
    if stddev_ts < 0:
        raise ContractError(f"{field}.stddev_ts must be non-negative")
    samples_value = row.get("samples_ts")
    if not isinstance(samples_value, list) or not samples_value:
        raise ContractError(f"{field}.samples_ts must be a non-empty list")
    samples = [
        _finite(item, f"{field}.samples_ts[{index}]", positive=True)
        for index, item in enumerate(samples_value)
    ]
    metrics: dict[str, Any] = {
        "reported_avg_tok_s": avg_ts,
        "reported_stddev_tok_s": stddev_ts,
        "samples_tok_s": samples,
        "sample_stats": exact_depth.summary_stats(samples),
    }
    for name in ("avg_ns", "stddev_ns"):
        if name in row:
            number = _finite(row[name], f"{field}.{name}")
            if number < 0:
                raise ContractError(f"{field}.{name} must be non-negative")
            metrics[name] = number
    if "samples_ns" in row:
        raw_ns = row["samples_ns"]
        if not isinstance(raw_ns, list) or len(raw_ns) != len(samples):
            raise ContractError(
                f"{field}.samples_ns must match samples_ts sample count"
            )
        metrics["samples_ns"] = [
            _plain_int(item, f"{field}.samples_ns[{index}]")
            for index, item in enumerate(raw_ns)
        ]
        if any(item < 0 for item in metrics["samples_ns"]):
            raise ContractError(f"{field}.samples_ns must be non-negative")
    return metrics


def validate_rows(value: object, metadata: Mapping[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ContractError("llama-bench JSON must be a non-empty row array")
    depths = set(metadata["declared_depths"])
    model_path = metadata["model"]["path"]
    decode: dict[int, tuple[dict[str, Any], dict[str, Any]]] = {}
    prefill: dict[int, tuple[dict[str, Any], dict[str, Any]]] = {}
    row_identity: dict[str, Any] | None = None

    for index, item in enumerate(value):
        field = f"llama_bench[{index}]"
        row = _mapping(item, field)
        try:
            depth = exact_depth.validate_depth(row.get("n_depth"))
        except ValueError as exc:
            raise ContractError(f"{field}.n_depth is invalid: {exc}") from exc
        if depth not in depths:
            raise ContractError(f"{field} has undeclared n_depth={depth}")
        n_prompt = _plain_int(row.get("n_prompt"), f"{field}.n_prompt")
        n_gen = _plain_int(row.get("n_gen"), f"{field}.n_gen")
        if n_prompt < 0 or n_gen < 0:
            raise ContractError(f"{field} prompt/generation sizes must be non-negative")
        if row.get("model_filename") != model_path:
            raise ContractError(
                f"{field}.model_filename does not match metadata.model.path"
            )
        identity = {
            key: row.get(key)
            for key in (
                "build_commit",
                "build_number",
                "backends",
                "model_filename",
                "model_type",
                "model_size",
                "model_n_params",
            )
            if key in row
        }
        if row_identity is None:
            row_identity = identity
        elif identity != row_identity:
            raise ContractError(f"{field} changes llama-bench row identity")

        metrics = _raw_metrics(row, field)
        if n_prompt == 0 and n_gen == exact_depth.COMPLETION_TOKEN_BUDGET:
            if depth in decode:
                raise ContractError(f"multiple tg128 rows found for depth {depth}")
            decode[depth] = (row, metrics)
        elif n_prompt > 0 and n_gen == 0:
            if depth in prefill:
                raise ContractError(f"multiple prefill rows found for depth {depth}")
            prefill[depth] = (row, metrics)
        else:
            raise ContractError(f"{field} is neither tg128 decode nor one prefill row")

    missing = [depth for depth in metadata["declared_depths"] if depth not in decode]
    if missing:
        raise ContractError(
            "exactly one tg128 row is required per declared depth; missing: "
            + ", ".join(str(depth) for depth in missing)
        )

    graph_mode = metadata["graph"]["cell_selector_graph_mode"]
    cell_ready = graph_mode is not None
    cells: list[dict[str, Any]] = []
    for depth in metadata["declared_depths"]:
        decode_row, decode_metrics = decode[depth]
        prefill_entry = prefill.get(depth)
        cell = {
            "cell_ready": cell_ready,
            "selectors": {
                **metadata["cell_selectors"],
                "active_context_tokens": depth,
                "graph_mode": graph_mode,
            },
            "active_context_tokens": depth,
            "depth_evidence": {
                "field": "n_depth",
                "reported_value": decode_row["n_depth"],
                "true_zero_measurement": depth == 0,
            },
            "decode": {
                "workload": "tg128",
                "n_prompt": 0,
                "n_gen": exact_depth.COMPLETION_TOKEN_BUDGET,
                **decode_metrics,
            },
            "prefill": None,
        }
        if prefill_entry is not None:
            prefill_row, prefill_metrics = prefill_entry
            cell["prefill"] = {
                "workload": f"pp{prefill_row['n_prompt']}",
                "n_prompt": prefill_row["n_prompt"],
                "n_gen": 0,
                **prefill_metrics,
            }
        cells.append(cell)
    return cells


def build_receipt(
    bench_json: object,
    metadata_json: object,
    *,
    bench_path: Path,
    metadata_path: Path,
) -> dict[str, Any]:
    metadata = validate_metadata(metadata_json)
    cells = validate_rows(bench_json, metadata)
    exact_cell_ready = all(cell["cell_ready"] for cell in cells)
    return {
        "schema": SCHEMA,
        "schema_version": 1,
        "receipt_id": metadata["receipt_id"],
        "status": "passed",
        "measurement": {
            "benchmark": "llama-bench",
            "classification": "raw-engine",
            "workload": "one averaged tg128 row per exact n_depth; optional prefill row",
            "is_http_serving_metric": False,
            "includes_quality_gate": False,
            "promotion_scope": "exact active-context raw-engine performance cells only",
        },
        "gate": {
            "passed": True,
            "declared_depths": metadata["declared_depths"],
            "tg128_rows_exact": True,
            "true_n_depth_zero_present": True,
            "exact_cell_ready": exact_cell_ready,
            "cell_ready_blocker": (
                None
                if exact_cell_ready
                else "graph requested without positive capture and replay evidence"
            ),
        },
        "identity": {
            "binary": metadata["binary"],
            "model": metadata["model"],
            "argv": metadata["argv"],
            "argv_sha256": exact_depth.canonical_json_sha256(metadata["argv"]),
            "env": metadata["env"],
            "env_sha256": exact_depth.canonical_json_sha256(metadata["env"]),
            "metadata_sha256": metadata["metadata_sha256"],
        },
        "graph": metadata["graph"],
        "inputs": {
            "llama_bench_json": str(bench_path.resolve()),
            "llama_bench_json_sha256": exact_depth.canonical_json_sha256(bench_json),
            "metadata_json": str(metadata_path.resolve()),
            "metadata_json_sha256": exact_depth.canonical_json_sha256(metadata_json),
        },
        "cells": cells,
    }


def rendered_json(receipt: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench-json", required=True, type=Path)
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true", help="validate without writing")
    mode.add_argument("--check", action="store_true", help="check an existing receipt")
    mode.add_argument(
        "--create", action="store_true", help="create a new receipt without overwrite"
    )
    return parser


def execute(args: argparse.Namespace) -> dict[str, Any]:
    bench_json = load_json(args.bench_json, "llama-bench JSON")
    metadata_json = load_json(args.metadata, "metadata JSON")
    receipt = build_receipt(
        bench_json,
        metadata_json,
        bench_path=args.bench_json,
        metadata_path=args.metadata,
    )
    data = rendered_json(receipt)
    mode = "check" if args.check else "create" if args.create else "plan"
    if mode == "check":
        if not args.output.is_file():
            raise ContractError(f"receipt does not exist for check: {args.output}")
        if args.output.read_bytes() != data:
            raise ContractError(
                f"receipt differs from regenerated contract: {args.output}"
            )
    elif mode == "create":
        args.output.parent.mkdir(parents=True, exist_ok=True)
        try:
            with args.output.open("xb") as stream:
                stream.write(data)
        except FileExistsError as exc:
            raise ContractError(
                f"refusing to overwrite receipt: {args.output}"
            ) from exc
    return {
        "mode": mode,
        "status": "passed"
        if mode == "check"
        else "created"
        if mode == "create"
        else "planned",
        "output": str(args.output),
        "receipt_sha256": exact_depth.canonical_json_sha256(receipt),
        "declared_depths": receipt["gate"]["declared_depths"],
        "exact_cell_ready": receipt["gate"]["exact_cell_ready"],
        "graph_classification": receipt["graph"]["classification"],
    }


def main() -> int:
    parser = make_parser()
    try:
        result = execute(parser.parse_args())
    except (ContractError, ValueError) as exc:
        parser.error(str(exc))
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
