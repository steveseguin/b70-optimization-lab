#!/usr/bin/env python3
"""Fail-closed analysis for the Laguna M8 current-stream event diagnostic.

This is deliberately not a benchmark reducer.  XPU events timestamp work on
one rank-local current stream, so this tool selects one slowest *rank total*
and reports category sums only from that same rank.  It never constructs a
TP4 critical path from independent per-category maxima.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any

from laguna_m8_current_stream_event_contract import (
    expected_environment as shared_expected_environment,
)
from run_laguna_m8_current_stream_event_arm import KERNELS as EXPECTED_KERNELS

ARMS = ("q1", "graph-event")
RANKS = tuple(range(4))
COMPLETION_TOKENS = 272
PROFILE_SCHEMA = "laguna-m8-current-stream-event-profile-v1"
ARM_SCHEMA = "laguna-m8-current-stream-event-arm-v1"
CLOSURE_SCHEMA = "laguna-m8-current-stream-event-closure-v1"
ANALYSIS_SCHEMA = "laguna-m8-current-stream-event-analysis-v1"
EXPECTED_MODEL = "/mnt/fast-ai/llm-models/laguna-s-2.1/int4"
EXPECTED_DRAFT = "/mnt/fast-ai/llm-models/laguna-s-2.1/dflash-int4"
EXPECTED_VLLM_ROOT = "/home/steve/src/laguna-vllm-runtime-graph-20260724"
EXPECTED_VLLM_COMMIT = "fcc2506f7da3a9fd142928af9275d25b9687342a"
EXPECTED_KERNEL_ROOT = "/home/steve/src/deepseek-v4-xpu-kernels-record-4772f727"
EXPECTED_KERNEL_COMMIT = "4772f727590c51b72add79350b913d098cf67872"
KIND_ORDER_SHA256 = "e5b64443ef499d8bb8b138a94ad504effeaa6434a8884ae9f885aecf12d34e1b"
KIND_COUNTS = {"graph": 146, "collective": 97, "attention": 48}
CHECK_NAMES = (
    "pre-workers.txt",
    "pre-idle.json",
    "q1/pre-workers.txt",
    "q1/pre-idle.json",
    "q1/post-workers.txt",
    "q1/post-idle.json",
    "graph-event/pre-workers.txt",
    "graph-event/pre-idle.json",
    "graph-event/post-workers.txt",
    "graph-event/post-idle.json",
    "post-workers.txt",
    "post-idle.json",
)


def die(message: str) -> None:
    raise SystemExit(f"Laguna current-stream event analysis: {message}")


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
        die(f"{label} is missing: {exc}")
    if (
        path.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) not in (0o400, 0o600)
    ):
        die(f"{label} must be a regular mode-0400/0600 non-symlink file")


def read_json(path: Path, label: str) -> dict[str, Any]:
    require_regular(path, label)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        die(f"cannot parse {label}: {exc}")
    if not isinstance(value, dict):
        die(f"{label} must be one JSON object")
    return value


def write_exclusive(path: Path, value: dict[str, Any]) -> None:
    raw = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    descriptor = os.open(
        path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC, 0o600
    )
    try:
        offset = 0
        while offset < len(raw):
            written = os.write(descriptor, raw[offset:])
            if written <= 0:
                die("short analysis write")
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def nonnegative_int(value: Any, label: str) -> int:
    if type(value) is not int or value < 0:
        die(f"{label} must be a non-negative integer")
    return value


def positive_int(value: Any, label: str) -> int:
    parsed = nonnegative_int(value, label)
    if parsed == 0:
        die(f"{label} must be positive")
    return parsed


def canonical_kind_order() -> list[str]:
    first = ["graph", "collective", "graph", "attention"]
    middle = ["graph", "collective", "graph", "collective", "graph", "attention"]
    last = ["graph", "collective", "graph", "collective", "graph"]
    return first + middle * 47 + last


EXPECTED_KINDS = canonical_kind_order()
assert len(EXPECTED_KINDS) == 291
assert {kind: EXPECTED_KINDS.count(kind) for kind in KIND_COUNTS} == KIND_COUNTS
assert (
    hashlib.sha256(",".join(EXPECTED_KINDS).encode()).hexdigest() == KIND_ORDER_SHA256
)


def hash_is_valid(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        die(f"{label} must be a lowercase SHA-256")
    return value


def git_commit_is_valid(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 40
        or any(c not in "0123456789abcdef" for c in value)
    ):
        die(f"{label} must be a lowercase Git commit")
    return value


def expected_environment(profile_root: Path | None) -> dict[str, str]:
    return shared_expected_environment(profile_root is not None, profile_root)


def validate_arm(record: dict[str, Any], arm: str, profile_root: Path | None) -> None:
    graph = arm == "graph-event"
    required = {
        "schema": ARM_SCHEMA,
        "status": "complete",
        "diagnostic_only": True,
        "not_benchmark_or_submission_evidence": True,
        "single_generate_call": True,
        "fresh_process": True,
        "arm": arm,
        "graph": graph,
        "model": EXPECTED_MODEL,
        "draft_model": EXPECTED_DRAFT if graph else None,
        "vllm_root": EXPECTED_VLLM_ROOT,
        "vllm_commit": EXPECTED_VLLM_COMMIT,
        "kernel_root": EXPECTED_KERNEL_ROOT,
        "kernel_commit": EXPECTED_KERNEL_COMMIT,
        "completion_tokens": COMPLETION_TOKENS,
        "cached_tokens": 0,
        "finish_reason": "length",
        "async_scheduling": not graph,
    }
    for key, expected in required.items():
        if record.get(key) != expected:
            die(f"{arm} arm field {key!r} drifted")
    for key in ("prompt_sha256", "text_sha256"):
        hash_is_valid(record.get(key), f"{arm} {key}")
    positive_int(record.get("prompt_tokens"), f"{arm} prompt_tokens")
    positive_int(record.get("generation_wall_ns"), f"{arm} generation_wall_ns")
    token_ids = record.get("token_ids")
    if (
        not isinstance(token_ids, list)
        or len(token_ids) != COMPLETION_TOKENS
        or not all(type(token) is int for token in token_ids)
    ):
        die(f"{arm} token IDs drifted")
    digest = hashlib.sha256(
        json.dumps(token_ids, separators=(",", ":")).encode()
    ).hexdigest()
    if record.get("token_ids_sha256") != digest:
        die(f"{arm} token digest drifted")
    kernel_identity = record.get("kernel_identity")
    if not isinstance(kernel_identity, dict) or set(kernel_identity) != set(
        EXPECTED_KERNELS
    ):
        die(f"{arm} kernel identity drifted")
    for name, expected_hash in EXPECTED_KERNELS.items():
        expected = {
            "path": str(Path(EXPECTED_KERNEL_ROOT) / "vllm_xpu_kernels" / name),
            "sha256": expected_hash,
        }
        if kernel_identity.get(name) != expected:
            die(f"{arm} kernel binary {name} drifted")
    if record.get("environment") != expected_environment(profile_root):
        die(f"{arm} environment drifted")
    if graph:
        if record.get("event_root") != str(profile_root) or not isinstance(
            record.get("event_rank_files"), dict
        ):
            die("graph-event profile identity drifted")
        expected_compile = {
            "mode": "NONE",
            "cudagraph_mode": "PIECEWISE",
            "cudagraph_capture_sizes": [8],
            "max_cudagraph_capture_size": 8,
        }
        if record.get("compilation_config") != expected_compile:
            die("graph-event compilation identity drifted")
    elif any(
        record.get(key) is not None
        for key in ("event_root", "event_rank_files", "compilation_config")
    ):
        die("q1 arm unexpectedly carries graph telemetry")


def validate_profile(payload: dict[str, Any], rank: int) -> dict[str, Any]:
    required = {
        "schema": PROFILE_SCHEMA,
        "status": "complete",
        "rank": rank,
        "world_size": 4,
        "graphs": 146,
        "eager_breaks": 145,
        "boundary_categories": {"attention": 48, "collective": 97},
        "event_count": 292,
        "interval_count": 291,
        "segment_kind_order_sha256": KIND_ORDER_SHA256,
        "rank_local_only": True,
        "global_critical_path_validated": False,
        "collective_cross_stream_completion_validated": False,
        "diagnostic_only": True,
        "not_benchmark_or_submission_evidence": True,
    }
    for key, expected in required.items():
        if payload.get(key) != expected:
            die(f"rank{rank} profile field {key!r} drifted")
    batch_descriptor = payload.get("batch_descriptor")
    if not isinstance(batch_descriptor, str) or not batch_descriptor:
        die(f"rank{rank} batch descriptor drifted")
    stream = payload.get("stream_identity")
    if (
        not isinstance(stream, dict)
        or set(stream) != {"device_type", "device_index", "stream_id"}
        or stream.get("device_type") != "xpu"
    ):
        die(f"rank{rank} stream identity drifted")
    nonnegative_int(stream.get("device_index"), f"rank{rank} stream device index")
    nonnegative_int(stream.get("stream_id"), f"rank{rank} stream id")
    total = positive_int(payload.get("total_duration_ns"), f"rank{rank} total duration")
    intervals = payload.get("intervals")
    if not isinstance(intervals, list) or len(intervals) != 291:
        die(f"rank{rank} interval count drifted")
    kinds: list[str] = []
    sums = {kind: 0 for kind in KIND_COUNTS}
    for index, interval in enumerate(intervals):
        if not isinstance(interval, dict) or set(interval) != {
            "index",
            "kind",
            "duration_ns",
        }:
            die(f"rank{rank} interval{index} schema drifted")
        if interval["index"] != index or interval["kind"] != EXPECTED_KINDS[index]:
            die(f"rank{rank} interval{index} ordering drifted")
        duration = nonnegative_int(
            interval["duration_ns"], f"rank{rank} interval{index} duration"
        )
        kinds.append(interval["kind"])
        sums[interval["kind"]] += duration
    if {kind: kinds.count(kind) for kind in KIND_COUNTS} != KIND_COUNTS:
        die(f"rank{rank} interval category counts drifted")
    return {
        "batch_descriptor": batch_descriptor,
        "total_duration_ns": total,
        "kind_sums_ns": sums,
        "stream_identity": stream,
    }


def validate_profiles(root: Path, arm: dict[str, Any]) -> dict[str, Any]:
    profile_root = root / "graph-event" / "current-stream-event-profile"
    metadata = profile_root.lstat()
    if (
        profile_root.is_symlink()
        or not stat.S_ISDIR(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) not in (0o500, 0o700)
    ):
        die("event-profile root identity drifted")
    if arm.get("event_root") != str(profile_root):
        die("graph-event profile root binding drifted")
    expected_names = {f"rank{rank}.json" for rank in RANKS}
    if {entry.name for entry in profile_root.iterdir()} != expected_names:
        die("event-profile root must contain exactly four rank files")
    ranks: dict[int, dict[str, Any]] = {}
    files: dict[str, dict[str, str]] = {}
    for rank in RANKS:
        path = profile_root / f"rank{rank}.json"
        payload = read_json(path, f"event profile rank{rank}")
        ranks[rank] = validate_profile(payload, rank)
        identity = {"path": str(path), "sha256": sha256_file(path)}
        if arm["event_rank_files"].get(str(rank)) != identity:
            die(f"rank{rank} profile hash binding drifted")
        files[str(rank)] = identity
    totals = {rank: ranks[rank]["total_duration_ns"] for rank in RANKS}
    descriptors = {ranks[rank]["batch_descriptor"] for rank in RANKS}
    if len(descriptors) != 1:
        die("event-profile batch descriptor drifted across ranks")
    slowest_rank = min(
        rank for rank, total in totals.items() if total == max(totals.values())
    )
    return {
        "profile_root": str(profile_root),
        "files": files,
        "batch_descriptor": next(iter(descriptors)),
        "rank_total_duration_ns": {str(rank): totals[rank] for rank in RANKS},
        "per_rank_kind_sums_ns": {
            str(rank): ranks[rank]["kind_sums_ns"] for rank in RANKS
        },
        "slowest_rank": slowest_rank,
        "slowest_rank_total_duration_ns": totals[slowest_rank],
        "selected_rank_kind_sums_ns": ranks[slowest_rank]["kind_sums_ns"],
        "selected_rank_stream_identity": ranks[slowest_rank]["stream_identity"],
    }


def validate_closure(
    root: Path, arms: dict[str, dict[str, Any]], profile: dict[str, Any]
) -> dict[str, Any]:
    closure_path = root / "closure.json"
    closure = read_json(closure_path, "campaign closure")
    expected_keys = {
        "schema",
        "status",
        "diagnostic_only",
        "model_generation_count",
        "network_access",
        "localmaxxing_submission_made",
        "identity",
        "arms",
        "profiles",
        "checks",
    }
    if (
        set(closure) != expected_keys
        or closure.get("schema") != CLOSURE_SCHEMA
        or closure.get("status") != "complete"
        or closure.get("diagnostic_only") is not True
        or closure.get("model_generation_count") != 2
        or closure.get("network_access") is not False
        or closure.get("localmaxxing_submission_made") is not False
    ):
        die("campaign closure schema or honesty fields drifted")
    for arm in ARMS:
        path = root / arm / "driver.json"
        if closure["arms"].get(arm) != {"path": str(path), "sha256": sha256_file(path)}:
            die(f"closure arm {arm} binding drifted")
    identity_path = root / "identity.txt"
    require_regular(identity_path, "controller identity")
    if closure["identity"] != {
        "path": str(identity_path),
        "sha256": sha256_file(identity_path),
    }:
        die("closure controller identity binding drifted")
    if closure["profiles"] != profile["files"]:
        die("closure profile binding drifted")
    checks = closure.get("checks")
    if not isinstance(checks, dict) or set(checks) != set(CHECK_NAMES):
        die("campaign closure check set drifted")
    for name in CHECK_NAMES:
        path = root / name
        require_regular(path, f"campaign check {name}")
        identity = {"path": str(path), "sha256": sha256_file(path)}
        if checks.get(name) != identity:
            die(f"campaign closure check {name} binding drifted")
        if name.endswith("workers.txt"):
            if path.read_bytes() != b"":
                die(f"campaign closure worker check {name} is not empty")
        else:
            idle = read_json(path, f"idle check {name}")
            if (
                idle.get("format")
                != "laguna-m8-gather-sharded-operational-preflight-v2"
                or idle.get("status") != "passed"
                or not isinstance(idle.get("idle"), dict)
                or idle["idle"].get("device_ids") != [0, 1, 2, 3]
            ):
                die(f"campaign closure idle check {name} failed")
    return {
        "path": str(closure_path),
        "sha256": sha256_file(closure_path),
        "record": closure,
        "checks": checks,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    unresolved = args.run_dir
    metadata = unresolved.lstat()
    root = unresolved.resolve(strict=True)
    if (
        unresolved.is_symlink()
        or not stat.S_ISDIR(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) not in (0o500, 0o700)
        or not root.is_relative_to(
            Path("/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs")
        )
    ):
        die("run root must be an owner-private internal-NVMe directory")
    if args.out.exists() or args.out.is_symlink():
        die("refusing to overwrite analysis output")
    if stat.S_IMODE(metadata.st_mode) == 0o500 and args.out.parent.resolve(
        strict=True
    ).is_relative_to(root):
        die("sealed run analysis output must stay outside the run root")
    arm_paths = {arm: root / arm / "driver.json" for arm in ARMS}
    arms = {arm: read_json(path, f"{arm} arm") for arm, path in arm_paths.items()}
    profile_root = root / "graph-event" / "current-stream-event-profile"
    validate_arm(arms["q1"], "q1", None)
    validate_arm(arms["graph-event"], "graph-event", profile_root)
    for key in (
        "model",
        "vllm_root",
        "vllm_commit",
        "kernel_root",
        "kernel_commit",
        "kernel_identity",
        "prompt_sha256",
        "prompt_tokens",
        "token_ids",
        "token_ids_sha256",
        "text_sha256",
        "finish_reason",
    ):
        if json.dumps(arms["q1"].get(key), sort_keys=True) != json.dumps(
            arms["graph-event"].get(key), sort_keys=True
        ):
            die(f"q1/graph-event exact identity drifted at {key}")
    profile = validate_profiles(root, arms["graph-event"])
    closure = validate_closure(root, arms, profile)
    selected = profile["selected_rank_kind_sums_ns"]
    largest_kind = min(
        kind for kind, value in selected.items() if value == max(selected.values())
    )
    next_action = {
        "attention": "separate_arithmetic_identical_eager_fa2_candidate_only",
        "graph": "replay_plan_submission_research_only",
        "collective": "prove_xccl_completion_join_before_collective_work",
    }[largest_kind]
    result = {
        "schema": ANALYSIS_SCHEMA,
        "status": "exact_event_profile_stop",
        "diagnostic_only": True,
        "not_benchmark_or_submission_evidence": True,
        "global_critical_path_validated": False,
        "collective_cross_stream_completion_validated": False,
        "bitwise_exact_q1_graph_event": True,
        "profile": profile,
        "decision": {
            "largest_kind_on_selected_rank": largest_kind,
            "next_action": next_action,
            "automatic_benchmark_or_submission_authorized": False,
        },
        "arms": {
            arm: {"path": str(arm_paths[arm]), "sha256": sha256_file(arm_paths[arm])}
            for arm in ARMS
        },
        "closure": closure,
    }
    write_exclusive(args.out, result)
    print(f"Laguna current-stream event analysis: {result['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
