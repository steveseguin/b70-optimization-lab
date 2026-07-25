#!/usr/bin/env python3
"""Fail-closed analysis for Laguna's in-process Breakable-replay telemetry.

This is diagnostic-only evidence.  It validates the one-request q1/eager/graph
parity gate and reduces the graph arm's four owner-private rank profiles using
the maximum rank time for each replay sample.  It intentionally makes no
throughput or endpoint claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import stat
from pathlib import Path
from typing import Any


ARM_NAMES = ("q1", "eager", "graph")
RANKS = tuple(range(4))
SAMPLES = 31
EXPECTED_MODEL = "/mnt/fast-ai/llm-models/laguna-s-2.1/int4"
EXPECTED_DRAFT = "/mnt/fast-ai/llm-models/laguna-s-2.1/dflash-int4"
EXPECTED_VLLM_ROOT = "/home/steve/src/laguna-vllm-runtime-graph-20260724"
EXPECTED_VLLM_COMMIT = "8cf58ed0f3679245053b6f298b4bf1ccd13906ed"
EXPECTED_KERNEL_ROOT = "/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc"
EXPECTED_KERNEL_COMMIT = "4772f727590c51b72add79350b913d098cf67872"
EXPECTED_KERNELS = {
    "_C.abi3.so": "126da37b23e5eff6840dd256c90164e3a282469e5fafa27830530e63ff36bce2",
    "_xpu_C.abi3.so": "f5f672130cc1b1d550646f732a6d576952c49514eba7a10db60fc1c361938fd8",
    "_moe_C.abi3.so": "6a6794249421aceb51f14980a3e2c0b0a9d7b492abf2f8d25b129b86f099bc5b",
    "libgrouped_gemm_xe_2.so": (
        "fc74a6452b95643768889e2598df77bc4f4aa2b0925257a4c0eff371b1cf6c96"
    ),
}
SEGMENT_COUNTS = {"graph": 146, "collective": 97, "attention": 48, "eager": 0}
TIMING_FIELDS = (
    "capture_replay_host_loop_ns",
    "debug_guard_ns",
    "offloader_sync_ns",
    "post_replay_synchronize_ns",
    "replay_host_total_ns",
    "static_signature_collect_ns",
    "static_signature_compare_ns",
    "whole_replay_completion_ns",
)


def die(message: str) -> None:
    raise SystemExit(f"Laguna M8 in-process replay analysis: {message}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_regular(path: Path, label: str) -> None:
    try:
        metadata = path.lstat()
    except OSError as exc:
        die(f"{label} is missing: {path}: {exc}")
    if path.is_symlink() or not stat.S_ISREG(metadata.st_mode):
        die(f"{label} must be a regular non-symlink file: {path}")


def read_json(path: Path, label: str) -> dict[str, Any]:
    require_regular(path, label)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        die(f"cannot parse {label}: {path}: {exc}")
    if not isinstance(value, dict):
        die(f"{label} must contain one JSON object: {path}")
    return value


def nonnegative_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        die(f"{label} must be a non-negative integer")
    return value


def positive_int(value: Any, label: str) -> int:
    parsed = nonnegative_int(value, label)
    if parsed == 0:
        die(f"{label} must be positive")
    return parsed


def write_exclusive(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
        0o600,
    )
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                die("short analysis write")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def percentile(values: list[int], fraction: float) -> float:
    if not values:
        die("cannot summarize an empty timing vector")
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    lower, upper = math.floor(index), math.ceil(index)
    if lower == upper:
        return float(ordered[lower])
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def arm_record_path(root: Path, arm: str) -> Path:
    arm_root = root / arm
    candidates = [arm_root / "driver.json", arm_root / "arm.json"]
    present = [path for path in candidates if path.exists() or path.is_symlink()]
    if len(present) != 1:
        die(f"{arm} requires exactly one arm record named driver.json or arm.json")
    return present[0]


def validate_arm(record: dict[str, Any], arm: str, profile_root: Path | None) -> None:
    optimized_dflash = arm != "q1"
    required = {
        "schema": "laguna-m8-inprocess-replay-arm-v1",
        "status": "complete",
        "diagnostic_only": True,
        "single_generate_call": True,
        "fresh_process": True,
        "arm": arm,
        "model": EXPECTED_MODEL,
        "vllm_root": EXPECTED_VLLM_ROOT,
        "vllm_commit": EXPECTED_VLLM_COMMIT,
        "kernel_root": EXPECTED_KERNEL_ROOT,
        "kernel_commit": EXPECTED_KERNEL_COMMIT,
        "async_scheduling": arm == "q1",
        "completion_tokens": 128,
        "cached_tokens": 0,
    }
    for key, expected in required.items():
        if record.get(key) != expected:
            die(f"{arm} arm field {key!r} drifted")
    for key in ("prompt_sha256", "text_sha256", "finish_reason"):
        if not isinstance(record.get(key), str) or not record[key]:
            die(f"{arm} arm lacks non-empty {key}")
    positive_int(record.get("prompt_tokens"), f"{arm} prompt_tokens")
    positive_int(record.get("generation_wall_ns"), f"{arm} generation_wall_ns")
    token_ids = record.get("token_ids")
    if not isinstance(token_ids, list) or len(token_ids) != 128 or not all(
        isinstance(token, int) and not isinstance(token, bool) for token in token_ids
    ):
        die(f"{arm} arm token IDs are not exactly 128 integers")
    expected_token_hash = hashlib.sha256(
        json.dumps(token_ids, separators=(",", ":")).encode()
    ).hexdigest()
    if record.get("token_ids_sha256") != expected_token_hash:
        die(f"{arm} arm token ID digest drifted")
    kernel_identity = record.get("kernel_identity")
    if not isinstance(kernel_identity, dict) or set(kernel_identity) != set(
        EXPECTED_KERNELS
    ):
        die(f"{arm} arm kernel identity drifted")
    for name, expected_hash in EXPECTED_KERNELS.items():
        expected_path = str(Path(EXPECTED_KERNEL_ROOT) / "vllm_xpu_kernels" / name)
        if kernel_identity[name] != {
            "path": expected_path,
            "sha256": expected_hash,
        }:
            die(f"{arm} arm kernel binary {name} drifted")
    environment = record.get("environment")
    if not isinstance(environment, dict):
        die(f"{arm} arm lacks its frozen environment")
    graph = arm == "graph"
    expected_environment = {
        "CCL_ATL_TRANSPORT": "ofi",
        "CCL_KVS_IFACE": "eno1",
        "CCL_TOPO_P2P_ACCESS": "1",
        "FI_TCP_IFACE": "eno1",
        "LAGUNA_DFLASH_NUM_SPECULATIVE_TOKENS": "7",
        "ONEAPI_DEVICE_SELECTOR": "level_zero:0,1,2,3",
        "TORCH_XCCL_ASYNC_ERROR_HANDLING": "1",
        "VLLM_DISABLE_SHARED_EXPERTS_STREAM": "0",
        "VLLM_KV_CACHE_LAYOUT": "NHD",
        "VLLM_SHARED_EXPERTS_STREAM_TOKEN_THRESHOLD": "256",
        "VLLM_TRACE_FUNCTION": "0",
        "VLLM_USE_AOT_COMPILE": "0",
        "VLLM_USE_BREAKABLE_CUDAGRAPH": "1" if graph else "0",
        "VLLM_XPU_ENABLE_XPU_GRAPH": "1" if graph else "0",
        "VLLM_XPU_EXACT_SPEC_ATTN": "1",
        "VLLM_XPU_EXPERT_MAP_ROUND_ROBIN": "0",
        "VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE": "1",
        "VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH": "0",
        "VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH": "1" if graph else "0",
        "VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM": "0",
        "VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK": "0",
        "VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2": (
            "1" if optimized_dflash else "0"
        ),
        "VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION": "0",
        "VLLM_XPU_LAGUNA_M8_GATHER_FINALIZE": "0",
        "VLLM_XPU_LAGUNA_M8_GATHER_SHARDED": "0",
        "VLLM_XPU_LAGUNA_M8_QKNORM_ROPE": "1" if optimized_dflash else "0",
        "VLLM_XPU_LAGUNA_M8_REMOTE_ZERO": "0",
        "VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE": (
            "1" if optimized_dflash else "0"
        ),
        "VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM": "0",
        "VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE": (
            "1" if optimized_dflash else "0"
        ),
        "VLLM_XPU_LAGUNA_M8_SHARED_EXPERT_STREAM": "0",
        "VLLM_XPU_LAGUNA_M8_SHARED_GATE_MM": "0",
        "VLLM_XPU_LAGUNA_M8_SHARED_GATE_UP_MM": "0",
        "VLLM_XPU_LAGUNA_M8_W1_N_TILE": "64",
        "VLLM_XPU_LAGUNA_PARITY_PROBE": "0",
        "VLLM_XPU_V4_M1_BIASED_TOPK": "0",
        "VLLM_XPU_V4_M1_ROUTER_NORM": "0",
        "XPU_GRAPH": "1" if graph else "0",
        "ZE_AFFINITY_MASK": "0,1,2,3",
    }
    if graph:
        assert profile_root is not None
        expected_environment.update(
            {
                "VLLM_XPU_LAGUNA_REPLAY_PROFILE_ROOT": str(profile_root),
                "VLLM_XPU_LAGUNA_REPLAY_PROFILE_SAMPLES": "31",
            }
        )
    if environment != expected_environment:
        die(f"{arm} arm frozen environment drifted")
    if arm == "graph":
        if record.get("profile_samples") != SAMPLES or profile_root is None:
            die("graph arm profile sample contract drifted")
        if record.get("profile_root") != str(profile_root):
            die("graph arm profile root disagrees with the profile directory")
        expected_compile = {
            "mode": "NONE",
            "cudagraph_mode": "PIECEWISE",
            "cudagraph_capture_sizes": [8],
            "max_cudagraph_capture_size": 8,
        }
        if record.get("compilation_config") != expected_compile:
            die("graph arm compilation identity drifted")
        rank_files = record.get("profile_rank_files")
        if not isinstance(rank_files, dict) or set(rank_files) != {
            str(rank) for rank in RANKS
        }:
            die("graph arm lacks its four closed profile-file identities")
    else:
        if (
            record.get("profile_root") is not None
            or record.get("profile_samples") is not None
            or record.get("profile_rank_files") is not None
        ):
            die(f"{arm} arm unexpectedly carries replay telemetry")
        if record.get("compilation_config") is not None:
            die(f"{arm} arm unexpectedly uses compilation")
    if arm == "q1":
        if record.get("draft_model") is not None:
            die("q1 arm unexpectedly has a draft model")
    elif record.get("draft_model") != EXPECTED_DRAFT:
        die(f"{arm} arm DFlash model identity drifted")


def validate_profile(payload: dict[str, Any], rank: int) -> list[dict[str, Any]]:
    expected = {
        "schema": "laguna-m8-breakable-replay-profile-v1",
        "status": "complete",
        "rank": rank,
        "samples": SAMPLES,
        "graphs": 146,
        "eager_breaks": 145,
        "boundary_categories": {"attention": 48, "collective": 97},
    }
    for key, value in expected.items():
        if payload.get(key) != value:
            die(f"rank{rank} profile {key!r} drifted")
    if not isinstance(payload.get("batch_descriptor"), str) or not payload["batch_descriptor"]:
        die(f"rank{rank} profile lacks batch descriptor")
    digest = payload.get("segment_kind_order_sha256")
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        die(f"rank{rank} profile has an invalid segment-order digest")
    records = payload.get("records")
    if not isinstance(records, list) or len(records) != SAMPLES:
        die(f"rank{rank} profile must contain exactly {SAMPLES} replay rows")
    for sample, record in enumerate(records):
        if not isinstance(record, dict) or record.get("sample") != sample:
            die(f"rank{rank} replay sample order drifted at {sample}")
        if set(record) != {"sample", *TIMING_FIELDS, "segment_host_call_ns", "segment_host_call_total_ns", "segment_ordered_host_call_ns"}:
            die(f"rank{rank} sample {sample} schema drifted")
        for name in TIMING_FIELDS:
            nonnegative_int(record[name], f"rank{rank} sample {sample} {name}")
        for name in set(TIMING_FIELDS) - {"debug_guard_ns"}:
            positive_int(record[name], f"rank{rank} sample {sample} {name}")
        durations = record["segment_host_call_ns"]
        totals = record["segment_host_call_total_ns"]
        ordered = record["segment_ordered_host_call_ns"]
        if not isinstance(durations, dict) or set(durations) != set(SEGMENT_COUNTS):
            die(f"rank{rank} sample {sample} duration categories drifted")
        if not isinstance(totals, dict) or set(totals) != set(SEGMENT_COUNTS):
            die(f"rank{rank} sample {sample} total categories drifted")
        if not isinstance(ordered, list) or len(ordered) != sum(SEGMENT_COUNTS.values()):
            die(f"rank{rank} sample {sample} ordered segment count drifted")
        seen = {kind: 0 for kind in SEGMENT_COUNTS}
        for kind, values in durations.items():
            if not isinstance(values, list) or len(values) != SEGMENT_COUNTS[kind]:
                die(f"rank{rank} sample {sample} {kind} duration count drifted")
            numbers = [nonnegative_int(value, f"rank{rank} sample {sample} {kind} duration") for value in values]
            if kind != "eager" and any(value == 0 for value in numbers):
                die(f"rank{rank} sample {sample} {kind} duration must be positive")
            if totals[kind] != sum(numbers):
                die(f"rank{rank} sample {sample} {kind} total does not equal its rows")
        for ordinal, value in enumerate(ordered):
            if not isinstance(value, list) or len(value) != 2 or value[0] not in SEGMENT_COUNTS:
                die(f"rank{rank} sample {sample} ordered segment {ordinal} drifted")
            kind, duration = value
            nonnegative_int(duration, f"rank{rank} sample {sample} ordered duration")
            seen[kind] += 1
        if seen != SEGMENT_COUNTS:
            die(f"rank{rank} sample {sample} ordered category counts drifted")
        offsets = {kind: 0 for kind in SEGMENT_COUNTS}
        for ordinal, (kind, duration) in enumerate(ordered):
            if duration != durations[kind][offsets[kind]]:
                die(f"rank{rank} sample {sample} ordered duration drifted at {ordinal}")
            offsets[kind] += 1
        segment_total = sum(totals.values())
        if (
            record["capture_replay_host_loop_ns"] < segment_total
            or record["replay_host_total_ns"]
            < record["capture_replay_host_loop_ns"]
            or record["whole_replay_completion_ns"]
            < record["replay_host_total_ns"]
            + record["post_replay_synchronize_ns"]
        ):
            die(f"rank{rank} sample {sample} timing containment drifted")
    return records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.run_dir.resolve(strict=True)
    if not root.is_dir() or root.is_symlink() or not root.is_relative_to(Path("/mnt/fast-ai")):
        die("run directory must be an internal-NVMe non-symlink directory")
    if args.out.exists() or args.out.is_symlink():
        die("refusing to overwrite analysis output")

    arm_paths = {arm: arm_record_path(root, arm) for arm in ARM_NAMES}
    arms = {arm: read_json(path, f"{arm} arm record") for arm, path in arm_paths.items()}
    graph_profile_text = arms["graph"].get("profile_root")
    if not isinstance(graph_profile_text, str):
        die("graph arm has no profile root")
    profile_root_unresolved = Path(graph_profile_text)
    try:
        profile_metadata = profile_root_unresolved.lstat()
        profile_root = profile_root_unresolved.resolve(strict=True)
    except OSError as exc:
        die(f"graph profile root is unavailable: {exc}")
    if (
        profile_root_unresolved.is_symlink()
        or not stat.S_ISDIR(profile_metadata.st_mode)
        or stat.S_IMODE(profile_metadata.st_mode) != 0o700
        or not profile_root.is_relative_to(Path("/mnt/fast-ai"))
    ):
        die("graph profile root must be an owner-private internal-NVMe directory")
    for arm, record in arms.items():
        validate_arm(record, arm, profile_root if arm == "graph" else None)

    identity_fields = (
        "model",
        "vllm_root",
        "vllm_commit",
        "kernel_root",
        "kernel_commit",
        "kernel_identity",
        "prompt_sha256",
        "prompt_tokens",
    )
    for field in identity_fields:
        if len({json.dumps(arms[arm].get(field), sort_keys=True) for arm in ARM_NAMES}) != 1:
            die(f"q1/eager/graph identity drifted at {field}")
    exact_fields = ("token_ids", "token_ids_sha256", "text_sha256", "finish_reason")
    for field in exact_fields:
        if len({json.dumps(arms[arm].get(field), sort_keys=True) for arm in ARM_NAMES}) != 1:
            die(f"q1/eager/graph exact output mismatch at {field}")

    profiles: dict[int, dict[str, Any]] = {}
    rank_records: dict[int, list[dict[str, Any]]] = {}
    for rank in RANKS:
        path = profile_root / f"rank{rank}.json"
        metadata = path.lstat() if path.exists() or path.is_symlink() else None
        if metadata is None or stat.S_IMODE(metadata.st_mode) != 0o600:
            die(f"rank{rank} profile must be owner-private mode 0600")
        profiles[rank] = read_json(path, f"rank{rank} profile")
        rank_records[rank] = validate_profile(profiles[rank], rank)
        graph_file_identity = arms["graph"]["profile_rank_files"][str(rank)]
        if graph_file_identity != {
            "path": str(path),
            "sha256": sha256_file(path),
        }:
            die(f"graph arm rank{rank} profile identity drifted")
    names = {path.name for path in profile_root.iterdir()}
    expected_names = {f"rank{rank}.json" for rank in RANKS}
    if names != expected_names:
        die("profile root must contain exactly the four rank profile files")
    descriptors = {profiles[rank]["batch_descriptor"] for rank in RANKS}
    digests = {profiles[rank]["segment_kind_order_sha256"] for rank in RANKS}
    if len(descriptors) != 1 or len(digests) != 1:
        die("four ranks disagree on descriptor or segment-order digest")
    expected_kind_order = [row[0] for row in rank_records[0][0]["segment_ordered_host_call_ns"]]
    for rank in RANKS:
        for sample, record in enumerate(rank_records[rank]):
            kind_order = [row[0] for row in record["segment_ordered_host_call_ns"]]
            if kind_order != expected_kind_order:
                die(f"rank{rank} sample {sample} segment-kind ordering drifted")

    max_rank_rows: list[dict[str, Any]] = []
    for sample in range(SAMPLES):
        row: dict[str, Any] = {"sample": sample}
        for field in TIMING_FIELDS:
            values = [rank_records[rank][sample][field] for rank in RANKS]
            maximum = max(values)
            row[field] = maximum
            row[f"{field}_max_rank"] = min(rank for rank, value in zip(RANKS, values) if value == maximum)
        for kind in SEGMENT_COUNTS:
            values = [rank_records[rank][sample]["segment_host_call_total_ns"][kind] for rank in RANKS]
            maximum = max(values)
            row[f"segment_host_call_total_ns_{kind}"] = maximum
            row[f"segment_host_call_total_ns_{kind}_max_rank"] = min(rank for rank, value in zip(RANKS, values) if value == maximum)
        max_rank_rows.append(row)

    summary = {
        field: {
            "min_ns": min(row[field] for row in max_rank_rows),
            "median_ns": percentile([row[field] for row in max_rank_rows], 0.5),
            "p10_ns": percentile([row[field] for row in max_rank_rows], 0.1),
            "p90_ns": percentile([row[field] for row in max_rank_rows], 0.9),
            "max_ns": max(row[field] for row in max_rank_rows),
        }
        for field in (*TIMING_FIELDS, *(f"segment_host_call_total_ns_{kind}" for kind in SEGMENT_COUNTS))
    }
    result = {
        "schema": "laguna-m8-inprocess-replay-analysis-v1",
        "status": "pass",
        "diagnostic_only": True,
        "not_benchmark_or_submission_evidence": True,
        "bitwise_exact_q1_eager_graph": True,
        "profile_contract": {
            "ranks": list(RANKS),
            "samples_per_rank": SAMPLES,
            "graphs": 146,
            "eager_breaks": 145,
            "boundary_categories": {"attention": 48, "collective": 97},
            "batch_descriptor": next(iter(descriptors)),
            "segment_kind_order_sha256": next(iter(digests)),
        },
        "arms": {
            arm: {"path": str(arm_paths[arm]), "sha256": sha256_file(arm_paths[arm]), "record": arms[arm]}
            for arm in ARM_NAMES
        },
        "profiles": {
            str(rank): {"path": str(profile_root / f"rank{rank}.json"), "sha256": sha256_file(profile_root / f"rank{rank}.json")}
            for rank in RANKS
        },
        "max_rank_samples": max_rank_rows,
        "max_rank_summary": summary,
    }
    write_exclusive(args.out, result)
    print("Laguna M8 in-process replay analysis PASS: q1/eager/graph exact; four rank profiles; max-rank aggregate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
