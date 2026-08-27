#!/usr/bin/env python3
"""Verify one relocated Qwen3.8 Flash-Next FP8 tree against its pinned identity.

The model root is configurable, but the model revision and artifact contract are
not.  The verifier reads the Hugging Face tree metadata stored below the model,
checks the exact root inventory, and hashes every declared artifact.  It does
not contact Hugging Face or read a token.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CHUNK_BYTES = 16 * 1024 * 1024
RECEIPT_FORMAT = "qwen38-flash-next-fp8-tree-verification-v1"


class VerificationError(RuntimeError):
    """The candidate tree failed its frozen artifact contract."""


@dataclass(frozen=True)
class Contract:
    repo_id: str
    revision: str
    tree_metadata_sha256: str
    root_file_count: int
    root_total_bytes: int
    shard_count: int
    config_sha256: str
    index_sha256: str


PINNED = Contract(
    repo_id="Qwen/Qwen3.8-Flash-Next-FP8",
    revision="bcd9f01ddc9cff2316eb84281bebcd5b058bddce",
    tree_metadata_sha256="4a3793bd4a795ea6761b3d322200b4a1fd8300cdeb75cc127d330d513f590eb2",
    root_file_count=144,
    root_total_bytes=185_563_783_127,
    shard_count=131,
    config_sha256="99c11efba4012d0f760f4e4831a8d6cafd845044e21d0aa9e6d9e70a15a90a8d",
    index_sha256="0419e2c2dfbb925257d7409405433a793cf7ff7d96f3eba882a815ec6d9fe7a6",
)


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise VerificationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=strict_object
        )
    except VerificationError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"cannot read strict JSON {path}: {exc}") from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb", buffering=0) as stream:
            while chunk := stream.read(CHUNK_BYTES):
                digest.update(chunk)
    except OSError as exc:
        raise VerificationError(f"cannot hash {path}: {exc}") from exc
    return digest.hexdigest()


def git_blob_sha1(path: Path, size: int) -> str:
    digest = hashlib.sha1(f"blob {size}\0".encode("ascii"))
    try:
        with path.open("rb", buffering=0) as stream:
            while chunk := stream.read(CHUNK_BYTES):
                digest.update(chunk)
    except OSError as exc:
        raise VerificationError(f"cannot hash {path}: {exc}") from exc
    return digest.hexdigest()


def root_filename(value: object) -> str:
    if not isinstance(value, str) or not value or "\0" in value or "\\" in value:
        raise VerificationError(f"unsafe metadata filename: {value!r}")
    path = Path(value)
    if path.is_absolute() or len(path.parts) != 1 or path.name in {".", ".."}:
        raise VerificationError(f"metadata entry is not a root filename: {value!r}")
    return value


def regular_file(path: Path, label: str) -> os.stat_result:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise VerificationError(f"cannot inspect {label} {path}: {exc}") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise VerificationError(f"{label} is not a regular file: {path}")
    return metadata


def expected_shards(count: int) -> set[str]:
    return {
        f"model-{number:05d}-of-{count:05d}.safetensors"
        for number in range(1, count + 1)
    }


def load_tree_metadata(
    root: Path, contract: Contract
) -> tuple[Path, dict[str, dict[str, Any]]]:
    metadata_path = (
        root / ".cache" / "huggingface" / "trees" / f"{contract.revision}.json"
    )
    regular_file(metadata_path, "Hugging Face tree metadata")
    actual_metadata_sha = sha256_file(metadata_path)
    if actual_metadata_sha != contract.tree_metadata_sha256:
        raise VerificationError(
            "Hugging Face tree metadata SHA-256 mismatch: "
            f"expected {contract.tree_metadata_sha256}, got {actual_metadata_sha}"
        )

    payload = load_json(metadata_path)
    if not isinstance(payload, dict):
        raise VerificationError("invalid Hugging Face tree metadata format")
    files = payload.get("files")
    if payload.get("format_version") != 1 or not isinstance(files, dict):
        raise VerificationError("invalid Hugging Face tree metadata format")

    normalized: dict[str, dict[str, Any]] = {}
    for raw_name, raw_metadata in files.items():
        name = root_filename(raw_name)
        if not isinstance(raw_metadata, dict):
            raise VerificationError(f"invalid metadata object for {name}")
        size = raw_metadata.get("size")
        blob_id = raw_metadata.get("blob_id")
        lfs_sha256 = raw_metadata.get("lfs_sha256")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise VerificationError(f"invalid declared size for {name}")
        if not isinstance(blob_id, str) or not re.fullmatch(r"[0-9a-f]{40}", blob_id):
            raise VerificationError(f"invalid Git blob ID for {name}")
        if lfs_sha256 is not None and (
            not isinstance(lfs_sha256, str)
            or not re.fullmatch(r"[0-9a-f]{64}", lfs_sha256)
        ):
            raise VerificationError(f"invalid LFS SHA-256 for {name}")
        normalized[name] = {
            "size": size,
            "blob_id": blob_id,
            "lfs_sha256": lfs_sha256,
        }

    if len(normalized) != contract.root_file_count:
        raise VerificationError(
            f"declared root file count is {len(normalized)}, expected {contract.root_file_count}"
        )
    declared_bytes = sum(item["size"] for item in normalized.values())
    if declared_bytes != contract.root_total_bytes:
        raise VerificationError(
            f"declared root bytes are {declared_bytes}, expected {contract.root_total_bytes}"
        )
    return metadata_path, normalized


def actual_root_files(root: Path) -> set[str]:
    try:
        entries = list(root.iterdir())
    except OSError as exc:
        raise VerificationError(f"cannot list model root {root}: {exc}") from exc
    actual: set[str] = set()
    for path in entries:
        if path.name == ".cache":
            if not path.is_dir() or path.is_symlink():
                raise VerificationError("model .cache is not a real directory")
            continue
        regular_file(path, "model artifact")
        actual.add(path.name)
    return actual


def validate_index(
    root: Path, files: dict[str, dict[str, Any]], contract: Contract
) -> tuple[dict[str, Any], set[str]]:
    config_path = root / "config.json"
    index_path = root / "model.safetensors.index.json"
    if sha256_file(config_path) != contract.config_sha256:
        raise VerificationError("config.json fixed SHA-256 mismatch")
    if sha256_file(index_path) != contract.index_sha256:
        raise VerificationError("model index fixed SHA-256 mismatch")

    index = load_json(index_path)
    weight_map = index.get("weight_map") if isinstance(index, dict) else None
    if not isinstance(weight_map, dict) or not weight_map:
        raise VerificationError("model index has no weight_map")

    referenced: set[str] = set()
    for tensor_name, raw_shard in weight_map.items():
        if not isinstance(tensor_name, str) or not tensor_name:
            raise VerificationError("model index has an invalid tensor name")
        shard = root_filename(raw_shard)
        referenced.add(shard)

    expected = expected_shards(contract.shard_count)
    declared = {
        name
        for name in files
        if re.fullmatch(r"model-\d{5}-of-\d{5}\.safetensors", name)
    }
    if referenced != expected:
        raise VerificationError(
            f"indexed shard set mismatch: indexed={len(referenced)}, expected={len(expected)}"
        )
    if declared != expected:
        raise VerificationError(
            f"declared shard set mismatch: declared={len(declared)}, expected={len(expected)}"
        )
    for shard in expected:
        if shard not in files or files[shard]["lfs_sha256"] is None:
            raise VerificationError(f"indexed shard lacks pinned LFS metadata: {shard}")
    return index, referenced


def verify_tree(root: Path, contract: Contract = PINNED) -> dict[str, Any]:
    root = root.resolve()
    if not root.is_dir():
        raise VerificationError(f"model root is not a directory: {root}")

    metadata_path, files = load_tree_metadata(root, contract)
    actual = actual_root_files(root)
    expected = set(files)
    if actual != expected:
        raise VerificationError(
            "root inventory mismatch: "
            f"missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
        )

    verified: list[dict[str, Any]] = []
    actual_bytes = 0
    for name in sorted(files):
        declared = files[name]
        path = root / name
        metadata = regular_file(path, "model artifact")
        if metadata.st_size != declared["size"]:
            raise VerificationError(
                f"size mismatch for {name}: expected {declared['size']}, got {metadata.st_size}"
            )
        actual_bytes += metadata.st_size
        if declared["lfs_sha256"] is not None:
            digest_kind = "lfs_sha256"
            expected_digest = declared["lfs_sha256"]
            actual_digest = sha256_file(path)
        else:
            digest_kind = "git_blob_sha1"
            expected_digest = declared["blob_id"]
            actual_digest = git_blob_sha1(path, metadata.st_size)
        if actual_digest != expected_digest:
            raise VerificationError(f"{digest_kind} mismatch for {name}")
        verified.append(
            {
                "path": name,
                "size": metadata.st_size,
                "digest_kind": digest_kind,
                "digest": actual_digest,
            }
        )

    if actual_bytes != contract.root_total_bytes:
        raise VerificationError(
            f"actual root bytes are {actual_bytes}, expected {contract.root_total_bytes}"
        )
    index, shards = validate_index(root, files, contract)
    return {
        "status": "pass",
        "format": RECEIPT_FORMAT,
        "completed_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model_root": str(root),
        "metadata_path": str(metadata_path),
        "contract": asdict(contract),
        "observed": {
            "root_file_count": len(actual),
            "root_total_bytes": actual_bytes,
            "lfs_file_count": sum(
                item["lfs_sha256"] is not None for item in files.values()
            ),
            "ordinary_file_count": sum(
                item["lfs_sha256"] is None for item in files.values()
            ),
            "indexed_shard_count": len(shards),
            "indexed_tensor_count": len(index["weight_map"]),
        },
        "files": verified,
    }


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary_name = stream.name
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary_name is not None:
            try:
                Path(temporary_name).unlink()
            except FileNotFoundError:
                pass


def receipt_outside_model(root: Path, receipt: Path) -> None:
    resolved_root = root.resolve()
    resolved_receipt = receipt.resolve()
    if resolved_receipt == resolved_root or resolved_receipt.is_relative_to(
        resolved_root
    ):
        raise VerificationError("receipt must be outside the model tree")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        receipt_outside_model(args.model_root, args.receipt)
        payload = verify_tree(args.model_root, PINNED)
    except VerificationError as exc:
        payload = {
            "status": "fail",
            "format": RECEIPT_FORMAT,
            "completed_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "model_root": str(args.model_root.resolve()),
            "contract": asdict(PINNED),
            "error": str(exc),
        }
        try:
            receipt_outside_model(args.model_root, args.receipt)
            write_json_atomic(args.receipt, payload)
        except (OSError, VerificationError) as receipt_error:
            print(f"cannot write failure receipt: {receipt_error}", file=sys.stderr)
        print(f"verification failed: {exc}", file=sys.stderr)
        return 2

    try:
        write_json_atomic(args.receipt, payload)
    except OSError as exc:
        print(f"cannot write receipt: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {"status": "pass", "receipt": str(args.receipt.resolve())}, sort_keys=True
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
