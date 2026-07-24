#!/usr/bin/env python3
"""Host-only v3 packet, schema, and artifact validation for Laguna Phase A.

This module deliberately does not start a campaign, import a runtime, load a
native library, enumerate an accelerator, or create an artifact.  Its public
validators are shared by the later Phase-B implementation so that the common
identity has exactly one definition.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
import re
import socket
import stat
import statistics
import struct
import sys
import types
import uuid
from pathlib import Path
from typing import Any


ARTIFACT_ROOT = Path("/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1")
NVME_PREFIX = Path("/mnt/fast-ai")
REPOSITORY_DATA_ROOT = Path("/home/steve/llm-optimizations/data")
REPOSITORY_ROOT = Path("/home/steve/llm-optimizations")
COMMON_FORMAT = "laguna-m8-gather-sharded-common-v3"
PHASE_A_FORMAT = "laguna-m8-gather-sharded-phase-a-authorization-v3"
PHASE_A_BODY_FORMAT = "laguna-m8-gather-sharded-phase-a-body-v3"
PHASE_B_FORMAT = "laguna-m8-gather-sharded-phase-b-authorization-v3"
PHASE_B_BODY_FORMAT = "laguna-m8-gather-sharded-phase-b-body-v3"
FREEZER_FORMAT = "laguna-m8-gather-sharded-native-bundle-v1"
FREEZER_PREPARED_FORMAT = "laguna-m8-gather-sharded-native-bundle-prepared-v1"
FIXTURE_FORMAT = "laguna-m8-gather-sharded-fixtures-v1"
PREFLIGHT_FORMAT = "laguna-m8-gather-sharded-operational-preflight-v2"
EPOCHS = 288
PRE_EPOCHS, POST_EPOCHS = 256, 32
SOURCE_IR_IDENTITY = {"path": "/home/steve/llm-optimizations/data/laguna-s-2.1-m8-gather-sharded-source-build-ir-20260724.json", "sha256": "09b2ee98240058e96860fb04f487509acd2e8253cd862cee108af6de8c3c557c", "device_ir_report_sha256": "e6fefcaacc3253718c8a21ee6eae2544131fee613099ebf91cac9ddbdebd0505", "status": "source_build_ir_pass_stage0_incomplete"}
OPERATIONAL_PREFLIGHT_IDENTITY = {"path": "/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/m8-gather-sharded-operational-preflight-20260724T104851Z/report.json", "sha256": "1c08e4e22fb24931258124f7dee3b31e5d117d715fae239c024e69ffb28b3649", "format": PREFLIGHT_FORMAT, "status": "passed"}
RUNTIME_IDENTITY = {"aot_compile": False, "eager": True, "observed_identity": {"files": {"level_zero_driver": {"path": "/usr/lib/x86_64-linux-gnu/libze_intel_gpu.so.1", "resolved_path": "/usr/lib/x86_64-linux-gnu/libze_intel_gpu.so.1.15.38308", "sha256": "26fa68779adb03b200a8c3001cf81e59fc9a3d63e0f38627ec0005ffce574e7a"}, "level_zero_loader": {"path": "/lib/x86_64-linux-gnu/libze_loader.so.1", "resolved_path": "/usr/lib/x86_64-linux-gnu/libze_loader.so.1.28.2", "sha256": "0fe232b18985ae078dd546b57bc6d11bacf1030834c0544f7e3feb53ed71c1d0"}, "libtorch_xpu": {"path": "/home/steve/.venvs/deepseek-v4-xpu/lib/python3.12/site-packages/torch/lib/libtorch_xpu.so", "resolved_path": "/home/steve/.venvs/deepseek-v4-xpu/lib/python3.12/site-packages/torch/lib/libtorch_xpu.so", "sha256": "63b7a56723482bc35d31842f442f6e903ef0b7fbd741c1a4ae309123bbc90572"}, "python": {"path": "/home/steve/.venvs/deepseek-v4-xpu/bin/python", "resolved_path": "/home/steve/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu/bin/python3.12", "sha256": "202c17d1671602a4ef1d43e9b2fdbef0769443f37bf5e51f6b603e0b2c27d9d8"}, "torch_init": {"path": "/home/steve/.venvs/deepseek-v4-xpu/lib/python3.12/site-packages/torch/__init__.py", "resolved_path": "/home/steve/.venvs/deepseek-v4-xpu/lib/python3.12/site-packages/torch/__init__.py", "sha256": "d9dfff4b75d46e4c75572200a3466b70231d05b0318e38ac1bd121789165fb49"}, "torch_version": {"path": "/home/steve/.venvs/deepseek-v4-xpu/lib/python3.12/site-packages/torch/version.py", "resolved_path": "/home/steve/.venvs/deepseek-v4-xpu/lib/python3.12/site-packages/torch/version.py", "sha256": "454023e3d6adf79f58a7441ffdebc8cf63c9ded2809a254817fa436f9dc7b5c3"}}, "python_executable": "/home/steve/.venvs/deepseek-v4-xpu/bin/python", "python_version": "3.12.13 (main, May 10 2026, 19:30:01) [Clang 22.1.3 ]", "torch_version": "2.12.0+xpu"}, "xpu_driver": "1.15.38308+1", "xpu_graph": False}

LIBRARIES = (
    "shared-_C.abi3.so",
    "shared-_xpu_C.abi3.so",
    "candidate-_moe_C.abi3.so",
    "libgdn_attn_kernels_xe_2.so",
    "libgrouped_gemm_xe_2.so",
    "libgrouped_gemm_xe_default.so",
    "libmhc_kernels_xe_2.so",
    "libmqa_logits_kernels_xe_2.so",
)
FIXTURE_RECORDS = (
    "route_rows",
    "weights",
    "scale_add_input",
    "four_rank_tail",
    "residual_input",
    "norm_weight",
)
PHYSICAL_CARDS = (
    {"physical_rank": 0, "xpu_smi_uuid": "00000000-0000-0023-0000-0000e2238086", "bdf": "0000:23:00.0", "drm_card": "/dev/dri/card3"},
    {"physical_rank": 1, "xpu_smi_uuid": "00000000-0000-0027-0000-0000e2238086", "bdf": "0000:27:00.0", "drm_card": "/dev/dri/card4"},
    {"physical_rank": 2, "xpu_smi_uuid": "00000000-0000-0043-0000-0000e2238086", "bdf": "0000:43:00.0", "drm_card": "/dev/dri/card0"},
    {"physical_rank": 3, "xpu_smi_uuid": "00000000-0000-0047-0000-0000e2238086", "bdf": "0000:47:00.0", "drm_card": "/dev/dri/card2"},
)
COMMON_KEYS = frozenset({"format", "source", "source_ir", "stage0_completion", "native_bundle", "fixture", "cards", "treatments", "logical_cycle", "operational_preflight", "runtime_identity"})
PHASE_A_BODY_KEYS = frozenset({"format", "common", "common_binding_sha256", "phase_b_reference", "runner", "analyzer", "runtime", "coordinator", "protocol", "cards", "aggregate_path", "capability"})
PHASE_B_BODY_KEYS = frozenset({"phase", "common", "common_binding_sha256", "phase_a_binding", "output_root", "cards", "protocol", "counter_gates", "counter_header", "tools", "counter_tools", "temporal_control"})
B_TOOL_FILENAMES = {"runner": "run_laguna_m8_gather_sharded_phase_b.py", "analyzer": "analyze_laguna_m8_gather_sharded_phase_b.py", "fixture": "profile_laguna_m8_gather_sharded_phase_b_fixture.py", "counter_parser": "laguna_m8_gather_sharded_counter_parser.py", "tests": "test_laguna_m8_gather_sharded_phase_b.py", "operational_preflight": "preflight_laguna_m8_gather_sharded_operational.py"}
A_TOOL_FILENAMES = {"runner": "run_laguna_m8_gather_sharded_phase_a.py", "analyzer": "analyze_laguna_m8_gather_sharded_phase_a.py", "runtime": "laguna_m8_gather_sharded_phase_a_runtime.py", "coordinator": "orchestrate_laguna_m8_gather_sharded_phase_a.py"}
TOOLS_ROOT = REPOSITORY_ROOT / "experiments/laguna-s-2.1-xpu-b70/tools"
F_GET_SEALS = getattr(fcntl, "F_GET_SEALS", 1034)
REQUIRED_SEALS = (getattr(fcntl, "F_SEAL_SEAL", 1) | getattr(fcntl, "F_SEAL_SHRINK", 2) |
                  getattr(fcntl, "F_SEAL_GROW", 4) | getattr(fcntl, "F_SEAL_WRITE", 8))


def expected_environment(rank: int, output_root: Path) -> dict[str, str]:
    """The entire env -i surface; packet freezer must call this exact builder."""
    require(0 <= rank < 4 and output_root.is_absolute(), "environment rank/root")
    # Runtime caches are deliberately outside the immutable evidence subtree.
    runtime, cache = output_root / "scratch/runtime", output_root / "scratch/runtime/cache"
    return {"HOME": str(runtime / "home"), "HF_HOME": str(cache / "huggingface"),
            "NUMBA_CACHE_DIR": str(cache / "numba"), "PYTHONPYCACHEPREFIX": str(cache / "pycache"),
            "SYCL_CACHE_DIR": str(cache / "sycl"), "TORCHINDUCTOR_CACHE_DIR": str(cache / "torchinductor"),
            "TRANSFORMERS_CACHE": str(cache / "transformers"), "TRITON_CACHE_DIR": str(cache / "triton"),
            "VLLM_CACHE_ROOT": str(cache / "vllm"), "XDG_CACHE_HOME": str(cache / "xdg-cache"),
            "XDG_CONFIG_HOME": str(cache / "xdg-config"), "XDG_DATA_HOME": str(cache / "xdg-data"),
            "XDG_STATE_HOME": str(cache / "xdg-state"), "TEMP": str(runtime / "tmp"), "TMP": str(runtime / "tmp"),
            "TMPDIR": str(runtime / "tmp"), "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            # -P deliberately removes the script directory.  This is the one
            # explicit, packet-hash-bound import root.
            "PYTHONPATH": str(TOOLS_ROOT),
            "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1", "PYTHONSAFEPATH": "1", "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
            "VLLM_NO_USAGE_STATS": "1", "LD_PRELOAD": "", "LD_LIBRARY_PATH": "", "MKL_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1", "ACTIVE_REQUESTS": "1", "DP": "1", "EP": "4", "PP": "1", "TP": "4",
            "LAGUNA_DFLASH_NUM_SPECULATIVE_TOKENS": "7", "ZE_AFFINITY_MASK": str(rank),
            "ONEAPI_DEVICE_SELECTOR": "level_zero:0", "VLLM_XPU_LAGUNA_M8_GATHER_SHARDED": "1",
            "VLLM_XPU_LAGUNA_M8_GATHER_FINALIZE": "0", "VLLM_XPU_LAGUNA_M8_REMOTE_ZERO": "0",
            "VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION": "0", "VLLM_XPU_LAGUNA_M8_GRAPH": "0", "XPU_GRAPH": "0",
            "VLLM_XPU_ENABLE_XPU_GRAPH": "0", "VLLM_XPU_FORCE_GRAPH_WITH_COMM": "0",
            "VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE": "0", "VLLM_XPU_GDN_NATIVE_FALLBACK": "0", "VLLM_USE_V1": "0",
            "VLLM_USE_AOT_COMPILE": "0", "TORCH_COMPILE_DISABLE": "1", "TORCHINDUCTOR_DISABLE": "1",
            "VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH": "0", "VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM": "0",
            "VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK": "0", "VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM": "0",
            "VLLM_XPU_LAGUNA_M8_SHARED_EXPERT_STREAM": "0", "VLLM_XPU_LAGUNA_M8_SHARED_GATE_MM": "0",
            "VLLM_XPU_LAGUNA_M8_SHARED_GATE_UP_MM": "0", "VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE": "1",
            "VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2": "1", "VLLM_XPU_LAGUNA_M8_QKNORM_ROPE": "1",
            "VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE": "1", "VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE": "1",
            "VLLM_XPU_LAGUNA_M8_W1_N_TILE": "64", "VLLM_XPU_EXACT_SPEC_ATTN": "1",
            "VLLM_XPU_RUN_DEVICE_TESTS": "0", "VLLM_XPU_LAGUNA_PARITY_PROBE": "0",
            "VLLM_XPU_LAGUNA_PARITY_RETURN_STAGE": "0"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def canonical_json(value: Any) -> bytes:
    """Return canonical JSON bytes, including the required terminal newline."""
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def canonical(value: Any) -> bytes:
    """Compatibility alias used by packet tooling."""
    return canonical_json(value)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def common_hash(common: dict[str, Any]) -> str:
    return sha_bytes(canonical_json(common))


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _absolute_nvme_path(value: object, label: str) -> Path:
    require(isinstance(value, str), f"{label} path must be a string")
    path = Path(value)
    require(path.is_absolute() and (path.is_relative_to(NVME_PREFIX) or path.is_relative_to(REPOSITORY_DATA_ROOT) or path.is_relative_to(REPOSITORY_ROOT)), f"{label} must be below an approved internal-NVMe root")
    return path


def _absolute_path(value: object, label: str) -> Path:
    require(isinstance(value, str) and Path(value).is_absolute(), f"{label} path must be absolute")
    return Path(value)


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _open_regular(path: Path, label: str) -> tuple[int, os.stat_result]:
    """Open a final regular component safely and retain its descriptor."""
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    except OSError as error:
        raise RuntimeError(f"cannot open {label}") from error
    metadata = os.fstat(descriptor)
    if not stat.S_ISREG(metadata.st_mode):
        os.close(descriptor)
        raise RuntimeError(f"{label} is not a regular file")
    return descriptor, metadata


def sha256_file(path: Path, label: str = "file") -> str:
    """Descriptor-based stable hash; never follows the final path component."""
    descriptor, before = _open_regular(path, label)
    try:
        digest = hashlib.sha256()
        while block := os.read(descriptor, 1024 * 1024):
            digest.update(block)
        after = os.fstat(descriptor)
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), f"{label} changed while hashing")
        return digest.hexdigest()
    finally:
        os.close(descriptor)


def read_canonical_json(path: Path, label: str, max_bytes: int = 8 * 1024 * 1024) -> tuple[dict[str, Any], bytes]:
    """Descriptor-based canonical JSON read with duplicate-key rejection."""
    require(_is_int(max_bytes) and max_bytes > 0, "invalid JSON size limit")
    descriptor, before = _open_regular(path, label)
    try:
        require(before.st_size <= max_bytes, f"{label} exceeds size limit")
        raw = bytearray()
        while len(raw) <= max_bytes:
            block = os.read(descriptor, min(1024 * 1024, max_bytes + 1 - len(raw)))
            if not block:
                break
            raw.extend(block)
        after = os.fstat(descriptor)
        require(len(raw) == before.st_size and before.st_size == after.st_size and before.st_dev == after.st_dev and before.st_ino == after.st_ino and before.st_mtime_ns == after.st_mtime_ns, f"{label} changed while reading")
    finally:
        os.close(descriptor)
    try:
        value = json.loads(bytes(raw), object_pairs_hook=_strict_object)
    except (TypeError, ValueError, UnicodeDecodeError) as error:
        raise RuntimeError(f"invalid {label} JSON") from error
    require(isinstance(value, dict) and bytes(raw) == canonical_json(value), f"{label} is not canonical JSON")
    return value, bytes(raw)


def read_canonical_json_fd(descriptor: int, label: str, max_bytes: int = 8 * 1024 * 1024) -> tuple[dict[str, Any], bytes]:
    before = os.fstat(descriptor)
    require(stat.S_ISREG(before.st_mode) and 0 <= before.st_size <= max_bytes, f"invalid {label} descriptor")
    raw = os.pread(descriptor, before.st_size, 0)
    after = os.fstat(descriptor)
    require(len(raw) == before.st_size and (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), f"{label} descriptor changed")
    value = json.loads(raw, object_pairs_hook=_strict_object)
    require(isinstance(value, dict) and raw == canonical_json(value), f"{label} is not canonical JSON")
    return value, raw


def _assert_internal_nvme(path: Path, label: str) -> None:
    """Reject USB and every non-ext4/non-NVMe mount before artifact reads."""
    _absolute_nvme_path(str(path), label)
    resolved = path.resolve(strict=True)
    require(resolved.is_relative_to(NVME_PREFIX) or resolved.is_relative_to(REPOSITORY_DATA_ROOT) or resolved.is_relative_to(REPOSITORY_ROOT), f"{label} resolves outside approved internal-NVMe roots")
    mount_rows: list[tuple[Path, str, str]] = []
    try:
        lines = Path("/proc/self/mountinfo").read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise RuntimeError("cannot inspect mount identity") from error
    for line in lines:
        left, separator, right = line.partition(" - ")
        if not separator:
            continue
        fields, tail = left.split(), right.split()
        if len(fields) < 5 or len(tail) < 2:
            continue
        mount_rows.append((Path(fields[4].replace("\\040", " ")), tail[0], tail[1]))
    candidates = [row for row in mount_rows if resolved.is_relative_to(row[0])]
    require(candidates, f"cannot identify mount for {label}")
    _mount, filesystem, source = max(candidates, key=lambda row: len(str(row[0])))
    require(filesystem == "ext4" and source.startswith("/dev/nvme"), f"{label} is not on approved internal NVMe/ext4")


def assert_live_internal_nvme(path: Path, label: str) -> None:
    """Attest an existing output directory, rather than trusting its spelling."""
    _assert_internal_nvme(path, label)
    descriptor, metadata = _open_dir(path, label)
    try:
        require(stat.S_ISDIR(metadata.st_mode), f"{label} is not a directory")
    finally:
        os.close(descriptor)


def _validate_file_identity(value: object, label: str, *, artifact: bool = False, internal_nvme: bool = True) -> dict[str, str]:
    require(isinstance(value, dict) and set(value) == {"path", "sha256"}, f"{label} schema")
    path = _absolute_nvme_path(value["path"], label) if internal_nvme else _absolute_path(value["path"], label)
    require(_is_sha256(value["sha256"]), f"{label} SHA-256")
    if artifact:
        _assert_internal_nvme(path, label)
        require(sha256_file(path, label) == value["sha256"], f"{label} digest drift")
    return value


def _validate_card_rows(value: object, label: str) -> list[dict[str, Any]]:
    require(isinstance(value, list) and value == list(PHYSICAL_CARDS), f"{label} physical card identity drift")
    return value


def validate_common(common: object) -> dict[str, Any]:
    """Validate the byte-shareable v3 common identity without touching files."""
    require(isinstance(common, dict) and set(common) == COMMON_KEYS, "common schema")
    require(common["format"] == COMMON_FORMAT, "common format")

    source = common["source"]
    require(isinstance(source, dict) and source == {"approved_record_vllm_commit": "8936aac144929190c1e53f8b8624ca397ce16f5b", "approved_record_kernel_commit": "b6076ce1249ffee0e30bee528f4cd15c3bffb234", "candidate_kernel_commit": "7e6a74026a2a4370abcb7973d28bbc9d1ddd1be6"}, "source identity")
    source_ir = common["source_ir"]
    require(source_ir == SOURCE_IR_IDENTITY, "source/IR identity")
    _absolute_path(source_ir["path"], "source/IR")
    stage0 = common["stage0_completion"]
    require(isinstance(stage0, dict) and set(stage0) == {"path", "sha256", "status", "input"} and stage0["status"] == "stage0_host_only_complete_pending_packet_commit" and _is_sha256(stage0["sha256"]), "Stage-0 completion schema")
    _absolute_nvme_path(stage0["path"], "Stage-0 completion")
    _validate_file_identity(stage0["input"], "Stage-0 completion input")

    bundle = common["native_bundle"]
    bundle_keys = {"root", "manifest", "manifest_sha256", "prepared", "prepared_sha256", "library_sha256", "libraries", "status", "validation_protocol", "storage"}
    require(isinstance(bundle, dict) and set(bundle) == bundle_keys, "native bundle schema")
    root = _absolute_nvme_path(bundle["root"], "native bundle root")
    for key in ("manifest", "prepared"):
        path = _absolute_nvme_path(bundle[key], f"native bundle {key}")
        require(path.parent == root, f"native bundle {key} location")
    require(_is_sha256(bundle["manifest_sha256"]) and _is_sha256(bundle["prepared_sha256"]), "native bundle metadata hashes")
    require(bundle["status"] == "validated_host_only_not_imported" and bundle["validation_protocol"] == "separate_successful_validate_existing_invocation_required", "native bundle status")
    require(isinstance(bundle["storage"], dict) and set(bundle["storage"]) == {"mount_point", "filesystem", "source", "major_minor", "sysfs_device"} and bundle["storage"].get("filesystem") == "ext4" and bundle["storage"].get("source") == "/dev/nvme0n1p2" and bundle["storage"].get("major_minor") == "259:2" and isinstance(bundle["storage"].get("mount_point"), str) and isinstance(bundle["storage"].get("sysfs_device"), str) and any(part.startswith("nvme") for part in Path(bundle["storage"]["sysfs_device"]).parts), "native bundle storage")
    require(isinstance(bundle["library_sha256"], dict) and set(bundle["library_sha256"]) == set(LIBRARIES) and all(_is_sha256(value) for value in bundle["library_sha256"].values()), "native bundle eight-library identity")
    require(isinstance(bundle["libraries"], dict) and set(bundle["libraries"]) == set(LIBRARIES), "native bundle detailed library inventory")
    for name, record in bundle["libraries"].items():
        require(isinstance(record, dict) and set(record) == {"role", "source", "path", "sha256", "bytes", "mode"} and isinstance(record["role"], str) and isinstance(record["source"], str) and _absolute_nvme_path(record["path"], f"native bundle {name}").parent == root and record["sha256"] == bundle["library_sha256"][name] and _is_int(record["bytes"]) and record["bytes"] > 0 and record["mode"] == 0o444, f"native bundle {name} detailed identity")

    fixture = common["fixture"]
    require(isinstance(fixture, dict) and set(fixture) == {"root", "manifest", "manifest_sha256", "analysis", "analysis_sha256", "canonical_route_map", "records"}, "fixture schema")
    fixture_root = _absolute_nvme_path(fixture["root"], "fixture root")
    for key in ("manifest", "analysis"):
        path = _absolute_nvme_path(fixture[key], f"fixture {key}")
        require(path.parent == fixture_root, f"fixture {key} location")
    require(_is_sha256(fixture["manifest_sha256"]) and _is_sha256(fixture["analysis_sha256"]), "fixture metadata hashes")
    _validate_file_identity(fixture["canonical_route_map"], "fixture canonical route map")
    require(Path(fixture["canonical_route_map"]["path"]).parent == fixture_root, "fixture canonical route map location")
    require(isinstance(fixture["records"], dict) and set(fixture["records"]) == set(FIXTURE_RECORDS), "fixture six-record inventory")
    for name in FIXTURE_RECORDS:
        record = fixture["records"][name]
        require(isinstance(record, dict) and set(record) == {"path", "sha256", "dtype", "shape", "per_epoch_sha256"}, f"fixture {name} schema")
        path = _absolute_nvme_path(record["path"], f"fixture {name}")
        require(path.parent == fixture_root and _is_sha256(record["sha256"]) and isinstance(record["dtype"], str) and isinstance(record["shape"], list) and all(_is_int(item) and item > 0 for item in record["shape"]), f"fixture {name} identity")
        hashes = record["per_epoch_sha256"]
        require(isinstance(hashes, list) and len(hashes) == EPOCHS and all(_is_sha256(item) for item in hashes), f"fixture {name} epoch hashes")

    _validate_card_rows(common["cards"], "common cards")
    require(common["treatments"] == {"A": "generic_moe_gather", "B": "laguna_m8_moe_gather_sharded", "same_candidate_moe_library": True}, "treatments")
    require(common["logical_cycle"] == {"layers": 47, "warm_cycles_per_arm": 20, "blocks": 31, "cycles_per_arm": 64, "arm_order": "A-B-B-A", "rotation": "(block*47)%256", "pre_epochs": 256, "post_epochs": 32, "minimum_wins": 28, "minimum_median_saving_ms": 0.08}, "logical cycle")
    preflight = common["operational_preflight"]
    require(preflight == OPERATIONAL_PREFLIGHT_IDENTITY, "operational preflight identity")
    _absolute_nvme_path(preflight["path"], "operational preflight")
    runtime = common["runtime_identity"]
    require(runtime == RUNTIME_IDENTITY, "runtime identity")
    observed = runtime["observed_identity"]
    require(isinstance(observed, dict) and set(observed) == {"files", "python_executable", "python_version", "torch_version"} and observed["torch_version"] == "2.12.0+xpu" and isinstance(observed["python_executable"], str) and isinstance(observed["python_version"], str), "runtime observed identity")
    files = observed["files"]
    require(isinstance(files, dict) and set(files) == {"level_zero_driver", "level_zero_loader", "libtorch_xpu", "python", "torch_init", "torch_version"}, "runtime six-file inventory")
    for name, identity in files.items():
        require(isinstance(identity, dict) and set(identity) == {"path", "resolved_path", "sha256"} and isinstance(identity["resolved_path"], str) and Path(identity["resolved_path"]).is_absolute(), f"runtime {name} resolved schema")
        _validate_file_identity({"path": identity["path"], "sha256": identity["sha256"]}, f"runtime {name}", internal_nvme=False)
    require(observed["python_executable"] == files["python"]["path"], "runtime Python executable binding")
    return common


def _validate_body_cards(value: object, common_cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    require(isinstance(value, list) and len(value) == 4, "phase card schema")
    for rank, card in enumerate(value):
        require(isinstance(card, dict) and set(card) == {"rank", "physical_rank", "environment", "output_root"}, "phase card keys")
        require(card["rank"] == rank and card["physical_rank"] == common_cards[rank]["physical_rank"], "phase card physical binding")
        _absolute_nvme_path(card["output_root"], "phase card output root")
        require(card["environment"] == expected_environment(rank, Path(card["output_root"])), "phase card exact environment")
    return value


def _validate_component_identity(value: object, label: str) -> dict[str, str]:
    return _validate_file_identity(value, label)


def validate_phase_a_packet(packet: object, path: Path, *, verify_artifacts: bool = False) -> dict[str, Any]:
    """Validate Phase-A's nonrecursive wrapper and complete future body schema."""
    require(isinstance(packet, dict) and set(packet) == {"format", "packet_path", "body", "paired_phase_b_packet_sha256"}, "Phase-A wrapper schema")
    require(packet["format"] == PHASE_A_FORMAT and packet["packet_path"] == str(path) and _is_sha256(packet["paired_phase_b_packet_sha256"]), "Phase-A wrapper identity")
    body = packet["body"]
    require(isinstance(body, dict) and set(body) == PHASE_A_BODY_KEYS and body["format"] == PHASE_A_BODY_FORMAT, "Phase-A body schema")
    common = validate_common(body["common"])
    require(body["common_binding_sha256"] == common_hash(common), "Phase-A common hash")
    reference = body["phase_b_reference"]
    require(isinstance(reference, dict) and set(reference) == {"authorization_path", "runner_path", "runner_sha256", "common_binding_sha256"}, "Phase-B reference schema")
    _absolute_nvme_path(reference["authorization_path"], "Phase-B authorization")
    require(_absolute_path(reference["runner_path"], "Phase-B runner") and _is_sha256(reference["runner_sha256"]), "Phase-B runner identity")
    require(reference["common_binding_sha256"] == body["common_binding_sha256"], "Phase-B reference common hash")
    for key in ("runner", "analyzer", "runtime", "coordinator"):
        _validate_component_identity(body[key], f"Phase-A {key}")
        require(body[key]["path"] == str(REPOSITORY_ROOT / "experiments/laguna-s-2.1-xpu-b70/tools" / A_TOOL_FILENAMES[key]), f"Phase-A {key} path")
    require(isinstance(body["protocol"], dict) and set(body["protocol"]) == {"phase", "authorization"} and body["protocol"] == {"phase": "A", "authorization": "component_exactness_and_timing_only"}, "Phase-A protocol")
    _validate_body_cards(body["cards"], common["cards"])
    aggregate = _absolute_nvme_path(body["aggregate_path"], "Phase-A aggregate")
    require(aggregate.name == "aggregate.json" and all(Path(card["output_root"]) == aggregate.parent / f"card{rank}"
            for rank, card in enumerate(body["cards"])), "Phase-A aggregate/card-root closure")
    require(body["capability"] == {"phase": "A", "phase_b_counters_authorized": False, "endpoint_authorized": False, "model_generation_authorized": False, "submission_authorized": False}, "Phase-A capability")
    if verify_artifacts:
        verify_common_artifacts(common)
    return packet


def validate_phase_b_packet_shape(packet: object, path: Path, *, verify_artifacts: bool = False) -> dict[str, Any]:
    """Validate the B shape needed for mutual binding; B owns its execution rules."""
    require(isinstance(packet, dict) and set(packet) == {"format", "packet_path", "body"}, "Phase-B wrapper schema")
    require(packet["format"] == PHASE_B_FORMAT and packet["packet_path"] == str(path), "Phase-B wrapper identity")
    body = packet["body"]
    require(isinstance(body, dict) and set(body) == PHASE_B_BODY_KEYS and body["phase"] == "B", "Phase-B body schema")
    common = validate_common(body["common"])
    require(body["common_binding_sha256"] == common_hash(common), "Phase-B common hash")
    binding = body["phase_a_binding"]
    require(isinstance(binding, dict) and set(binding) == {"authorization_path", "phase_a_body_sha256", "phase_a_runner_path", "phase_a_runner_sha256", "aggregate_path", "aggregate_format", "required_status", "required_passed", "common_binding_sha256"}, "Phase-A binding schema")
    _absolute_nvme_path(binding["authorization_path"], "Phase-A authorization")
    require(_is_sha256(binding["phase_a_body_sha256"]) and _absolute_path(binding["phase_a_runner_path"], "Phase-A runner") and _is_sha256(binding["phase_a_runner_sha256"]) and _absolute_nvme_path(binding["aggregate_path"], "Phase-A aggregate") and binding["aggregate_format"] == "laguna-m8-gather-sharded-phase-a-aggregate-v3" and binding["required_status"] == "component_timing_pass_pending_mandatory_counters" and binding["required_passed"] is True and binding["common_binding_sha256"] == body["common_binding_sha256"], "Phase-A binding identity")
    output_root = _absolute_nvme_path(body["output_root"], "Phase-B output root")
    tools = body["tools"]
    require(isinstance(tools, dict) and set(tools) == {"runner", "analyzer", "fixture", "counter_parser", "tests", "operational_preflight"}, "Phase-B tools schema")
    for name, identity in tools.items():
        _validate_component_identity(identity, f"Phase-B tool {name}")
        require(identity["path"] == str(REPOSITORY_ROOT / "experiments/laguna-s-2.1-xpu-b70/tools" / B_TOOL_FILENAMES[name]), f"Phase-B tool {name} path")
    require(isinstance(body["cards"], list) and len(body["cards"]) == 4, "Phase-B card count")
    sessions: set[str] = set()
    for rank, card in enumerate(body["cards"]):
        require(isinstance(card, dict) and set(card) == {"rank", "output_root", "environments", "sessions"} and card["rank"] == rank and card["output_root"] == str(output_root / f"card{rank}") and isinstance(card["environments"], dict) and set(card["environments"]) == {"A1", "B1", "B2", "A2"} and all(isinstance(env, dict) and all(isinstance(key, str) and isinstance(item, str) for key, item in env.items()) for env in card["environments"].values()) and isinstance(card["sessions"], dict) and set(card["sessions"]) == {"A1", "B1", "B2", "A2"}, "Phase-B card schema")
        for arm, session in card["sessions"].items():
            require(isinstance(session, str) and re.fullmatch(rf"Laguna{arm}Card{rank}[0-9a-f]{{32}}", session) is not None and session not in sessions, "Phase-B session identity")
            sessions.add(session)
    if verify_artifacts:
        verify_common_artifacts(common)
    return packet


def verify_mutual_packets(phase_a_packet: dict[str, Any], phase_b_packet: dict[str, Any] | None = None, *, phase_b_path: Path | None = None) -> None:
    """Verify both directions without putting a recursive B digest in B."""
    a_path = Path(phase_a_packet["packet_path"])
    validate_phase_a_packet(phase_a_packet, a_path)
    reference = phase_a_packet["body"]["phase_b_reference"]
    if phase_b_packet is None:
        source = phase_b_path or Path(reference["authorization_path"])
        phase_b_packet, raw_b = read_canonical_json(source, "paired Phase-B packet")
    else:
        source = phase_b_path or Path(phase_b_packet["packet_path"])
        raw_b = canonical_json(phase_b_packet)
    require(source == Path(reference["authorization_path"]), "paired Phase-B path")
    require(sha_bytes(raw_b) == phase_a_packet["paired_phase_b_packet_sha256"], "paired Phase-B full hash")
    validate_phase_b_packet_shape(phase_b_packet, source)
    a_body, b_body = phase_a_packet["body"], phase_b_packet["body"]
    require(canonical_json(a_body["common"]) == canonical_json(b_body["common"]), "A/B common bytes differ")
    binding = b_body["phase_a_binding"]
    require(binding["authorization_path"] == phase_a_packet["packet_path"], "Phase-B A authorization path")
    require(binding["phase_a_body_sha256"] == sha_bytes(canonical_json(a_body)), "Phase-B A body hash")
    require(binding["common_binding_sha256"] == a_body["common_binding_sha256"], "Phase-B A common hash")
    require(binding["phase_a_runner_path"] == a_body["runner"]["path"] and binding["phase_a_runner_sha256"] == a_body["runner"]["sha256"], "Phase-B A runner binding")
    require(binding["aggregate_path"] == a_body["aggregate_path"], "Phase-B aggregate path binding")
    for key in A_TOOL_FILENAMES:
        require(sha256_file(Path(a_body[key]["path"]), f"Phase-A {key}") == a_body[key]["sha256"], f"Phase-A {key} live source binding")
    reference_runner = a_body["phase_b_reference"]
    b_runner = b_body["tools"]["runner"]
    require(reference_runner["runner_path"] == b_runner["path"] and reference_runner["runner_sha256"] == b_runner["sha256"], "Phase-A B runner binding")
    require(sha256_file(Path(b_runner["path"]), "Phase-B runner") == b_runner["sha256"], "Phase-B runner live source binding")


def _hash_epoch_chunks(path: Path, hashes: list[str], label: str) -> None:
    descriptor, before = _open_regular(path, label)
    try:
        require(before.st_size > 0 and before.st_size % EPOCHS == 0, f"{label} epoch layout")
        bytes_per_epoch = before.st_size // EPOCHS
        for index, expected in enumerate(hashes):
            remaining, digest = bytes_per_epoch, hashlib.sha256()
            while remaining:
                block = os.read(descriptor, min(1024 * 1024, remaining))
                require(block, f"short {label} epoch read")
                digest.update(block)
                remaining -= len(block)
            require(digest.hexdigest() == expected, f"{label} epoch {index} digest drift")
        after = os.fstat(descriptor)
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), f"{label} changed while checking epochs")
    finally:
        os.close(descriptor)


def _verify_native_bundle(bundle: dict[str, Any]) -> None:
    root = Path(bundle["root"])
    _assert_internal_nvme(root, "native bundle root")
    require(root.is_dir() and not root.is_symlink(), "native bundle root safety")
    require(set(os.listdir(root)) == set(LIBRARIES) | {"manifest.json", "bundle-prepared.json"}, "native bundle inventory")
    manifest_path, prepared_path = Path(bundle["manifest"]), Path(bundle["prepared"])
    require(sha256_file(manifest_path, "native bundle manifest") == bundle["manifest_sha256"], "native bundle manifest hash")
    require(sha256_file(prepared_path, "native bundle prepared marker") == bundle["prepared_sha256"], "native bundle prepared hash")
    manifest, _ = read_canonical_json(manifest_path, "native bundle manifest")
    prepared, _ = read_canonical_json(prepared_path, "native bundle prepared marker")
    expected_libraries: dict[str, dict[str, Any]] = {}
    for name in LIBRARIES:
        path = root / name
        metadata = os.stat(path, follow_symlinks=False)
        require(stat.S_ISREG(metadata.st_mode) and stat.S_IMODE(metadata.st_mode) == 0o444, f"native bundle {name} mode")
        digest = sha256_file(path, f"native bundle {name}")
        require(digest == bundle["library_sha256"][name], f"native bundle {name} digest")
        expected_libraries[name] = {"role": None, "source": None, "path": str(path), "sha256": digest, "bytes": metadata.st_size}
    require(isinstance(manifest, dict) and set(manifest) == {"format", "status", "root", "storage", "candidate_kernel_commit", "approved_record_kernel_commit", "approved_record_vllm_commit", "libraries", "actions_not_performed"}, "freezer manifest schema")
    require(manifest["format"] == FREEZER_FORMAT and manifest["status"] == "prepared_host_only_not_imported" and manifest["root"] == str(root) and manifest["storage"] == bundle["storage"], "freezer manifest identity")
    require(isinstance(manifest["libraries"], dict) and set(manifest["libraries"]) == set(LIBRARIES), "freezer manifest library inventory")
    for name, expected in expected_libraries.items():
        actual = manifest["libraries"][name]
        detailed = bundle["libraries"][name]
        require(isinstance(actual, dict) and set(actual) == {"role", "source", "path", "sha256", "bytes"} and actual == {key: detailed[key] for key in ("role", "source", "path", "sha256", "bytes")} and actual["path"] == expected["path"] and actual["sha256"] == expected["sha256"] and actual["bytes"] == expected["bytes"], f"freezer manifest {name}")
    require(prepared == {"format": FREEZER_PREPARED_FORMAT, "status": "prepared_requires_separate_validation", "root": str(root), "manifest_sha256": bundle["manifest_sha256"], "library_sha256": bundle["library_sha256"]}, "freezer prepared marker")


def _verify_fixture(fixture: dict[str, Any]) -> None:
    root = Path(fixture["root"])
    _assert_internal_nvme(root, "fixture root")
    manifest_path, analysis_path = Path(fixture["manifest"]), Path(fixture["analysis"])
    require(sha256_file(manifest_path, "fixture manifest") == fixture["manifest_sha256"], "fixture manifest hash")
    require(sha256_file(analysis_path, "fixture analysis") == fixture["analysis_sha256"], "fixture analysis hash")
    manifest, _ = read_canonical_json(manifest_path, "fixture manifest", 8 * 1024 * 1024)
    analysis, _ = read_canonical_json(analysis_path, "fixture analysis", 8 * 1024 * 1024)
    require(isinstance(manifest, dict) and set(manifest) == {"format", "production", "pre_timing_epochs", "post_timing_epochs", "epochs", "geometry", "canonical_route_map", "local_masks_uint16", "fixtures", "classes", "tensors"}, "fixture manifest schema")
    require(manifest["format"] == FIXTURE_FORMAT and manifest["production"] is True and manifest["pre_timing_epochs"] == 256 and manifest["post_timing_epochs"] == 32 and manifest["epochs"] == EPOCHS, "fixture manifest identity")
    route_map = fixture["canonical_route_map"]
    require(sha256_file(Path(route_map["path"]), "fixture canonical route map") == route_map["sha256"], "fixture canonical route map hash")
    require(manifest["canonical_route_map"] == {"file": "canonical_route_map.int32.le.bin", "dtype": "<i4", "shape": [8, 10], "sha256": route_map["sha256"], "definition": "arange(80).reshape(8,10)"}, "fixture canonical route map manifest binding")
    require(isinstance(manifest["tensors"], dict) and set(manifest["tensors"]) == set(FIXTURE_RECORDS), "fixture manifest records")
    for name in FIXTURE_RECORDS:
        record, manifest_record = fixture["records"][name], manifest["tensors"][name]
        require(isinstance(manifest_record, dict) and set(manifest_record) == {"name", "file", "dtype", "shape", "sha256", "epoch_sha256"}, f"fixture manifest {name} schema")
        require(manifest_record["name"] == name and str(root / manifest_record["file"]) == record["path"] and manifest_record["dtype"] == record["dtype"] and manifest_record["shape"] == record["shape"] and manifest_record["sha256"] == record["sha256"] and manifest_record["epoch_sha256"] == record["per_epoch_sha256"], f"fixture manifest {name} binding")
        path = Path(record["path"])
        require(sha256_file(path, f"fixture {name}") == record["sha256"], f"fixture {name} whole hash")
        _hash_epoch_chunks(path, record["per_epoch_sha256"], f"fixture {name}")
    require(isinstance(manifest["fixtures"], list) and len(manifest["fixtures"]) == EPOCHS, "fixture per-epoch manifest")
    for index, entry in enumerate(manifest["fixtures"]):
        require(isinstance(entry, dict) and set(entry) == {"id", "phase", "class", "local_masks_uint16", "route_pattern", "independent_slot_probes", "tensor_sha256"} and entry["id"] == f"epoch-{index:03d}" and isinstance(entry["tensor_sha256"], dict) and entry["tensor_sha256"] == {name: fixture["records"][name]["per_epoch_sha256"][index] for name in FIXTURE_RECORDS}, f"fixture epoch {index} binding")
    require(isinstance(analysis, dict) and set(analysis) == {"manifest_sha256", "hashes_match_manifest", "deterministic_bytes_match", "tensors", "coverage", "status"} and analysis["status"] == "passed" and analysis["manifest_sha256"] == fixture["manifest_sha256"] and analysis["hashes_match_manifest"] is True and analysis["deterministic_bytes_match"] is True, "fixture analysis binding")


def _load_stage0_validator(certificate: dict[str, Any]) -> tuple[Any, list[int]]:
    """Load the certificate-bound helper closure from retained exact bytes."""
    closure = certificate.get("tools", {}).get("local_helper_closure")
    require(isinstance(closure, list), "Stage-0 helper closure missing")
    records = {item.get("path"): item for item in closure if isinstance(item, dict)}
    names = (
        ("preflight_laguna_m8_gather_sharded_operational", "experiments/laguna-s-2.1-xpu-b70/tools/preflight_laguna_m8_gather_sharded_operational.py"),
        ("freeze_laguna_m8_gather_sharded_binary_bundle", "experiments/laguna-s-2.1-xpu-b70/tools/freeze_laguna_m8_gather_sharded_binary_bundle.py"),
        ("prepare_laguna_m8_gather_sharded_fixtures", "experiments/laguna-s-2.1-xpu-b70/tools/prepare_laguna_m8_gather_sharded_fixtures.py"),
        ("freeze_laguna_m8_gather_sharded_stage0_completion", "experiments/laguna-s-2.1-xpu-b70/tools/freeze_laguna_m8_gather_sharded_stage0_completion.py"),
    )
    retained: list[int] = []
    try:
        for module_name, relative in names:
            record = records.get(relative)
            require(isinstance(record, dict) and set(record) == {"path", "sha256"} and _is_sha256(record["sha256"]),
                    f"Stage-0 helper binding missing: {relative}")
            path = REPOSITORY_ROOT / relative
            descriptor, _metadata = _open_regular(path, f"Stage-0 helper {module_name}")
            digest, stable = _hash_retained(descriptor, f"Stage-0 helper {module_name}")
            require(digest == record["sha256"], f"Stage-0 helper hash drift: {module_name}")
            raw = os.pread(descriptor, stable.st_size, 0)
            retained.append(descriptor)
            module = types.ModuleType(module_name)
            module.__file__ = str(path)
            sys.modules[module_name] = module
            exec(compile(raw, str(path), "exec"), module.__dict__)
        return sys.modules["freeze_laguna_m8_gather_sharded_stage0_completion"], retained
    except BaseException:
        for descriptor in retained:
            os.close(descriptor)
        raise


def verify_common_artifacts(common: object) -> None:
    """Rehash all common host artifacts and fail closed on non-NVMe storage."""
    common_value = validate_common(common)
    for key, status in (("source_ir", "source_build_ir_pass_stage0_incomplete"), ("stage0_completion", "stage0_host_only_complete_pending_packet_commit")):
        record = common_value[key]
        path = Path(record["path"])
        _assert_internal_nvme(path, key)
        require(sha256_file(path, key) == record["sha256"], f"{key} hash")
        value, _ = read_canonical_json(path, key)
        require(value.get("status") == status, f"{key} status")
        if key == "stage0_completion":
            input_path = Path(record["input"]["path"])
            _assert_internal_nvme(input_path, "Stage-0 completion input")
            require(sha256_file(input_path, "Stage-0 completion input") == record["input"]["sha256"], "Stage-0 completion input hash")
            validator, retained_helpers = _load_stage0_validator(value)
            try:
                require(validator.validate_certificate_only(path) == value, "Stage-0 completion certificate closure")
            finally:
                for descriptor in retained_helpers:
                    os.close(descriptor)
    preflight = common_value["operational_preflight"]
    preflight_path = Path(preflight["path"])
    _assert_internal_nvme(preflight_path, "operational preflight")
    require(sha256_file(preflight_path, "operational preflight") == preflight["sha256"], "operational preflight hash")
    preflight_value, _ = read_canonical_json(preflight_path, "operational preflight")
    require(preflight_value.get("format") == PREFLIGHT_FORMAT and preflight_value.get("status") == "passed", "operational preflight identity")
    _verify_native_bundle(common_value["native_bundle"])
    _verify_fixture(common_value["fixture"])
    for name, identity in common_value["runtime_identity"]["observed_identity"]["files"].items():
        path, resolved = Path(identity["path"]), Path(identity["resolved_path"])
        require(path.resolve(strict=True) == resolved and resolved.is_file() and not resolved.is_symlink(), f"runtime {name} symlink binding")
        require(sha256_file(resolved, f"runtime {name}") == identity["sha256"], f"runtime {name} digest drift")


# The execution entrypoint below remains in this file so the frozen packet has
# one hash-bound runner.  Everything above it is still usable by Phase B as a
# host-only shared identity validator.

CARD_RESULT_FORMAT = "laguna-m8-gather-sharded-phase-a-card-result-v3"
PREIMPORT_FORMAT = "laguna-m8-gather-sharded-phase-a-preimport-v3"


def _write_exclusive_at(directory_fd: int, name: str, value: dict[str, Any]) -> str:
    require(name and "/" not in name and name not in {".", ".."}, "unsafe evidence name")
    data = canonical_json(value)
    descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400,
                         dir_fd=directory_fd)
    try:
        offset = 0
        while offset < len(data):
            written = os.write(descriptor, data[offset:])
            require(written > 0, "short evidence write")
            offset += written
        os.fsync(descriptor)
        os.fchmod(descriptor, 0o444)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.fsync(directory_fd)
    return sha_bytes(data)


def _open_dir(path: Path, label: str) -> tuple[int, os.stat_result]:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    except OSError as error:
        raise RuntimeError(f"cannot open {label}") from error
    metadata = os.fstat(descriptor)
    if not stat.S_ISDIR(metadata.st_mode):
        os.close(descriptor)
        raise RuntimeError(f"{label} is not a directory")
    return descriptor, metadata


def _open_at(directory_fd: int, name: str, label: str) -> tuple[int, os.stat_result]:
    require(name and "/" not in name and name not in {".", ".."}, f"unsafe {label} name")
    try:
        descriptor = os.open(name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=directory_fd)
    except OSError as error:
        raise RuntimeError(f"cannot open retained {label}") from error
    metadata = os.fstat(descriptor)
    if not stat.S_ISREG(metadata.st_mode):
        os.close(descriptor)
        raise RuntimeError(f"retained {label} is not a regular file")
    return descriptor, metadata


def _hash_retained(descriptor: int, label: str) -> tuple[str, os.stat_result]:
    before = os.fstat(descriptor)
    digest, offset = hashlib.sha256(), 0
    while offset < before.st_size:
        block = os.pread(descriptor, min(1024 * 1024, before.st_size - offset), offset)
        require(block, f"short retained read: {label}")
        digest.update(block)
        offset += len(block)
    after = os.fstat(descriptor)
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), f"retained {label} changed")
    return digest.hexdigest(), after


def _retain_runtime_inputs(common: dict[str, Any]) -> dict[str, Any]:
    """Pin every object whose bytes can influence a native call before torch."""
    bundle = common["native_bundle"]
    bundle_fd, bundle_meta = _open_dir(Path(bundle["root"]), "sealed native bundle")
    fixture = common["fixture"]
    fixture_fd, fixture_meta = _open_dir(Path(fixture["root"]), "fixture root")
    retained: dict[str, Any] = {"bundle_fd": bundle_fd, "fixture_fd": fixture_fd, "fds": {},
                                "records": fixture["records"], "library_fds": {},
                                "directory_identity": {"bundle": {"dev": bundle_meta.st_dev, "inode": bundle_meta.st_ino},
                                                       "fixture": {"dev": fixture_meta.st_dev, "inode": fixture_meta.st_ino}}}
    try:
        for name, record in bundle["libraries"].items():
            require(Path(record["path"]).parent == Path(bundle["root"]), f"bundle member parent: {name}")
            fd, metadata = _open_at(bundle_fd, name, f"bundle {name}")
            digest, after = _hash_retained(fd, f"bundle {name}")
            require(digest == record["sha256"] and after.st_size == record["bytes"] and stat.S_IMODE(metadata.st_mode) == 0o444,
                    f"bundle identity drift: {name}")
            retained["library_fds"][name] = fd
        for name, record in fixture["records"].items():
            path = Path(record["path"])
            require(path.parent == Path(fixture["root"]), f"fixture member parent: {name}")
            fd, metadata = _open_at(fixture_fd, path.name, f"fixture {name}")
            digest, after = _hash_retained(fd, f"fixture {name}")
            width = {"<u2": 2, "<u4": 4}.get(record["dtype"])
            require(width is not None and len(record["shape"]) >= 2, f"fixture dtype/shape: {name}")
            epoch_bytes = width
            for dimension in record["shape"][1:]:
                epoch_bytes *= dimension
            require(record["shape"][0] == EPOCHS and after.st_size == epoch_bytes * EPOCHS and
                    digest == record["sha256"] and len(record["per_epoch_sha256"]) == EPOCHS,
                    f"fixture retained identity: {name}")
            retained["fds"][name] = fd
        route_record = fixture["canonical_route_map"]
        route_path = Path(route_record["path"])
        require(route_path.parent == Path(fixture["root"]), "route map parent")
        route_fd, route_meta = _open_at(fixture_fd, route_path.name, "canonical route map")
        route_digest, route_after = _hash_retained(route_fd, "canonical route map")
        require(route_digest == route_record["sha256"] and route_after.st_size == 8 * 10 * 4,
                "canonical route map identity")
        route_bytes = os.pread(route_fd, route_after.st_size, 0)
        require(route_bytes == b"".join(index.to_bytes(4, "little", signed=True) for index in range(80)),
                "canonical route map bytes")
        retained.update(route_map_fd=route_fd, route_map=route_bytes, route_map_sha256=route_digest)
        return retained
    except BaseException:
        _close_retained(retained)
        raise


def _close_retained(retained: dict[str, Any]) -> None:
    for key in ("library_fds", "fds"):
        for descriptor in retained.get(key, {}).values():
            try:
                os.close(descriptor)
            except OSError:
                pass
    for key in ("route_map_fd", "fixture_fd", "bundle_fd"):
        descriptor = retained.get(key)
        if isinstance(descriptor, int):
            try:
                os.close(descriptor)
            except OSError:
                pass


def _load_runtime_from_retained_source(body: dict[str, Any]) -> Any:
    """Execute the hash-bound runtime bytes; never re-open it through import."""
    identity = body["runtime"]
    source = Path(identity["path"])
    require(source.parent == TOOLS_ROOT and source.name == A_TOOL_FILENAMES["runtime"], "runtime source path")
    tools_fd, _ = _open_dir(TOOLS_ROOT, "Phase-A tools root")
    try:
        descriptor, metadata = _open_at(tools_fd, source.name, "Phase-A runtime source")
        try:
            digest, stable = _hash_retained(descriptor, "Phase-A runtime source")
            require(digest == identity["sha256"] and stable.st_size == metadata.st_size, "runtime source hash drift")
            raw = os.pread(descriptor, stable.st_size, 0)
            require(len(raw) == stable.st_size, "short retained runtime source")
        finally:
            os.close(descriptor)
    finally:
        os.close(tools_fd)
    module = types.ModuleType("laguna_m8_gather_sharded_phase_a_runtime")
    module.__file__ = str(source)
    exec(compile(raw, str(source), "exec"), module.__dict__)
    return module


def _install_runtime_import_root(common: dict[str, Any]) -> str:
    """Enable only the hash-verified venv site-packages after `-I -S`."""
    record = common["runtime_identity"]["observed_identity"]["files"]["torch_init"]
    torch_init = Path(record["resolved_path"])
    require(torch_init.name == "__init__.py" and torch_init.parent.name == "torch", "Torch import root identity")
    site_packages = torch_init.parent.parent
    require(site_packages.name == "site-packages" and site_packages.is_dir() and
            sha256_file(torch_init, "Torch import root") == record["sha256"], "Torch import root drift")
    require(str(site_packages) not in sys.path, "Torch import root was enabled before authorization")
    sys.path.append(str(site_packages))
    return str(site_packages)


def _require_sealed_memfd(descriptor: int, expected_sha256: str, label: str) -> os.stat_result:
    require(descriptor >= 3 and _is_sha256(expected_sha256), f"invalid {label} descriptor")
    metadata = os.fstat(descriptor)
    require(stat.S_ISREG(metadata.st_mode), f"{label} is not regular")
    require(fcntl.fcntl(descriptor, F_GET_SEALS) & REQUIRED_SEALS == REQUIRED_SEALS, f"{label} is not sealed")
    digest, stable = _hash_retained(descriptor, label)
    require(digest == expected_sha256 and stable.st_ino == metadata.st_ino, f"{label} hash drift")
    return stable


def _proc_bytes(path: str, label: str, limit: int = 1024 * 1024) -> bytes:
    descriptor, metadata = _open_regular(Path(path), label)
    try:
        require(metadata.st_size <= limit, f"{label} exceeds limit")
        raw = os.pread(descriptor, limit + 1, 0)
        require(len(raw) <= limit, f"{label} exceeds limit")
        return raw
    finally:
        os.close(descriptor)


def _consume_capability(
    descriptor: int,
    packet_sha256: str,
    rank: int,
    root: Path,
    campaign_fd: int,
    card_fd: int,
    runner_source_fd: int,
    body: dict[str, Any],
    authorization: Path,
) -> dict[str, Any]:
    """Authenticate the live coordinator and its retained authorization FDs."""
    require(descriptor >= 3, "invalid inherited capability descriptor")
    sock = socket.socket(fileno=descriptor)
    try:
        require(sock.family == socket.AF_UNIX and sock.type & socket.SOCK_SEQPACKET == socket.SOCK_SEQPACKET and
                sock.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE) == socket.SOCK_SEQPACKET,
                "capability transport is not AF_UNIX SOCK_SEQPACKET")
        peer_pid, peer_uid, peer_gid = struct.unpack("3i", sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))
        parent_pid = os.getppid()
        require(peer_pid == parent_pid and peer_uid == os.getuid() and peer_gid == os.getgid(), "capability peer credentials")
        raw, ancillary, flags, _address = sock.recvmsg(65537, 0)
        require(not ancillary and not flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC) and 0 < len(raw) <= 65536,
                "capability message framing")
        require(sock.recv(1) == b"", "capability channel was not one-shot")
    finally:
        sock.close()
    value = json.loads(raw, object_pairs_hook=_strict_object)
    keys = {"format", "packet_sha256", "rank", "nonce", "one_shot", "root_dev", "root_inode", "campaign_dev", "campaign_inode", "peer_pid", "peer_uid", "peer_gid", "coordinator_source_fd", "coordinator_cmdline_sha256"}
    require(isinstance(value, dict) and raw == canonical_json(value) and set(value) == keys and
            value["format"] == "laguna-m8-gather-sharded-phase-a-capability-v2" and
            value["packet_sha256"] == packet_sha256 and value["rank"] == rank and
            isinstance(value["nonce"], str) and len(value["nonce"]) == 64 and value["one_shot"] is True and
            (value["peer_pid"], value["peer_uid"], value["peer_gid"]) == (peer_pid, peer_uid, peer_gid) and
            all(_is_int(value[key]) and value[key] > 0 for key in ("root_dev", "root_inode", "campaign_dev", "campaign_inode", "coordinator_source_fd")) and
            _is_sha256(value["coordinator_cmdline_sha256"]), "one-shot capability mismatch")
    require(os.getppid() == parent_pid, "coordinator exited during capability authentication")

    campaign_meta, card_meta = os.fstat(campaign_fd), os.fstat(card_fd)
    require(stat.S_ISDIR(campaign_meta.st_mode) and stat.S_ISDIR(card_meta.st_mode) and
            (campaign_meta.st_dev, campaign_meta.st_ino) == (value["campaign_dev"], value["campaign_inode"]) and
            (card_meta.st_dev, card_meta.st_ino) == (value["root_dev"], value["root_inode"]), "retained output FD provenance")
    require(Path(os.readlink(f"/proc/self/fd/{campaign_fd}")).resolve(strict=True) == root.parent.resolve(strict=True) and
            Path(os.readlink(f"/proc/self/fd/{card_fd}")).resolve(strict=True) == root.resolve(strict=True), "retained output path binding")
    _require_sealed_memfd(runner_source_fd, body["runner"]["sha256"], "runner source")
    require(Path(__file__).as_posix() == f"/proc/self/fd/{runner_source_fd}", "runner was not executed from its sealed source")

    coordinator_fd_path = f"/proc/{parent_pid}/fd/{value['coordinator_source_fd']}"
    coordinator_fd = os.open(coordinator_fd_path, os.O_RDONLY | os.O_CLOEXEC)
    try:
        _require_sealed_memfd(coordinator_fd, body["coordinator"]["sha256"], "coordinator source")
    finally:
        os.close(coordinator_fd)
    cmdline = _proc_bytes(f"/proc/{parent_pid}/cmdline", "coordinator cmdline")
    require(sha_bytes(cmdline) == value["coordinator_cmdline_sha256"], "coordinator cmdline hash")
    argv = [item.decode("utf-8", errors="strict") for item in cmdline.rstrip(b"\0").split(b"\0")]
    expected_python = body["common"]["runtime_identity"]["observed_identity"]["python_executable"]
    expected = [expected_python, "-I", "-S", f"/proc/self/fd/{value['coordinator_source_fd']}", "--sealed-self-fd", str(value["coordinator_source_fd"]), "--authorization-json", str(authorization), "--expected-authorization-sha256", packet_sha256]
    require(argv == expected, "coordinator invocation identity")
    parent_exe = Path(f"/proc/{parent_pid}/exe").resolve(strict=True)
    python_record = body["common"]["runtime_identity"]["observed_identity"]["files"]["python"]
    require(parent_exe == Path(python_record["resolved_path"]) and sha256_file(parent_exe, "coordinator Python") == python_record["sha256"], "coordinator Python identity")
    return value


def _seal_card_root(root: Path) -> None:
    require(root.is_absolute() and root.is_dir() and not root.is_symlink(),
            "card output root must be coordinator-created")
    assert_live_internal_nvme(root, "card output root")
    descriptor, _ = _open_dir(root, "new card output root")
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _prepare_runtime_directories(root: Path, environment: dict[str, str]) -> list[str]:
    """Create every cache/home/temp destination before the first Torch import."""
    path_keys = ("HOME", "HF_HOME", "NUMBA_CACHE_DIR", "PYTHONPYCACHEPREFIX", "SYCL_CACHE_DIR",
                 "TORCHINDUCTOR_CACHE_DIR", "TRANSFORMERS_CACHE", "TRITON_CACHE_DIR", "VLLM_CACHE_ROOT",
                 "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "TEMP", "TMP", "TMPDIR")
    root_fd, _ = _open_dir(root, "new card root")
    created: list[str] = []
    declared: set[Path] = set()
    try:
        for key in path_keys:
            path = Path(environment[key])
            require(path.is_absolute() and path.is_relative_to(root) and not path.is_symlink(),
                    f"runtime environment path escapes fresh card root: {key}")
            relative = path.relative_to(root)
            current_fd = os.dup(root_fd)
            try:
                prefix: list[str] = []
                for part in relative.parts:
                    prefix.append(part)
                    try:
                        os.mkdir(part, 0o700, dir_fd=current_fd)
                    except FileExistsError:
                        require(relative in declared or part != relative.parts[-1],
                                f"pre-existing runtime environment leaf: {key}")
                    next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                                      dir_fd=current_fd)
                    os.close(current_fd)
                    current_fd = next_fd
                    created.append(str(Path(*prefix)))
                metadata = os.fstat(current_fd)
                require(stat.S_ISDIR(metadata.st_mode), f"runtime environment path is not a directory: {key}")
            finally:
                os.close(current_fd)
            declared.add(relative)
        os.fsync(root_fd)
    finally:
        os.close(root_fd)
    return sorted(set(created))


def _card_environment(card: dict[str, Any]) -> None:
    expected = card["environment"]
    require(isinstance(expected, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in expected.items()),
            "packet environment schema")
    require(expected == expected_environment(card["rank"], Path(card["output_root"])), "packet exact environment")
    # The coordinator uses env -i/Popen(env=...), so a nonidentical map means a
    # selector, graph, cache, or source path changed after packet authorization.
    require(dict(os.environ) == expected, "runtime environment is not the exact packet environment")
    required = {
        "VLLM_XPU_LAGUNA_M8_GATHER_SHARDED": "1", "VLLM_XPU_LAGUNA_M8_GATHER_FINALIZE": "0",
        "VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE": "1", "VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2": "1",
        "VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE": "1", "VLLM_XPU_LAGUNA_M8_W1_N_TILE": "64",
        "VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE": "1", "VLLM_XPU_LAGUNA_M8_QKNORM_ROPE": "1",
        "VLLM_XPU_EXACT_SPEC_ATTN": "1", "VLLM_XPU_LAGUNA_M8_REMOTE_ZERO": "0",
        "VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION": "0", "VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM": "0",
        "VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK": "0", "VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM": "0",
        "VLLM_XPU_LAGUNA_M8_SHARED_GATE_MM": "0", "VLLM_XPU_LAGUNA_M8_SHARED_GATE_UP_MM": "0",
        "VLLM_XPU_LAGUNA_M8_SHARED_EXPERT_STREAM": "0", "VLLM_XPU_ENABLE_XPU_GRAPH": "0",
        "VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH": "0", "VLLM_XPU_FORCE_GRAPH_WITH_COMM": "0",
        "VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE": "0", "XPU_GRAPH": "0", "VLLM_USE_AOT_COMPILE": "0",
        "TP": "4", "EP": "4", "DP": "1", "PP": "1", "ACTIVE_REQUESTS": "1",
        "LAGUNA_DFLASH_NUM_SPECULATIVE_TOKENS": "7",
        "LD_PRELOAD": "", "LD_LIBRARY_PATH": "", "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1", "PYTHONSAFEPATH": "1",
    }
    require(all(expected.get(key) == value for key, value in required.items()), "candidate frozen environment drift")


def _validate_classification(value: object) -> None:
    keys = {"positive_zero", "negative_zero", "subnormal", "finite_normal", "infinity", "nan", "nan_payloads_sha256"}
    require(isinstance(value, dict) and set(value) == keys and _is_sha256(value["nan_payloads_sha256"]) and
            all(_is_int(value[key]) and value[key] >= 0 for key in keys - {"nan_payloads_sha256"}) and
            sum(value[key] for key in keys - {"nan_payloads_sha256"}) == 8 * 3072, "BF16 classification")


def _validate_comparison(value: object) -> None:
    keys = {"left_raw_bf16_le_sha256", "right_raw_bf16_le_sha256", "raw_uint16_equal", "left_classification",
            "right_classification", "torch_equal", "nan_policy", "passed"}
    require(isinstance(value, dict) and set(value) == keys and _is_sha256(value["left_raw_bf16_le_sha256"]) and
            _is_sha256(value["right_raw_bf16_le_sha256"]) and value["raw_uint16_equal"] is True and value["passed"] is True and
            value["left_raw_bf16_le_sha256"] == value["right_raw_bf16_le_sha256"], "raw BF16 comparison")
    _validate_classification(value["left_classification"])
    _validate_classification(value["right_classification"])
    require(value["left_classification"] == value["right_classification"], "BF16 classification equality")
    if value["left_classification"]["nan"]:
        require(value["torch_equal"] is None and value["nan_policy"] == "raw_bits_and_classification", "NaN equality policy")
    else:
        require(value["torch_equal"] is True and value["nan_policy"] == "torch_equal_and_raw_bits", "finite equality policy")


def validate_card_result(value: object, packet: dict[str, Any], rank: int) -> dict[str, Any]:
    """Independent Phase-B-safe validation of a complete card result."""
    require(isinstance(value, dict) and value.get("format") == CARD_RESULT_FORMAT, "card result format")
    common = packet["body"]["common"]
    required = {"format", "status", "passed", "rank", "physical", "authorization", "runtime_binding", "native_modules",
                "retained_fixture_before", "retained_fixture_after", "runtime_directories", "pre_epochs", "post_epochs", "timing", "terminal"}
    require(set(value) == required and value["status"] == "component_timing_pass_pending_mandatory_counters" and
            value["passed"] is True and value["rank"] == rank and value["physical"] == common["cards"][rank], "card result identity")
    require(value["authorization"] == {"path": packet["packet_path"], "sha256": sha_bytes(canonical_json(packet))}, "card authorization binding")
    runtime_binding = value["runtime_binding"]
    expected_raw_uuid = uuid.UUID(common["cards"][rank]["xpu_smi_uuid"]).bytes[::-1].hex()
    require(isinstance(runtime_binding, dict) and set(runtime_binding) == {"physical_rank", "bdf", "drm_card", "vendor", "device", "torch_version", "device_name", "oneapi_device_selector", "ze_affinity_mask", "logical_probe", "torch_uuid_bytes_hex", "xpu_smi_uuid", "uuid_mapping"} and runtime_binding.get("physical_rank") == rank and
            runtime_binding.get("bdf") == common["cards"][rank]["bdf"] and
            runtime_binding.get("drm_card") == common["cards"][rank]["drm_card"] and
            runtime_binding.get("vendor") == "0x8086" and runtime_binding.get("device") == "0xe223" and
            runtime_binding.get("torch_version") == "2.12.0+xpu" and
            runtime_binding.get("device_name") == "Intel(R) Arc(TM) Pro B70 Graphics" and
            runtime_binding.get("oneapi_device_selector") == "level_zero:0" and
            runtime_binding.get("ze_affinity_mask") == str(rank) and runtime_binding.get("logical_probe") == "xpu:0" and
            runtime_binding.get("torch_uuid_bytes_hex") == expected_raw_uuid and
            runtime_binding.get("xpu_smi_uuid") == common["cards"][rank]["xpu_smi_uuid"] and
            runtime_binding.get("uuid_mapping") == "xpu_smi_uuid_is_reverse_of_torch_level_zero_bytes", "runtime card binding")
    native = value["native_modules"]
    require(isinstance(native, dict) and set(native) == set(LIBRARIES) and
            all(isinstance(entry, dict) and set(entry) == {"sha256", "bytes", "dev", "inode", "loaded_via", "rtld_global", "mapping_verified"} and
                entry.get("sha256") == common["native_bundle"]["libraries"][name]["sha256"] and
                entry.get("bytes") == common["native_bundle"]["libraries"][name]["bytes"] and
                _is_int(entry.get("dev")) and entry["dev"] > 0 and _is_int(entry.get("inode")) and entry["inode"] > 0 and
                isinstance(entry.get("loaded_via"), str) and re.fullmatch(r"/proc/self/fd/[0-9]+", entry["loaded_via"]) and
                isinstance(entry.get("rtld_global"), bool) and entry.get("rtld_global") == (name in {"libgdn_attn_kernels_xe_2.so", "libgrouped_gemm_xe_2.so", "libgrouped_gemm_xe_default.so", "libmhc_kernels_xe_2.so", "libmqa_logits_kernels_xe_2.so"}) and
                entry.get("mapping_verified") is True for name, entry in native.items()),
            "sealed native module inventory")
    require(isinstance(value["retained_fixture_before"], dict) and
            value["retained_fixture_before"] == value["retained_fixture_after"] and
            set(value["retained_fixture_before"]) == {f"library:{name}" for name in LIBRARIES} | set(FIXTURE_RECORDS) | {"canonical_route_map"},
            "retained descriptor closure")
    retained_rows = value["retained_fixture_before"]
    for name in LIBRARIES:
        row, record = retained_rows[f"library:{name}"], common["native_bundle"]["libraries"][name]
        require(isinstance(row, dict) and set(row) == {"sha256", "dev", "inode", "bytes"} and
                row["sha256"] == record["sha256"] and row["bytes"] == record["bytes"] and
                _is_int(row["dev"]) and row["dev"] > 0 and _is_int(row["inode"]) and row["inode"] > 0,
                f"retained library binding: {name}")
    for name in FIXTURE_RECORDS:
        row, record = retained_rows[name], common["fixture"]["records"][name]
        width = {"<u2": 2, "<u4": 4}[record["dtype"]]
        expected_bytes = width
        for dimension in record["shape"]:
            expected_bytes *= dimension
        require(isinstance(row, dict) and set(row) == {"sha256", "dev", "inode", "bytes"} and
                row["sha256"] == record["sha256"] and row["bytes"] == expected_bytes and
                _is_int(row["dev"]) and row["dev"] > 0 and _is_int(row["inode"]) and row["inode"] > 0,
                f"retained fixture binding: {name}")
    route_row = retained_rows["canonical_route_map"]
    require(isinstance(route_row, dict) and set(route_row) == {"sha256", "dev", "inode", "bytes"} and
            route_row["sha256"] == common["fixture"]["canonical_route_map"]["sha256"] and route_row["bytes"] == 320 and
            _is_int(route_row["dev"]) and route_row["dev"] > 0 and _is_int(route_row["inode"]) and route_row["inode"] > 0,
            "retained route-map binding")
    expected_dirs: set[str] = set()
    root = Path(packet["body"]["cards"][rank]["output_root"])
    for path in expected_environment(rank, root).values():
        candidate = Path(path)
        if candidate.is_absolute() and candidate.is_relative_to(root):
            relative = candidate.relative_to(root)
            for offset in range(1, len(relative.parts) + 1):
                expected_dirs.add(str(Path(*relative.parts[:offset])))
    require(value["runtime_directories"] == sorted(expected_dirs), "runtime directory closure")
    for field, rows, start, count in (("pre_epochs", value["pre_epochs"], 0, PRE_EPOCHS),
                                      ("post_epochs", value["post_epochs"], PRE_EPOCHS, POST_EPOCHS)):
        require(isinstance(rows, list) and len(rows) == count, f"{field} count")
        for offset, row in enumerate(rows):
            require(isinstance(row, dict) and set(row) == {"epoch", "input_before", "input_after", "outputs", "raw_bf16_classification", "comparisons", "passed"} and
                    row.get("epoch") == start + offset and row.get("passed") is True and
                    row.get("input_before") == row.get("input_after") and isinstance(row.get("comparisons"), dict) and
                    set(row["comparisons"]) == {"gather", "candidate_repeat", "scale_add", "rank_order_bf16_sum", "fused_add_rms_norm_hidden", "fused_add_rms_norm_residual"} and
                    isinstance(row.get("outputs"), dict) and set(row["outputs"]) == {"control_gather", "candidate_gather", "candidate_repeat", "scale_add", "rank_order_bf16_sum", "fused_add_rms_norm_hidden", "fused_add_rms_norm_residual", "candidate_scale_add", "candidate_rank_order_bf16_sum", "candidate_fused_add_rms_norm_hidden", "candidate_fused_add_rms_norm_residual"} and
                    isinstance(row.get("raw_bf16_classification"), dict) and
                    all(isinstance(item, dict) and item.get("passed") is True for item in row["comparisons"].values()), f"{field} exactness")
            expected_inputs = {name: common["fixture"]["records"][name]["per_epoch_sha256"][start + offset]
                               for name in FIXTURE_RECORDS}
            expected_inputs["canonical_route_map"] = common["fixture"]["canonical_route_map"]["sha256"]
            require(row["input_before"] == expected_inputs and all(_is_sha256(item) for item in row["outputs"].values()),
                    f"{field} fixture hash binding")
            _validate_classification(row["raw_bf16_classification"])
            for comparison in row["comparisons"].values():
                _validate_comparison(comparison)
            links = {"gather": ("control_gather", "candidate_gather"), "candidate_repeat": ("candidate_gather", "candidate_repeat"), "scale_add": ("scale_add", "candidate_scale_add"), "rank_order_bf16_sum": ("rank_order_bf16_sum", "candidate_rank_order_bf16_sum"), "fused_add_rms_norm_hidden": ("fused_add_rms_norm_hidden", "candidate_fused_add_rms_norm_hidden"), "fused_add_rms_norm_residual": ("fused_add_rms_norm_residual", "candidate_fused_add_rms_norm_residual")}
            for name, (left, right) in links.items():
                comparison = row["comparisons"][name]
                require(comparison["left_raw_bf16_le_sha256"] == row["outputs"][left] and comparison["right_raw_bf16_le_sha256"] == row["outputs"][right], f"{field} output/comparison linkage")
            require(row["raw_bf16_classification"] == row["comparisons"]["gather"]["left_classification"], f"{field} raw classification linkage")
    timing = value["timing"]
    timing_keys = {"clock", "warm_cycles_per_arm", "blocks", "arm_order", "cycles_per_arm", "layers_per_cycle", "rotation", "cpu_work_inside_event_interval", "selected_gather_launches_per_cycle", "control_geometry", "candidate_geometry", "blocks_detail", "candidate_block_wins", "median_saving_ms_per_cycle", "passed"}
    require(isinstance(timing, dict) and set(timing) == timing_keys and timing.get("passed") is True and timing.get("candidate_block_wins", -1) >= 28 and
            isinstance(timing.get("median_saving_ms_per_cycle"), (int, float)) and math.isfinite(float(timing["median_saving_ms_per_cycle"])) and timing["median_saving_ms_per_cycle"] >= 0.08 and
            timing.get("clock") == "torch.xpu.Event device elapsed time" and timing.get("warm_cycles_per_arm") == 20 and
            timing.get("cpu_work_inside_event_interval") is False and
            timing.get("control_geometry") == {"workgroups": 8, "simd32_subgroups": 64} and
            timing.get("candidate_geometry") == {"workgroups": 48, "simd32_subgroups": 96} and
            timing.get("blocks") == 31 and timing.get("cycles_per_arm") == 64 and timing.get("layers_per_cycle") == 47 and
            timing.get("arm_order") == "A-B-B-A" and timing.get("rotation") == "(block*47)%256" and
            timing.get("selected_gather_launches_per_cycle") == {"control": 47, "candidate": 47} and
            len(timing.get("blocks_detail", [])) == 31, "timing threshold/protocol")
    savings: list[float] = []
    for expected_index, block in enumerate(timing["blocks_detail"]):
        index = block.get("block")
        block_keys = {"block", "fixture_indices", "A1_control_elapsed_ns", "B1_candidate_elapsed_ns", "B2_candidate_elapsed_ns", "A2_control_elapsed_ns", "paired_control_ms_per_47_layer_cycle", "paired_candidate_ms_per_47_layer_cycle", "saving_ms_per_47_layer_cycle", "selected_gather_launches", "post_block_raw_exactness"}
        require(isinstance(block, dict) and set(block) == block_keys and index == expected_index and
                block.get("fixture_indices") == [(index * 47 + slot) % 256 for slot in range(47)] and
                block.get("selected_gather_launches") == {"control": 47, "candidate": 47} and
                all(isinstance(block.get(key), int) and block[key] > 0 for key in
                    ("A1_control_elapsed_ns", "B1_candidate_elapsed_ns", "B2_candidate_elapsed_ns", "A2_control_elapsed_ns")) and
                isinstance(block.get("post_block_raw_exactness"), list) and len(block["post_block_raw_exactness"]) == 47 and
                all(isinstance(item, dict) and item.get("passed") is True for item in block["post_block_raw_exactness"]),
                "timed block evidence")
        control = (block["A1_control_elapsed_ns"] + block["A2_control_elapsed_ns"]) / (2 * 64) / 1_000_000
        candidate = (block["B1_candidate_elapsed_ns"] + block["B2_candidate_elapsed_ns"]) / (2 * 64) / 1_000_000
        require(isinstance(block.get("paired_control_ms_per_47_layer_cycle"), (int, float)) and
                isinstance(block.get("paired_candidate_ms_per_47_layer_cycle"), (int, float)) and
                isinstance(block.get("saving_ms_per_47_layer_cycle"), (int, float)) and
                all(math.isfinite(float(block[key])) for key in ("paired_control_ms_per_47_layer_cycle", "paired_candidate_ms_per_47_layer_cycle", "saving_ms_per_47_layer_cycle")) and
                block["paired_control_ms_per_47_layer_cycle"] == control and
                block["paired_candidate_ms_per_47_layer_cycle"] == candidate and
                block["saving_ms_per_47_layer_cycle"] == control - candidate, "timing arithmetic")
        savings.append(control - candidate)
        for comparison in block["post_block_raw_exactness"]:
            _validate_comparison(comparison)
    require(timing["candidate_block_wins"] == sum(item > 0.0 for item in savings) and
            timing["median_saving_ms_per_cycle"] == statistics.median(savings), "timing aggregate recomputation")
    require(value["terminal"] == {"status": "component_timing_pass_pending_mandatory_counters", "passed": True,
                                  "endpoint_authorized": False, "phase_b_required": True}, "card terminal")
    return value


def run_card(authorization: Path, expected_sha256: str, rank: int, capability_fd: int,
             campaign_fd: int, card_fd: int, runner_source_fd: int, packet_fd: int) -> int:
    packet, raw = read_canonical_json_fd(packet_fd, "Phase-A authorization")
    require(sha_bytes(raw) == expected_sha256, "authorization SHA-256")
    visible_fd, visible_meta = _open_regular(authorization, "visible Phase-A authorization")
    try:
        retained_meta = os.fstat(packet_fd)
        require((visible_meta.st_dev, visible_meta.st_ino) == (retained_meta.st_dev, retained_meta.st_ino),
                "authorization path/FD identity")
    finally:
        os.close(visible_fd)
    validate_phase_a_packet(packet, authorization, verify_artifacts=True)
    verify_mutual_packets(packet)
    require(0 <= rank < 4, "rank")
    body, card = packet["body"], packet["body"]["cards"][rank]
    expected_python = Path(body["common"]["runtime_identity"]["observed_identity"]["python_executable"])
    require(expected_python.is_file() and Path(sys.executable).samefile(expected_python), "runner Python identity drift")
    _card_environment(card)
    root = Path(card["output_root"])
    capability = _consume_capability(capability_fd, expected_sha256, rank, root, campaign_fd, card_fd,
                                     runner_source_fd, body, authorization)
    _seal_card_root(root)
    runtime_directories = _prepare_runtime_directories(root, card["environment"])
    evidence_fd = os.open("evidence", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                          dir_fd=card_fd)
    retained: dict[str, Any] | None = None
    result: dict[str, Any] = {"format": CARD_RESULT_FORMAT, "status": "component_failed", "passed": False,
                              "rank": rank, "physical": packet["body"]["common"]["cards"][rank],
                              "authorization": {"path": str(authorization), "sha256": expected_sha256},
                              "runtime_binding": None, "native_modules": None, "retained_fixture_before": None,
                              "retained_fixture_after": None, "runtime_directories": runtime_directories, "pre_epochs": [], "post_epochs": [], "timing": None,
                              "terminal": {"status": "component_failed", "passed": False, "endpoint_authorized": False, "phase_b_required": True}}
    try:
        retained = _retain_runtime_inputs(body["common"])
        _write_exclusive_at(evidence_fd, "runtime-preimport-seal.json", {"format": PREIMPORT_FORMAT, "packet_sha256": expected_sha256,
            "rank": rank, "capability_nonce_sha256": sha_bytes(capability["nonce"].encode()), "torch_or_native_imported": False,
            "retained_bundle_libraries": sorted(retained["library_fds"]), "retained_fixture_records": sorted(retained["fds"]),
            "runtime_directories": runtime_directories})
        _install_runtime_import_root(body["common"])
        # Execute retained, packet-hashed bytes after the durable marker; a
        # normal import would re-open a mutable pathname after validation.
        runtime = _load_runtime_from_retained_source(body)
        campaign = runtime.run_phase_a_campaign({"common": body["common"], "retained": retained, "rank": rank})
        result.update(campaign, status="component_timing_pass_pending_mandatory_counters", passed=True,
                      terminal={"status": "component_timing_pass_pending_mandatory_counters", "passed": True,
                                "endpoint_authorized": False, "phase_b_required": True})
    except BaseException as error:
        result["failure"] = {"type": type(error).__name__, "message": str(error)}
    try:
        # Descriptors remain live until the terminal output itself is fsynced;
        # no path is re-opened to produce the result after native work begins.
        _write_exclusive_at(evidence_fd, "component-result.json", result)
        inventory = set(os.listdir(evidence_fd))
        require("component-result.json" in inventory and inventory <= {"runtime-preimport-seal.json", "component-result.json"},
                "card evidence inventory")
        os.fchmod(evidence_fd, 0o555)
        os.fsync(evidence_fd)
    finally:
        if retained is not None:
            _close_retained(retained)
        os.close(evidence_fd)
    return 0 if result["passed"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one inherited-capability Phase-A card")
    parser.add_argument("--authorization-json", type=Path, required=True)
    parser.add_argument("--expected-authorization-sha256", required=True)
    parser.add_argument("--rank", type=int, required=True)
    parser.add_argument("--capability-fd", type=int, required=True)
    parser.add_argument("--campaign-fd", type=int, required=True)
    parser.add_argument("--card-fd", type=int, required=True)
    parser.add_argument("--runner-source-fd", type=int, required=True)
    parser.add_argument("--packet-fd", type=int, required=True)
    args = parser.parse_args()
    return run_card(args.authorization_json, args.expected_authorization_sha256, args.rank, args.capability_fd,
                    args.campaign_fd, args.card_fd, args.runner_source_fd, args.packet_fd)


if __name__ == "__main__":
    raise SystemExit(main())
