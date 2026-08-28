#!/usr/bin/env python3
"""Verify and install the exact split Qwen3.8 Flash-Next runtime stage.

This is an offline consumer-side tool. It accepts local part files because the
large runtime has not been publicly hosted. It never imports or executes the
native payload.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO


CHUNK_BYTES = 16 * 1024 * 1024
CONTRACT_FORMAT = "qwen38-flash-next-runtime-download-contract-v1"
ARCHIVE_FORMAT = "qwen38-flash-next-runtime-stage-archive-v1"
INSTALL_RECEIPT_FORMAT = "qwen38-flash-next-runtime-install-receipt-v1"
SCRIPT_ROOT = Path(__file__).resolve().parent
DEFAULT_CONTRACT = SCRIPT_ROOT / "runtime-contract.json"
DEFAULT_MANIFEST = SCRIPT_ROOT / "runtime-stage.sha256"
FROZEN_CONTRACT_SHA256 = (
    "2ca2f7fbf67cef90145e4d99c9223d9e9fca83fa489b2906d73b982218e53a3d"
)
FROZEN_MANIFEST_SHA256 = (
    "9fa443fdb7a6d0042cf04f859cc6fd6a7bdc09943e16cafb4ea084573c892d2b"
)


class RuntimeStageError(RuntimeError):
    """The downloaded runtime failed its frozen contract."""


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RuntimeStageError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json_bytes(raw: bytes, source: Path) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=strict_object)
    except RuntimeStageError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeStageError(f"cannot read strict JSON {source}: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeStageError(f"JSON root is not an object: {source}")
    return value


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def copy_and_hash(
    source: BinaryIO, destination: BinaryIO | None = None
) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    while chunk := source.read(CHUNK_BYTES):
        digest.update(chunk)
        size += len(chunk)
        if destination is not None:
            destination.write(chunk)
    return digest.hexdigest(), size


def regular_file(path: Path, label: str) -> os.stat_result:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise RuntimeStageError(f"cannot inspect {label} {path}: {exc}") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise RuntimeStageError(f"{label} is not a regular file: {path}")
    return metadata


def clean_relative(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\0" in value:
        raise RuntimeStageError(f"unsafe relative path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or "." in path.parts or ".." in path.parts:
        raise RuntimeStageError(f"unsafe relative path: {value!r}")
    if path.as_posix() != value:
        raise RuntimeStageError(f"non-canonical relative path: {value!r}")
    return value


def hex_digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or value.lower() != value:
        raise RuntimeStageError(f"invalid SHA-256 for {label}")
    try:
        int(value, 16)
    except ValueError as exc:
        raise RuntimeStageError(f"invalid SHA-256 for {label}") from exc
    return value


def positive_size(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise RuntimeStageError(f"invalid size for {label}")
    return value


def validate_contract(contract: dict[str, Any]) -> dict[str, Any]:
    if contract.get("format") != CONTRACT_FORMAT:
        raise RuntimeStageError("unsupported runtime contract format")
    if contract.get("status") != "pre-publication":
        raise RuntimeStageError("runtime contract must remain pre-publication")
    publication = contract.get("publication")
    if not isinstance(publication, dict) or publication != {
        "public_readback_verified": False,
        "status": "not-hosted",
    }:
        raise RuntimeStageError(
            "runtime publication state is not the frozen local-only state"
        )

    archive = contract.get("archive")
    manifest = contract.get("manifest")
    parts = contract.get("parts")
    files = contract.get("files")
    if not isinstance(archive, dict) or not isinstance(manifest, dict):
        raise RuntimeStageError("contract archive or manifest is not an object")
    if not isinstance(parts, list) or not parts:
        raise RuntimeStageError("contract has no split parts")
    if not isinstance(files, list) or not files:
        raise RuntimeStageError("contract has no runtime files")
    archive["name"] = clean_relative(archive.get("name"))
    archive["prefix"] = clean_relative(archive.get("prefix"))
    archive["size_bytes"] = positive_size(archive.get("size_bytes"), "archive")
    archive["sha256"] = hex_digest(archive.get("sha256"), "archive")
    archive["archive_metadata_sha256"] = hex_digest(
        archive.get("archive_metadata_sha256"), "archive metadata"
    )
    if archive.get("compression") != "none" or not archive["name"].endswith(".tar"):
        raise RuntimeStageError("runtime archive must be an uncompressed tar")
    manifest["name"] = clean_relative(manifest.get("name"))
    manifest["size_bytes"] = positive_size(manifest.get("size_bytes"), "manifest")
    manifest["sha256"] = hex_digest(manifest.get("sha256"), "manifest")

    normalized_parts: list[dict[str, Any]] = []
    part_names: set[str] = set()
    for expected_index, raw in enumerate(parts):
        if not isinstance(raw, dict) or raw.get("index") != expected_index:
            raise RuntimeStageError("part indexes are not contiguous and ordered")
        if raw.get("url") is not None:
            raise RuntimeStageError(
                "pre-publication contract must not claim a part URL"
            )
        name = clean_relative(raw.get("name"))
        if name in part_names:
            raise RuntimeStageError(f"duplicate part name: {name}")
        part_names.add(name)
        normalized_parts.append(
            {
                "index": expected_index,
                "name": name,
                "size_bytes": positive_size(raw.get("size_bytes"), name),
                "sha256": hex_digest(raw.get("sha256"), name),
                "url": None,
            }
        )
    if sum(item["size_bytes"] for item in normalized_parts) != archive["size_bytes"]:
        raise RuntimeStageError("part sizes do not sum to archive size")

    normalized_files: list[dict[str, Any]] = []
    file_names: set[str] = set()
    for raw in files:
        if not isinstance(raw, dict):
            raise RuntimeStageError("runtime file contract entry is not an object")
        name = clean_relative(raw.get("path"))
        if not (name.endswith(".py") or name.endswith(".so")):
            raise RuntimeStageError(f"non-runtime payload in contract: {name}")
        if name in file_names:
            raise RuntimeStageError(f"duplicate runtime file: {name}")
        file_names.add(name)
        normalized_files.append(
            {
                "path": name,
                "size_bytes": positive_size(raw.get("size_bytes"), name),
                "sha256": hex_digest(raw.get("sha256"), name),
            }
        )
    if [item["path"] for item in normalized_files] != sorted(file_names):
        raise RuntimeStageError("runtime file contract is not in lexical order")
    contract["parts"] = normalized_parts
    contract["files"] = normalized_files
    return contract


def parse_manifest(raw: bytes) -> dict[str, str]:
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise RuntimeStageError("runtime manifest is not UTF-8") from exc
    result: dict[str, str] = {}
    for line_number, line in enumerate(lines, 1):
        fields = line.split("  ", 1)
        if len(fields) != 2:
            raise RuntimeStageError(f"invalid manifest line {line_number}")
        digest = hex_digest(fields[0], f"manifest line {line_number}")
        name = clean_relative(fields[1])
        if name in result:
            raise RuntimeStageError(f"duplicate manifest path: {name}")
        result[name] = digest
    if list(result) != sorted(result):
        raise RuntimeStageError("runtime manifest is not in lexical order")
    return result


def expected_archive_metadata(
    contract: dict[str, Any], manifest_sha256: str
) -> dict[str, Any]:
    files = contract["files"]
    return {
        "format": ARCHIVE_FORMAT,
        "archive_prefix": contract["archive"]["prefix"],
        "manifest_sha256": manifest_sha256,
        "file_count": len(files),
        "total_file_bytes": sum(item["size_bytes"] for item in files),
        "files": files,
        "tar": {
            "format": "gnu",
            "compression": "none",
            "member_order": "metadata,manifest,files-lexical",
            "mtime": 0,
            "uid": 0,
            "gid": 0,
            "uname": "",
            "gname": "",
            "python_mode": "0644",
            "shared_object_mode": "0755",
        },
    }


def verify_manifest(contract: dict[str, Any], manifest_path: Path) -> bytes:
    metadata = regular_file(manifest_path, "runtime manifest")
    raw = manifest_path.read_bytes()
    expected = contract["manifest"]
    if (
        metadata.st_size != expected["size_bytes"]
        or sha256_bytes(raw) != expected["sha256"]
    ):
        raise RuntimeStageError("runtime manifest size or SHA-256 mismatch")
    parsed = parse_manifest(raw)
    contracted = {item["path"]: item["sha256"] for item in contract["files"]}
    if parsed != contracted:
        raise RuntimeStageError("runtime manifest differs from file contract")
    return raw


def reassemble_parts(
    contract: dict[str, Any], parts_dir: Path, archive_path: Path
) -> None:
    if not parts_dir.is_dir():
        raise RuntimeStageError(f"parts directory is missing: {parts_dir}")
    expected_names = {item["name"] for item in contract["parts"]}
    archive_name = contract["archive"]["name"]
    observed_names = {path.name for path in parts_dir.glob(f"{archive_name}.part-*")}
    if observed_names != expected_names:
        raise RuntimeStageError(
            "split part inventory mismatch: "
            f"missing={sorted(expected_names - observed_names)}, "
            f"extra={sorted(observed_names - expected_names)}"
        )

    archive_digest = hashlib.sha256()
    archive_size = 0
    with archive_path.open("xb", buffering=0) as output:
        for part in contract["parts"]:
            path = parts_dir / part["name"]
            metadata = regular_file(path, "runtime part")
            if metadata.st_size != part["size_bytes"]:
                raise RuntimeStageError(f"part size mismatch: {part['name']}")
            with path.open("rb", buffering=0) as source:
                digest = hashlib.sha256()
                size = 0
                while chunk := source.read(CHUNK_BYTES):
                    digest.update(chunk)
                    archive_digest.update(chunk)
                    output.write(chunk)
                    size += len(chunk)
                    archive_size += len(chunk)
            if size != part["size_bytes"] or digest.hexdigest() != part["sha256"]:
                raise RuntimeStageError(f"part SHA-256 mismatch: {part['name']}")
    archive = contract["archive"]
    if archive_size != archive["size_bytes"]:
        raise RuntimeStageError("reassembled archive size mismatch")
    if archive_digest.hexdigest() != archive["sha256"]:
        raise RuntimeStageError("reassembled archive SHA-256 mismatch")


def expected_members(contract: dict[str, Any]) -> list[str]:
    prefix = contract["archive"]["prefix"]
    return [
        f"{prefix}/ARCHIVE-METADATA.json",
        f"{prefix}/{contract['manifest']['name']}",
        *(f"{prefix}/{item['path']}" for item in contract["files"]),
    ]


def validate_member_path(name: str) -> None:
    clean_relative(name)


def verify_and_extract_archive(
    contract: dict[str, Any],
    manifest_raw: bytes,
    archive_path: Path,
    stage_root: Path,
) -> list[dict[str, Any]]:
    expected_names = expected_members(contract)
    expected_metadata = canonical_json_bytes(
        expected_archive_metadata(contract, sha256_bytes(manifest_raw))
    )
    if (
        sha256_bytes(expected_metadata)
        != contract["archive"]["archive_metadata_sha256"]
    ):
        raise RuntimeStageError("derived archive metadata identity mismatch")
    installed: list[dict[str, Any]] = []
    try:
        archive = tarfile.open(archive_path, mode="r:")
    except (OSError, tarfile.TarError) as exc:
        raise RuntimeStageError(f"cannot open exact uncompressed tar: {exc}") from exc
    with archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        for name in names:
            validate_member_path(name)
        if len(names) != len(set(names)):
            raise RuntimeStageError("archive contains duplicate member names")
        if names != expected_names:
            raise RuntimeStageError(
                "archive inventory/order mismatch: "
                f"missing={sorted(set(expected_names) - set(names))}, "
                f"extra={sorted(set(names) - set(expected_names))}"
            )
        for index, member in enumerate(members):
            expected_mode = (
                0o755 if index >= 2 and member.name.endswith(".so") else 0o644
            )
            if not member.isreg():
                raise RuntimeStageError(f"archive member is not regular: {member.name}")
            if (
                member.mtime != 0
                or member.uid != 0
                or member.gid != 0
                or member.uname != ""
                or member.gname != ""
                or member.mode != expected_mode
            ):
                raise RuntimeStageError(
                    f"archive member metadata mismatch: {member.name}"
                )

        metadata_source = archive.extractfile(members[0])
        manifest_source = archive.extractfile(members[1])
        if metadata_source is None or manifest_source is None:
            raise RuntimeStageError("cannot read embedded archive contracts")
        metadata_raw = metadata_source.read()
        embedded_manifest = manifest_source.read()
        if metadata_raw != expected_metadata:
            raise RuntimeStageError("embedded archive metadata mismatch")
        if embedded_manifest != manifest_raw:
            raise RuntimeStageError("embedded runtime manifest mismatch")

        stage_root.mkdir(mode=0o755)
        for member, file_contract in zip(members[2:], contract["files"], strict=True):
            expected_size = file_contract["size_bytes"]
            if member.size != expected_size:
                raise RuntimeStageError(
                    f"archive file size mismatch: {file_contract['path']}"
                )
            source = archive.extractfile(member)
            if source is None:
                raise RuntimeStageError(
                    f"cannot read runtime file: {file_contract['path']}"
                )
            relative = PurePosixPath(file_contract["path"])
            destination = stage_root.joinpath(*relative.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb", buffering=0) as output:
                digest, size = copy_and_hash(source, output)
            os.chmod(destination, 0o755 if destination.suffix == ".so" else 0o644)
            if size != expected_size or digest != file_contract["sha256"]:
                raise RuntimeStageError(
                    f"runtime file SHA-256 mismatch: {file_contract['path']}"
                )
            installed.append(
                {"path": file_contract["path"], "sha256": digest, "size_bytes": size}
            )
    return installed


def verify_installed_layout(stage_root: Path, files: list[dict[str, Any]]) -> None:
    expected = {item["path"] for item in files}
    actual: set[str] = set()
    for root_text, directory_names, file_names in os.walk(
        stage_root, topdown=True, followlinks=False
    ):
        root = Path(root_text)
        for directory_name in directory_names:
            path = root / directory_name
            if path.is_symlink():
                raise RuntimeStageError("installed stage contains a directory symlink")
        for file_name in file_names:
            path = root / file_name
            relative = path.relative_to(stage_root).as_posix()
            regular_file(path, "installed runtime file")
            actual.add(relative)
    if actual != expected:
        raise RuntimeStageError(
            f"installed layout mismatch: missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )


def atomic_receipt(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise RuntimeStageError(f"receipt already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_text = tempfile.mkstemp(
        prefix=f".{path.name}.tmp-", dir=path.parent
    )
    temporary = Path(temporary_text)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def directory_identity(path: Path) -> tuple[int, int]:
    metadata = path.lstat()
    if not stat.S_ISDIR(metadata.st_mode):
        raise RuntimeStageError(f"reserved destination is not a directory: {path}")
    return metadata.st_dev, metadata.st_ino


def remove_owned_directory(path: Path, identity: tuple[int, int]) -> None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return
    if (
        stat.S_ISDIR(metadata.st_mode)
        and (metadata.st_dev, metadata.st_ino) == identity
    ):
        shutil.rmtree(path)


def verify_frozen_inputs(
    contract_path: Path,
    contract_raw: bytes,
    manifest_path: Path,
    manifest_raw: bytes,
) -> None:
    if contract_path != DEFAULT_CONTRACT.resolve(strict=True):
        raise RuntimeStageError(
            "production install requires the tracked runtime contract"
        )
    if manifest_path != DEFAULT_MANIFEST.resolve(strict=True):
        raise RuntimeStageError(
            "production install requires the tracked runtime manifest"
        )
    if sha256_bytes(contract_raw) != FROZEN_CONTRACT_SHA256:
        raise RuntimeStageError("tracked runtime contract identity mismatch")
    if sha256_bytes(manifest_raw) != FROZEN_MANIFEST_SHA256:
        raise RuntimeStageError("tracked runtime manifest identity mismatch")


def install_runtime(
    contract_path: Path,
    manifest_path: Path,
    parts_dir: Path,
    kernel_stage: Path,
    receipt_path: Path,
    work_dir: Path,
    *,
    require_frozen: bool = False,
) -> dict[str, Any]:
    contract_path = contract_path.resolve(strict=True)
    manifest_path = manifest_path.resolve(strict=True)
    parts_dir = parts_dir.resolve(strict=True)
    kernel_stage = kernel_stage.resolve()
    receipt_path = receipt_path.resolve()
    work_dir = work_dir.resolve(strict=True)
    if kernel_stage.exists():
        raise RuntimeStageError(f"kernel stage already exists: {kernel_stage}")
    if receipt_path.exists():
        raise RuntimeStageError(f"receipt already exists: {receipt_path}")
    if receipt_path == kernel_stage or receipt_path.is_relative_to(kernel_stage):
        raise RuntimeStageError("receipt must be outside the installed kernel stage")

    contract_raw = contract_path.read_bytes()
    contract = validate_contract(load_json_bytes(contract_raw, contract_path))
    manifest_raw = verify_manifest(contract, manifest_path)
    if require_frozen:
        verify_frozen_inputs(contract_path, contract_raw, manifest_path, manifest_raw)
    kernel_stage.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".qwen38-runtime-work-", dir=work_dir
    ) as temporary_text:
        temporary = Path(temporary_text)
        archive_path = temporary / contract["archive"]["name"]
        reassemble_parts(contract, parts_dir, archive_path)
        kernel_stage.mkdir(mode=0o755)
        owned_identity = directory_identity(kernel_stage)
        installed_root = kernel_stage / "vllm_xpu_kernels"
        try:
            installed = verify_and_extract_archive(
                contract, manifest_raw, archive_path, installed_root
            )
            verify_installed_layout(installed_root, installed)
        except Exception:
            remove_owned_directory(kernel_stage, owned_identity)
            raise

    receipt = {
        "archive": contract["archive"],
        "completed_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "contract_sha256": sha256_bytes(contract_raw),
        "files": installed,
        "format": INSTALL_RECEIPT_FORMAT,
        "hybrid_runtime": contract["hybrid_runtime"],
        "installed_root": str(kernel_stage / "vllm_xpu_kernels"),
        "manifest_sha256": contract["manifest"]["sha256"],
        "parts": contract["parts"],
        "publication": contract["publication"],
        "status": "pass",
    }
    try:
        atomic_receipt(receipt_path, receipt)
    except Exception:
        # This invocation exclusively created the destination, so do not leave
        # an apparently complete install behind without its verification receipt.
        remove_owned_directory(kernel_stage, owned_identity)
        raise
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parts-dir", type=Path, required=True)
    parser.add_argument("--kernel-stage", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = install_runtime(
            DEFAULT_CONTRACT,
            DEFAULT_MANIFEST,
            args.parts_dir,
            args.kernel_stage,
            args.receipt,
            args.work_dir,
            require_frozen=True,
        )
    except (OSError, RuntimeStageError, tarfile.TarError) as exc:
        print(f"prepare-runtime: FAIL: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "installed_root": result["installed_root"],
                "publication": result["publication"]["status"],
                "status": "pass",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
