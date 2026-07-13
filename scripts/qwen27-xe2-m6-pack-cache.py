#!/usr/bin/env python3
"""Build and validate persistent Qwen27 Xe2 M6 Q4_0 tensor packs.

The cache is development infrastructure.  It does not alter llama.cpp and is
not benchmark or LocalMaxxing evidence.  Payloads use the exact ``dpas-v2``
layout consumed by the guarded M=6 gate/up experiment in the protected source.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import shutil
import struct
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SPEC = ROOT / "experiments/qwen27-dflash-sycl-b70/harness/model-pack-manifest.json"
DEFAULT_CACHE = Path("/mnt/usb-models/model-packs/qwen27-xe2-m6-v2")
DEFAULT_RAM_ROOT = Path("/dev/shm/qwen27-xe2-m6-v2")
ARCHITECTURE = "bmg-g31"
LAYOUT_NAME = "q4_0-xe2-dpas-v2"
LAYOUT_VERSION = 2
EXPECTED_TENSORS = 130
EXPECTED_K = 5120
EXPECTED_N = 17408
Q4_0_TYPE = 2
Q4_0_BLOCK_BYTES = 18
HASH_CHUNK = 16 * 1024 * 1024
TOOL_REVISION = 2


GGUF_VALUE_SIZES = {
    0: 1,  # UINT8
    1: 1,  # INT8
    2: 2,  # UINT16
    3: 2,  # INT16
    4: 4,  # UINT32
    5: 4,  # INT32
    6: 4,  # FLOAT32
    7: 1,  # BOOL
    10: 8,  # UINT64
    11: 8,  # INT64
    12: 8,  # FLOAT64
}


@dataclass(frozen=True)
class TensorInfo:
    name: str
    shape: tuple[int, ...]
    ggml_type: int
    relative_offset: int
    absolute_offset: int
    size_bytes: int


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def canonical_sha(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def hash_file(path: Path, offset: int = 0, size: int | None = None) -> tuple[str, int]:
    digest = hashlib.sha256()
    consumed = 0
    with path.open("rb", buffering=0) as handle:
        handle.seek(offset)
        while size is None or consumed < size:
            request = HASH_CHUNK if size is None else min(HASH_CHUNK, size - consumed)
            if request == 0:
                break
            chunk = handle.read(request)
            if not chunk:
                break
            digest.update(chunk)
            consumed += len(chunk)
    if size is not None and consumed != size:
        raise ValueError(f"short read hashing {path}: got {consumed}, expected {size}")
    return digest.hexdigest(), consumed


def read_exact(handle: BinaryIO, size: int) -> bytes:
    value = handle.read(size)
    if len(value) != size:
        raise ValueError("truncated GGUF header")
    return value


def read_u32(handle: BinaryIO) -> int:
    return struct.unpack("<I", read_exact(handle, 4))[0]


def read_u64(handle: BinaryIO) -> int:
    return struct.unpack("<Q", read_exact(handle, 8))[0]


def read_string(handle: BinaryIO) -> str:
    length = read_u64(handle)
    return read_exact(handle, length).decode("utf-8")


def skip_value(handle: BinaryIO, value_type: int) -> None:
    if value_type in GGUF_VALUE_SIZES:
        handle.seek(GGUF_VALUE_SIZES[value_type], os.SEEK_CUR)
    elif value_type == 8:  # STRING
        handle.seek(read_u64(handle), os.SEEK_CUR)
    elif value_type == 9:  # ARRAY
        element_type = read_u32(handle)
        count = read_u64(handle)
        if element_type in GGUF_VALUE_SIZES:
            handle.seek(GGUF_VALUE_SIZES[element_type] * count, os.SEEK_CUR)
        elif element_type == 8:
            for _ in range(count):
                handle.seek(read_u64(handle), os.SEEK_CUR)
        else:
            raise ValueError(f"unsupported GGUF array element type {element_type}")
    else:
        raise ValueError(f"unsupported GGUF metadata value type {value_type}")


def read_metadata_value(handle: BinaryIO, value_type: int) -> Any:
    if value_type == 4:
        return read_u32(handle)
    if value_type == 10:
        return read_u64(handle)
    if value_type == 8:
        return read_string(handle)
    skip_value(handle, value_type)
    return None


def q4_0_size(shape: tuple[int, ...]) -> int:
    elements = 1
    for dimension in shape:
        elements *= dimension
    if elements % 32:
        raise ValueError(f"Q4_0 tensor element count is not divisible by 32: {shape}")
    return elements // 32 * Q4_0_BLOCK_BYTES


def read_gguf(path: Path) -> tuple[dict[str, Any], list[TensorInfo]]:
    with path.open("rb") as handle:
        if read_exact(handle, 4) != b"GGUF":
            raise ValueError(f"not a GGUF file: {path}")
        version = read_u32(handle)
        if version not in (2, 3):
            raise ValueError(f"unsupported GGUF version {version}")
        tensor_count = read_u64(handle)
        metadata_count = read_u64(handle)
        metadata: dict[str, Any] = {}
        for _ in range(metadata_count):
            key = read_string(handle)
            value_type = read_u32(handle)
            value = read_metadata_value(handle, value_type)
            if value is not None:
                metadata[key] = value
        raw_tensors = []
        for _ in range(tensor_count):
            name = read_string(handle)
            dimensions = read_u32(handle)
            shape = tuple(read_u64(handle) for _ in range(dimensions))
            ggml_type = read_u32(handle)
            relative_offset = read_u64(handle)
            raw_tensors.append((name, shape, ggml_type, relative_offset))
        alignment = int(metadata.get("general.alignment", 32))
        if alignment <= 0 or alignment & (alignment - 1):
            raise ValueError(f"invalid GGUF alignment {alignment}")
        data_offset = (handle.tell() + alignment - 1) // alignment * alignment
    file_size = path.stat().st_size
    tensors = []
    for name, shape, ggml_type, relative_offset in raw_tensors:
        if ggml_type != Q4_0_TYPE:
            size = -1
        else:
            size = q4_0_size(shape)
        absolute_offset = data_offset + relative_offset
        if size >= 0 and absolute_offset + size > file_size:
            raise ValueError(f"tensor {name} extends beyond GGUF file")
        tensors.append(TensorInfo(name, shape, ggml_type, relative_offset, absolute_offset, size))
    return {
        "version": version,
        "tensor_count": tensor_count,
        "metadata_count": metadata_count,
        "alignment": alignment,
        "data_offset": data_offset,
        "file_size": file_size,
    }, tensors


def select_m6_tensors(tensors: list[TensorInfo]) -> list[TensorInfo]:
    selected = []
    for tensor in tensors:
        suffix = tensor.name.endswith(".ffn_gate.weight") or tensor.name.endswith(".ffn_up.weight")
        if suffix and tensor.shape == (EXPECTED_K, EXPECTED_N) and tensor.ggml_type == Q4_0_TYPE:
            selected.append(tensor)
    selected.sort(key=lambda item: item.name)
    return selected


def layout_identity() -> dict[str, Any]:
    return {
        "name": LAYOUT_NAME,
        "version": LAYOUT_VERSION,
        "architecture": ARCHITECTURE,
        "quant_region": "[k_block][n16_tile][k8_group][n_lane][8 signed-s4 nibbles]",
        "scale_region": "fp16 [k_block][n_row]",
        "q4_zero_point_transform": "stored_nibble_xor_0x8",
        "endianness": "little",
    }


def tensor_identity(model_sha: str, tensor: TensorInfo) -> dict[str, Any]:
    return {
        "target_model_sha256": model_sha,
        "tensor_name": tensor.name,
        "tensor_shape": list(tensor.shape),
        "tensor_type": "GGML_TYPE_Q4_0",
        "pack_layout_version": LAYOUT_VERSION,
        "target_architecture": ARCHITECTURE,
    }


def require_numpy() -> Any:
    try:
        import numpy as np
    except ImportError as exc:
        raise RuntimeError(
            "NumPy is required for the 6.1 GiB vectorized pack. Run with "
            "/home/steve/.venvs/vllm-xpu/bin/python."
        ) from exc
    return np


def pack_tensor(source_path: Path, tensor: TensorInfo, destination: Path) -> None:
    """Emit the exact protected-runtime q4_0 DPAS-v2 layout."""
    np = require_numpy()
    k, n = tensor.shape
    kb, nt = k // 32, n // 16
    quant_bytes = k * n // 2
    packed_bytes = quant_bytes + kb * n * 2
    source = np.memmap(
        source_path, dtype=np.uint8, mode="r", offset=tensor.absolute_offset,
        shape=(n, kb, Q4_0_BLOCK_BYTES), order="C",
    )
    with destination.open("wb") as handle:
        handle.truncate(packed_bytes)
    output = np.memmap(destination, dtype=np.uint8, mode="r+", shape=(packed_bytes,))
    quants = output[:quant_bytes].reshape(kb, nt, 4, 16, 4)
    source_qs = source[:, :, 2:18].reshape(nt, 16, kb, 16).transpose(2, 0, 1, 3)
    # Work in small K-block chunks to bound temporary allocations while still
    # vectorizing every N tile and lane.
    for block0 in range(0, kb, 8):
        block1 = min(kb, block0 + 8)
        chunk = source_qs[block0:block1]
        for group in range(4):
            base = (group & 1) * 8
            half = group // 2
            values = chunk[..., base:base + 8]
            if half == 0:
                low = values[..., 0::2] & 0x0F
                high = (values[..., 1::2] & 0x0F) << 4
            else:
                low = (values[..., 0::2] >> 4) & 0x0F
                high = values[..., 1::2] & 0xF0
            quants[block0:block1, :, group, :, :] = (low | high) ^ 0x88
    scales = output[quant_bytes:].reshape(kb, n, 2)
    scales[:] = source[:, :, 0:2].transpose(1, 0, 2)
    output.flush()
    del scales, quants, output, source_qs, source


def validate_source(
    args: argparse.Namespace, expected_sha: str, expected_path: Path, expected_size: int | None,
) -> tuple[str, float]:
    started = time.monotonic()
    if args.skip_source_hash:
        if args.model.resolve() != expected_path.resolve():
            raise RuntimeError("--skip-source-hash requires the tracked source-model path")
        if expected_size is not None and args.model.stat().st_size != expected_size:
            raise RuntimeError("--skip-source-hash source-model size mismatch")
        return expected_sha, time.monotonic() - started
    actual, _ = hash_file(args.model)
    if actual != expected_sha:
        raise RuntimeError(f"target model SHA256 mismatch: expected {expected_sha}, got {actual}")
    return actual, time.monotonic() - started


def expected_pack_size(tensor: TensorInfo) -> int:
    k, n = tensor.shape
    return k * n // 2 + (k // 32) * n * 2


def prepare(args: argparse.Namespace) -> int:
    spec = load_json(args.model_spec)
    expected_model_sha = spec["source"]["sha256"]
    model_sha, model_hash_seconds = validate_source(
        args, expected_model_sha, Path(spec["source"]["path"]), spec["source"].get("size_bytes")
    )
    gguf, tensors = read_gguf(args.model)
    selected = select_m6_tensors(tensors)
    if len(selected) != EXPECTED_TENSORS:
        raise RuntimeError(f"expected {EXPECTED_TENSORS} M6 gate/up tensors, found {len(selected)}")
    set_identity = {
        "target_model_sha256": model_sha,
        "target_architecture": ARCHITECTURE,
        "pack_layout_version": LAYOUT_VERSION,
        "tensor_keys": [canonical_sha(tensor_identity(model_sha, tensor)) for tensor in selected],
    }
    set_key = canonical_sha(set_identity)
    root = args.cache_root / set_key
    entries = []
    packed_count = reused_count = 0
    pack_seconds = 0.0
    root.mkdir(parents=True, exist_ok=True)
    (root / "tensors").mkdir(exist_ok=True)
    for index, tensor in enumerate(selected, 1):
        identity = tensor_identity(model_sha, tensor)
        key = canonical_sha(identity)
        payload = root / "tensors" / f"{key}.bin"
        payload_size = expected_pack_size(tensor)
        old = None
        old_manifest = root / "tensors" / f"{key}.json"
        if old_manifest.is_file():
            old = load_json(old_manifest)
        reusable = (
            old is not None and old.get("key") == key and old.get("identity") == identity
            and payload.is_file() and payload.stat().st_size == payload_size
            and old.get("payload", {}).get("size_bytes") == payload_size
        )
        if reusable:
            reused_count += 1
            entry = old
        else:
            temporary = payload.with_name(f".{payload.name}.tmp-{os.getpid()}")
            started = time.monotonic()
            pack_tensor(args.model, tensor, temporary)
            elapsed = time.monotonic() - started
            payload_sha, actual_size = hash_file(temporary)
            source_sha, source_size = hash_file(args.model, tensor.absolute_offset, tensor.size_bytes)
            if actual_size != payload_size:
                temporary.unlink(missing_ok=True)
                raise RuntimeError(f"packed size mismatch for {tensor.name}")
            os.replace(temporary, payload)
            entry = {
                "schema_version": 1,
                "format": "qwen27-xe2-m6-tensor-pack-v2",
                "status": "ready",
                "key": key,
                "identity": identity,
                "source_tensor": {
                    "gguf_offset": tensor.absolute_offset,
                    "size_bytes": source_size,
                    "sha256": source_sha,
                },
                "payload": {
                    "path": f"tensors/{payload.name}",
                    "size_bytes": actual_size,
                    "sha256": payload_sha,
                },
                "pack_seconds": elapsed,
                "created_unix": time.time(),
            }
            atomic_json(old_manifest, entry)
            packed_count += 1
            pack_seconds += elapsed
        entries.append(entry)
        if not args.quiet:
            print(f"[{index:03d}/{len(selected)}] {'reused' if reusable else 'packed'} {tensor.name}", file=sys.stderr)
    manifest = {
        "schema_version": 1,
        "format": "qwen27-xe2-m6-pack-set-v2",
        "status": "ready",
        "evidence_class": "development-initialization-cache-only",
        "promotion_eligible": False,
        "key": set_key,
        "identity": set_identity,
        "source_model": {
            "path": str(args.model.resolve()),
            "sha256": model_sha,
            "size_bytes": args.model.stat().st_size,
            "hash_validated": not args.skip_source_hash,
        },
        "gguf": gguf,
        "layout": layout_identity(),
        "tool": {"path": str(Path(__file__).resolve()), "revision": TOOL_REVISION},
        "tensor_count": len(entries),
        "packed_count_this_run": packed_count,
        "reused_count_this_run": reused_count,
        "payload_size_bytes": sum(item["payload"]["size_bytes"] for item in entries),
        "model_hash_seconds_this_run": model_hash_seconds,
        "pack_seconds_this_run": pack_seconds,
        "tensors": entries,
        "loader_contract": {
            "lookup_fields": [
                "target_model_sha256", "tensor_name", "tensor_shape", "tensor_type",
                "pack_layout_version", "target_architecture",
            ],
            "required_validation": ["set-key", "tensor-key", "payload-size", "payload-sha256"],
            "mmap_safe": True,
        },
        "created_unix": time.time(),
    }
    atomic_json(root / "manifest.json", manifest)
    print(json.dumps({
        "status": "ready", "set_key": set_key, "manifest": str(root / "manifest.json"),
        "tensor_count": len(entries), "packed": packed_count, "reused": reused_count,
        "payload_size_bytes": manifest["payload_size_bytes"],
        "model_hash_seconds": model_hash_seconds, "pack_seconds": pack_seconds,
    }, indent=2))
    return 0


def find_manifest(args: argparse.Namespace) -> Path:
    if args.set_key:
        candidate = args.cache_root / args.set_key / "manifest.json"
        if not candidate.is_file():
            raise FileNotFoundError(candidate)
        return candidate
    candidates = sorted(args.cache_root.glob("*/manifest.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not candidates:
        raise FileNotFoundError(f"no pack-set manifests below {args.cache_root}")
    return candidates[0]


def validate_pack_manifest(
    manifest_path: Path, model_spec: Path, deep: bool,
) -> tuple[dict[str, Any], list[str]]:
    started = time.monotonic()
    manifest = load_json(manifest_path)
    spec = load_json(model_spec)
    failures = []
    if manifest.get("format") != "qwen27-xe2-m6-pack-set-v2":
        failures.append("set-format")
    if canonical_sha(manifest.get("identity")) != manifest.get("key"):
        failures.append("set-key")
    identity = manifest.get("identity", {})
    if identity.get("target_model_sha256") != spec["source"]["sha256"]:
        failures.append("target-model-sha256")
    if identity.get("target_architecture") != ARCHITECTURE:
        failures.append("target-architecture")
    if identity.get("pack_layout_version") != LAYOUT_VERSION:
        failures.append("pack-layout-version")
    if manifest.get("layout") != layout_identity():
        failures.append("layout-contract")
    if manifest.get("tensor_count") != EXPECTED_TENSORS or len(manifest.get("tensors", [])) != EXPECTED_TENSORS:
        failures.append("tensor-count")
    root = manifest_path.parent
    checked_bytes = 0
    actual_tensor_keys = []
    for entry in manifest.get("tensors", []):
        actual_tensor_keys.append(entry.get("key"))
        if canonical_sha(entry.get("identity")) != entry.get("key"):
            failures.append(f"tensor-key:{entry.get('identity', {}).get('tensor_name')}")
            continue
        payload = root / entry["payload"]["path"]
        expected_size = entry["payload"]["size_bytes"]
        if not payload.is_file() or payload.stat().st_size != expected_size:
            failures.append(f"payload-size:{entry['identity']['tensor_name']}")
            continue
        checked_bytes += expected_size
        if deep:
            sha, _ = hash_file(payload)
            if sha != entry["payload"]["sha256"]:
                failures.append(f"payload-sha256:{entry['identity']['tensor_name']}")
    if identity.get("tensor_keys") != actual_tensor_keys:
        failures.append("tensor-key-table")
    elapsed = time.monotonic() - started
    result = {
        "status": "failed" if failures else "ready",
        "validation": "deep" if deep else "shallow",
        "manifest": str(manifest_path),
        "set_key": manifest.get("key"),
        "tensor_count": len(manifest.get("tensors", [])),
        "checked_bytes": checked_bytes,
        "seconds": elapsed,
        "failures": failures,
    }
    return result, failures


def payload_table_sha(manifest: dict[str, Any]) -> str:
    return canonical_sha([
        {
            "key": entry["key"],
            "path": entry["payload"]["path"],
            "size_bytes": entry["payload"]["size_bytes"],
            "sha256": entry["payload"]["sha256"],
        }
        for entry in manifest["tensors"]
    ])


def payload_stat_table_sha(manifest_path: Path, manifest: dict[str, Any]) -> str:
    root = manifest_path.parent
    table = []
    for entry in manifest["tensors"]:
        payload = root / entry["payload"]["path"]
        if not payload.is_file():
            return "missing"
        stat = payload.stat()
        table.append({
            "key": entry["key"], "size_bytes": stat.st_size,
            "mtime_ns": stat.st_mtime_ns, "device": stat.st_dev, "inode": stat.st_ino,
        })
    return canonical_sha(table)


def trust_receipt_path(manifest_path: Path) -> Path:
    return manifest_path.parent / "deep-validation.json"


def trust_receipt_matches(manifest_path: Path, manifest: dict[str, Any]) -> tuple[bool, dict[str, Any] | None]:
    receipt_path = trust_receipt_path(manifest_path)
    if not receipt_path.is_file():
        return False, None
    receipt = load_json(receipt_path)
    manifest_sha, manifest_size = hash_file(manifest_path)
    okay = (
        receipt.get("format") == "qwen27-xe2-m6-deep-validation-v1"
        and receipt.get("set_key") == manifest.get("key")
        and receipt.get("manifest_sha256") == manifest_sha
        and receipt.get("manifest_size_bytes") == manifest_size
        and receipt.get("payload_table_sha256") == payload_table_sha(manifest)
        and receipt.get("payload_stat_table_sha256") == payload_stat_table_sha(manifest_path, manifest)
        and receipt.get("validated_bytes") == manifest.get("payload_size_bytes")
    )
    return okay, receipt


def establish_trust(manifest_path: Path, model_spec: Path) -> tuple[dict[str, Any], bool]:
    manifest = load_json(manifest_path)
    trusted, receipt = trust_receipt_matches(manifest_path, manifest)
    if trusted and receipt is not None:
        return receipt, True
    result, failures = validate_pack_manifest(manifest_path, model_spec, deep=True)
    if failures:
        raise RuntimeError(f"cannot trust invalid disk pack: {', '.join(failures)}")
    manifest_sha, manifest_size = hash_file(manifest_path)
    receipt = {
        "schema_version": 1,
        "format": "qwen27-xe2-m6-deep-validation-v1",
        "status": "trusted",
        "set_key": manifest["key"],
        "manifest_sha256": manifest_sha,
        "manifest_size_bytes": manifest_size,
        "payload_table_sha256": payload_table_sha(manifest),
        "payload_stat_table_sha256": payload_stat_table_sha(manifest_path, manifest),
        "validated_bytes": result["checked_bytes"],
        "deep_validation_seconds": result["seconds"],
        "created_unix": time.time(),
        "trust_boundary": "local immutable artifact; invalidate when manifest identity changes",
    }
    atomic_json(trust_receipt_path(manifest_path), receipt)
    return receipt, False


def verify(args: argparse.Namespace) -> int:
    manifest_path = find_manifest(args)
    result, failures = validate_pack_manifest(manifest_path, args.model_spec, args.deep)
    print(json.dumps(result, indent=2))
    return 1 if failures else 0


def filesystem_available(path: Path) -> int:
    stats = os.statvfs(path)
    return stats.f_bavail * stats.f_frsize


def validate_ram_stage(
    stage: Path, source_manifest_path: Path, model_spec: Path, deep: bool,
) -> tuple[dict[str, Any], list[str]]:
    started = time.monotonic()
    failures: list[str] = []
    source_manifest = load_json(source_manifest_path)
    trusted, trust = trust_receipt_matches(source_manifest_path, source_manifest)
    if not trusted or trust is None:
        failures.append("source-deep-trust")
    stage_manifest_path = stage / "manifest.json"
    stage_receipt_path = stage / "ram-stage.json"
    stage_trust_path = stage / "deep-validation.json"
    if not stage_manifest_path.is_file() or not stage_receipt_path.is_file() or not stage_trust_path.is_file():
        failures.append("ram-metadata")
        return {
            "status": "failed", "stage": str(stage), "validation": "deep" if deep else "trusted-shallow",
            "seconds": time.monotonic() - started, "failures": failures,
        }, failures
    stage_manifest = load_json(stage_manifest_path)
    stage_receipt = load_json(stage_receipt_path)
    stage_trust = load_json(stage_trust_path)
    source_manifest_sha, _ = hash_file(source_manifest_path)
    if stage_manifest != source_manifest:
        failures.append("ram-manifest")
    if trust is not None and stage_trust != trust:
        failures.append("ram-deep-trust")
    if (
        stage_receipt.get("format") != "qwen27-xe2-m6-ram-stage-v1"
        or stage_receipt.get("set_key") != source_manifest.get("key")
        or stage_receipt.get("source_manifest_sha256") != source_manifest_sha
        or stage_receipt.get("payload_table_sha256") != payload_table_sha(source_manifest)
    ):
        failures.append("ram-stage-receipt")
    checked_bytes = 0
    for entry in source_manifest.get("tensors", []):
        payload = stage / entry["payload"]["path"]
        expected_size = entry["payload"]["size_bytes"]
        if not payload.is_file() or payload.stat().st_size != expected_size:
            failures.append(f"ram-payload-size:{entry['identity']['tensor_name']}")
            continue
        checked_bytes += expected_size
        if deep:
            sha, _ = hash_file(payload)
            if sha != entry["payload"]["sha256"]:
                failures.append(f"ram-payload-sha256:{entry['identity']['tensor_name']}")
    result = {
        "status": "failed" if failures else "ready",
        "stage": str(stage),
        "set_key": source_manifest.get("key"),
        "validation": "deep" if deep else "trusted-shallow",
        "tensor_count": len(source_manifest.get("tensors", [])),
        "checked_bytes": checked_bytes,
        "seconds": time.monotonic() - started,
        "available_bytes": filesystem_available(stage.parent),
        "failures": failures,
    }
    return result, failures


def stage_ram(args: argparse.Namespace) -> int:
    overall_started = time.monotonic()
    manifest_path = find_manifest(args)
    manifest = load_json(manifest_path)
    args.ram_root.mkdir(parents=True, exist_ok=True)
    trust_started = time.monotonic()
    trust, trust_reused = establish_trust(manifest_path, args.model_spec)
    trust_seconds = time.monotonic() - trust_started
    final = args.ram_root / manifest["key"]
    if final.exists():
        source_trust_path = trust_receipt_path(manifest_path)
        ram_trust_path = final / "deep-validation.json"
        if not ram_trust_path.is_file() or ram_trust_path.read_bytes() != source_trust_path.read_bytes():
            temporary_trust = final / f".deep-validation.json.tmp-{os.getpid()}"
            shutil.copyfile(source_trust_path, temporary_trust)
            os.replace(temporary_trust, ram_trust_path)
        result, failures = validate_ram_stage(final, manifest_path, args.model_spec, deep=False)
        result["status"] = "reused" if not failures else "failed"
        result["lookup_seconds"] = time.monotonic() - overall_started
        result["source_trust_reused"] = trust_reused
        result["trust_lookup_seconds"] = trust_seconds
        if not failures:
            atomic_json(manifest_path.parent / "last-ram-lookup.json", result)
        print(json.dumps(result, indent=2))
        return 1 if failures else 0

    payload_bytes = manifest["payload_size_bytes"]
    available_before = filesystem_available(args.ram_root)
    if available_before - payload_bytes < args.min_free_bytes:
        raise RuntimeError(
            f"insufficient RAM-stage headroom: available={available_before} payload={payload_bytes} "
            f"required_free={args.min_free_bytes}"
        )
    staging = args.ram_root / f".{manifest['key']}.tmp-{os.getpid()}"
    if staging.exists():
        raise RuntimeError(f"staging path already exists: {staging}")
    copy_started = time.monotonic()
    staging.mkdir()
    try:
        (staging / "tensors").mkdir()
        for entry in manifest["tensors"]:
            source = manifest_path.parent / entry["payload"]["path"]
            destination = staging / entry["payload"]["path"]
            shutil.copyfile(source, destination)
        shutil.copyfile(manifest_path, staging / "manifest.json")
        shutil.copyfile(trust_receipt_path(manifest_path), staging / "deep-validation.json")
        copy_seconds = time.monotonic() - copy_started
        available_after_copy = filesystem_available(args.ram_root)
        source_manifest_sha, _ = hash_file(manifest_path)
        stage_receipt = {
            "schema_version": 1,
            "format": "qwen27-xe2-m6-ram-stage-v1",
            "status": "ready",
            "set_key": manifest["key"],
            "source_manifest": str(manifest_path),
            "source_manifest_sha256": source_manifest_sha,
            "payload_table_sha256": payload_table_sha(manifest),
            "payload_size_bytes": payload_bytes,
            "tensor_count": len(manifest["tensors"]),
            "source_deep_trust_reused": trust_reused,
            "source_deep_validation_seconds": trust["deep_validation_seconds"],
            "trust_lookup_seconds_this_run": trust_seconds,
            "copy_seconds": copy_seconds,
            "available_bytes_before": available_before,
            "available_bytes_after_copy": available_after_copy,
            "created_unix": time.time(),
        }
        atomic_json(staging / "ram-stage.json", stage_receipt)
        os.replace(staging, final)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    result, failures = validate_ram_stage(final, manifest_path, args.model_spec, deep=False)
    result.update({
        "status": "staged" if not failures else "failed",
        "cold_stage_seconds": time.monotonic() - overall_started,
        "copy_seconds": copy_seconds,
        "source_trust_reused": trust_reused,
        "available_bytes_before": available_before,
        "available_bytes_after": filesystem_available(args.ram_root),
    })
    if not failures:
        atomic_json(manifest_path.parent / "last-ram-stage.json", result)
    print(json.dumps(result, indent=2))
    return 1 if failures else 0


def stage_validate(args: argparse.Namespace) -> int:
    manifest_path = find_manifest(args)
    manifest = load_json(manifest_path)
    stage = args.ram_root / manifest["key"]
    if not stage.is_dir():
        raise FileNotFoundError(stage)
    result, failures = validate_ram_stage(stage, manifest_path, args.model_spec, args.deep)
    if not failures and not args.deep:
        atomic_json(manifest_path.parent / "last-ram-lookup.json", result)
    print(json.dumps(result, indent=2))
    return 1 if failures else 0


def inspect(args: argparse.Namespace) -> int:
    spec = load_json(args.model_spec)
    gguf, tensors = read_gguf(args.model)
    selected = select_m6_tensors(tensors)
    print(json.dumps({
        "status": "inspect",
        "model": str(args.model),
        "expected_model_sha256": spec["source"]["sha256"],
        "gguf": gguf,
        "selected_tensor_count": len(selected),
        "expected_tensor_count": EXPECTED_TENSORS,
        "expected_pack_size_bytes": sum(expected_pack_size(tensor) for tensor in selected),
        "first_tensor": selected[0].name if selected else None,
        "last_tensor": selected[-1].name if selected else None,
    }, indent=2))
    return 0 if len(selected) == EXPECTED_TENSORS else 1


def self_test() -> int:
    k, n = 32, 16
    rng = random.Random(0xB70)
    source = bytearray()
    for row in range(n):
        source.extend(bytes((row, 255 - row)))
        source.extend(bytes(rng.randrange(256) for _ in range(16)))
    with tempfile.TemporaryDirectory(prefix="qwen27-xe2-m6-pack-test-") as directory:
        source_path = Path(directory) / "source.bin"
        packed_path = Path(directory) / "packed.bin"
        source_path.write_bytes(source)
        tensor = TensorInfo("self-test", (k, n), Q4_0_TYPE, 0, 0, len(source))
        pack_tensor(source_path, tensor, packed_path)
        quant = bytearray(k * n // 2)
        scales = bytearray(n * 2)
        for row in range(n):
            block = source[row * Q4_0_BLOCK_BYTES:(row + 1) * Q4_0_BLOCK_BYTES]
            scales[row * 2:row * 2 + 2] = block[:2]
            for ki in range(32):
                stored = block[2 + (ki & 15)]
                signed = ((stored >> (4 * (ki // 16))) & 0x0F) ^ 0x08
                nibble = (((ki // 8) * 16 + row) * 8 + ki % 8)
                quant[nibble // 2] |= signed << (4 * (nibble & 1))
        expected = bytes(quant + scales)
        actual = packed_path.read_bytes()
    if actual != expected:
        raise RuntimeError("vectorized DPAS-v2 pack differs from scalar contract")
    print(json.dumps({
        "status": "passed", "source_size_bytes": len(source),
        "payload_size_bytes": len(actual), "payload_sha256": hashlib.sha256(actual).hexdigest(),
    }, indent=2))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("inspect", "self-test", "prepare", "verify", "stage-ram", "stage-validate")
    )
    parser.add_argument("--model-spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--ram-root", type=Path, default=DEFAULT_RAM_ROOT)
    parser.add_argument("--set-key")
    parser.add_argument("--skip-source-hash", action="store_true",
                        help="trust the SHA256 recorded in model-pack-manifest.json")
    parser.add_argument("--deep", action="store_true", help="rehash every cached payload")
    parser.add_argument("--min-free-bytes", type=int, default=8 * 1024**3,
                        help="minimum /dev/shm headroom retained after staging")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    if args.model is None:
        args.model = Path(load_json(args.model_spec)["source"]["path"])
    if args.command in ("inspect", "prepare") and not args.model.is_file():
        parser.error(f"model does not exist: {args.model}")
    return args


def main() -> int:
    args = parse_args()
    if args.command == "inspect":
        return inspect(args)
    if args.command == "self-test":
        return self_test()
    if args.command == "prepare":
        return prepare(args)
    if args.command == "verify":
        return verify(args)
    if args.command == "stage-ram":
        return stage_ram(args)
    if args.command == "stage-validate":
        return stage_validate(args)
    raise AssertionError(args.command)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
