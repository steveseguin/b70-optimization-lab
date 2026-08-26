#!/usr/bin/env python3
"""Build a revision-bound, portable 0731 DSpark draft-only pack.

The default is a metadata-only plan. Payload copying and hashing require both
``--execute`` and the frozen acknowledgement. The source checkpoint is never
modified, and promotion is an atomic rename from an explicit sibling staging
directory.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import struct
import sys
from typing import Any


VERIFIER_PATH = Path(__file__).with_name("verify-0731-reap-artifact.py")
VERIFIER_SPEC = importlib.util.spec_from_file_location(
    "verify_0731_reap_artifact_for_draft_pack", VERIFIER_PATH
)
assert VERIFIER_SPEC and VERIFIER_SPEC.loader
VERIFIER = importlib.util.module_from_spec(VERIFIER_SPEC)
VERIFIER_SPEC.loader.exec_module(VERIFIER)

SCHEMA = "deepseek-v4-0731-dspark-draft-pack-v1"
ACK = "BUILD_0731_DSPARK_DRAFT_PACK_DDC04540"
REVISION = "ddc04540efda3d2a0788b129f1fad828ddc19b60"
SOURCE_REVISION = "9e165c30e2704aec5d9d593cce3eebd58bbef1cb"
EXPECTED_STAGES = {"0", "1", "2"}
EXPECTED_SHARDS = {
    "model-00046-of-00048.safetensors",
    "model-00047-of-00048.safetensors",
    "model-00048-of-00048.safetensors",
}
EXPECTED_MTP_TENSORS = 2_977
EXPECTED_TOTAL_TENSORS = 45_821
EXPECTED_SOURCE_TENSOR_BYTES = 107_803_320_952
EXPECTED_DRAFT_TENSOR_BYTES = 7_010_106_780
EXPECTED_SHARD_BYTES = {
    "model-00046-of-00048.safetensors": 2_326_148_888,
    "model-00047-of-00048.safetensors": 2_275_805_664,
    "model-00048-of-00048.safetensors": 2_408_468_964,
}
EXPECTED_SHARD_TENSORS = {
    "model-00046-of-00048.safetensors": 992,
    "model-00047-of-00048.safetensors": 989,
    "model-00048-of-00048.safetensors": 996,
}
EXPECTED_SHARD_TENSOR_BYTES = {
    "model-00046-of-00048.safetensors": 2_326_043_608,
    "model-00047-of-00048.safetensors": 2_275_700_696,
    "model-00048-of-00048.safetensors": 2_408_362_476,
}
RECEIPT_SIDECARS = (
    "deepseek-v4-flash-0731-reap-hashes.jsonl",
    "deepseek-v4-flash-0731-reap-headers.jsonl",
    "deepseek-v4-flash-0731-reap-dry-run.stdout.json",
)


class PackError(RuntimeError):
    pass


@dataclass(frozen=True)
class Prepared:
    plan: dict[str, Any]
    draft_map: dict[str, str]
    config_bytes: bytes
    source_index_bytes: bytes


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PackError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json_bytes(raw: bytes, label: str) -> Any:
    try:
        return json.loads(raw, object_pairs_hook=strict_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackError(f"cannot parse strict JSON {label}: {exc}") from exc


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb", buffering=0) as handle:
        while chunk := handle.read(16 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return sha256_bytes(raw)


def publisher_hashes(path: Path) -> dict[str, str]:
    pattern = re.compile(r"^([0-9a-f]{64})  ([^\\\0]+)$")
    result: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise PackError(f"cannot read publisher checksum manifest: {exc}") from exc
    for line in lines:
        match = pattern.fullmatch(line)
        if not match:
            raise PackError("malformed publisher checksum manifest")
        name = match.group(2)
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or name in result:
            raise PackError(f"unsafe or duplicate publisher checksum path: {name!r}")
        result[name] = match.group(1)
    return result


def require_config(config: Any) -> None:
    if not isinstance(config, dict):
        raise PackError("config must be a JSON object")
    required = {
        "architectures": ["DeepseekV4ForCausalLM"],
        "model_type": "deepseek_v4",
        "dspark_block_size": 5,
        "dspark_markov_rank": 256,
        "dspark_target_layer_ids": [40, 41, 42],
        "hidden_size": 4096,
        "vocab_size": 129280,
    }
    mismatched = {
        key: {"expected": expected, "actual": config.get(key)}
        for key, expected in required.items()
        if config.get(key) != expected
    }
    if mismatched:
        raise PackError(f"0731 DSpark config identity mismatch: {mismatched}")


def select_draft_map(index: Any) -> dict[str, str]:
    if not isinstance(index, dict) or not isinstance(index.get("weight_map"), dict):
        raise PackError("source index lacks a weight_map object")
    weight_map = index["weight_map"]
    if len(weight_map) != EXPECTED_TOTAL_TENSORS:
        raise PackError(
            f"source tensor count {len(weight_map)} != {EXPECTED_TOTAL_TENSORS}"
        )
    try:
        source_total = int(index.get("metadata", {}).get("total_size", -1))
    except (TypeError, ValueError) as exc:
        raise PackError("source index total_size is invalid") from exc
    if source_total != EXPECTED_SOURCE_TENSOR_BYTES:
        raise PackError("source index total_size mismatch")
    if any(
        not isinstance(name, str) or not isinstance(shard, str)
        for name, shard in weight_map.items()
    ):
        raise PackError("source weight_map entries must be string pairs")

    draft_map = {
        name: shard for name, shard in weight_map.items() if name.startswith("mtp.")
    }
    if len(draft_map) != EXPECTED_MTP_TENSORS:
        raise PackError(f"MTP tensor count {len(draft_map)} != {EXPECTED_MTP_TENSORS}")
    stages: set[str] = set()
    for name in draft_map:
        parts = name.split(".", 2)
        if len(parts) != 3:
            raise PackError(f"malformed MTP tensor name: {name}")
        stages.add(parts[1])
    if stages != EXPECTED_STAGES:
        raise PackError(f"MTP stages {sorted(stages)} != {sorted(EXPECTED_STAGES)}")
    if set(draft_map.values()) != EXPECTED_SHARDS:
        raise PackError("MTP shard placement does not equal pinned shards 46-48")
    selected_entries = {
        name for name, shard in weight_map.items() if shard in EXPECTED_SHARDS
    }
    if selected_entries != set(draft_map):
        extra = sorted(selected_entries - set(draft_map))
        raise PackError(
            f"selected MTP shards contain non-MTP index entries: {extra[:5]}"
        )
    observed_counts = {
        shard: sum(value == shard for value in draft_map.values())
        for shard in EXPECTED_SHARDS
    }
    if observed_counts != EXPECTED_SHARD_TENSORS:
        raise PackError(f"per-shard MTP tensor counts mismatch: {observed_counts}")
    return dict(sorted(draft_map.items()))


def validate_paths(source: Path, output: Path, staging: Path) -> None:
    if output == staging:
        raise PackError("output and staging paths must differ")
    if output.parent != staging.parent:
        raise PackError(
            "staging must be an explicit sibling of output for atomic rename"
        )
    if output == source or source in output.parents:
        raise PackError("output must stay outside the source checkpoint")
    if staging == source or source in staging.parents:
        raise PackError("staging must stay outside the source checkpoint")
    if output.exists():
        raise PackError(f"refusing to replace existing output: {output}")
    if staging.exists():
        raise PackError(f"refusing to reuse existing staging path: {staging}")


def prepare(source: Path, output: Path, staging: Path, receipt: Path) -> Prepared:
    source = source.resolve()
    output = output.resolve(strict=False)
    staging = staging.resolve(strict=False)
    receipt = receipt.resolve()
    if not receipt.is_file():
        raise PackError(f"completed validation receipt is missing: {receipt}")
    validate_paths(source, output, staging)

    try:
        verification = VERIFIER.validate(source, receipt)
    except VERIFIER.VerificationError as exc:
        raise PackError(f"0731 source verification failed: {exc}") from exc
    if (
        verification.get("status") != "pass"
        or verification.get("revision") != REVISION
        or Path(str(verification.get("crypto_receipt", ""))).resolve() != receipt
    ):
        raise PackError("source verifier did not bind the completed ddc04540 receipt")

    config_path = source / "config.json"
    index_path = source / "model.safetensors.index.json"
    config_bytes = config_path.read_bytes()
    source_index_bytes = index_path.read_bytes()
    config = load_json_bytes(config_bytes, str(config_path))
    source_index = load_json_bytes(source_index_bytes, str(index_path))
    require_config(config)
    draft_map = select_draft_map(source_index)

    publisher_manifest_path = source / "SHA256SUMS"
    published = publisher_hashes(publisher_manifest_path)
    config_sha = sha256_bytes(config_bytes)
    source_index_sha = sha256_bytes(source_index_bytes)
    for name, observed in {
        "config.json": config_sha,
        "model.safetensors.index.json": source_index_sha,
    }.items():
        if published.get(name) != observed:
            raise PackError(f"publisher checksum mismatch for source {name}")

    shards = []
    for name in sorted(EXPECTED_SHARDS):
        path = source / name
        if path.is_symlink() or not path.is_file():
            raise PackError(f"source shard must be a regular non-symlink file: {name}")
        if path.stat().st_size != EXPECTED_SHARD_BYTES[name]:
            raise PackError(f"source shard size mismatch: {name}")
        publisher_sha = published.get(name)
        if not isinstance(publisher_sha, str):
            raise PackError(f"publisher checksum is missing for {name}")
        shards.append(
            {
                "name": name,
                "file_bytes": EXPECTED_SHARD_BYTES[name],
                "tensor_count": EXPECTED_SHARD_TENSORS[name],
                "tensor_payload_bytes": EXPECTED_SHARD_TENSOR_BYTES[name],
                "publisher_sha256": publisher_sha,
            }
        )

    sidecars = []
    for name in RECEIPT_SIDECARS:
        path = receipt.parent / name
        if not path.is_file():
            raise PackError(f"completed receipt sidecar is missing: {name}")
        sidecars.append({"name": name, "sha256": sha256_file(path)})

    plan = {
        "schema": SCHEMA,
        "mode": "metadata_only_plan",
        "payload_reads": False,
        "writes": False,
        "source": {
            "path": str(source),
            "repo_id": "0xSero/DeepSeek-V4-Flash-0731-REAP",
            "revision": REVISION,
            "source_model": "deepseek-ai/DeepSeek-V4-Flash-0731",
            "source_revision": SOURCE_REVISION,
            "validation_receipt": {
                "path": str(receipt),
                "sha256": sha256_file(receipt),
                "sidecars": sidecars,
            },
            "verifier_result": verification,
            "publisher_manifest_sha256": sha256_file(publisher_manifest_path),
            "config_sha256": config_sha,
            "index_sha256": source_index_sha,
        },
        "selection": {
            "prefix": "mtp.",
            "tensor_count": len(draft_map),
            "tensor_names_sha256": canonical_sha256(sorted(draft_map)),
            "stages": sorted(EXPECTED_STAGES),
            "logical_tensor_bytes": EXPECTED_DRAFT_TENSOR_BYTES,
            "physical_shard_bytes": sum(EXPECTED_SHARD_BYTES.values()),
            "shards": shards,
        },
        "destination": {"staging": str(staging), "output": str(output)},
    }
    return Prepared(plan, draft_map, config_bytes, source_index_bytes)


def exclusive_write(path: Path, raw: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o444)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)


def copy_and_hash(source: Path, destination: Path) -> str:
    source_flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        source_flags |= os.O_NOFOLLOW
    source_descriptor = os.open(source, source_flags)
    if not stat.S_ISREG(os.fstat(source_descriptor).st_mode):
        os.close(source_descriptor)
        raise PackError(f"source payload is not a regular file: {source}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(destination, flags, 0o444)
    except OSError:
        os.close(source_descriptor)
        raise
    digest = hashlib.sha256()
    try:
        with (
            os.fdopen(source_descriptor, "rb", buffering=0, closefd=False) as reader,
            os.fdopen(descriptor, "wb", closefd=False) as writer,
        ):
            while chunk := reader.read(16 * 1024 * 1024):
                digest.update(chunk)
                writer.write(chunk)
            writer.flush()
            os.fsync(writer.fileno())
    finally:
        os.close(source_descriptor)
        os.close(descriptor)
    return digest.hexdigest()


def read_safetensors_header(path: Path) -> tuple[dict[str, Any], int]:
    size = path.stat().st_size
    with path.open("rb", buffering=0) as handle:
        raw_length = handle.read(8)
        if len(raw_length) != 8:
            raise PackError(f"short safetensors file: {path}")
        header_size = struct.unpack("<Q", raw_length)[0]
        if header_size <= 0 or 8 + header_size > size:
            raise PackError(f"invalid safetensors header size: {path}")
        header = load_json_bytes(handle.read(header_size), str(path))
    if not isinstance(header, dict):
        raise PackError(f"safetensors header is not an object: {path}")
    tensors = {key: value for key, value in header.items() if key != "__metadata__"}
    payload_bytes = size - 8 - header_size
    ranges: list[tuple[int, int]] = []
    for name, entry in tensors.items():
        offsets = entry.get("data_offsets") if isinstance(entry, dict) else None
        if (
            not isinstance(offsets, list)
            or len(offsets) != 2
            or not all(isinstance(value, int) for value in offsets)
        ):
            raise PackError(f"invalid tensor offsets for {name} in {path}")
        start, end = offsets
        if start < 0 or end < start or end > payload_bytes:
            raise PackError(f"out-of-range tensor offsets for {name} in {path}")
        if end > start:
            ranges.append((start, end))
    cursor = 0
    for start, end in sorted(ranges):
        if start != cursor:
            raise PackError(f"gap or overlap in safetensors payload: {path}")
        cursor = end
    if cursor != payload_bytes:
        raise PackError(f"unindexed safetensors payload bytes: {path}")
    return tensors, payload_bytes


def draft_index(draft_map: dict[str, str]) -> dict[str, Any]:
    return {
        "metadata": {
            "total_size": EXPECTED_DRAFT_TENSOR_BYTES,
            "draft_only": True,
            "draft_prefix": "mtp.",
            "source_revision": REVISION,
        },
        "weight_map": draft_map,
    }


def validate_staging(
    staging: Path,
    prepared: Prepared,
    observed_shards: dict[str, dict[str, str]],
    *,
    expect_manifest: bool,
    expected_manifest: dict[str, Any] | None = None,
) -> None:
    expected_names = {
        "config.json",
        "model.safetensors.index.json",
        *EXPECTED_SHARDS,
    }
    if expect_manifest:
        expected_names.add("draft-pack-manifest.json")
    actual_names = {path.name for path in staging.iterdir()}
    if actual_names != expected_names:
        raise PackError(
            f"staging inventory mismatch: missing={sorted(expected_names - actual_names)} "
            f"extra={sorted(actual_names - expected_names)}"
        )
    for path in staging.iterdir():
        if path.is_symlink() or not path.is_file():
            raise PackError(
                f"pack entry is not a regular non-symlink file: {path.name}"
            )
    if sha256_file(staging / "config.json") != prepared.plan["source"]["config_sha256"]:
        raise PackError("destination config hash mismatch")
    actual_index = load_json_bytes(
        (staging / "model.safetensors.index.json").read_bytes(),
        "destination draft index",
    )
    if actual_index != draft_index(prepared.draft_map):
        raise PackError("destination draft index identity mismatch")
    if expect_manifest:
        actual_manifest = load_json_bytes(
            (staging / "draft-pack-manifest.json").read_bytes(),
            "destination draft manifest",
        )
        if expected_manifest is None or actual_manifest != expected_manifest:
            raise PackError("destination draft manifest identity mismatch")

    logical_total = 0
    for shard in prepared.plan["selection"]["shards"]:
        name = shard["name"]
        path = staging / name
        if path.stat().st_size != shard["file_bytes"]:
            raise PackError(f"destination shard size mismatch: {name}")
        assigned = {
            tensor for tensor, mapped in prepared.draft_map.items() if mapped == name
        }
        header, payload_bytes = read_safetensors_header(path)
        if set(header) != assigned or len(header) != shard["tensor_count"]:
            raise PackError(f"destination shard tensor closure mismatch: {name}")
        if payload_bytes != shard["tensor_payload_bytes"]:
            raise PackError(f"destination shard tensor bytes mismatch: {name}")
        logical_total += payload_bytes
        observed = observed_shards.get(name, {})
        if (
            observed.get("source_sha256") != shard["publisher_sha256"]
            or observed.get("destination_sha256") != shard["publisher_sha256"]
        ):
            raise PackError(f"source/destination shard checksum mismatch: {name}")
    if logical_total != EXPECTED_DRAFT_TENSOR_BYTES:
        raise PackError("destination aggregate tensor bytes mismatch")


def execute(prepared: Prepared, ack: str) -> dict[str, Any]:
    if ack != ACK:
        raise PackError(f"execution requires --ack {ACK}")
    source = Path(prepared.plan["source"]["path"])
    staging = Path(prepared.plan["destination"]["staging"])
    output = Path(prepared.plan["destination"]["output"])
    validate_paths(source, output, staging)
    if not output.parent.is_dir():
        raise PackError(f"output parent does not exist: {output.parent}")

    # Recheck small source metadata immediately before the first write.
    if sha256_file(source / "config.json") != prepared.plan["source"]["config_sha256"]:
        raise PackError("source config changed after planning")
    if (
        sha256_file(source / "model.safetensors.index.json")
        != prepared.plan["source"]["index_sha256"]
    ):
        raise PackError("source index changed after planning")
    if (
        sha256_file(source / "SHA256SUMS")
        != prepared.plan["source"]["publisher_manifest_sha256"]
    ):
        raise PackError("publisher checksum manifest changed after planning")
    receipt = prepared.plan["source"]["validation_receipt"]
    if sha256_file(Path(receipt["path"])) != receipt["sha256"]:
        raise PackError("validation receipt changed after planning")
    for sidecar in receipt["sidecars"]:
        path = Path(receipt["path"]).parent / sidecar["name"]
        if sha256_file(path) != sidecar["sha256"]:
            raise PackError(f"validation receipt sidecar changed: {sidecar['name']}")

    staging.mkdir(mode=0o755)
    exclusive_write(staging / "config.json", prepared.config_bytes)
    rendered_index = (
        json.dumps(draft_index(prepared.draft_map), indent=2, sort_keys=True).encode()
        + b"\n"
    )
    exclusive_write(staging / "model.safetensors.index.json", rendered_index)

    observed_shards: dict[str, dict[str, str]] = {}
    for shard in prepared.plan["selection"]["shards"]:
        name = shard["name"]
        source_sha = copy_and_hash(source / name, staging / name)
        if source_sha != shard["publisher_sha256"]:
            raise PackError(f"source payload checksum mismatch during copy: {name}")
        destination_sha = sha256_file(staging / name)
        observed_shards[name] = {
            "source_sha256": source_sha,
            "destination_sha256": destination_sha,
        }
    validate_staging(staging, prepared, observed_shards, expect_manifest=False)

    manifest = {
        **prepared.plan,
        "mode": "executed_and_validated",
        "payload_reads": True,
        "writes": True,
        "draft_index_sha256": sha256_bytes(rendered_index),
        "shard_hashes": observed_shards,
        "validation": {
            "status": "pass",
            "no_symlinks": True,
            "index_header_closure": True,
            "destination_full_hashes": True,
            "atomic_sibling_promotion": True,
        },
    }
    rendered_manifest = json.dumps(manifest, indent=2, sort_keys=True).encode() + b"\n"
    exclusive_write(staging / "draft-pack-manifest.json", rendered_manifest)
    validate_staging(
        staging,
        prepared,
        observed_shards,
        expect_manifest=True,
        expected_manifest=manifest,
    )

    directory_fd = os.open(staging, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    if output.exists():
        raise PackError(f"output appeared before atomic promotion: {output}")
    os.rename(staging, output)
    parent_fd = os.open(output.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)
    return {
        "status": "pass",
        "output": str(output),
        "manifest": str(output / "draft-pack-manifest.json"),
        "manifest_sha256": sha256_bytes(rendered_manifest),
        "tensor_count": EXPECTED_MTP_TENSORS,
        "logical_tensor_bytes": EXPECTED_DRAFT_TENSOR_BYTES,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--ack", default="")
    args = parser.parse_args(argv)

    prepared = prepare(args.source, args.output, args.staging, args.receipt)
    if not args.execute:
        print(json.dumps(prepared.plan, indent=2, sort_keys=True))
        return 0
    print(json.dumps(execute(prepared, args.ack), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PackError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
