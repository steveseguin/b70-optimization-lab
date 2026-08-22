#!/usr/bin/env python3
"""Fail-closed eager W4A16 qualifier for Qwen3.8 ``mtp.fc`` TP shards.

The module is intentionally CPU-importable.  Only the ``run`` subcommand
imports torch, safetensors, or the XPU extension.  A passing isolated result
authorizes a separately reviewed integration experiment; it does not authorize
an endpoint benchmark, deployment, or submission.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import ctypes
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import random
import re
import socket
import statistics
import struct
import sys
import time
from typing import Any, Callable, Iterable, Iterator


SCHEMA_CACHE = "qwen38-mtp-fc-int4-cache-snapshot-v1"
SCHEMA_PREFLIGHT = "qwen38-mtp-fc-int4-preflight-v1"
SCHEMA_RUN = "qwen38-mtp-fc-int4-operator-run-v1"
SCHEMA_INVALID = "qwen38-mtp-fc-int4-operator-invalid-v1"
SCHEMA_COMPARE = "qwen38-mtp-fc-int4-operator-compare-v1"

# Q1 authorization (2026-08-22): every drafted prerequisite is satisfied and
# frozen — the authorized host-wide xe recovery completed with its full gate,
# the fresh-root GPU3 stock-health r2 published a supervisor-validated
# immutable pass terminal on the same boot, and the launch driver now carries
# the bounded per-arm process-group watchdog, live GPU2 BDF/UUID binding, and
# enclosing campaign terminal. Authorized by the tracked Q1 preregistration
# note committed together with this edit.  There is intentionally no
# environment or command-line override.
CAMPAIGN_LAUNCH_AUTHORIZED = True
AUTHORIZED_HEALTH_TERMINAL_PATH: str | None = (
    "/home/steve/qwen38-gpu3-incumbent-control-health-20260821-r2/terminal.json"
)
AUTHORIZED_HEALTH_TERMINAL_SHA256: str | None = (
    "7c04155e969dbbc97b00268fe7bcbefda0b232feabdd47db817d26aa5a631ae2"
)

MODEL_FILE = Path(
    "/mnt/usb-models/llm-models/qwen3.8-27b-int4-autoround-devan/"
    "model_extra_tensors.safetensors"
)
MODEL_SHA256 = "94102b67c6b84e65dbb9bae37c00bd88ac1a43ff577ce65fd8842d231c7e89de"
TENSOR_NAME = "mtp.fc.weight"
TENSOR_DTYPE = "BF16"
FULL_SHAPE = (5120, 10240)
TP_SIZE = 2
SHARD_SHAPE = (2560, 10240)
GROUP_SIZE = 128
PACK_FACTOR = 8
QWEIGHT_SHAPE = (1280, 2560)
QWEIGHT_STRIDE = (1, 1280)
SCALE_SHAPE = (80, 2560)

EXTENSION_FILE = Path(
    "/home/steve/staged-xpu-commitfix-graphfa-composite-20260820/"
    "vllm_xpu_kernels/_xpu_C.abi3.so"
)
EXTENSION_SHA256 = "4dd336013d155aab004fb1c916118957cb9349b491938da65769f2d8af18ffb0"
EXPECTED_DEVICE_NAME = "Intel(R) Arc(TM) Pro B70 Graphics"
EXPECTED_GPU2_UUID = "868023e2-0000-0000-4300-000000000000"
EXPECTED_GPU2_BDF_CONTEXT = "0000:43:00.0"
EXPECTED_PYTHON_VERSION_PREFIX = "3.12.13 "
EXPECTED_TORCH_VERSION = "2.11.0+xpu"
STAGE_GRAPH_MANIFEST = Path(
    "/home/steve/llm-optimizations/repro/qwen38-27b-autoround-int4-b70/"
    "manifests/staged-xpu-commitfix-graphfa-composite-20260820.graph.sha256"
)
STAGE_GRAPH_MANIFEST_SHA256 = (
    "47861e8391b6b25dd9c3eb25e25c5939753aa470858b667d5bdf181344db18da"
)
COMPLETION_ENV = "VLLM_XPU_ONEDNN_INT4_COMPLETION_BARRIER"
INPUT_MARKER = "VLLM_XPU_ONEDNN_INT4_INPUT_DEPENDENCY reached"
COMPLETION_MARKER = "VLLM_XPU_ONEDNN_INT4_COMPLETION_BARRIER reached"
DETPAD_MARKER = "VLLM_XPU_ONEDNN_INT4_DETERMINISM_PAD"
INPUT_MARKER_SOURCE_LINE = 200
COMPLETION_MARKER_SOURCE_LINE = 213

ROWS = (1, 6)
KERNEL_ATOL = 2.0e-2
KERNEL_RTOL = 1.0e-2
MIN_STABILITY_REPLAYS = 32
MIN_SAMPLES = 40
MIN_LAUNCHES_PER_SAMPLE = 100
WARMUP_LAUNCHES = 20
MIN_M6_SAVING_US = 17.092
BOOTSTRAP_ITERATIONS = 10_000

HEALTH_SUPERVISOR = Path(
    "/home/steve/llm-optimizations/experiments/qwen38-27b-b70/scripts/"
    "qwen38_gpu3_incumbent_control_health_supervisor.py"
)
HEALTH_SUPERVISOR_SHA256 = (
    "eb619535786a3c7a8929b2d3b1c3848486d3edc1b96804c79831eaf8c3923375"
)
HEALTH_GPU_UUID = "868023e2-0000-0000-4700-000000000000"

FULL_TENSOR_SHA256 = "4eee377b67ec2122cf214dbe6946d16261873441f1851d64409d9c7566bb20cc"
SHARD_DIGESTS = {
    0: {
        "bf16": "1757625239f6436af83d61a2353b4f406ae1eef22ac1828b03d6cbbe2913d5ed",
        "fp16": "6cea656bf5e4d0683dff2a1e65b9c822d62fdb63d8510439afb9cf26d00ccc4b",
        "packed_storage": (
            "da795b5a921bd14f0d3ae814dab268199ccb88aa16bf1aa69ec27b51a7dfda79"
        ),
        "qweight_logical": (
            "adef7804c30b41794ba89e6fbcec88d14020db5760b4020e8d313a71160fab7a"
        ),
        "scales": ("c71498b300127c358d59166fb3380ad58871c700c7c077f81ebd6ff32359cb3b"),
    },
    1: {
        "bf16": "31ee2a7fc864ce05e3263257df7a7a11a0326b90c49c0868807324bce48241ed",
        "fp16": "7237258ded520195d2e22c4d7a2a6d4c8e0a54158d1bb992d4c9d0701c48395b",
        "packed_storage": (
            "8eda2db1e4aef2d5e0d711730973b23199a0f27daff7160f43c0c140cda9b03b"
        ),
        "qweight_logical": (
            "79b7f43a70342916d21229a474844fc4ba4eaeafad08247e45c70f6d1ae013f8"
        ),
        "scales": ("42594dc0dac733bc2e6044f7cc4b09090087eb82e08e811c5fcea11df9c48986"),
    },
}
QZERO_SHA256 = "beead77994cf573341ec17b58bbf7eb34d2711c993c1d976b128b3188dc1829a"


class ContractError(RuntimeError):
    """A fail-closed qualification-contract violation."""


def _require_campaign_launch_authorized(command: str) -> None:
    if CAMPAIGN_LAUNCH_AUTHORIZED is not True:
        raise ContractError(
            f"{command} is blocked in this frozen source; a future tracked "
            "preregistration must authorize and refreeze the campaign"
        )
    if (
        AUTHORIZED_HEALTH_TERMINAL_PATH is None
        or AUTHORIZED_HEALTH_TERMINAL_SHA256 is None
        or re.fullmatch(r"[0-9a-f]{64}", AUTHORIZED_HEALTH_TERMINAL_SHA256) is None
    ):
        raise ContractError("authorized source lacks a frozen health terminal binding")


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        raise ContractError(f"invalid JSON {path}: {error}") from error


def _canonical(path: Path, where: str) -> Path:
    if not path.is_absolute():
        raise ContractError(f"{where} must be absolute: {path}")
    resolved = path.resolve(strict=True)
    if resolved != path:
        raise ContractError(f"{where} must be canonical: {path} -> {resolved}")
    return resolved


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _require_sha(value: Any, where: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ContractError(f"{where} must be a lowercase SHA-256")
    return value


def _require_int(value: Any, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractError(f"{where} must be an integer")
    return value


def _require_finite(value: Any, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError(f"{where} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ContractError(f"{where} must be finite")
    return result


def _exact_keys(value: Any, keys: Iterable[str], where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError(f"{where} must be an object")
    expected = set(keys)
    actual = set(value)
    if actual != expected:
        raise ContractError(
            f"{where} keys differ: missing={sorted(expected - actual)} "
            f"extra={sorted(actual - expected)}"
        )
    return value


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, allow_nan=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def _write_json_exclusive(path: Path, payload: dict[str, Any]) -> None:
    temporary = Path(f"{path}.tmp")
    if path.exists() or temporary.exists():
        raise ContractError(f"refusing existing output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(payload, allow_nan=False, indent=2, sort_keys=True).encode("utf-8")
        + b"\n"
    )
    descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o444)
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _safetensors_header(path: Path) -> dict[str, Any]:
    """Read only the safetensors header; importing torch is not required."""
    try:
        with path.open("rb") as stream:
            length_bytes = stream.read(8)
            if len(length_bytes) != 8:
                raise ContractError(f"short safetensors header: {path}")
            header_length = struct.unpack("<Q", length_bytes)[0]
            if header_length <= 0 or header_length > 64 * 1024 * 1024:
                raise ContractError(f"implausible safetensors header length: {path}")
            header_bytes = stream.read(header_length)
            if len(header_bytes) != header_length:
                raise ContractError(f"short safetensors JSON header: {path}")
        header = json.loads(
            header_bytes,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        raise ContractError(f"invalid safetensors header {path}: {error}") from error
    if not isinstance(header, dict):
        raise ContractError(f"safetensors header must be an object: {path}")
    entry = header.get(TENSOR_NAME)
    if not isinstance(entry, dict):
        raise ContractError(f"missing {TENSOR_NAME} in {path}")
    if entry.get("dtype") != TENSOR_DTYPE or entry.get("shape") != list(FULL_SHAPE):
        raise ContractError(
            f"{TENSOR_NAME} identity mismatch: "
            f"dtype={entry.get('dtype')} shape={entry.get('shape')}"
        )
    offsets = entry.get("data_offsets")
    if (
        not isinstance(offsets, list)
        or len(offsets) != 2
        or any(isinstance(item, bool) or not isinstance(item, int) for item in offsets)
        or offsets[0] < 0
        or offsets[1] <= offsets[0]
    ):
        raise ContractError(f"malformed {TENSOR_NAME} offsets")
    expected_bytes = FULL_SHAPE[0] * FULL_SHAPE[1] * 2
    if offsets[1] - offsets[0] != expected_bytes:
        raise ContractError(f"{TENSOR_NAME} byte extent mismatch")
    return {
        "header_length": header_length,
        "tensor_name": TENSOR_NAME,
        "serialized_dtype": TENSOR_DTYPE,
        "full_shape": list(FULL_SHAPE),
        "data_offsets": offsets,
    }


def _inventory(root_paths: list[Path]) -> dict[str, Any]:
    canonical_roots: list[Path] = []
    for index, root in enumerate(root_paths):
        resolved = _canonical(root, f"cache root {index}")
        if not resolved.is_dir():
            raise ContractError(f"cache root is not a directory: {resolved}")
        if resolved in canonical_roots:
            raise ContractError(f"duplicate cache root: {resolved}")
        canonical_roots.append(resolved)
    if not canonical_roots:
        raise ContractError("at least one cache root is required")

    roots: list[dict[str, Any]] = []
    for root in canonical_roots:
        directories: list[str] = []
        files: list[dict[str, Any]] = []
        for current, dirnames, filenames in os.walk(root, followlinks=False):
            current_path = Path(current)
            dirnames.sort()
            filenames.sort()
            for dirname in dirnames:
                path = current_path / dirname
                if path.is_symlink():
                    raise ContractError(f"symlink in cache root: {path}")
                directories.append(str(path.relative_to(root)))
            for filename in filenames:
                path = current_path / filename
                if path.is_symlink() or not path.is_file():
                    raise ContractError(f"non-regular file in cache root: {path}")
                stat = path.stat()
                files.append(
                    {
                        "relative_path": str(path.relative_to(root)),
                        "size": stat.st_size,
                        "mtime_ns": stat.st_mtime_ns,
                        "sha256": _sha256_file(path),
                    }
                )
        root_payload = {
            "path": str(root),
            "directories": sorted(directories),
            "files": sorted(files, key=lambda item: item["relative_path"]),
        }
        roots.append(root_payload)
    inventory_sha = _sha256_bytes(_canonical_json_bytes(roots))
    return {"roots": roots, "inventory_sha256": inventory_sha}


def _validate_cache_packet(packet: Any, path: Path) -> dict[str, Any]:
    packet = _exact_keys(
        packet,
        ("schema", "created_time_ns", "roots", "inventory_sha256"),
        str(path),
    )
    if packet["schema"] != SCHEMA_CACHE:
        raise ContractError(f"{path}: cache schema mismatch")
    if _require_int(packet["created_time_ns"], f"{path}.created_time_ns") <= 0:
        raise ContractError(f"{path}: invalid creation time")
    if not isinstance(packet["roots"], list) or not packet["roots"]:
        raise ContractError(f"{path}: empty cache roots")
    seen_roots: set[str] = set()
    for index, root in enumerate(packet["roots"]):
        root = _exact_keys(root, ("path", "directories", "files"), f"root {index}")
        root_path = _canonical(Path(root["path"]), f"{path}.root[{index}]")
        if str(root_path) in seen_roots:
            raise ContractError(f"{path}: duplicate root")
        seen_roots.add(str(root_path))
        directories = root["directories"]
        if (
            not isinstance(directories, list)
            or directories != sorted(set(directories))
            or not all(isinstance(item, str) and item for item in directories)
        ):
            raise ContractError(f"{path}: malformed directory inventory")
        files = root["files"]
        if not isinstance(files, list):
            raise ContractError(f"{path}: malformed file inventory")
        relative_paths: list[str] = []
        for file_index, entry in enumerate(files):
            entry = _exact_keys(
                entry,
                ("relative_path", "size", "mtime_ns", "sha256"),
                f"{path}.root[{index}].file[{file_index}]",
            )
            relative = entry["relative_path"]
            if not isinstance(relative, str) or not relative:
                raise ContractError(f"{path}: malformed relative path")
            if Path(relative).is_absolute() or ".." in Path(relative).parts:
                raise ContractError(f"{path}: unsafe relative path {relative}")
            relative_paths.append(relative)
            if _require_int(entry["size"], f"{path}.size") < 0:
                raise ContractError(f"{path}: negative file size")
            if _require_int(entry["mtime_ns"], f"{path}.mtime_ns") < 0:
                raise ContractError(f"{path}: negative mtime")
            _require_sha(entry["sha256"], f"{path}.sha256")
        if relative_paths != sorted(set(relative_paths)):
            raise ContractError(f"{path}: file inventory is not sorted and unique")
    expected = _sha256_bytes(_canonical_json_bytes(packet["roots"]))
    if _require_sha(packet["inventory_sha256"], f"{path}.inventory") != expected:
        raise ContractError(f"{path}: cache inventory digest mismatch")
    return packet


def _current_inventory_from_packet(packet: dict[str, Any]) -> dict[str, Any]:
    return _inventory([Path(root["path"]) for root in packet["roots"]])


def cache_snapshot_command(args: argparse.Namespace) -> dict[str, Any]:
    output = Path(args.output)
    if not output.is_absolute():
        raise ContractError("cache snapshot output must be absolute")
    resolved_parent = output.parent.resolve(strict=True)
    prospective = resolved_parent / output.name
    roots = [_canonical(Path(item), "cache root") for item in args.root]
    for root in roots:
        if prospective == root or root in prospective.parents:
            raise ContractError("cache snapshot output must be outside cache roots")
    inventory = _inventory(roots)
    packet = {
        "schema": SCHEMA_CACHE,
        "created_time_ns": time.time_ns(),
        **inventory,
    }
    _validate_cache_packet(packet, prospective)
    _write_json_exclusive(prospective, packet)
    return packet


def _health_identity(
    path: Path, expected_sha: str, physical_gpu: int
) -> dict[str, Any]:
    if os.environ.get("PYTHONDONTWRITEBYTECODE") != "1":
        raise ContractError(
            "PYTHONDONTWRITEBYTECODE=1 is required before health-validator import"
        )
    if physical_gpu != 2:
        raise ContractError(
            "operator health binding is only defined for physical GPU 2"
        )
    path = _canonical(path, "health packet")
    if path.name != "terminal.json" or path.stat().st_mode & 0o222:
        raise ContractError("health terminal must be immutable terminal.json")
    actual_sha = _sha256_file(path)
    if actual_sha != _require_sha(expected_sha, "health packet SHA"):
        raise ContractError("health packet SHA mismatch")
    supervisor_identity = _file_identity(
        HEALTH_SUPERVISOR,
        HEALTH_SUPERVISOR_SHA256,
        "GPU3 health supervisor validator",
    )
    spec = importlib.util.spec_from_file_location(
        "qwen38_mtp_fc_health_validator", HEALTH_SUPERVISOR
    )
    if spec is None or spec.loader is None:
        raise ContractError("cannot load the pinned health supervisor validator")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        packet = module.validate_terminal(path.parent)
    except Exception as error:
        raise ContractError(f"health supervisor validation failed: {error}") from error
    if (
        not isinstance(packet, dict)
        or packet.get("schema") != "qwen38-gpu3-incumbent-control-health-terminal-v1"
        or packet.get("passed") is not True
        or packet.get("classification") != "gpu3-incumbent-control-health-pass"
    ):
        raise ContractError("health terminal is not a validated GPU3 pass")
    worker_success = packet.get("worker_success")
    if not isinstance(worker_success, dict):
        raise ContractError("health terminal lacks validated worker success")
    # The r2 terminal records worker_success as an immutable pointer
    # (path/sha256/phase_count); the device identity lives in the referenced
    # worker-result.json. Follow that pointer, verify its sha256, and confirm
    # it resides in this terminal's own health root before reading .device.
    worker_result_path = worker_success.get("path")
    worker_result_sha = worker_success.get("sha256")
    if not isinstance(worker_result_path, str) or not isinstance(
        worker_result_sha, str
    ):
        raise ContractError("health terminal worker success lacks path/sha256")
    worker_result = _canonical(Path(worker_result_path), "health worker result")
    if worker_result.parent != path.parent:
        raise ContractError("health worker result is outside the health root")
    if worker_result.name != "worker-result.json" or (
        worker_result.stat().st_mode & 0o222
    ):
        raise ContractError("health worker result must be immutable worker-result.json")
    if _sha256_file(worker_result) != _require_sha(
        worker_result_sha, "health worker result SHA"
    ):
        raise ContractError("health worker result SHA mismatch")
    device = load_json(worker_result).get("device")
    if (
        not isinstance(device, dict)
        or device.get("physical_gpu") != 3
        or device.get("logical_device") != "xpu:0"
        or device.get("name") != EXPECTED_DEVICE_NAME
        or device.get("uuid") != HEALTH_GPU_UUID
    ):
        raise ContractError("health terminal nested GPU3 identity mismatch")
    child_process = packet.get("child_process")
    supervisor_process = packet.get("supervisor_process")
    if not isinstance(child_process, dict) or not isinstance(supervisor_process, dict):
        raise ContractError("health terminal lacks process identity")
    child_boot_id = child_process.get("boot_id")
    supervisor_boot_id = supervisor_process.get("boot_id")
    try:
        current_boot_id = (
            Path("/proc/sys/kernel/random/boot_id").read_text(encoding="utf-8").strip()
        )
    except (OSError, UnicodeError) as error:
        raise ContractError(f"cannot read current boot identity: {error}") from error
    if (
        not isinstance(child_boot_id, str)
        or child_boot_id != supervisor_boot_id
        or child_boot_id != current_boot_id
    ):
        raise ContractError("GPU3 health pass is not from the current host boot")
    return {
        "path": str(path),
        "sha256": actual_sha,
        "schema": "qwen38-gpu3-incumbent-control-health-terminal-v1",
        "classification": "gpu3-incumbent-control-health-pass",
        "passed": True,
        "worker_device": device,
        "boot_id": child_boot_id,
        "supervisor_validator": supervisor_identity,
        "supervisor_validation_passed": True,
        "operator_physical_gpu": physical_gpu,
    }


def _file_identity(path: Path, expected_sha: str, where: str) -> dict[str, str]:
    path = _canonical(path, where)
    actual = _sha256_file(path)
    if actual != _require_sha(expected_sha, f"{where} SHA"):
        raise ContractError(f"{where} SHA mismatch")
    return {"path": str(path), "sha256": actual}


def _stage_graph_identity() -> dict[str, Any]:
    manifest = _canonical(STAGE_GRAPH_MANIFEST, "stage graph manifest")
    if _sha256_file(manifest) != STAGE_GRAPH_MANIFEST_SHA256:
        raise ContractError("stage graph manifest SHA mismatch")
    stage = _canonical(EXTENSION_FILE.parent.parent, "composite stage")
    package = stage / "vllm_xpu_kernels"
    if not package.is_dir() or package.is_symlink():
        raise ContractError("composite stage package is missing or symlinked")
    entries: dict[Path, str] = {}
    try:
        lines = manifest.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        raise ContractError(f"cannot read stage graph manifest: {error}") from error
    if not lines:
        raise ContractError("stage graph manifest is empty")
    for line_number, line in enumerate(lines, 1):
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match is None:
            raise ContractError(f"malformed stage graph manifest line {line_number}")
        relative = Path(match.group(2))
        if relative.is_absolute() or ".." in relative.parts:
            raise ContractError("unsafe stage graph manifest path")
        candidate = stage / relative
        if candidate in entries:
            raise ContractError("duplicate stage graph manifest path")
        if candidate.is_symlink() or not candidate.is_file():
            raise ContractError(f"stage graph entry is not a regular file: {candidate}")
        entries[candidate.resolve(strict=True)] = match.group(1)
    stage_files: set[Path] = set()
    for candidate in package.rglob("*"):
        if candidate.is_symlink():
            raise ContractError(f"symlink in composite stage: {candidate}")
        if candidate.is_file():
            stage_files.add(candidate.resolve(strict=True))
    if set(entries) != stage_files:
        raise ContractError("stage graph manifest inventory differs from stage")
    files: dict[str, str] = {}
    for candidate, expected_sha in sorted(
        entries.items(), key=lambda item: str(item[0])
    ):
        actual_sha = _sha256_file(candidate)
        if actual_sha != expected_sha:
            raise ContractError(f"stage graph file SHA mismatch: {candidate}")
        files[str(candidate.relative_to(stage))] = actual_sha
    return {
        "stage": str(stage),
        "manifest_path": str(manifest),
        "manifest_sha256": STAGE_GRAPH_MANIFEST_SHA256,
        "file_count": len(files),
        "files": files,
    }


def _preflight_payload(args: argparse.Namespace) -> dict[str, Any]:
    if os.environ.get("PYTHONDONTWRITEBYTECODE") != "1":
        raise ContractError("PYTHONDONTWRITEBYTECODE=1 is required")
    if args.physical_gpu != 2:
        raise ContractError(
            "this preregistered screen is limited to healthy physical GPU 2"
        )
    if Path(args.model_file) != MODEL_FILE or args.model_sha256 != MODEL_SHA256:
        raise ContractError("model path/SHA must match the pinned Qwen3.8 tensor file")
    if (
        Path(args.extension) != EXTENSION_FILE
        or args.extension_sha256 != EXTENSION_SHA256
    ):
        raise ContractError("extension path/SHA must match the deployed composite DSO")
    script = _file_identity(
        Path(__file__).resolve(strict=True), args.script_sha256, "qualifier"
    )
    driver = _file_identity(Path(args.driver), args.driver_sha256, "driver")
    if re.fullmatch(r"[0-9a-f]{40}", args.repo_head) is None:
        raise ContractError("repo HEAD must be a 40-character lowercase Git object")
    model = _file_identity(Path(args.model_file), args.model_sha256, "model file")
    model["tensor"] = _safetensors_header(Path(model["path"]))
    extension = _file_identity(Path(args.extension), args.extension_sha256, "extension")
    stage_graph = _stage_graph_identity()
    health = _health_identity(
        Path(args.health_packet), args.health_sha256, args.physical_gpu
    )
    cache_path = _canonical(Path(args.cache_snapshot), "cache snapshot")
    cache_sha = _sha256_file(cache_path)
    if cache_sha != _require_sha(args.cache_sha256, "cache snapshot SHA"):
        raise ContractError("cache snapshot SHA mismatch")
    cache_packet = _validate_cache_packet(load_json(cache_path), cache_path)
    current = _current_inventory_from_packet(cache_packet)
    if current != {
        "roots": cache_packet["roots"],
        "inventory_sha256": cache_packet["inventory_sha256"],
    }:
        raise ContractError("cache roots already differ from frozen snapshot")
    return {
        "schema": SCHEMA_PREFLIGHT,
        "passed": True,
        "created_time_ns": time.time_ns(),
        "physical_gpu": args.physical_gpu,
        "device_name": EXPECTED_DEVICE_NAME,
        "lab_repo_head": args.repo_head,
        "qualifier": script,
        "driver": driver,
        "model": model,
        "extension": extension,
        "stage_graph": stage_graph,
        "health": health,
        "cache": {
            "path": str(cache_path),
            "sha256": cache_sha,
            "inventory_sha256": cache_packet["inventory_sha256"],
            "roots": [root["path"] for root in cache_packet["roots"]],
        },
        "contract": {
            "tp_size": TP_SIZE,
            "full_shape": list(FULL_SHAPE),
            "shard_shape": list(SHARD_SHAPE),
            "serialized_dtype": TENSOR_DTYPE,
            "live_dtype": "float16",
            "cast_order": "full BF16 tensor -> output-row shard -> FP16 -> FP32 pack math",
            "group_size": GROUP_SIZE,
            "packing": "eight K-consecutive unsigned nibbles, least-significant first",
            "qweight_shape": list(QWEIGHT_SHAPE),
            "qweight_stride": list(QWEIGHT_STRIDE),
            "scale_shape": list(SCALE_SHAPE),
            "qzero": 8,
            "rows": list(ROWS),
            "kernel_atol": KERNEL_ATOL,
            "kernel_rtol": KERNEL_RTOL,
            "warmup_launches": WARMUP_LAUNCHES,
            "bootstrap_iterations": BOOTSTRAP_ITERATIONS,
            "m6_equals_six_serial_m1_required": True,
            "minimum_m6_saving_us_per_call": MIN_M6_SAVING_US,
            "screen_scope": "isolated eager operator only",
        },
    }


def _validate_preflight(packet: Any, path: Path) -> dict[str, Any]:
    keys = (
        "schema",
        "passed",
        "created_time_ns",
        "physical_gpu",
        "device_name",
        "lab_repo_head",
        "qualifier",
        "driver",
        "model",
        "extension",
        "stage_graph",
        "health",
        "cache",
        "contract",
    )
    packet = _exact_keys(packet, keys, str(path))
    if packet["schema"] != SCHEMA_PREFLIGHT or packet["passed"] is not True:
        raise ContractError(f"{path}: preflight schema/pass mismatch")
    if _require_int(packet["created_time_ns"], f"{path}.created_time_ns") <= 0:
        raise ContractError(f"{path}: invalid creation time")
    if packet["physical_gpu"] != 2 or packet["device_name"] != EXPECTED_DEVICE_NAME:
        raise ContractError(f"{path}: preflight device mismatch")
    if re.fullmatch(r"[0-9a-f]{40}", packet["lab_repo_head"]) is None:
        raise ContractError(f"{path}: malformed repo HEAD")
    for name in ("qualifier", "driver", "extension"):
        identity = _exact_keys(packet[name], ("path", "sha256"), f"{path}.{name}")
        current = _file_identity(Path(identity["path"]), identity["sha256"], name)
        if current != identity:
            raise ContractError(f"{path}: {name} no longer revalidates")
    qualifier_path = Path(__file__).resolve(strict=True)
    if packet["qualifier"] != {
        "path": str(qualifier_path),
        "sha256": _sha256_file(qualifier_path),
    }:
        raise ContractError(f"{path}: qualifier identity is not this file")
    if packet["extension"] != {
        "path": str(EXTENSION_FILE),
        "sha256": EXTENSION_SHA256,
    }:
        raise ContractError(f"{path}: extension identity is not the pinned DSO")
    if packet["stage_graph"] != _stage_graph_identity():
        raise ContractError(f"{path}: composite stage graph identity mismatch")
    model = packet["model"]
    if not isinstance(model, dict) or set(model) != {"path", "sha256", "tensor"}:
        raise ContractError(f"{path}: malformed model identity")
    current_model = _file_identity(Path(model["path"]), model["sha256"], "model")
    current_model["tensor"] = _safetensors_header(Path(model["path"]))
    if current_model != model:
        raise ContractError(f"{path}: model no longer revalidates")
    if model["path"] != str(MODEL_FILE) or model["sha256"] != MODEL_SHA256:
        raise ContractError(f"{path}: model identity is not the pinned tensor file")
    health = packet["health"]
    if not isinstance(health, dict):
        raise ContractError(f"{path}: malformed health identity")
    current_health = _health_identity(
        Path(health.get("path", "")), health.get("sha256", ""), 2
    )
    if current_health != health:
        raise ContractError(f"{path}: health packet no longer revalidates")
    cache = _exact_keys(
        packet["cache"],
        ("path", "sha256", "inventory_sha256", "roots"),
        f"{path}.cache",
    )
    cache_path = _canonical(Path(cache["path"]), "preflight cache")
    if _sha256_file(cache_path) != _require_sha(cache["sha256"], "cache SHA"):
        raise ContractError(f"{path}: cache packet changed")
    cache_packet = _validate_cache_packet(load_json(cache_path), cache_path)
    if (
        cache_packet["inventory_sha256"] != cache["inventory_sha256"]
        or [root["path"] for root in cache_packet["roots"]] != cache["roots"]
        or _current_inventory_from_packet(cache_packet)
        != {
            "roots": cache_packet["roots"],
            "inventory_sha256": cache_packet["inventory_sha256"],
        }
    ):
        raise ContractError(f"{path}: cache identity no longer revalidates")
    expected_contract = _preflight_contract_literal()
    if packet["contract"] != expected_contract:
        raise ContractError(f"{path}: preflight contract mismatch")
    return packet


def _preflight_contract_literal() -> dict[str, Any]:
    return {
        "tp_size": TP_SIZE,
        "full_shape": list(FULL_SHAPE),
        "shard_shape": list(SHARD_SHAPE),
        "serialized_dtype": TENSOR_DTYPE,
        "live_dtype": "float16",
        "cast_order": "full BF16 tensor -> output-row shard -> FP16 -> FP32 pack math",
        "group_size": GROUP_SIZE,
        "packing": "eight K-consecutive unsigned nibbles, least-significant first",
        "qweight_shape": list(QWEIGHT_SHAPE),
        "qweight_stride": list(QWEIGHT_STRIDE),
        "scale_shape": list(SCALE_SHAPE),
        "qzero": 8,
        "rows": list(ROWS),
        "kernel_atol": KERNEL_ATOL,
        "kernel_rtol": KERNEL_RTOL,
        "warmup_launches": WARMUP_LAUNCHES,
        "bootstrap_iterations": BOOTSTRAP_ITERATIONS,
        "m6_equals_six_serial_m1_required": True,
        "minimum_m6_saving_us_per_call": MIN_M6_SAVING_US,
        "screen_scope": "isolated eager operator only",
    }


def preflight_command(args: argparse.Namespace) -> dict[str, Any]:
    _require_campaign_launch_authorized("preflight")
    if (
        args.health_packet != AUTHORIZED_HEALTH_TERMINAL_PATH
        or args.health_sha256 != AUTHORIZED_HEALTH_TERMINAL_SHA256
    ):
        raise ContractError("preflight health terminal is not the frozen authorization")
    packet = _preflight_payload(args)
    output = Path(args.output)
    if not output.is_absolute():
        raise ContractError("preflight output must be absolute")
    _validate_preflight(packet, output)
    _write_json_exclusive(output, packet)
    return packet


def _tensor_sha256(torch: Any, tensor: Any) -> str:
    cpu = tensor.detach().cpu().contiguous()
    raw = cpu.view(torch.uint8).numpy().tobytes(order="C")
    return _sha256_bytes(raw)


def _encode_nibbles(torch: Any, nibbles: Any) -> Any:
    if nibbles.dtype != torch.int32 or nibbles.shape[-1] != PACK_FACTOR:
        raise ContractError("nibble encoder requires int32 groups of eight")
    if bool(((nibbles < 0) | (nibbles > 15)).any().item()):
        raise ContractError("nibble encoder input is outside [0, 15]")
    factors = (16 ** torch.arange(PACK_FACTOR, dtype=torch.int64)).view(
        *((1,) * (nibbles.ndim - 1)), PACK_FACTOR
    )
    return (nibbles.to(torch.int64) * factors).sum(dim=-1).to(torch.int32)


def _pack_weight(torch: Any, weight_fp16: Any) -> tuple[Any, Any, Any, int]:
    if weight_fp16.device.type != "cpu" or weight_fp16.dtype != torch.float16:
        raise ContractError("packer requires a CPU FP16 live-runtime shard")
    if weight_fp16.ndim != 2 or weight_fp16.shape[1] % GROUP_SIZE != 0:
        raise ContractError("packer received an invalid shard shape")
    n_rows, hidden = weight_fp16.shape
    groups = hidden // GROUP_SIZE
    packed_k = hidden // PACK_FACTOR
    packed_storage = torch.empty((n_rows, packed_k), dtype=torch.int32)
    scales = torch.empty((groups, n_rows), dtype=torch.float16)
    zero_groups = 0
    for start in range(0, n_rows, 64):
        end = min(start + 64, n_rows)
        grouped = weight_fp16[start:end].float().view(end - start, groups, GROUP_SIZE)
        amax = grouped.abs().amax(dim=-1)
        zero_mask = amax == 0
        zero_groups += int(zero_mask.sum().item())
        quant_scale = torch.where(zero_mask, torch.ones_like(amax), amax / 7.0)
        quantized = torch.round(grouped / quant_scale.unsqueeze(-1)).clamp(-8, 7)
        unsigned = quantized.to(torch.int32) + 8
        packed_storage[start:end].copy_(
            _encode_nibbles(torch, unsigned.reshape(end - start, packed_k, PACK_FACTOR))
        )
        scales[:, start:end] = quant_scale.t().to(torch.float16)
    qweight = packed_storage.t()
    if (
        tuple(qweight.shape) != QWEIGHT_SHAPE
        or tuple(qweight.stride()) != QWEIGHT_STRIDE
    ):
        raise ContractError("packed qweight shape/stride mismatch")
    if tuple(scales.shape) != SCALE_SHAPE or not scales.is_contiguous():
        raise ContractError("packed scale shape/layout mismatch")
    return packed_storage, qweight, scales, zero_groups


def _decode_weight(torch: Any, packed_storage: Any, scales: Any) -> Any:
    """Independently decode packed bytes; do not reuse the quantized tensor."""
    if packed_storage.dtype != torch.int32 or not packed_storage.is_contiguous():
        raise ContractError("decoder requires contiguous int32 backing storage")
    n_rows, packed_k = packed_storage.shape
    hidden = packed_k * PACK_FACTOR
    decoded = torch.empty((n_rows, hidden), dtype=torch.float32)
    source = packed_storage.to(torch.int64)
    for nibble_index in range(PACK_FACTOR):
        decoded[:, nibble_index::PACK_FACTOR] = (
            (source >> (4 * nibble_index)) & 0xF
        ).to(torch.float32) - 8.0
    scale_rows = scales.t().float().repeat_interleave(GROUP_SIZE, dim=1)
    if scale_rows.shape != decoded.shape:
        raise ContractError("decoded scale expansion shape mismatch")
    decoded.mul_(scale_rows)
    return decoded


def _packing_self_test(torch: Any) -> dict[str, Any]:
    sentinel = torch.tensor([[[0, 1, 7, 8, 9, 14, 15, 0]]], dtype=torch.int32)
    encoded = int(_encode_nibbles(torch, sentinel).item()) & 0xFFFFFFFF
    expected = sum(
        value << (4 * index) for index, value in enumerate(sentinel.flatten())
    )
    if encoded != expected:
        raise ContractError("least-significant-first nibble sentinel failed")
    zero_weight = torch.zeros((1, GROUP_SIZE), dtype=torch.float16)
    grouped = zero_weight.float().view(1, 1, GROUP_SIZE)
    amax = grouped.abs().amax(dim=-1)
    scale = torch.where(amax == 0, torch.ones_like(amax), amax / 7.0)
    unsigned = (
        torch.round(grouped / scale.unsqueeze(-1)).clamp(-8, 7).to(torch.int32) + 8
    )
    packed = _encode_nibbles(
        torch, unsigned.reshape(1, GROUP_SIZE // PACK_FACTOR, PACK_FACTOR)
    )
    decoded = torch.empty_like(grouped.reshape(1, GROUP_SIZE))
    source = packed.to(torch.int64)
    for nibble_index in range(PACK_FACTOR):
        decoded[:, nibble_index::PACK_FACTOR] = (
            (source >> (4 * nibble_index)) & 0xF
        ).float() - 8.0
    decoded.mul_(scale.item())
    if not bool((unsigned == 8).all().item()) or not bool((decoded == 0).all().item()):
        raise ContractError("zero-group scale/nibble/dequantization self-test failed")
    return {
        "nibble_order": "least-significant-first",
        "sentinel_packed_uint32": encoded,
        "zero_group_scale": float(scale.item()),
        "zero_group_nibble": 8,
        "zero_group_dequant_exact_zero": True,
    }


def _load_and_pack(
    torch: Any, preflight: dict[str, Any], tp_rank: int
) -> dict[str, Any]:
    from safetensors import safe_open

    model_path = Path(preflight["model"]["path"])
    with safe_open(model_path, framework="pt", device="cpu") as handle:
        full_bf16 = handle.get_tensor(TENSOR_NAME)
    if full_bf16.dtype != torch.bfloat16 or tuple(full_bf16.shape) != FULL_SHAPE:
        raise ContractError("loaded mtp.fc tensor identity mismatch")
    full_sha = _tensor_sha256(torch, full_bf16)
    if full_sha != FULL_TENSOR_SHA256:
        raise ContractError("full mtp.fc tensor digest mismatch")
    row_start = tp_rank * SHARD_SHAPE[0]
    row_end = row_start + SHARD_SHAPE[0]
    shard_bf16 = full_bf16[row_start:row_end].contiguous()
    shard_bf16_sha = _tensor_sha256(torch, shard_bf16)
    live_fp16 = shard_bf16.to(torch.float16).contiguous()
    live_fp16_sha = _tensor_sha256(torch, live_fp16)
    expected = SHARD_DIGESTS[tp_rank]
    if shard_bf16_sha != expected["bf16"] or live_fp16_sha != expected["fp16"]:
        raise ContractError("BF16-to-live-FP16 TP shard digest mismatch")
    packed_storage, qweight, scales, zero_groups = _pack_weight(torch, live_fp16)
    packing_hashes = {
        "packed_storage": _tensor_sha256(torch, packed_storage),
        "qweight_logical": _tensor_sha256(torch, qweight),
        "scales": _tensor_sha256(torch, scales),
        "qzero": QZERO_SHA256,
    }
    if any(
        packing_hashes[name] != expected[name]
        for name in expected
        if name not in {"bf16", "fp16"}
    ):
        raise ContractError("packed TP shard digest mismatch")
    qzero = torch.tensor([8], dtype=torch.int8)
    if _tensor_sha256(torch, qzero) != QZERO_SHA256:
        raise ContractError("qzero digest mismatch")
    if not bool(torch.isfinite(scales).all().item()) or not bool(
        (scales > 0).all().item()
    ):
        raise ContractError("packed scales must be finite and positive")
    decoded_fp32 = _decode_weight(torch, packed_storage, scales)
    return {
        "live_fp16": live_fp16,
        "packed_storage": packed_storage,
        "qweight": qweight,
        "scales": scales,
        "qzero": qzero,
        "decoded_fp32": decoded_fp32,
        "identity": {
            "tensor_name": TENSOR_NAME,
            "full_shape": list(FULL_SHAPE),
            "serialized_dtype": "bfloat16",
            "full_tensor_sha256": full_sha,
            "tp_rank": tp_rank,
            "row_range": [row_start, row_end],
            "shard_shape": list(SHARD_SHAPE),
            "shard_bf16_sha256": shard_bf16_sha,
            "live_fp16_sha256": live_fp16_sha,
            "cast_order": "output-row shard before BF16-to-FP16 cast",
        },
        "packing": {
            "group_size": GROUP_SIZE,
            "qweight_shape": list(qweight.shape),
            "qweight_stride": list(qweight.stride()),
            "scales_shape": list(scales.shape),
            "scales_dtype": "float16",
            "qzero": 8,
            "zero_group_count": zero_groups,
            "hashes": packing_hashes,
            "self_test": _packing_self_test(torch),
        },
    }


def _mapped_extension_identity(
    extension_path: Path, expected_sha: str
) -> dict[str, Any]:
    basenames = {extension_path.name}
    mapped: set[Path] = set()
    try:
        for line in Path("/proc/self/maps").read_text(encoding="utf-8").splitlines():
            fields = line.split(maxsplit=5)
            if len(fields) != 6 or not fields[5].startswith("/"):
                continue
            raw_path = fields[5]
            deleted = raw_path.endswith(" (deleted)")
            text = raw_path.removesuffix(" (deleted)")
            candidate = Path(text).resolve(strict=False)
            if candidate.name in basenames:
                if deleted:
                    raise ContractError(
                        f"required extension mapping is deleted: {raw_path}"
                    )
                mapped.add(candidate)
    except (OSError, UnicodeError) as error:
        raise ContractError(f"cannot read mapped libraries: {error}") from error
    same_basename = sorted(str(path) for path in mapped)
    if same_basename != [str(extension_path)]:
        raise ContractError(
            f"extension mapping is not exact and unique: {same_basename}"
        )
    if _sha256_file(extension_path) != expected_sha:
        raise ContractError("mapped extension changed after import")
    return {
        "required_path": str(extension_path),
        "required_sha256": expected_sha,
        "same_basename_paths": same_basename,
        "mapping_gate_passed": True,
    }


def _device_uuid_text(properties: Any) -> str:
    value = str(getattr(properties, "uuid", None)).lower()
    if re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", value) is None:
        raise ContractError(f"malformed XPU device UUID: {value!r}")
    return value


@contextmanager
def _capture_stderr(path: Path) -> Iterator[None]:
    temporary = Path(f"{path}.tmp")
    if path.exists() or temporary.exists():
        raise ContractError(f"refusing existing stderr path: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    saved = os.dup(2)
    try:
        sys.stderr.flush()
        os.dup2(descriptor, 2)
        yield
        sys.stderr.flush()
        try:
            ctypes.CDLL(None).fflush(None)
        except Exception:
            pass
    finally:
        os.dup2(saved, 2)
        os.close(saved)
        os.close(descriptor)
        os.chmod(temporary, 0o444)
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)


def _marker_evidence(stderr_path: Path, role: str) -> dict[str, Any]:
    try:
        lines = stderr_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        raise ContractError(f"invalid stderr log {stderr_path}: {error}") from error

    def exact_warning_count(marker: str, source_line: int) -> tuple[int, int]:
        raw_count = sum(line.count(marker) for line in lines)
        pattern = re.compile(
            rf"^(?:\[rank[01]\]:)?\[W[0-9]+ [0-9:.]+ "
            rf"int4_gemm_w4a16\.h:{source_line}\] Warning: "
            rf"{re.escape(marker)} \(function operator\(\)\)$"
        )
        exact_count = sum(pattern.fullmatch(line) is not None for line in lines)
        return raw_count, exact_count

    input_raw, input_count = exact_warning_count(INPUT_MARKER, INPUT_MARKER_SOURCE_LINE)
    completion_raw, completion_count = exact_warning_count(
        COMPLETION_MARKER, COMPLETION_MARKER_SOURCE_LINE
    )
    detpad_count = sum(line.count(DETPAD_MARKER) for line in lines)
    expected = 1 if role == "candidate" else 0
    if (
        input_raw != expected
        or input_count != expected
        or completion_raw != expected
        or completion_count != expected
        or detpad_count != 0
    ):
        raise ContractError(
            "operator marker mismatch: "
            f"input_raw={input_raw} input_exact={input_count} "
            f"completion_raw={completion_raw} completion_exact={completion_count} "
            f"detpad={detpad_count}"
        )
    return {
        "stderr_path": str(stderr_path),
        "stderr_sha256": _sha256_file(stderr_path),
        "stderr_line_count": len(lines),
        "input_dependency_marker": INPUT_MARKER,
        "input_dependency_marker_count": input_count,
        "completion_marker": COMPLETION_MARKER,
        "completion_marker_count": completion_count,
        "determinism_pad_marker_prefix": DETPAD_MARKER,
        "determinism_pad_marker_count": detpad_count,
        "passed": True,
    }


def _process_identity(started_ns: int) -> dict[str, Any]:
    stat = Path("/proc/self/stat").read_text(encoding="utf-8").split()
    return {
        "pid": os.getpid(),
        "start_ticks": int(stat[21]),
        "boot_id": Path("/proc/sys/kernel/random/boot_id")
        .read_text(encoding="utf-8")
        .strip(),
        "hostname": socket.gethostname(),
        "started_time_ns": started_ns,
        "finished_time_ns": time.time_ns(),
    }


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = fraction * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _sample_summary(values: list[float]) -> dict[str, float]:
    if not values or any(not math.isfinite(value) or value <= 0 for value in values):
        raise ContractError("timing samples must be finite and positive")
    median = statistics.median(values)
    return {
        "minimum": min(values),
        "p10": _percentile(values, 0.10),
        "median": median,
        "p90": _percentile(values, 0.90),
        "maximum": max(values),
        "mean": statistics.mean(values),
        "mad": statistics.median([abs(value - median) for value in values]),
    }


def _comparison_metrics(torch: Any, actual: Any, expected: Any) -> dict[str, Any]:
    actual_f = actual.detach().cpu().float()
    expected_f = expected.detach().cpu().float()
    if actual_f.shape != expected_f.shape:
        raise ContractError("comparison tensor shape mismatch")
    if not bool(torch.isfinite(actual_f).all().item()) or not bool(
        torch.isfinite(expected_f).all().item()
    ):
        raise ContractError("comparison contains a nonfinite value")
    difference = (actual_f - expected_f).abs()
    relative = difference / expected_f.abs().clamp_min(1.0e-12)
    cosine = torch.nn.functional.cosine_similarity(
        actual_f.reshape(1, -1), expected_f.reshape(1, -1), dim=1
    ).item()
    passed = bool(
        torch.allclose(actual_f, expected_f, atol=KERNEL_ATOL, rtol=KERNEL_RTOL)
    )
    return {
        "passed": passed,
        "atol": KERNEL_ATOL,
        "rtol": KERNEL_RTOL,
        "maximum_absolute_difference": float(difference.max().item()),
        "mean_absolute_difference": float(difference.mean().item()),
        "p99_absolute_difference": float(
            torch.quantile(difference.flatten(), 0.99).item()
        ),
        "maximum_relative_difference": float(relative.max().item()),
        "cosine_similarity": float(cosine),
    }


def _deterministic_input(torch: Any, rows: int) -> Any:
    generator = torch.Generator(device="cpu")
    generator.manual_seed(380000 + rows)
    value = torch.randn((rows, FULL_SHAPE[1]), generator=generator, dtype=torch.float32)
    half = FULL_SHAPE[1] // 2
    for start in (0, half):
        section = value[:, start : start + half]
        section.div_(section.square().mean(dim=1, keepdim=True).sqrt())
    return value.to(torch.float16).contiguous()


def _event_samples(
    torch: Any,
    operation: Callable[[Any], Any],
    input_xpu: Any,
    samples: int,
    launches_per_sample: int,
) -> list[float]:
    retained: list[Any] = []
    for _ in range(WARMUP_LAUNCHES):
        retained.append(operation(input_xpu))
    torch.xpu.synchronize()
    retained.clear()
    timings: list[float] = []
    for _ in range(samples):
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        outputs: list[Any] = []
        start.record()
        for _ in range(launches_per_sample):
            outputs.append(operation(input_xpu))
        end.record()
        end.synchronize()
        elapsed_us = float(start.elapsed_time(end)) * 1000.0 / launches_per_sample
        if not math.isfinite(elapsed_us) or elapsed_us <= 0:
            raise ContractError(f"invalid XPU event duration: {elapsed_us}")
        timings.append(elapsed_us)
        del outputs
    return timings


def _load_preflight_for_run(
    args: argparse.Namespace,
) -> tuple[dict[str, Any], Path, str]:
    path = _canonical(Path(args.preflight), "preflight packet")
    digest = _sha256_file(path)
    if digest != _require_sha(args.preflight_sha256, "preflight SHA"):
        raise ContractError("preflight packet SHA mismatch")
    packet = _validate_preflight(load_json(path), path)
    if packet["physical_gpu"] != args.physical_gpu:
        raise ContractError("run/preflight physical GPU mismatch")
    return packet, path, digest


def _cache_unchanged(preflight: dict[str, Any]) -> dict[str, Any]:
    cache_path = Path(preflight["cache"]["path"])
    cache_packet = _validate_cache_packet(load_json(cache_path), cache_path)
    current = _current_inventory_from_packet(cache_packet)
    passed = current == {
        "roots": cache_packet["roots"],
        "inventory_sha256": cache_packet["inventory_sha256"],
    }
    return {
        "before_packet_path": str(cache_path),
        "before_packet_sha256": preflight["cache"]["sha256"],
        "before_inventory_sha256": cache_packet["inventory_sha256"],
        "after_inventory_sha256": current["inventory_sha256"],
        "roots": [root["path"] for root in cache_packet["roots"]],
        "unchanged": passed,
    }


def _case_result(
    torch: Any,
    role: str,
    rows: int,
    operation: Callable[[Any], Any],
    live_fp16: Any,
    decoded_fp32: Any,
    samples: int,
    launches_per_sample: int,
    stability_replays: int,
) -> dict[str, Any]:
    input_cpu = _deterministic_input(torch, rows)
    mutated_cpu = input_cpu.clone()
    mutated_cpu[0, 0] = (mutated_cpu[0, 0].float() + 0.25).to(torch.float16)
    input_sha = _tensor_sha256(torch, input_cpu)
    mutated_input_sha = _tensor_sha256(torch, mutated_cpu)
    if input_sha == mutated_input_sha:
        raise ContractError(f"M{rows}: input mutation did not alter the fixture")

    original_oracle = torch.nn.functional.linear(input_cpu.float(), live_fp16.float())
    dequant_oracle = torch.nn.functional.linear(input_cpu.float(), decoded_fp32)
    mutated_original_oracle = torch.nn.functional.linear(
        mutated_cpu.float(), live_fp16.float()
    )
    mutated_dequant_oracle = torch.nn.functional.linear(
        mutated_cpu.float(), decoded_fp32
    )
    selected_oracle = original_oracle if role == "control" else dequant_oracle
    selected_mutated_oracle = (
        mutated_original_oracle if role == "control" else mutated_dequant_oracle
    )

    input_xpu = input_cpu.to("xpu:0")
    output_digests: list[str] = []
    output_cpu: Any | None = None
    oracle_checks: list[dict[str, Any]] = []
    for replay in range(stability_replays):
        output = operation(input_xpu)
        torch.xpu.synchronize()
        current = output.detach().cpu()
        output_digests.append(_tensor_sha256(torch, current))
        check = _comparison_metrics(torch, current, selected_oracle)
        if check["passed"] is not True:
            raise ContractError(
                f"M{rows} {role} replay {replay} differs from its CPU oracle: "
                f"max_abs={check['maximum_absolute_difference']}"
            )
        oracle_checks.append(check)
        output_cpu = current
    if len(set(output_digests)) != 1 or output_cpu is None:
        raise ContractError(f"M{rows}: output is not bit-stable across eager replays")

    serial_m1_output_sha: str | None = None
    m6_equals_serial: bool | None = None
    if rows == 6:
        serial_outputs: list[Any] = []
        for row_index in range(rows):
            serial_outputs.append(operation(input_xpu[row_index : row_index + 1]))
        torch.xpu.synchronize()
        serial_cpu = torch.cat(
            [output.detach().cpu() for output in serial_outputs], dim=0
        )
        serial_m1_output_sha = _tensor_sha256(torch, serial_cpu)
        m6_equals_serial = bool(torch.equal(serial_cpu, output_cpu))
        if not m6_equals_serial:
            raise ContractError(
                f"M{rows}: batched output differs from six serial M1 rows"
            )

    mutated_output = operation(mutated_cpu.to("xpu:0"))
    torch.xpu.synchronize()
    mutated_output_cpu = mutated_output.detach().cpu()
    mutated_output_sha = _tensor_sha256(torch, mutated_output_cpu)
    if mutated_output_sha == output_digests[0]:
        raise ContractError(f"M{rows}: mutated input produced a stale output")
    mutation_check = _comparison_metrics(
        torch, mutated_output_cpu, selected_mutated_oracle
    )
    if mutation_check["passed"] is not True:
        raise ContractError(f"M{rows}: mutated output differs from its CPU oracle")

    samples_us = _event_samples(
        torch, operation, input_xpu, samples, launches_per_sample
    )
    return {
        "rows": rows,
        "input_sha256": input_sha,
        "mutated_input_sha256": mutated_input_sha,
        "selected_oracle": "live_fp16" if role == "control" else "packed_dequant_fp32",
        "original_fp16_oracle_sha256": _tensor_sha256(torch, original_oracle),
        "dequant_oracle_sha256": _tensor_sha256(torch, dequant_oracle),
        "output_sha256": output_digests[0],
        "stability_replays": stability_replays,
        "bit_stable": True,
        "serial_m1_output_sha256": serial_m1_output_sha,
        "m6_equals_six_serial_m1": m6_equals_serial,
        "oracle_check": oracle_checks[0],
        "original_fp16_drift": _comparison_metrics(torch, output_cpu, original_oracle),
        "mutated_output_sha256": mutated_output_sha,
        "mutation_changed_output": True,
        "mutation_oracle_check": mutation_check,
        "event_samples_us_per_call": samples_us,
        "event_summary_us_per_call": _sample_summary(samples_us),
    }


def _run_xpu_inner(
    args: argparse.Namespace,
    preflight: dict[str, Any],
    started_ns: int,
    progress: dict[str, Any],
) -> dict[str, Any]:
    if os.environ.get("PYTHONDONTWRITEBYTECODE") != "1":
        raise ContractError("PYTHONDONTWRITEBYTECODE=1 is required")
    if os.environ.get("ZE_AFFINITY_MASK") != str(args.physical_gpu):
        raise ContractError("ZE_AFFINITY_MASK must select exactly the physical GPU")
    if os.environ.get(COMPLETION_ENV) != "1":
        raise ContractError(f"{COMPLETION_ENV}=1 must be set before torch import")
    stage_root = EXTENSION_FILE.parent.parent
    pythonpath_first = os.environ.get("PYTHONPATH", "").split(os.pathsep)[0]
    ld_library_path_first = os.environ.get("LD_LIBRARY_PATH", "").split(os.pathsep)[0]
    if pythonpath_first != str(stage_root) or ld_library_path_first != str(
        EXTENSION_FILE.parent
    ):
        raise ContractError("PYTHONPATH/LD_LIBRARY_PATH do not select the pinned stage")
    if any(name in sys.modules for name in ("torch", "vllm_xpu_kernels._xpu_C")):
        raise ContractError(
            "torch/XPU extension was imported before run identity gates"
        )

    import torch
    import vllm_xpu_kernels._xpu_C as xpu_extension

    if not sys.version.startswith(EXPECTED_PYTHON_VERSION_PREFIX):
        raise ContractError(f"unexpected Python runtime: {sys.version}")
    if torch.__version__ != EXPECTED_TORCH_VERSION:
        raise ContractError(f"unexpected Torch runtime: {torch.__version__}")
    if torch.xpu.device_count() != 1:
        raise ContractError("affinity-scoped process must expose exactly one XPU")
    device_name = torch.xpu.get_device_name(0)
    device_uuid = _device_uuid_text(torch.xpu.get_device_properties(0))
    if device_name != EXPECTED_DEVICE_NAME or device_uuid != EXPECTED_GPU2_UUID:
        raise ContractError(
            f"unexpected affinity-scoped device: name={device_name!r} "
            f"uuid={device_uuid!r}"
        )
    extension_path = _canonical(Path(xpu_extension.__file__), "imported XPU extension")
    if extension_path != Path(preflight["extension"]["path"]):
        raise ContractError("imported extension path differs from preflight")
    mapping = _mapped_extension_identity(
        extension_path, preflight["extension"]["sha256"]
    )
    progress["mapping_evidence"] = mapping
    runtime = {
        "python": sys.version,
        "torch_version": torch.__version__,
        "hostname": socket.gethostname(),
        "physical_gpu": args.physical_gpu,
        "logical_device": "xpu:0",
        "ze_affinity_mask": os.environ["ZE_AFFINITY_MASK"],
        "device_name": device_name,
        "device_uuid": device_uuid,
        "pci_bdf_context": EXPECTED_GPU2_BDF_CONTEXT,
        "extension_module_path": str(extension_path),
        "pythonpath_first": pythonpath_first,
        "ld_library_path_first": ld_library_path_first,
        "python_dont_write_bytecode": True,
        "torch_compile_used": False,
        "xpu_graph_used": False,
        "vllm_service_used": False,
    }
    progress["runtime_identity"] = runtime

    packed = _load_and_pack(torch, preflight, args.tp_rank)
    progress["model_identity"] = packed["identity"]
    progress["packing"] = packed["packing"]
    live_fp16 = packed["live_fp16"]
    decoded_fp32 = packed["decoded_fp32"]
    live_xpu = live_fp16.to("xpu:0")
    if args.role == "control":

        def operation(value: Any) -> Any:
            return torch.nn.functional.linear(value, live_xpu)

        abi = {
            "operator": "torch.nn.functional.linear",
            "input_dependency": None,
            "completion_barrier_env": os.environ[COMPLETION_ENV],
        }
    else:
        packed_storage_xpu = packed["packed_storage"].to("xpu:0")
        qweight_xpu = packed_storage_xpu.t()
        scales_xpu = packed["scales"].to("xpu:0")
        qzero_xpu = packed["qzero"].to("xpu:0")
        if (
            tuple(qweight_xpu.shape) != QWEIGHT_SHAPE
            or tuple(qweight_xpu.stride()) != QWEIGHT_STRIDE
        ):
            raise ContractError("XPU qweight shape/stride mismatch")

        def operation(value: Any) -> Any:
            return torch.ops._xpu_C.int4_gemm_w4a16(
                value,
                qweight_xpu,
                None,
                scales_xpu,
                qzero_xpu,
                GROUP_SIZE,
                None,
                True,
            )

        abi = {
            "operator": "torch.ops._xpu_C.int4_gemm_w4a16",
            "arguments": [
                "input",
                "qweight",
                "bias=None",
                "scales",
                "qzero=8",
                "group_size=128",
                "g_idx=None",
                "input_dependency=True",
            ],
            "input_dependency": True,
            "completion_barrier_env": os.environ[COMPLETION_ENV],
        }
    progress["abi"] = abi

    cases: list[dict[str, Any]] = []
    progress["completed_cases"] = cases
    for rows in ROWS:
        cases.append(
            _case_result(
                torch,
                args.role,
                rows,
                operation,
                live_fp16,
                decoded_fp32,
                args.samples,
                args.launches_per_sample,
                args.stability_replays,
            )
        )
    torch.xpu.synchronize()
    return {
        "schema": SCHEMA_RUN,
        "passed": True,
        "classification": "isolated-eager-operator-arm-passed",
        "role": args.role,
        "tp_rank": args.tp_rank,
        "arm_id": args.arm_id,
        "campaign_slot": args.campaign_slot,
        "process": _process_identity(started_ns),
        "preflight": {
            "path": str(Path(args.preflight)),
            "sha256": args.preflight_sha256,
            "lab_repo_head": preflight["lab_repo_head"],
            "qualifier_sha256": preflight["qualifier"]["sha256"],
            "driver_sha256": preflight["driver"]["sha256"],
            "health_sha256": preflight["health"]["sha256"],
        },
        "runtime_identity": runtime,
        "model_identity": packed["identity"],
        "packing": packed["packing"],
        "abi": abi,
        "mapping_evidence": mapping,
        "marker_evidence": None,
        "cache_evidence": None,
        "timing_contract": {
            "clock": "torch.xpu.Event elapsed time",
            "warmup_launches": WARMUP_LAUNCHES,
            "samples_per_shape": args.samples,
            "launches_per_sample": args.launches_per_sample,
            "stability_replays_per_shape": args.stability_replays,
        },
        "cases": cases,
        "authorization": (
            "arm evidence only; no endpoint, deployment, or submission authorization"
        ),
    }


def _invalid_packet(
    args: argparse.Namespace,
    started_ns: int,
    error: BaseException,
    stderr_path: Path,
    progress: dict[str, Any],
) -> dict[str, Any]:
    stderr_identity: dict[str, Any] | None = None
    if stderr_path.is_file():
        try:
            lines = stderr_path.read_text(encoding="utf-8").splitlines()
            marker_observation: dict[str, Any] | None = {
                "input_dependency_marker_count": sum(
                    INPUT_MARKER in line for line in lines
                ),
                "completion_marker_count": sum(
                    COMPLETION_MARKER in line for line in lines
                ),
                "determinism_pad_marker_count": sum(
                    DETPAD_MARKER in line for line in lines
                ),
                "stderr_line_count": len(lines),
            }
        except (OSError, UnicodeError):
            marker_observation = None
        stderr_identity = {
            "path": str(stderr_path),
            "sha256": _sha256_file(stderr_path),
            "writable": bool(stderr_path.stat().st_mode & 0o222),
            "marker_observation": marker_observation,
        }
    cache_evidence: dict[str, Any] | None = None
    try:
        preflight_path = Path(args.preflight)
        if preflight_path.is_file():
            preflight = load_json(preflight_path)
            if isinstance(preflight, dict) and isinstance(preflight.get("cache"), dict):
                cache_evidence = _cache_unchanged(preflight)
    except Exception as cache_error:
        cache_evidence = {"error": f"{type(cache_error).__name__}: {cache_error}"}
    return {
        "schema": SCHEMA_INVALID,
        "passed": False,
        "classification": "invalid-arm-no-scientific-result",
        "role": args.role,
        "tp_rank": args.tp_rank,
        "arm_id": args.arm_id,
        "campaign_slot": args.campaign_slot,
        "process": _process_identity(started_ns),
        "preflight_path": str(Path(args.preflight)),
        "preflight_sha256_expected": args.preflight_sha256,
        "stderr": stderr_identity,
        "cache_evidence": cache_evidence,
        "progress": progress,
        "failure": {
            "exception_type": type(error).__name__,
            "message": str(error),
        },
        "authorization": "stop; preserve root; no same-root retry or later arm",
    }


def run_command(args: argparse.Namespace) -> dict[str, Any]:
    _require_campaign_launch_authorized("run")
    output = Path(args.output)
    stderr_path = Path(args.stderr_log)
    if not output.is_absolute() or not stderr_path.is_absolute():
        raise ContractError("run output and stderr log must be absolute")
    if output.parent != stderr_path.parent:
        raise ContractError("run packet and stderr log must share one output root")
    if output.exists() or Path(f"{output}.tmp").exists():
        raise ContractError(f"refusing existing run output: {output}")
    expected_roles = ("control", "candidate", "candidate", "control")
    expected_suffixes = ("a1", "b1", "b2", "a2")
    if args.role != expected_roles[args.campaign_slot - 1]:
        raise ContractError("role does not match ABBA campaign slot")
    expected_arm = f"rank{args.tp_rank}-{expected_suffixes[args.campaign_slot - 1]}"
    if args.arm_id != expected_arm:
        raise ContractError(f"arm ID must be {expected_arm}")

    started_ns = time.time_ns()
    error: BaseException | None = None
    packet: dict[str, Any] | None = None
    progress: dict[str, Any] = {}
    try:
        preflight, _, _ = _load_preflight_for_run(args)
        with _capture_stderr(stderr_path):
            packet = _run_xpu_inner(args, preflight, started_ns, progress)
    except BaseException as caught:
        error = caught

    if error is None and packet is not None:
        try:
            packet["marker_evidence"] = _marker_evidence(stderr_path, args.role)
            packet["cache_evidence"] = _cache_unchanged(preflight)
            if packet["cache_evidence"]["unchanged"] is not True:
                raise ContractError("production compile-cache roots changed during arm")
            packet["process"]["finished_time_ns"] = time.time_ns()
            _validate_run_packet(packet, output, revalidate_external=True)
        except BaseException as caught:
            error = caught
    if error is not None:
        invalid = _invalid_packet(args, started_ns, error, stderr_path, progress)
        _validate_invalid_packet(invalid, output)
        _write_json_exclusive(output, invalid)
        raise ContractError(
            f"invalid arm recorded at {output}: {type(error).__name__}: {error}"
        ) from error
    assert packet is not None
    _write_json_exclusive(output, packet)
    return packet


def _validate_metrics(value: Any, where: str, *, require_pass: bool) -> None:
    keys = (
        "passed",
        "atol",
        "rtol",
        "maximum_absolute_difference",
        "mean_absolute_difference",
        "p99_absolute_difference",
        "maximum_relative_difference",
        "cosine_similarity",
    )
    value = _exact_keys(value, keys, where)
    if not isinstance(value["passed"], bool):
        raise ContractError(f"{where}.passed must be Boolean")
    if require_pass and value["passed"] is not True:
        raise ContractError(f"{where} did not pass")
    if value["atol"] != KERNEL_ATOL or value["rtol"] != KERNEL_RTOL:
        raise ContractError(f"{where} tolerance mismatch")
    for name in keys[3:]:
        number = _require_finite(value[name], f"{where}.{name}")
        if name != "cosine_similarity" and number < 0:
            raise ContractError(f"{where}.{name} must be nonnegative")
    cosine = float(value["cosine_similarity"])
    if cosine < -1.000001 or cosine > 1.000001:
        raise ContractError(f"{where}.cosine_similarity is outside [-1,1]")


def _validate_case(
    case: Any,
    role: str,
    timing: dict[str, Any],
    where: str,
) -> dict[str, Any]:
    keys = (
        "rows",
        "input_sha256",
        "mutated_input_sha256",
        "selected_oracle",
        "original_fp16_oracle_sha256",
        "dequant_oracle_sha256",
        "output_sha256",
        "stability_replays",
        "bit_stable",
        "serial_m1_output_sha256",
        "m6_equals_six_serial_m1",
        "oracle_check",
        "original_fp16_drift",
        "mutated_output_sha256",
        "mutation_changed_output",
        "mutation_oracle_check",
        "event_samples_us_per_call",
        "event_summary_us_per_call",
    )
    case = _exact_keys(case, keys, where)
    rows = _require_int(case["rows"], f"{where}.rows")
    if rows not in ROWS:
        raise ContractError(f"{where}: unexpected M")
    for name in (
        "input_sha256",
        "mutated_input_sha256",
        "original_fp16_oracle_sha256",
        "dequant_oracle_sha256",
        "output_sha256",
        "mutated_output_sha256",
    ):
        _require_sha(case[name], f"{where}.{name}")
    if case["input_sha256"] == case["mutated_input_sha256"]:
        raise ContractError(f"{where}: input mutation digest collision")
    if case["output_sha256"] == case["mutated_output_sha256"]:
        raise ContractError(f"{where}: stale mutation output")
    expected_oracle = "live_fp16" if role == "control" else "packed_dequant_fp32"
    if case["selected_oracle"] != expected_oracle:
        raise ContractError(f"{where}: selected oracle mismatch")
    if (
        _require_int(case["stability_replays"], f"{where}.stability")
        != timing["stability_replays_per_shape"]
        or case["bit_stable"] is not True
        or case["mutation_changed_output"] is not True
    ):
        raise ContractError(f"{where}: stability/mutation gate failed")
    if rows == 6:
        _require_sha(
            case["serial_m1_output_sha256"],
            f"{where}.serial_m1_output_sha256",
        )
        if (
            case["m6_equals_six_serial_m1"] is not True
            or case["serial_m1_output_sha256"] != case["output_sha256"]
        ):
            raise ContractError(f"{where}: M6/serial-M1 exact-row gate failed")
    elif (
        case["serial_m1_output_sha256"] is not None
        or case["m6_equals_six_serial_m1"] is not None
    ):
        raise ContractError(f"{where}: M1 case carries an M6 row gate")
    _validate_metrics(case["oracle_check"], f"{where}.oracle_check", require_pass=True)
    _validate_metrics(
        case["mutation_oracle_check"],
        f"{where}.mutation_oracle_check",
        require_pass=True,
    )
    _validate_metrics(
        case["original_fp16_drift"],
        f"{where}.original_fp16_drift",
        require_pass=False,
    )
    samples = case["event_samples_us_per_call"]
    if not isinstance(samples, list) or len(samples) != timing["samples_per_shape"]:
        raise ContractError(f"{where}: timing sample count mismatch")
    numeric = [_require_finite(value, f"{where}.sample") for value in samples]
    if any(value <= 0 for value in numeric):
        raise ContractError(f"{where}: timing sample is nonpositive")
    expected_summary = _sample_summary(numeric)
    if case["event_summary_us_per_call"] != expected_summary:
        raise ContractError(f"{where}: timing summary does not rederive")
    return case


def _validate_run_packet(
    packet: Any, path: Path, *, revalidate_external: bool
) -> dict[str, Any]:
    keys = (
        "schema",
        "passed",
        "classification",
        "role",
        "tp_rank",
        "arm_id",
        "campaign_slot",
        "process",
        "preflight",
        "runtime_identity",
        "model_identity",
        "packing",
        "abi",
        "mapping_evidence",
        "marker_evidence",
        "cache_evidence",
        "timing_contract",
        "cases",
        "authorization",
    )
    packet = _exact_keys(packet, keys, str(path))
    if (
        packet["schema"] != SCHEMA_RUN
        or packet["passed"] is not True
        or packet["classification"] != "isolated-eager-operator-arm-passed"
    ):
        raise ContractError(f"{path}: run schema/pass mismatch")
    if packet["role"] not in ("control", "candidate"):
        raise ContractError(f"{path}: invalid role")
    rank = _require_int(packet["tp_rank"], f"{path}.tp_rank")
    slot = _require_int(packet["campaign_slot"], f"{path}.campaign_slot")
    if rank not in (0, 1) or slot not in (1, 2, 3, 4):
        raise ContractError(f"{path}: invalid rank/slot")
    expected_role = ("control", "candidate", "candidate", "control")[slot - 1]
    suffix = ("a1", "b1", "b2", "a2")[slot - 1]
    if packet["role"] != expected_role or packet["arm_id"] != f"rank{rank}-{suffix}":
        raise ContractError(f"{path}: arm identity/order mismatch")

    process = _exact_keys(
        packet["process"],
        (
            "pid",
            "start_ticks",
            "boot_id",
            "hostname",
            "started_time_ns",
            "finished_time_ns",
        ),
        f"{path}.process",
    )
    for name in ("pid", "start_ticks", "started_time_ns", "finished_time_ns"):
        if _require_int(process[name], f"{path}.process.{name}") <= 0:
            raise ContractError(f"{path}: invalid process value")
    if process["finished_time_ns"] < process["started_time_ns"]:
        raise ContractError(f"{path}: process interval is reversed")
    if not isinstance(process["boot_id"], str) or not process["boot_id"]:
        raise ContractError(f"{path}: missing boot ID")
    if not isinstance(process["hostname"], str) or not process["hostname"]:
        raise ContractError(f"{path}: missing hostname")

    preflight_identity = _exact_keys(
        packet["preflight"],
        (
            "path",
            "sha256",
            "lab_repo_head",
            "qualifier_sha256",
            "driver_sha256",
            "health_sha256",
        ),
        f"{path}.preflight",
    )
    for name in ("sha256", "qualifier_sha256", "driver_sha256", "health_sha256"):
        _require_sha(preflight_identity[name], f"{path}.preflight.{name}")
    if revalidate_external:
        preflight_path = _canonical(Path(preflight_identity["path"]), "run preflight")
        if _sha256_file(preflight_path) != preflight_identity["sha256"]:
            raise ContractError(f"{path}: preflight file changed")
        preflight_packet = _validate_preflight(
            load_json(preflight_path), preflight_path
        )
        expected_preflight = {
            "path": str(preflight_path),
            "sha256": preflight_identity["sha256"],
            "lab_repo_head": preflight_packet["lab_repo_head"],
            "qualifier_sha256": preflight_packet["qualifier"]["sha256"],
            "driver_sha256": preflight_packet["driver"]["sha256"],
            "health_sha256": preflight_packet["health"]["sha256"],
        }
        if preflight_identity != expected_preflight:
            raise ContractError(f"{path}: preflight identity mismatch")

    runtime = _exact_keys(
        packet["runtime_identity"],
        (
            "python",
            "torch_version",
            "hostname",
            "physical_gpu",
            "logical_device",
            "ze_affinity_mask",
            "device_name",
            "device_uuid",
            "pci_bdf_context",
            "extension_module_path",
            "pythonpath_first",
            "ld_library_path_first",
            "python_dont_write_bytecode",
            "torch_compile_used",
            "xpu_graph_used",
            "vllm_service_used",
        ),
        f"{path}.runtime",
    )
    if (
        runtime["hostname"] != process["hostname"]
        or runtime["physical_gpu"] != 2
        or runtime["logical_device"] != "xpu:0"
        or runtime["ze_affinity_mask"] != "2"
        or runtime["device_name"] != EXPECTED_DEVICE_NAME
        or runtime["device_uuid"] != EXPECTED_GPU2_UUID
        or runtime["pci_bdf_context"] != EXPECTED_GPU2_BDF_CONTEXT
        or runtime["pythonpath_first"] != str(EXTENSION_FILE.parent.parent)
        or runtime["ld_library_path_first"] != str(EXTENSION_FILE.parent)
        or runtime["python_dont_write_bytecode"] is not True
        or runtime["torch_compile_used"] is not False
        or runtime["xpu_graph_used"] is not False
        or runtime["vllm_service_used"] is not False
    ):
        raise ContractError(f"{path}: runtime identity mismatch")
    if (
        not isinstance(runtime["python"], str)
        or not runtime["python"].startswith(EXPECTED_PYTHON_VERSION_PREFIX)
        or runtime["torch_version"] != EXPECTED_TORCH_VERSION
    ):
        raise ContractError(f"{path}: runtime version mismatch")

    model = _exact_keys(
        packet["model_identity"],
        (
            "tensor_name",
            "full_shape",
            "serialized_dtype",
            "full_tensor_sha256",
            "tp_rank",
            "row_range",
            "shard_shape",
            "shard_bf16_sha256",
            "live_fp16_sha256",
            "cast_order",
        ),
        f"{path}.model",
    )
    expected_digest = SHARD_DIGESTS[rank]
    if model != {
        "tensor_name": TENSOR_NAME,
        "full_shape": list(FULL_SHAPE),
        "serialized_dtype": "bfloat16",
        "full_tensor_sha256": FULL_TENSOR_SHA256,
        "tp_rank": rank,
        "row_range": [rank * SHARD_SHAPE[0], (rank + 1) * SHARD_SHAPE[0]],
        "shard_shape": list(SHARD_SHAPE),
        "shard_bf16_sha256": expected_digest["bf16"],
        "live_fp16_sha256": expected_digest["fp16"],
        "cast_order": "output-row shard before BF16-to-FP16 cast",
    }:
        raise ContractError(f"{path}: model/shard identity mismatch")

    packing = _exact_keys(
        packet["packing"],
        (
            "group_size",
            "qweight_shape",
            "qweight_stride",
            "scales_shape",
            "scales_dtype",
            "qzero",
            "zero_group_count",
            "hashes",
            "self_test",
        ),
        f"{path}.packing",
    )
    hashes = expected_digest | {"qzero": QZERO_SHA256}
    expected_hashes = {
        name: hashes[name]
        for name in ("packed_storage", "qweight_logical", "scales", "qzero")
    }
    self_test = _exact_keys(
        packing["self_test"],
        (
            "nibble_order",
            "sentinel_packed_uint32",
            "zero_group_scale",
            "zero_group_nibble",
            "zero_group_dequant_exact_zero",
        ),
        f"{path}.packing.self_test",
    )
    sentinel_value = sum(
        value << (4 * index) for index, value in enumerate((0, 1, 7, 8, 9, 14, 15, 0))
    )
    if (
        packing["group_size"] != GROUP_SIZE
        or packing["qweight_shape"] != list(QWEIGHT_SHAPE)
        or packing["qweight_stride"] != list(QWEIGHT_STRIDE)
        or packing["scales_shape"] != list(SCALE_SHAPE)
        or packing["scales_dtype"] != "float16"
        or packing["qzero"] != 8
        or _require_int(packing["zero_group_count"], "zero groups") != 0
        or packing["hashes"] != expected_hashes
        or self_test
        != {
            "nibble_order": "least-significant-first",
            "sentinel_packed_uint32": sentinel_value,
            "zero_group_scale": 1.0,
            "zero_group_nibble": 8,
            "zero_group_dequant_exact_zero": True,
        }
    ):
        raise ContractError(f"{path}: packing identity mismatch")

    abi = packet["abi"]
    if packet["role"] == "control":
        expected_abi = {
            "operator": "torch.nn.functional.linear",
            "input_dependency": None,
            "completion_barrier_env": "1",
        }
    else:
        expected_abi = {
            "operator": "torch.ops._xpu_C.int4_gemm_w4a16",
            "arguments": [
                "input",
                "qweight",
                "bias=None",
                "scales",
                "qzero=8",
                "group_size=128",
                "g_idx=None",
                "input_dependency=True",
            ],
            "input_dependency": True,
            "completion_barrier_env": "1",
        }
    if abi != expected_abi:
        raise ContractError(f"{path}: operator ABI mismatch")

    mapping = _exact_keys(
        packet["mapping_evidence"],
        (
            "required_path",
            "required_sha256",
            "same_basename_paths",
            "mapping_gate_passed",
        ),
        f"{path}.mapping",
    )
    required_extension = EXTENSION_FILE
    if (
        mapping["required_path"] != str(required_extension)
        or mapping["required_sha256"] != EXTENSION_SHA256
        or mapping["same_basename_paths"] != [str(required_extension)]
        or mapping["mapping_gate_passed"] is not True
        or runtime["extension_module_path"] != str(required_extension)
    ):
        raise ContractError(f"{path}: mapped extension evidence mismatch")
    if revalidate_external and _sha256_file(required_extension) != EXTENSION_SHA256:
        raise ContractError(f"{path}: extension no longer matches")

    marker = _exact_keys(
        packet["marker_evidence"],
        (
            "stderr_path",
            "stderr_sha256",
            "stderr_line_count",
            "input_dependency_marker",
            "input_dependency_marker_count",
            "completion_marker",
            "completion_marker_count",
            "determinism_pad_marker_prefix",
            "determinism_pad_marker_count",
            "passed",
        ),
        f"{path}.marker",
    )
    expected_count = 1 if packet["role"] == "candidate" else 0
    if (
        marker["input_dependency_marker"] != INPUT_MARKER
        or marker["completion_marker"] != COMPLETION_MARKER
        or marker["determinism_pad_marker_prefix"] != DETPAD_MARKER
        or marker["input_dependency_marker_count"] != expected_count
        or marker["completion_marker_count"] != expected_count
        or marker["determinism_pad_marker_count"] != 0
        or marker["passed"] is not True
    ):
        raise ContractError(f"{path}: engagement marker mismatch")
    if revalidate_external:
        stderr_path = _canonical(Path(marker["stderr_path"]), "stderr evidence")
        if stderr_path.parent != path.parent:
            raise ContractError(f"{path}: stderr evidence escaped the run root")
        if stderr_path.stat().st_mode & 0o222:
            raise ContractError(f"{path}: stderr evidence is writable")
        current_marker = _marker_evidence(stderr_path, packet["role"])
        if current_marker != marker:
            raise ContractError(f"{path}: stderr evidence changed")

    cache = _exact_keys(
        packet["cache_evidence"],
        (
            "before_packet_path",
            "before_packet_sha256",
            "before_inventory_sha256",
            "after_inventory_sha256",
            "roots",
            "unchanged",
        ),
        f"{path}.cache",
    )
    if (
        cache["unchanged"] is not True
        or cache["before_inventory_sha256"] != cache["after_inventory_sha256"]
    ):
        raise ContractError(f"{path}: compile-cache mutation gate failed")
    if revalidate_external:
        preflight_path = Path(preflight_identity["path"])
        preflight_packet = load_json(preflight_path)
        current_cache = _cache_unchanged(preflight_packet)
        if current_cache != cache:
            raise ContractError(f"{path}: compile-cache evidence changed")

    timing = _exact_keys(
        packet["timing_contract"],
        (
            "clock",
            "warmup_launches",
            "samples_per_shape",
            "launches_per_sample",
            "stability_replays_per_shape",
        ),
        f"{path}.timing",
    )
    if (
        timing["clock"] != "torch.xpu.Event elapsed time"
        or timing["warmup_launches"] != WARMUP_LAUNCHES
        or _require_int(timing["samples_per_shape"], "samples") < MIN_SAMPLES
        or _require_int(timing["launches_per_sample"], "launches")
        < MIN_LAUNCHES_PER_SAMPLE
        or _require_int(timing["stability_replays_per_shape"], "replays")
        < MIN_STABILITY_REPLAYS
    ):
        raise ContractError(f"{path}: timing contract mismatch")
    cases = packet["cases"]
    if not isinstance(cases, list) or len(cases) != len(ROWS):
        raise ContractError(f"{path}: case inventory mismatch")
    validated = [
        _validate_case(case, packet["role"], timing, f"{path}.cases[{index}]")
        for index, case in enumerate(cases)
    ]
    if [case["rows"] for case in validated] != list(ROWS):
        raise ContractError(f"{path}: case order mismatch")
    if packet["authorization"] != (
        "arm evidence only; no endpoint, deployment, or submission authorization"
    ):
        raise ContractError(f"{path}: authorization boundary mismatch")
    return packet


def _validate_invalid_packet(packet: Any, path: Path) -> dict[str, Any]:
    keys = (
        "schema",
        "passed",
        "classification",
        "role",
        "tp_rank",
        "arm_id",
        "campaign_slot",
        "process",
        "preflight_path",
        "preflight_sha256_expected",
        "stderr",
        "cache_evidence",
        "progress",
        "failure",
        "authorization",
    )
    packet = _exact_keys(packet, keys, str(path))
    if (
        packet["schema"] != SCHEMA_INVALID
        or packet["passed"] is not False
        or packet["classification"] != "invalid-arm-no-scientific-result"
        or packet["authorization"]
        != "stop; preserve root; no same-root retry or later arm"
    ):
        raise ContractError(f"{path}: invalid-packet classification mismatch")
    if packet["role"] not in ("control", "candidate"):
        raise ContractError(f"{path}: invalid role")
    rank = _require_int(packet["tp_rank"], f"{path}.rank")
    slot = _require_int(packet["campaign_slot"], f"{path}.slot")
    if rank not in (0, 1) or slot not in (1, 2, 3, 4):
        raise ContractError(f"{path}: invalid rank/slot")
    expected_role = ("control", "candidate", "candidate", "control")[slot - 1]
    expected_suffix = ("a1", "b1", "b2", "a2")[slot - 1]
    if (
        packet["role"] != expected_role
        or packet["arm_id"] != f"rank{rank}-{expected_suffix}"
    ):
        raise ContractError(f"{path}: invalid-packet arm order mismatch")
    process = _exact_keys(
        packet["process"],
        (
            "pid",
            "start_ticks",
            "boot_id",
            "hostname",
            "started_time_ns",
            "finished_time_ns",
        ),
        f"{path}.process",
    )
    for name in ("pid", "start_ticks", "started_time_ns", "finished_time_ns"):
        if _require_int(process[name], f"{path}.process.{name}") <= 0:
            raise ContractError(f"{path}: invalid process evidence")
    if process["finished_time_ns"] < process["started_time_ns"]:
        raise ContractError(f"{path}: invalid process interval")
    _require_sha(packet["preflight_sha256_expected"], "expected preflight SHA")
    failure = _exact_keys(
        packet["failure"], ("exception_type", "message"), f"{path}.failure"
    )
    if not all(isinstance(failure[name], str) and failure[name] for name in failure):
        raise ContractError(f"{path}: empty failure evidence")
    stderr = packet["stderr"]
    if stderr is not None:
        stderr = _exact_keys(
            stderr,
            ("path", "sha256", "writable", "marker_observation"),
            f"{path}.stderr",
        )
        _require_sha(stderr["sha256"], f"{path}.stderr.sha")
        if stderr["writable"] is not False:
            raise ContractError(f"{path}: invalid stderr is writable")
        stderr_path = _canonical(Path(stderr["path"]), "invalid stderr")
        if stderr_path.parent != path.parent:
            raise ContractError(f"{path}: invalid stderr escaped the run root")
        if (
            stderr_path.stat().st_mode & 0o222
            or _sha256_file(stderr_path) != stderr["sha256"]
        ):
            raise ContractError(f"{path}: invalid stderr evidence changed")
        observation = stderr["marker_observation"]
        if observation is not None:
            observation = _exact_keys(
                observation,
                (
                    "input_dependency_marker_count",
                    "completion_marker_count",
                    "determinism_pad_marker_count",
                    "stderr_line_count",
                ),
                f"{path}.stderr.marker_observation",
            )
            lines = stderr_path.read_text(encoding="utf-8").splitlines()
            expected_observation = {
                "input_dependency_marker_count": sum(
                    INPUT_MARKER in line for line in lines
                ),
                "completion_marker_count": sum(
                    COMPLETION_MARKER in line for line in lines
                ),
                "determinism_pad_marker_count": sum(
                    DETPAD_MARKER in line for line in lines
                ),
                "stderr_line_count": len(lines),
            }
            if observation != expected_observation:
                raise ContractError(f"{path}: invalid marker observation changed")
    progress = packet["progress"]
    if not isinstance(progress, dict) or not set(progress).issubset(
        {
            "mapping_evidence",
            "runtime_identity",
            "model_identity",
            "packing",
            "abi",
            "completed_cases",
        }
    ):
        raise ContractError(f"{path}: malformed partial progress evidence")
    mapping = progress.get("mapping_evidence")
    if mapping is not None and mapping != {
        "required_path": str(EXTENSION_FILE),
        "required_sha256": EXTENSION_SHA256,
        "same_basename_paths": [str(EXTENSION_FILE)],
        "mapping_gate_passed": True,
    }:
        raise ContractError(f"{path}: partial mapping evidence mismatch")
    return packet


def _case_by_rows(packet: dict[str, Any], rows: int) -> dict[str, Any]:
    matches = [case for case in packet["cases"] if case["rows"] == rows]
    if len(matches) != 1:
        raise ContractError(f"packet has no unique M{rows} case")
    return matches[0]


def _bootstrap_abba_savings(cases: list[dict[str, Any]], seed: int) -> dict[str, Any]:
    """Deterministic within-arm resampling for A1-B1 and A2-B2 medians."""
    distributions = [case["event_samples_us_per_call"] for case in cases]
    sample_counts = {len(values) for values in distributions}
    if len(sample_counts) != 1:
        raise ContractError("ABBA timing arms have different sample counts")
    sample_count = next(iter(sample_counts))
    rng = random.Random(seed)
    pair1: list[float] = []
    pair2: list[float] = []
    combined: list[float] = []
    for _ in range(BOOTSTRAP_ITERATIONS):
        medians: list[float] = []
        for values in distributions:
            resampled = [
                values[rng.randrange(sample_count)] for _ in range(sample_count)
            ]
            medians.append(statistics.median(resampled))
        first = medians[0] - medians[1]
        second = medians[3] - medians[2]
        pair1.append(first)
        pair2.append(second)
        combined.append(statistics.mean((first, second)))
    return {
        "iterations": BOOTSTRAP_ITERATIONS,
        "seed": seed,
        "pair_1_95_ci_saving_us_per_call": [
            _percentile(pair1, 0.025),
            _percentile(pair1, 0.975),
        ],
        "pair_2_95_ci_saving_us_per_call": [
            _percentile(pair2, 0.025),
            _percentile(pair2, 0.975),
        ],
        "combined_95_ci_saving_us_per_call": [
            _percentile(combined, 0.025),
            _percentile(combined, 0.975),
        ],
    }


def _compare_packets(packets: list[dict[str, Any]]) -> dict[str, Any]:
    if len(packets) != 8:
        raise ContractError(f"expected eight rank-local ABBA arms, got {len(packets)}")
    identities = {
        (
            packet["preflight"]["sha256"],
            packet["preflight"]["qualifier_sha256"],
            packet["preflight"]["driver_sha256"],
            packet["preflight"]["health_sha256"],
            json.dumps(packet["timing_contract"], sort_keys=True),
            json.dumps(packet["runtime_identity"], sort_keys=True),
        )
        for packet in packets
    }
    if len(identities) != 1:
        raise ContractError("campaign identity/timing differs across arms")
    process_ids = {
        (
            packet["process"]["boot_id"],
            packet["process"]["pid"],
            packet["process"]["start_ticks"],
        )
        for packet in packets
    }
    if len(process_ids) != 8:
        raise ContractError("campaign arms are not eight fresh processes")
    if (
        len({packet["process"]["boot_id"] for packet in packets}) != 1
        or len({packet["process"]["hostname"] for packet in packets}) != 1
    ):
        raise ContractError("campaign arms do not come from one host boot")
    chronological = sorted(packets, key=lambda item: item["process"]["started_time_ns"])
    expected_order = [
        f"rank{rank}-{suffix}" for rank in (0, 1) for suffix in ("a1", "b1", "b2", "a2")
    ]
    if [packet["arm_id"] for packet in chronological] != expected_order:
        raise ContractError("campaign order is not rank0 ABBA then rank1 ABBA")
    for previous, current in zip(chronological, chronological[1:]):
        if (
            previous["process"]["finished_time_ns"]
            > current["process"]["started_time_ns"]
        ):
            raise ContractError("campaign arms overlap")
    for rows in ROWS:
        global_cases = [_case_by_rows(packet, rows) for packet in packets]
        if (
            len({case["input_sha256"] for case in global_cases}) != 1
            or len({case["mutated_input_sha256"] for case in global_cases}) != 1
        ):
            raise ContractError(f"M{rows}: input fixtures differ across TP ranks")

    rank_results: list[dict[str, Any]] = []
    all_passed = True
    for rank in (0, 1):
        arms = sorted(
            [packet for packet in packets if packet["tp_rank"] == rank],
            key=lambda item: item["campaign_slot"],
        )
        if [arm["role"] for arm in arms] != [
            "control",
            "candidate",
            "candidate",
            "control",
        ]:
            raise ContractError(f"rank {rank}: ABBA roles mismatch")
        shape_results: list[dict[str, Any]] = []
        rank_passed = True
        for rows in ROWS:
            cases = [_case_by_rows(arm, rows) for arm in arms]
            if (
                len({case["input_sha256"] for case in cases}) != 1
                or len({case["mutated_input_sha256"] for case in cases}) != 1
            ):
                raise ContractError(f"rank {rank} M{rows}: fixture drift")
            if (
                len({case["original_fp16_oracle_sha256"] for case in cases}) != 1
                or len({case["dequant_oracle_sha256"] for case in cases}) != 1
            ):
                raise ContractError(f"rank {rank} M{rows}: CPU oracle drift")
            if cases[0]["output_sha256"] != cases[3]["output_sha256"]:
                raise ContractError(f"rank {rank} M{rows}: control cross-process drift")
            if cases[1]["output_sha256"] != cases[2]["output_sha256"]:
                raise ContractError(
                    f"rank {rank} M{rows}: candidate cross-process drift"
                )
            if (
                cases[0]["mutated_output_sha256"] != cases[3]["mutated_output_sha256"]
                or cases[1]["mutated_output_sha256"]
                != cases[2]["mutated_output_sha256"]
            ):
                raise ContractError(f"rank {rank} M{rows}: mutation output drift")
            centers = [case["event_summary_us_per_call"]["median"] for case in cases]
            paired = [centers[0] - centers[1], centers[3] - centers[2]]
            central = statistics.mean(paired)
            bootstrap = _bootstrap_abba_savings(
                cases, seed=38_500_000 + rank * 100 + rows
            )
            ci_lowers = [
                bootstrap["pair_1_95_ci_saving_us_per_call"][0],
                bootstrap["pair_2_95_ci_saving_us_per_call"][0],
                bootstrap["combined_95_ci_saving_us_per_call"][0],
            ]
            if rows == 1:
                passed = (
                    all(value >= 0.0 for value in paired)
                    and central >= 0.0
                    and all(value >= 0.0 for value in ci_lowers)
                )
            else:
                passed = (
                    all(value > MIN_M6_SAVING_US for value in paired)
                    and central > MIN_M6_SAVING_US
                    and all(value > 0.0 for value in ci_lowers[:2])
                    and ci_lowers[2] > MIN_M6_SAVING_US
                )
            rank_passed = rank_passed and passed
            shape_results.append(
                {
                    "rows": rows,
                    "control_arm_medians_us_per_call": [centers[0], centers[3]],
                    "candidate_arm_medians_us_per_call": [centers[1], centers[2]],
                    "paired_abba_savings_us_per_call": paired,
                    "central_saving_us_per_call": central,
                    "bootstrap": bootstrap,
                    "all_pair_and_combined_ci_lowers_pass": all(
                        value >= 0.0 for value in ci_lowers
                    )
                    if rows == 1
                    else (
                        all(value > 0.0 for value in ci_lowers[:2])
                        and ci_lowers[2] > MIN_M6_SAVING_US
                    ),
                    "paired_point_estimates_clear_m6_hurdle": (
                        all(value > MIN_M6_SAVING_US for value in paired)
                        if rows == 6
                        else None
                    ),
                    "combined_ci_lower_clears_m6_hurdle": (
                        ci_lowers[2] > MIN_M6_SAVING_US if rows == 6 else None
                    ),
                    "m6_strict_hurdle_us_per_call": (
                        MIN_M6_SAVING_US if rows == 6 else None
                    ),
                    "passed": passed,
                }
            )
        all_passed = all_passed and rank_passed
        rank_results.append(
            {"tp_rank": rank, "shape_results": shape_results, "passed": rank_passed}
        )
    return {
        "schema": SCHEMA_COMPARE,
        "passed": all_passed,
        "classification": (
            "qualified-only-for-default-off-integration-design"
            if all_passed
            else "rejected-at-isolated-eager-operator-gate"
        ),
        "process_count": 8,
        "order": expected_order,
        "minimum_m6_saving_us_per_call_each_rank_strict": MIN_M6_SAVING_US,
        "requires_both_m6_pairs_above_strict_hurdle": True,
        "requires_nonnegative_both_m1_pairs": True,
        "requires_cross_process_bit_stability": True,
        "bootstrap_iterations": BOOTSTRAP_ITERATIONS,
        "requires_pair_and_combined_bootstrap_95_ci_lower": (
            "M1 all >= 0; M6 pair CIs > 0 and combined CI > strict hurdle"
        ),
        "rank_results": rank_results,
        "authorization": (
            "pass permits only a separately reviewed default-off integration patch "
            "and compiled/graph/TP2 model qualification; no endpoint run or submission"
        ),
    }


def compare_command(args: argparse.Namespace) -> dict[str, Any]:
    paths = [_canonical(Path(item), "run packet") for item in args.packets]
    if any(path.stat().st_mode & 0o222 for path in paths):
        raise ContractError("run packets must be immutable before comparison")
    loaded = [
        _validate_run_packet(load_json(path), path, revalidate_external=True)
        for path in paths
    ]
    result = _compare_packets(loaded)
    result["packet_paths"] = [str(path) for path in paths]
    result["packet_sha256"] = [_sha256_file(path) for path in paths]
    output = Path(args.output)
    if not output.is_absolute():
        raise ContractError("comparison output must be absolute")
    _write_json_exclusive(output, result)
    return result


def _validate_compare(packet: Any, path: Path) -> dict[str, Any]:
    extra_keys = ("packet_paths", "packet_sha256")
    base_keys = (
        "schema",
        "passed",
        "classification",
        "process_count",
        "order",
        "minimum_m6_saving_us_per_call_each_rank_strict",
        "requires_both_m6_pairs_above_strict_hurdle",
        "requires_nonnegative_both_m1_pairs",
        "requires_cross_process_bit_stability",
        "bootstrap_iterations",
        "requires_pair_and_combined_bootstrap_95_ci_lower",
        "rank_results",
        "authorization",
    )
    packet = _exact_keys(packet, base_keys + extra_keys, str(path))
    paths = packet["packet_paths"]
    digests = packet["packet_sha256"]
    if not isinstance(paths, list) or len(paths) != 8 or not isinstance(digests, list):
        raise ContractError(f"{path}: malformed compare source inventory")
    canonical_paths = [_canonical(Path(item), "compare source") for item in paths]
    if any(item.stat().st_mode & 0o222 for item in canonical_paths):
        raise ContractError(f"{path}: compare source packet is writable")
    current_digests = [_sha256_file(item) for item in canonical_paths]
    if current_digests != digests:
        raise ContractError(f"{path}: compare source packet changed")
    loaded = [
        _validate_run_packet(load_json(item), item, revalidate_external=True)
        for item in canonical_paths
    ]
    expected = _compare_packets(loaded)
    expected["packet_paths"] = paths
    expected["packet_sha256"] = digests
    if packet != expected:
        raise ContractError(f"{path}: comparison does not rederive")
    return packet


def validate_command(args: argparse.Namespace) -> dict[str, Any]:
    path = _canonical(Path(args.packet), "packet")
    if path.stat().st_mode & 0o222:
        raise ContractError("packet must be immutable before validation")
    packet = load_json(path)
    schema = packet.get("schema") if isinstance(packet, dict) else None
    if schema == SCHEMA_CACHE:
        validated = _validate_cache_packet(packet, path)
        current = _current_inventory_from_packet(validated)
        if current != {
            "roots": validated["roots"],
            "inventory_sha256": validated["inventory_sha256"],
        }:
            raise ContractError("cache snapshot no longer matches its roots")
    elif schema == SCHEMA_PREFLIGHT:
        validated = _validate_preflight(packet, path)
    elif schema == SCHEMA_RUN:
        validated = _validate_run_packet(packet, path, revalidate_external=True)
    elif schema == SCHEMA_INVALID:
        validated = _validate_invalid_packet(packet, path)
    elif schema == SCHEMA_COMPARE:
        validated = _validate_compare(packet, path)
    else:
        raise ContractError(f"unsupported packet schema: {schema}")
    return {
        "validated": True,
        "path": str(path),
        "sha256": _sha256_file(path),
        "schema": validated["schema"],
        "passed": validated["passed"] if "passed" in validated else None,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    snapshot = subparsers.add_parser(
        "cache-snapshot", help="freeze production compile-cache roots without torch"
    )
    snapshot.add_argument("--output", required=True)
    snapshot.add_argument("--root", action="append", required=True)

    preflight = subparsers.add_parser(
        "preflight", help="bind immutable model/operator/health/cache identity"
    )
    preflight.add_argument("--output", required=True)
    preflight.add_argument("--physical-gpu", type=int, required=True)
    preflight.add_argument("--script-sha256", required=True)
    preflight.add_argument("--driver", required=True)
    preflight.add_argument("--driver-sha256", required=True)
    preflight.add_argument("--repo-head", required=True)
    preflight.add_argument("--model-file", default=str(MODEL_FILE))
    preflight.add_argument("--model-sha256", default=MODEL_SHA256)
    preflight.add_argument("--extension", default=str(EXTENSION_FILE))
    preflight.add_argument("--extension-sha256", default=EXTENSION_SHA256)
    preflight.add_argument("--health-packet", required=True)
    preflight.add_argument("--health-sha256", required=True)
    preflight.add_argument("--cache-snapshot", required=True)
    preflight.add_argument("--cache-sha256", required=True)

    run = subparsers.add_parser("run", help="execute one fresh-process ABBA arm")
    run.add_argument("--role", choices=("control", "candidate"), required=True)
    run.add_argument("--tp-rank", type=int, choices=(0, 1), required=True)
    run.add_argument("--physical-gpu", type=int, choices=(2,), required=True)
    run.add_argument("--arm-id", required=True)
    run.add_argument("--campaign-slot", type=int, choices=(1, 2, 3, 4), required=True)
    run.add_argument("--preflight", required=True)
    run.add_argument("--preflight-sha256", required=True)
    run.add_argument("--stderr-log", required=True)
    run.add_argument("--output", required=True)
    run.add_argument("--samples", type=int, default=MIN_SAMPLES)
    run.add_argument("--launches-per-sample", type=int, default=MIN_LAUNCHES_PER_SAMPLE)
    run.add_argument("--stability-replays", type=int, default=MIN_STABILITY_REPLAYS)

    validate = subparsers.add_parser("validate", help="deep-validate one packet")
    validate.add_argument("--packet", required=True)

    compare = subparsers.add_parser(
        "compare", help="compare rank0 ABBA followed by rank1 ABBA"
    )
    compare.add_argument("--output", required=True)
    compare.add_argument("packets", nargs=8)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "cache-snapshot":
            result = cache_snapshot_command(args)
        elif args.command == "preflight":
            result = preflight_command(args)
        elif args.command == "run":
            if args.samples < MIN_SAMPLES:
                raise ContractError(f"--samples must be at least {MIN_SAMPLES}")
            if args.launches_per_sample < MIN_LAUNCHES_PER_SAMPLE:
                raise ContractError(
                    f"--launches-per-sample must be at least {MIN_LAUNCHES_PER_SAMPLE}"
                )
            if args.stability_replays < MIN_STABILITY_REPLAYS:
                raise ContractError(
                    f"--stability-replays must be at least {MIN_STABILITY_REPLAYS}"
                )
            result = run_command(args)
        elif args.command == "validate":
            result = validate_command(args)
        else:
            result = compare_command(args)
        print(json.dumps(result, allow_nan=False, indent=2, sort_keys=True))
        if args.command == "compare" and result["passed"] is not True:
            return 14
        return 0
    except ContractError as error:
        print(f"error: {error}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
