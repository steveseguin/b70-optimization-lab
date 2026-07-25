#!/usr/bin/env python3
"""Fail-closed analysis for the diagnostic-only persistent KV-view gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import stat
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_laguna_m8_inprocess_replay as replay

ARMS = ("q1", "eager", "graph-control", "graph-candidate")
GRAPH_ARMS = ("graph-control", "graph-candidate")
RANKS = tuple(range(4))
Q_WIDTHS = tuple(range(2, 9))
ATTENTION_CASES = ("full", "sliding")
SAMPLES = 31
COMPLETION_TOKENS = 272
EXPECTED_MODEL = "/mnt/fast-ai/llm-models/laguna-s-2.1/int4"
EXPECTED_DRAFT = "/mnt/fast-ai/llm-models/laguna-s-2.1/dflash-int4"
EXPECTED_VLLM_ROOT = "/home/steve/src/laguna-vllm-runtime-graph-20260724"
EXPECTED_VLLM_COMMIT = "5da4a8ccdde0abe77d2dd2abda7b6a12bc74c01a"
EXPECTED_KERNEL_ROOT = "/home/steve/src/deepseek-v4-xpu-kernels-record-4772f727"
EXPECTED_KERNEL_COMMIT = "4772f727590c51b72add79350b913d098cf67872"
EXPECTED_KERNELS = {
    "_C.abi3.so": "126da37b23e5eff6840dd256c90164e3a282469e5fafa27830530e63ff36bce2",
    "_xpu_C.abi3.so": "f5f672130cc1b1d550646f732a6d576952c49514eba7a10db60fc1c361938fd8",
    "_moe_C.abi3.so": "6a6794249421aceb51f14980a3e2c0b0a9d7b492abf2f8d25b129b86f099bc5b",
    "_vllm_fa2_C.abi3.so": (
        "e6faed930bbcd7a366cc55281b99e1a8d7016a8db40ab10015d78f72937c8e64"
    ),
    "libattn_kernels_xe_2.so": (
        "680d486970eb58dc63f0b7ef41e028e2bb4b5a630a2987c96f8609d46a00e161"
    ),
    "libgdn_attn_kernels_xe_2.so": (
        "cdcf9539ac1715ef1dd9a81df422dd5bc1f3a58eff93e1bc5bde05959b5d34bb"
    ),
    "libgrouped_gemm_xe_2.so": (
        "fc74a6452b95643768889e2598df77bc4f4aa2b0925257a4c0eff371b1cf6c96"
    ),
    "libgrouped_gemm_xe_default.so": (
        "982fb0b7fc96c877aaefa33f3342936af9403ed3960106dececf08697d98d53c"
    ),
    "libmhc_kernels_xe_2.so": (
        "f689c3d200731167394c387d267df90311fd5ec21eff9dededb619e871ce1a4f"
    ),
    "libmqa_logits_kernels_xe_2.so": (
        "58cca1a0507914762b36874d719557715f3a8ae045106bc0aed42bd16e5b6aeb"
    ),
}
EXPECTED_SEGMENT_ORDER = (
    "e5b64443ef499d8bb8b138a94ad504effeaa6434a8884ae9f885aecf12d34e1b"
)
SEGMENT_COUNTS = {"graph": 146, "collective": 97, "attention": 48, "eager": 0}
TIMING_FIELDS = replay.TIMING_FIELDS
KV_PREP_TIMING_FIELDS = (
    "kv_view_prepare_forward_ns",
    "kv_view_prepare_update_ns",
    "kv_view_prepare_total_ns",
)
SUMMARY_FIELDS = (
    *TIMING_FIELDS,
    *KV_PREP_TIMING_FIELDS,
    *(f"segment_host_call_total_ns_{kind}" for kind in SEGMENT_COUNTS),
)


def die(message: str) -> None:
    raise SystemExit(f"Laguna persistent KV-view analysis: {message}")


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
        die(f"{label} must contain one JSON object")
    return value


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
        die("cannot summarize an empty vector")
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    lower, upper = math.floor(index), math.ceil(index)
    if lower == upper:
        return float(ordered[lower])
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def expected_environment(
    arm: str,
    profile_root: Path | None,
) -> dict[str, str]:
    graph = arm in GRAPH_ARMS
    optimized_dflash = arm != "q1"
    candidate = arm == "graph-candidate"
    environment = {
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
        "VLLM_XPU_LAGUNA_M8_CAPTURE_ATTENTION_GRAPHS": "0",
        "VLLM_XPU_LAGUNA_M8_PREBUILT_EXACT_ATTN_METADATA": ("1" if graph else "0"),
        "VLLM_XPU_LAGUNA_M8_PERSISTENT_KV_CACHE_VIEWS": ("1" if candidate else "0"),
        "VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM": "0",
        "VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK": "0",
        "VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2": ("1" if optimized_dflash else "0"),
        "VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION": "0",
        "VLLM_XPU_LAGUNA_M8_GATHER_FINALIZE": "0",
        "VLLM_XPU_LAGUNA_M8_GATHER_SHARDED": "0",
        "VLLM_XPU_LAGUNA_M8_QKNORM_ROPE": "1" if optimized_dflash else "0",
        "VLLM_XPU_LAGUNA_M8_REMOTE_ZERO": "0",
        "VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE": ("1" if optimized_dflash else "0"),
        "VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM": "0",
        "VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE": ("1" if optimized_dflash else "0"),
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
        environment.update(
            {
                "VLLM_XPU_LAGUNA_REPLAY_PROFILE_ROOT": str(profile_root),
                "VLLM_XPU_LAGUNA_REPLAY_PROFILE_SAMPLES": str(SAMPLES),
            }
        )
    return environment


def normalize_graph_environment_for_comparison(
    environment: dict[str, str],
    profile_root: Path,
) -> dict[str, str]:
    """Remove the validated arm-local telemetry destination."""
    normalized = dict(environment)
    profile_key = "VLLM_XPU_LAGUNA_REPLAY_PROFILE_ROOT"
    if normalized.pop(profile_key, None) != str(profile_root):
        die("graph replay-profile environment identity drifted")
    return normalized


def validate_arm(
    record: dict[str, Any],
    arm: str,
    profile_root: Path | None,
) -> None:
    graph = arm in GRAPH_ARMS
    candidate = arm == "graph-candidate"
    required = {
        "schema": "laguna-persistent-kv-view-arm-v1",
        "status": "complete",
        "diagnostic_only": True,
        "single_generate_call": True,
        "fresh_process": True,
        "arm": arm,
        "graph": graph,
        "kv_view_selector": int(candidate),
        "model": EXPECTED_MODEL,
        "vllm_root": EXPECTED_VLLM_ROOT,
        "vllm_commit": EXPECTED_VLLM_COMMIT,
        "kernel_root": EXPECTED_KERNEL_ROOT,
        "kernel_commit": EXPECTED_KERNEL_COMMIT,
        "async_scheduling": arm == "q1",
        "completion_tokens": COMPLETION_TOKENS,
        "cached_tokens": 0,
        "finish_reason": "length",
    }
    for key, expected in required.items():
        if record.get(key) != expected:
            die(f"{arm} arm field {key!r} drifted")
    for key in ("prompt_sha256", "text_sha256"):
        value = record.get(key)
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            die(f"{arm} arm has invalid {key}")
    for key in ("prompt_tokens", "generation_wall_ns"):
        value = record.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            die(f"{arm} arm has invalid {key}")
    token_ids = record.get("token_ids")
    if (
        not isinstance(token_ids, list)
        or len(token_ids) != COMPLETION_TOKENS
        or not all(type(token) is int for token in token_ids)
    ):
        die(f"{arm} arm token IDs drifted")
    expected_token_hash = hashlib.sha256(
        json.dumps(token_ids, separators=(",", ":")).encode()
    ).hexdigest()
    if record.get("token_ids_sha256") != expected_token_hash:
        die(f"{arm} arm token digest drifted")
    expected_draft = None if arm == "q1" else EXPECTED_DRAFT
    if record.get("draft_model") != expected_draft:
        die(f"{arm} arm draft identity drifted")
    kernel_identity = record.get("kernel_identity")
    if not isinstance(kernel_identity, dict) or set(kernel_identity) != set(
        EXPECTED_KERNELS
    ):
        die(f"{arm} arm kernel identity drifted")
    for name, expected_hash in EXPECTED_KERNELS.items():
        if kernel_identity[name] != {
            "path": str(Path(EXPECTED_KERNEL_ROOT) / "vllm_xpu_kernels" / name),
            "sha256": expected_hash,
        }:
            die(f"{arm} arm kernel binary {name} drifted")
    if record.get("environment") != expected_environment(arm, profile_root):
        die(f"{arm} arm environment drifted")

    if graph:
        assert profile_root is not None
        if (
            record.get("profile_root") != str(profile_root)
            or record.get("profile_samples") != SAMPLES
            or not isinstance(record.get("profile_rank_files"), dict)
        ):
            die(f"{arm} arm profile identity drifted")
        expected_compile = {
            "mode": "NONE",
            "cudagraph_mode": "PIECEWISE",
            "cudagraph_capture_sizes": [8],
            "max_cudagraph_capture_size": 8,
        }
        if record.get("compilation_config") != expected_compile:
            die(f"{arm} arm compilation identity drifted")
    elif any(
        record.get(key) is not None
        for key in (
            "profile_root",
            "profile_samples",
            "profile_rank_files",
            "compilation_config",
        )
    ):
        die(f"{arm} arm unexpectedly carries graph telemetry")


def validate_parity(root: Path) -> dict[str, dict[str, str]]:
    identities: dict[str, dict[str, str]] = {}
    expected_rows = [
        (case, q_width) for case in ATTENTION_CASES for q_width in Q_WIDTHS
    ]
    for rank in RANKS:
        path = root / "parity" / f"rank{rank}.json"
        value = read_json(path, f"parity rank{rank}")
        required = {
            "schema": "laguna-persistent-kv-view-attention-parity-v1",
            "status": "pass",
            "rank": rank,
            "visible_xpus": 1,
            "vllm_root": EXPECTED_VLLM_ROOT,
            "vllm_commit": EXPECTED_VLLM_COMMIT,
            "kernel_root": EXPECTED_KERNEL_ROOT,
            "kernel_commit": EXPECTED_KERNEL_COMMIT,
            "control_selector": 0,
            "candidate_selector": 1,
            "control_state_absent": True,
            "candidate_state_present": True,
            "candidate_view_identity_reused": True,
            "compiled_fa2_fallback_forbidden": True,
            "platform_is_xpu": True,
            "fa2_available": True,
            "fa2_extension": str(
                Path(EXPECTED_KERNEL_ROOT) / "vllm_xpu_kernels" / "_vllm_fa2_C.abi3.so"
            ),
            "non_timing": True,
        }
        for key, expected in required.items():
            if value.get(key) != expected:
                die(f"parity rank{rank} field {key!r} drifted")
        if (
            not isinstance(value.get("device_name"), str)
            or "B70" not in value["device_name"]
        ):
            die(f"parity rank{rank} device identity drifted")
        kernel_identity = value.get("kernel_identity")
        if not isinstance(kernel_identity, dict) or set(kernel_identity) != set(
            EXPECTED_KERNELS
        ):
            die(f"parity rank{rank} kernel identity drifted")
        for name, expected_hash in EXPECTED_KERNELS.items():
            if kernel_identity[name] != {
                "path": str(Path(EXPECTED_KERNEL_ROOT) / "vllm_xpu_kernels" / name),
                "sha256": expected_hash,
            }:
                die(f"parity rank{rank} kernel binary {name} drifted")
        rows = value.get("q_outputs")
        if (
            not isinstance(rows, list)
            or [
                (row.get("case"), row.get("q")) for row in rows if isinstance(row, dict)
            ]
            != expected_rows
        ):
            die(f"parity rank{rank} q2..q8 case ordering drifted")
        for row in rows:
            control_hash = row.get("control_sha256")
            if (
                row.get("bitwise_equal") is not True
                or not isinstance(control_hash, str)
                or len(control_hash) != 64
                or control_hash != row.get("candidate_sha256")
                or not isinstance(row.get("control_fa_version"), int)
                or row["control_fa_version"] <= 0
                or row.get("candidate_fa_version") != row["control_fa_version"]
            ):
                die(f"parity rank{rank} {row.get('case')} q={row.get('q')} mismatch")
        identities[str(rank)] = {
            "path": str(path),
            "sha256": sha256_file(path),
        }
    return identities


def validate_profile_with_kv_prepare(
    payload: dict[str, Any],
    rank: int,
    arm: str,
) -> list[dict[str, Any]]:
    if payload.get("schema") != "laguna-m8-breakable-replay-profile-v2":
        die(f"{arm} rank{rank} profile schema drifted")
    rows = payload.get("records")
    if not isinstance(rows, list):
        die(f"{arm} rank{rank} profile records drifted")

    legacy_payload = dict(payload)
    legacy_payload["schema"] = "laguna-m8-breakable-replay-profile-v1"
    legacy_rows = []
    for sample, row in enumerate(rows):
        if not isinstance(row, dict):
            die(f"{arm} rank{rank} sample{sample} record drifted")
        legacy_row = dict(row)
        kv_prepare = legacy_row.pop("kv_view_prepare", None)
        if not isinstance(kv_prepare, dict) or set(kv_prepare) != {
            "control_calls",
            "forward_calls",
            "forward_ns",
            "persistent_builds",
            "persistent_calls",
            "persistent_hits",
            "total_calls",
            "total_ns",
            "update_calls",
            "update_ns",
        }:
            die(f"{arm} rank{rank} sample{sample} KV preparation schema drifted")
        for key, value in kv_prepare.items():
            replay.nonnegative_int(
                value,
                f"{arm} rank{rank} sample{sample} KV preparation {key}",
            )
        # The KV-update custom op is captured in the surrounding graph
        # segments, so its Python view preparation runs at capture time, not
        # during replay. Only the 48 eager attention boundaries execute
        # Python view preparation in this hot-replay profile.
        if (
            kv_prepare["forward_calls"] != 48
            or kv_prepare["update_calls"] != 0
            or kv_prepare["total_calls"] != 48
            or kv_prepare["total_calls"]
            != kv_prepare["forward_calls"] + kv_prepare["update_calls"]
            or kv_prepare["total_ns"]
            != kv_prepare["forward_ns"] + kv_prepare["update_ns"]
            or kv_prepare["forward_ns"] <= 0
            or kv_prepare["update_ns"] != 0
        ):
            die(f"{arm} rank{rank} sample{sample} KV preparation counts drifted")
        if arm == "graph-control":
            expected_mode = {
                "control_calls": 48,
                "persistent_calls": 0,
                "persistent_builds": 0,
                "persistent_hits": 0,
            }
        else:
            expected_mode = {
                "control_calls": 0,
                "persistent_calls": 48,
                "persistent_builds": 0,
                "persistent_hits": 48,
            }
        if any(kv_prepare[key] != value for key, value in expected_mode.items()):
            die(f"{arm} rank{rank} sample{sample} KV preparation mode drifted")
        segment_totals = row.get("segment_host_call_total_ns")
        if not isinstance(segment_totals, dict) or kv_prepare[
            "total_ns"
        ] > segment_totals.get("attention", -1):
            die(f"{arm} rank{rank} sample{sample} KV preparation containment drifted")
        legacy_rows.append(legacy_row)
    legacy_payload["records"] = legacy_rows
    replay.validate_profile(legacy_payload, rank)
    return rows


def validate_profile_arm(
    root: Path,
    arm: str,
    arm_record: dict[str, Any],
) -> dict[str, Any]:
    profile_root = root / arm / "replay-profile"
    metadata = profile_root.lstat()
    if (
        profile_root.is_symlink()
        or not stat.S_ISDIR(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) not in (0o500, 0o700)
        or arm_record.get("profile_root") != str(profile_root)
    ):
        die(f"{arm} profile root identity drifted")
    expected_names = {f"rank{rank}.json" for rank in RANKS}
    if {path.name for path in profile_root.iterdir()} != expected_names:
        die(f"{arm} profile root file set drifted")

    payloads: dict[int, dict[str, Any]] = {}
    records: dict[int, list[dict[str, Any]]] = {}
    file_identity: dict[str, dict[str, str]] = {}
    for rank in RANKS:
        path = profile_root / f"rank{rank}.json"
        payloads[rank] = read_json(path, f"{arm} rank{rank} profile")
        records[rank] = validate_profile_with_kv_prepare(
            payloads[rank],
            rank,
            arm,
        )
        identity = {"path": str(path), "sha256": sha256_file(path)}
        if arm_record["profile_rank_files"].get(str(rank)) != identity:
            die(f"{arm} rank{rank} closed profile identity drifted")
        file_identity[str(rank)] = identity

    descriptors = {payloads[rank]["batch_descriptor"] for rank in RANKS}
    digests = {payloads[rank]["segment_kind_order_sha256"] for rank in RANKS}
    if len(descriptors) != 1 or digests != {EXPECTED_SEGMENT_ORDER}:
        die(f"{arm} rank descriptor or segment-order identity drifted")
    expected_order = [row[0] for row in records[0][0]["segment_ordered_host_call_ns"]]
    for rank in RANKS:
        for sample, record in enumerate(records[rank]):
            observed_order = [row[0] for row in record["segment_ordered_host_call_ns"]]
            if observed_order != expected_order:
                die(f"{arm} rank{rank} sample{sample} segment order drifted")

    max_rank_rows: list[dict[str, Any]] = []
    for sample in range(SAMPLES):
        row: dict[str, Any] = {"sample": sample}
        for field in TIMING_FIELDS:
            values = [records[rank][sample][field] for rank in RANKS]
            maximum = max(values)
            row[field] = maximum
            row[f"{field}_max_rank"] = min(
                rank for rank, value in zip(RANKS, values) if value == maximum
            )
        for source, field in (
            ("forward_ns", "kv_view_prepare_forward_ns"),
            ("update_ns", "kv_view_prepare_update_ns"),
            ("total_ns", "kv_view_prepare_total_ns"),
        ):
            values = [
                records[rank][sample]["kv_view_prepare"][source] for rank in RANKS
            ]
            maximum = max(values)
            row[field] = maximum
            row[f"{field}_max_rank"] = min(
                rank for rank, value in zip(RANKS, values) if value == maximum
            )
        for kind in SEGMENT_COUNTS:
            values = [
                records[rank][sample]["segment_host_call_total_ns"][kind]
                for rank in RANKS
            ]
            maximum = max(values)
            field = f"segment_host_call_total_ns_{kind}"
            row[field] = maximum
            row[f"{field}_max_rank"] = min(
                rank for rank, value in zip(RANKS, values) if value == maximum
            )
        max_rank_rows.append(row)

    summary = {
        field: {
            "min_ns": min(row[field] for row in max_rank_rows),
            "median_ns": percentile(
                [row[field] for row in max_rank_rows],
                0.5,
            ),
            "p10_ns": percentile(
                [row[field] for row in max_rank_rows],
                0.1,
            ),
            "p90_ns": percentile(
                [row[field] for row in max_rank_rows],
                0.9,
            ),
            "max_ns": max(row[field] for row in max_rank_rows),
        }
        for field in SUMMARY_FIELDS
    }
    return {
        "profile_root": str(profile_root),
        "files": file_identity,
        "batch_descriptor": next(iter(descriptors)),
        "segment_kind_order_sha256": next(iter(digests)),
        "max_rank_samples": max_rank_rows,
        "max_rank_summary": summary,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    unresolved_root = args.run_dir
    metadata = unresolved_root.lstat()
    root = unresolved_root.resolve(strict=True)
    root_mode = stat.S_IMODE(metadata.st_mode)
    if (
        unresolved_root.is_symlink()
        or not stat.S_ISDIR(metadata.st_mode)
        or root_mode not in (0o500, 0o700)
        or not root.is_relative_to(
            Path("/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs")
        )
    ):
        die("run root must be an owner-private internal-NVMe directory")
    if args.out.exists() or args.out.is_symlink():
        die("refusing to overwrite analysis output")
    output_parent = args.out.parent.resolve(strict=True)
    if root_mode == 0o500 and (
        output_parent == root or output_parent.is_relative_to(root)
    ):
        die("sealed run analysis output must stay outside the run root")

    arm_paths = {arm: root / arm / "driver.json" for arm in ARMS}
    arms = {
        arm: read_json(path, f"{arm} arm record") for arm, path in arm_paths.items()
    }
    profile_roots = {arm: root / arm / "replay-profile" for arm in GRAPH_ARMS}
    for arm, record in arms.items():
        validate_arm(record, arm, profile_roots.get(arm))

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
    exact_fields = (
        "token_ids",
        "token_ids_sha256",
        "text_sha256",
        "finish_reason",
    )
    for field in (*identity_fields, *exact_fields):
        values = {json.dumps(arms[arm].get(field), sort_keys=True) for arm in ARMS}
        if len(values) != 1:
            die(f"four-arm identity or exactness drifted at {field}")
    control_environment = normalize_graph_environment_for_comparison(
        arms["graph-control"]["environment"],
        profile_roots["graph-control"],
    )
    candidate_environment = normalize_graph_environment_for_comparison(
        arms["graph-candidate"]["environment"],
        profile_roots["graph-candidate"],
    )
    selector = "VLLM_XPU_LAGUNA_M8_PERSISTENT_KV_CACHE_VIEWS"
    if control_environment.pop(selector) != "0":
        die("graph control selector drifted")
    if candidate_environment.pop(selector) != "1":
        die("graph candidate selector drifted")
    if control_environment != candidate_environment:
        die("graph arms differ by more than the sole treatment")

    parity_identity = validate_parity(root)
    graph_profiles = {
        arm: validate_profile_arm(root, arm, arms[arm]) for arm in GRAPH_ARMS
    }
    profile_contract_fields = (
        "batch_descriptor",
        "segment_kind_order_sha256",
    )
    for field in profile_contract_fields:
        if (
            graph_profiles["graph-control"][field]
            != graph_profiles["graph-candidate"][field]
        ):
            die(f"graph profile contract drifted at {field}")

    control_summary = graph_profiles["graph-control"]["max_rank_summary"]
    candidate_summary = graph_profiles["graph-candidate"]["max_rank_summary"]
    comparison = {}
    for field in SUMMARY_FIELDS:
        control = control_summary[field]
        candidate = candidate_summary[field]
        comparison[field] = {
            "control_median_ns": control["median_ns"],
            "candidate_median_ns": candidate["median_ns"],
            "median_saving_ns": control["median_ns"] - candidate["median_ns"],
            "control_p90_ns": control["p90_ns"],
            "candidate_p90_ns": candidate["p90_ns"],
            "p90_saving_ns": control["p90_ns"] - candidate["p90_ns"],
        }

    whole = comparison["whole_replay_completion_ns"]
    kv_prepare = comparison["kv_view_prepare_total_ns"]
    attention = comparison["segment_host_call_total_ns_attention"]
    post_sync = comparison["post_replay_synchronize_ns"]
    gates = {
        "positive_kv_view_prepare_median": kv_prepare["median_saving_ns"] > 0,
        "positive_attention_host_median": attention["median_saving_ns"] > 0,
        "positive_whole_replay_median": whole["median_saving_ns"] > 0,
        "positive_fresh_generation_wall": (
            arms["graph-control"]["generation_wall_ns"]
            > arms["graph-candidate"]["generation_wall_ns"]
        ),
        "whole_replay_p90_non_regression": whole["p90_saving_ns"] >= 0,
        "no_post_replay_sync_cost_transfer": post_sync["median_saving_ns"] >= 0,
    }
    passed = all(gates.values())
    result = {
        "schema": "laguna-persistent-kv-view-analysis-v1",
        "status": "diagnostic_pass" if passed else "exact_timing_stop",
        "diagnostic_only": True,
        "not_benchmark_or_submission_evidence": True,
        "bitwise_exact_all_four_arms": True,
        "q2_q8_attention_parity_all_four_cards": True,
        "sole_treatment": selector,
        "profile_contract": {
            "ranks": list(RANKS),
            "samples_per_rank_per_graph_arm": SAMPLES,
            "graphs": 146,
            "eager_breaks": 145,
            "boundary_categories": {"attention": 48, "collective": 97},
            "kv_view_prepare_calls_per_replay": {
                "forward": 48,
                "update": 0,
                "total": 48,
            },
            "batch_descriptor": graph_profiles["graph-control"]["batch_descriptor"],
            "segment_kind_order_sha256": EXPECTED_SEGMENT_ORDER,
        },
        "arms": {
            arm: {
                "path": str(arm_paths[arm]),
                "sha256": sha256_file(arm_paths[arm]),
                "record": arms[arm],
            }
            for arm in ARMS
        },
        "parity": parity_identity,
        "graph_profiles": graph_profiles,
        "comparison": comparison,
        "gates": gates,
    }
    write_exclusive(args.out, result)
    print(f"Laguna persistent KV-view analysis: {result['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
