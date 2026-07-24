#!/usr/bin/env python3
"""Freeze mutually bound v3 Phase-A/B authorizations for Laguna MoeGather.

This is CPU-only metadata tooling.  It derives the shared identity from one
frozen Stage-0 certificate, hashes the committed execution tools, and creates
one immutable authorization pair for fresh internal-NVMe campaign roots.
It never imports Torch, a native library, or an accelerator runtime.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import stat
import sys
import uuid
from pathlib import Path
from types import ModuleType
from typing import Any


REPOSITORY_ROOT = Path("/home/steve/llm-optimizations")
TOOLS_ROOT = REPOSITORY_ROOT / "experiments/laguna-s-2.1-xpu-b70/tools"
ARTIFACT_ROOT = Path("/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1")
RUNS_ROOT = ARTIFACT_ROOT / "runs"
AUTHORIZATION_ROOT = ARTIFACT_ROOT / "authorizations"
PHASE_A_NAME = "phase-a-authorization.json"
PHASE_B_NAME = "phase-b-authorization.json"
STAGE0_FORMAT = "laguna-m8-gather-sharded-stage0-completion-v1"
STAGE0_STATUS = "stage0_host_only_complete_pending_packet_commit"
PHYSICAL_CARDS = (
    {"physical_rank": 0, "xpu_smi_uuid": "00000000-0000-0023-0000-0000e2238086", "bdf": "0000:23:00.0", "drm_card": "/dev/dri/card3"},
    {"physical_rank": 1, "xpu_smi_uuid": "00000000-0000-0027-0000-0000e2238086", "bdf": "0000:27:00.0", "drm_card": "/dev/dri/card4"},
    {"physical_rank": 2, "xpu_smi_uuid": "00000000-0000-0043-0000-0000e2238086", "bdf": "0000:43:00.0", "drm_card": "/dev/dri/card0"},
    {"physical_rank": 3, "xpu_smi_uuid": "00000000-0000-0047-0000-0000e2238086", "bdf": "0000:47:00.0", "drm_card": "/dev/dri/card2"},
)
FIXTURE_NAMES = (
    "route_rows",
    "weights",
    "scale_add_input",
    "four_rank_tail",
    "residual_input",
    "norm_weight",
)
NATIVE_KEYS = {
    "root",
    "manifest",
    "manifest_sha256",
    "prepared",
    "prepared_sha256",
    "library_sha256",
    "libraries",
    "status",
    "validation_protocol",
    "storage",
}
_MODULES: dict[str, ModuleType] = {}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def canonical(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode("utf-8")


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(value: object) -> str:
    return sha_bytes(canonical(value))


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and re.fullmatch(r"[0-9a-f]{64}", value) is not None
    )


def _load_contract_module(name: str, filename: str) -> ModuleType:
    """Lazily load a host-only contract module from its absolute source."""
    cached = _MODULES.get(name)
    if cached is not None:
        return cached
    path = TOOLS_ROOT / filename
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, f"cannot load {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    _MODULES[name] = module
    return module


def _phase_a() -> ModuleType:
    return _load_contract_module(
        "_laguna_gather_packet_phase_a",
        "run_laguna_m8_gather_sharded_phase_a.py",
    )


def _phase_b() -> ModuleType:
    return _load_contract_module(
        "_laguna_gather_packet_phase_b",
        "run_laguna_m8_gather_sharded_phase_b.py",
    )


def _counter_parser() -> ModuleType:
    return _load_contract_module(
        "_laguna_gather_packet_counters",
        "laguna_m8_gather_sharded_counter_parser.py",
    )


def _read_regular(path: Path, label: str, maximum: int = 64 * 1024 * 1024) -> bytes:
    require(path.is_absolute() and not path.is_symlink(), f"unsafe {label} path")
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        before = os.fstat(descriptor)
        require(
            stat.S_ISREG(before.st_mode)
            and stat.S_IMODE(before.st_mode) == 0o444
            and 0 < before.st_size <= maximum,
            f"{label} must be a nonempty exact-0444 regular file",
        )
        raw = bytearray()
        while len(raw) < before.st_size:
            block = os.read(
                descriptor, min(1024 * 1024, before.st_size - len(raw))
            )
            require(bool(block), f"short {label} read")
            raw.extend(block)
        after = os.fstat(descriptor)
        require(
            (
                before.st_dev,
                before.st_ino,
                before.st_size,
                before.st_mtime_ns,
                before.st_mode,
            )
            == (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
                after.st_mode,
            ),
            f"{label} changed while reading",
        )
        visible = os.stat(path, follow_symlinks=False)
        require(
            (visible.st_dev, visible.st_ino) == (after.st_dev, after.st_ino),
            f"{label} visible identity changed",
        )
        return bytes(raw)
    finally:
        os.close(descriptor)


def _read_canonical(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    raw = _read_regular(path, label)
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, ValueError) as error:
        raise RuntimeError(f"invalid {label} JSON") from error
    require(isinstance(value, dict) and raw == canonical(value), f"noncanonical {label}")
    return value, raw


def _hash_source(path: Path) -> dict[str, str]:
    require(
        path.is_absolute() and path.is_file() and not path.is_symlink(),
        f"missing tool source: {path}",
    )
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        before = os.fstat(descriptor)
        require(stat.S_ISREG(before.st_mode), f"nonregular tool source: {path}")
        raw = os.pread(descriptor, before.st_size, 0)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    require(
        len(raw) == before.st_size
        and (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_mode,
        )
        == (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_mode,
        ),
        f"tool source changed while hashing: {path}",
    )
    return {"path": str(path), "sha256": sha_bytes(raw)}


def _assert_internal_parent(path: Path, label: str) -> None:
    require(path.is_absolute() and not path.exists(), f"{label} must be fresh")
    parent = path.parent.resolve(strict=True)
    require(
        parent.is_relative_to(Path("/mnt/fast-ai")),
        f"{label} parent must be on internal NVMe",
    )
    _phase_a()._assert_internal_nvme(parent, f"{label} parent")


def _source_tools(
    filenames: dict[str, str],
) -> dict[str, dict[str, str]]:
    return {
        role: _hash_source(TOOLS_ROOT / filename)
        for role, filename in filenames.items()
    }


def common_from_stage0(certificate_path: Path) -> dict[str, Any]:
    """Derive the exact shared v3 body from one immutable Stage-0 certificate."""
    certificate, raw = _read_canonical(certificate_path, "Stage-0 certificate")
    require(
        certificate.get("format") == STAGE0_FORMAT
        and certificate.get("status") == STAGE0_STATUS,
        "Stage-0 certificate status/format drift",
    )
    stage0_input = certificate.get("input")
    require(
        isinstance(stage0_input, dict)
        and set(stage0_input) == {"path", "sha256", "storage"}
        and _is_sha256(stage0_input.get("sha256")),
        "Stage-0 input binding drift",
    )
    source = certificate.get("source_packet")
    require(
        isinstance(source, dict)
        and source.get("path") == _phase_a().SOURCE_IR_IDENTITY["path"]
        and source.get("sha256") == _phase_a().SOURCE_IR_IDENTITY["sha256"]
        and source.get("device_ir_report_sha256")
        == _phase_a().SOURCE_IR_IDENTITY["device_ir_report_sha256"]
        and source.get("status") == _phase_a().SOURCE_IR_IDENTITY["status"],
        "Stage-0 source/IR identity drift",
    )
    native = certificate.get("native_bundle")
    require(
        isinstance(native, dict) and NATIVE_KEYS.issubset(native),
        "Stage-0 native bundle closure missing",
    )
    native_common = {key: native[key] for key in NATIVE_KEYS}
    fixture = certificate.get("fixture")
    require(
        isinstance(fixture, dict)
        and isinstance(fixture.get("manifest"), dict)
        and isinstance(fixture.get("analysis"), dict)
        and isinstance(fixture.get("canonical_route_map"), dict)
        and isinstance(fixture.get("tensors"), dict)
        and set(fixture["tensors"]) == set(FIXTURE_NAMES),
        "Stage-0 fixture closure missing",
    )
    fixture_root = Path(fixture["root"])
    route_map = fixture["canonical_route_map"]
    fixture_common = {
        "root": str(fixture_root),
        "manifest": fixture["manifest"]["path"],
        "manifest_sha256": fixture["manifest"]["sha256"],
        "analysis": fixture["analysis"]["path"],
        "analysis_sha256": fixture["analysis"]["sha256"],
        "canonical_route_map": {
            "path": str(fixture_root / route_map["file"]),
            "sha256": route_map["sha256"],
        },
        "records": {
            name: {
                "path": str(fixture_root / fixture["tensors"][name]["file"]),
                "sha256": fixture["tensors"][name]["sha256"],
                "dtype": fixture["tensors"][name]["dtype"],
                "shape": fixture["tensors"][name]["shape"],
                "per_epoch_sha256": fixture["tensors"][name]["epoch_sha256"],
            }
            for name in FIXTURE_NAMES
        },
    }
    common = {
        "format": _phase_a().COMMON_FORMAT,
        "source": {
            "approved_record_vllm_commit": "8936aac144929190c1e53f8b8624ca397ce16f5b",
            "approved_record_kernel_commit": "b6076ce1249ffee0e30bee528f4cd15c3bffb234",
            "candidate_kernel_commit": "7e6a74026a2a4370abcb7973d28bbc9d1ddd1be6",
        },
        "source_ir": dict(_phase_a().SOURCE_IR_IDENTITY),
        "stage0_completion": {
            "path": str(certificate_path),
            "sha256": sha_bytes(raw),
            "status": STAGE0_STATUS,
            "input": {
                "path": stage0_input["path"],
                "sha256": stage0_input["sha256"],
            },
        },
        "native_bundle": native_common,
        "fixture": fixture_common,
        "cards": [dict(card) for card in PHYSICAL_CARDS],
        "treatments": {
            "A": "generic_moe_gather",
            "B": "laguna_m8_moe_gather_sharded",
            "same_candidate_moe_library": True,
        },
        "logical_cycle": {
            "layers": 47,
            "warm_cycles_per_arm": 20,
            "blocks": 31,
            "cycles_per_arm": 64,
            "arm_order": "A-B-B-A",
            "rotation": "(block*47)%256",
            "pre_epochs": 256,
            "post_epochs": 32,
            "minimum_wins": 28,
            "minimum_median_saving_ms": 0.08,
        },
        "operational_preflight": dict(_phase_a().OPERATIONAL_PREFLIGHT_IDENTITY),
        "runtime_identity": dict(_phase_a().RUNTIME_IDENTITY),
    }
    _phase_a().validate_common(common)
    return common


def _counter_tools() -> dict[str, Any]:
    phase_b = _phase_b()
    # The runner's own host-only identity routine additionally verifies the
    # profiler commit and exact Level-Zero files.
    return phase_b.tool_identity()


def _temporal_control() -> dict[str, Any]:
    return _phase_b().temporal_control_identity()


def _phase_b_protocol() -> dict[str, Any]:
    phase_b = _phase_b()
    return {
        "cycles": 13,
        "layers_per_cycle": 47,
        "raw_selected_rows": 611,
        "discard_cycles": [0, 1],
        "retained_selected_rows": 517,
        "arm_order": ["A1", "B1", "B2", "A2"],
        "unitrace_inner_timeout_seconds": phase_b.INNER_TIMEOUT,
        "runner_outer_timeout_seconds": phase_b.OUTER_TIMEOUT,
        "pre_arm_strict_idle_seconds": phase_b.STRICT_IDLE_SECONDS,
        "pre_arm_idle_sample_interval_seconds": phase_b.IDLE_SAMPLE_INTERVAL_SECONDS,
        "pre_arm_idle_min_samples": phase_b.IDLE_MIN_SAMPLES,
        "same_boot_required": True,
        "fresh_private_runtime_per_arm": True,
    }


def _phase_b_counter_gates() -> dict[str, Any]:
    return {
        "gpu_memory_per_field_max_ratio": 1.02,
        "gpu_memory_total_max_ratio": 1.02,
        "lsc_per_field_max_ratio": 1.02,
        "lsc_total_max_ratio": 1.02,
        "xve_active_max_decline_pp": 0.5,
        "thread_occupancy_max_decline_pp": 0.5,
        "xve_stall_max_increase_pp": 0.5,
        "no_global_rescue": True,
    }


def packet_pair(
    common: dict[str, Any],
    authorization_directory: Path,
    phase_a_root: Path,
    phase_b_root: Path,
    *,
    session_nonces: dict[tuple[int, str], str] | None = None,
    counter_tools: dict[str, Any] | None = None,
    temporal_control: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build the nonrecursive pair.  A binds full B; B binds canonical A body."""
    phase_a = _phase_a()
    phase_b = _phase_b()
    phase_a.validate_common(common)
    a_path = authorization_directory / PHASE_A_NAME
    b_path = authorization_directory / PHASE_B_NAME
    aggregate = phase_a_root / "aggregate.json"
    a_tools = _source_tools(phase_a.A_TOOL_FILENAMES)
    b_tools = _source_tools(phase_b.TOOL_ROLES)
    common_sha = phase_a.common_hash(common)
    a_body = {
        "format": phase_a.PHASE_A_BODY_FORMAT,
        "common": common,
        "common_binding_sha256": common_sha,
        "phase_b_reference": {
            "authorization_path": str(b_path),
            "runner_path": b_tools["runner"]["path"],
            "runner_sha256": b_tools["runner"]["sha256"],
            "common_binding_sha256": common_sha,
        },
        **a_tools,
        "protocol": {
            "phase": "A",
            "authorization": "component_exactness_and_timing_only",
        },
        "cards": [
            {
                "rank": rank,
                "physical_rank": rank,
                "environment": phase_a.expected_environment(
                    rank, phase_a_root / f"card{rank}"
                ),
                "output_root": str(phase_a_root / f"card{rank}"),
            }
            for rank in range(4)
        ],
        "aggregate_path": str(aggregate),
        "capability": {
            "phase": "A",
            "phase_b_counters_authorized": False,
            "endpoint_authorized": False,
            "model_generation_authorized": False,
            "submission_authorized": False,
        },
    }
    nonces = session_nonces or {
        (rank, arm): uuid.uuid4().hex
        for rank in range(4)
        for arm in phase_b.ARMS
    }
    require(
        set(nonces)
        == {(rank, arm) for rank in range(4) for arm in phase_b.ARMS}
        and all(
            isinstance(value, str)
            and re.fullmatch(r"[0-9a-f]{32}", value) is not None
            for value in nonces.values()
        ),
        "Phase-B session nonce closure",
    )
    b_body = {
        "phase": "B",
        "common": json.loads(canonical(common)),
        "common_binding_sha256": common_sha,
        "phase_a_binding": {
            "authorization_path": str(a_path),
            "phase_a_body_sha256": sha(a_body),
            "phase_a_runner_path": a_tools["runner"]["path"],
            "phase_a_runner_sha256": a_tools["runner"]["sha256"],
            "aggregate_path": str(aggregate),
            "aggregate_format": "laguna-m8-gather-sharded-phase-a-aggregate-v3",
            "required_status": "component_timing_pass_pending_mandatory_counters",
            "required_passed": True,
            "common_binding_sha256": common_sha,
        },
        "output_root": str(phase_b_root),
        "cards": [
            {
                "rank": rank,
                "output_root": str(phase_b_root / f"card{rank}"),
                "environments": {
                    arm: phase_a.expected_environment(
                        rank, phase_b_root / f"card{rank}" / arm
                    )
                    for arm in phase_b.ARMS
                },
                "sessions": {
                    arm: f"Laguna{arm}Card{rank}{nonces[(rank, arm)]}"
                    for arm in phase_b.ARMS
                },
            }
            for rank in range(4)
        ],
        "protocol": _phase_b_protocol(),
        "counter_gates": _phase_b_counter_gates(),
        "counter_header": {
            "fields": 86,
            "sha256": _counter_parser().METRIC_HEADER_SHA256,
        },
        "tools": b_tools,
        "counter_tools": counter_tools if counter_tools is not None else _counter_tools(),
        "temporal_control": (
            temporal_control if temporal_control is not None else _temporal_control()
        ),
    }
    b_packet = {
        "format": phase_a.PHASE_B_FORMAT,
        "packet_path": str(b_path),
        "body": b_body,
    }
    a_packet = {
        "format": phase_a.PHASE_A_FORMAT,
        "packet_path": str(a_path),
        "body": a_body,
        "paired_phase_b_packet_sha256": sha(b_packet),
    }
    phase_a.validate_phase_a_packet(a_packet, a_path)
    phase_a.validate_phase_b_packet_shape(b_packet, b_path)
    phase_a.verify_mutual_packets(a_packet, b_packet, phase_b_path=b_path)
    return a_packet, b_packet


def _write_read_only(directory_fd: int, name: str, payload: bytes) -> str:
    descriptor = os.open(
        name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o400,
        dir_fd=directory_fd,
    )
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            require(written > 0, "short packet write")
            view = view[written:]
        os.fsync(descriptor)
        os.fchmod(descriptor, 0o444)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return sha_bytes(payload)


def write_packets(
    certificate_path: Path,
    authorization_directory: Path,
    phase_a_root: Path,
    phase_b_root: Path,
) -> dict[str, str]:
    for path, label in (
        (authorization_directory, "authorization directory"),
        (phase_a_root, "Phase-A root"),
        (phase_b_root, "Phase-B root"),
    ):
        _assert_internal_parent(path, label)
    require(
        authorization_directory.parent == AUTHORIZATION_ROOT
        and phase_a_root.parent == RUNS_ROOT
        and phase_b_root.parent == RUNS_ROOT
        and len({authorization_directory, phase_a_root, phase_b_root}) == 3,
        "campaign roots must be distinct children of frozen internal-NVMe roots",
    )
    common = common_from_stage0(certificate_path)
    phase_a, phase_b = packet_pair(
        common, authorization_directory, phase_a_root, phase_b_root
    )
    authorization_directory.mkdir(mode=0o700)
    directory_fd = os.open(
        authorization_directory,
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    try:
        b_sha = _write_read_only(
            directory_fd, PHASE_B_NAME, canonical(phase_b)
        )
        a_sha = _write_read_only(
            directory_fd, PHASE_A_NAME, canonical(phase_a)
        )
        os.fsync(directory_fd)
        os.fchmod(directory_fd, 0o555)
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    return {
        "phase_a": a_sha,
        "phase_b": b_sha,
        "common": _phase_a().common_hash(common),
    }


def _session_nonces(packet: dict[str, Any]) -> dict[tuple[int, str], str]:
    result: dict[tuple[int, str], str] = {}
    for rank, card in enumerate(packet["body"]["cards"]):
        for arm, session in card["sessions"].items():
            prefix = f"Laguna{arm}Card{rank}"
            require(session.startswith(prefix), "Phase-B session prefix drift")
            result[(rank, arm)] = session[len(prefix):]
    return result


def validate_packets(authorization_directory: Path) -> dict[str, str]:
    require(
        authorization_directory.parent == AUTHORIZATION_ROOT
        and stat.S_IMODE(os.stat(authorization_directory, follow_symlinks=False).st_mode)
        == 0o555
        and set(os.listdir(authorization_directory)) == {PHASE_A_NAME, PHASE_B_NAME},
        "authorization directory identity/inventory drift",
    )
    a_path = authorization_directory / PHASE_A_NAME
    b_path = authorization_directory / PHASE_B_NAME
    actual_a, raw_a = _read_canonical(a_path, "Phase-A authorization")
    actual_b, raw_b = _read_canonical(b_path, "Phase-B authorization")
    common = common_from_stage0(
        Path(actual_a["body"]["common"]["stage0_completion"]["path"])
    )
    expected_a, expected_b = packet_pair(
        common,
        authorization_directory,
        Path(actual_a["body"]["aggregate_path"]).parent,
        Path(actual_b["body"]["output_root"]),
        session_nonces=_session_nonces(actual_b),
        counter_tools=actual_b["body"]["counter_tools"],
        temporal_control=actual_b["body"]["temporal_control"],
    )
    require(
        actual_a == expected_a and actual_b == expected_b,
        "authorization pair differs from frozen v3 contract",
    )
    # Recompute host-tool identities instead of trusting the captured copies.
    require(
        actual_b["body"]["counter_tools"] == _counter_tools()
        and actual_b["body"]["temporal_control"] == _temporal_control(),
        "counter or temporal tool identity drift",
    )
    _phase_a().validate_phase_a_packet(actual_a, a_path, verify_artifacts=True)
    _phase_a().validate_phase_b_packet_shape(actual_b, b_path)
    _phase_a().verify_mutual_packets(actual_a, actual_b, phase_b_path=b_path)
    return {
        "phase_a": sha_bytes(raw_a),
        "phase_b": sha_bytes(raw_b),
        "common": _phase_a().common_hash(common),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorization-directory", type=Path, required=True)
    parser.add_argument("--stage0-certificate", type=Path)
    parser.add_argument("--phase-a-root", type=Path)
    parser.add_argument("--phase-b-root", type=Path)
    parser.add_argument("--validate-existing", action="store_true")
    args = parser.parse_args()
    if args.validate_existing:
        require(
            args.stage0_certificate is None
            and args.phase_a_root is None
            and args.phase_b_root is None,
            "validation accepts only the frozen authorization directory",
        )
        result = validate_packets(args.authorization_directory)
    else:
        require(
            args.stage0_certificate is not None
            and args.phase_a_root is not None
            and args.phase_b_root is not None,
            "packet creation requires Stage-0, Phase-A, and Phase-B roots",
        )
        result = write_packets(
            args.stage0_certificate,
            args.authorization_directory,
            args.phase_a_root,
            args.phase_b_root,
        )
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
