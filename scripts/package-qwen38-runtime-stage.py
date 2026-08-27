#!/usr/bin/env python3
"""Package and verify the exact certified Qwen3.8 Flash-Next runtime stage.

The production CLI is intentionally bound to the tracked 18-file SHA-256
manifest.  Library-level helpers accept a supplied manifest so the safety and
archive behavior can be exercised with tiny fixtures.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import stat
import sys
import tarfile
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Iterable


FORMAT = "qwen38-flash-next-runtime-stage-archive-v1"
RECEIPT_FORMAT = "qwen38-flash-next-runtime-stage-receipt-v1"
ARCHIVE_PREFIX = "qwen38-flash-next-runtime-stage"
EXPECTED_MANIFEST_SHA256 = (
    "9fa443fdb7a6d0042cf04f859cc6fd6a7bdc09943e16cafb4ea084573c892d2b"
)
EXPECTED_FILE_COUNT = 18
DEFAULT_SPLIT_BYTES = 1024 * 1024 * 1024
CHUNK_BYTES = 16 * 1024 * 1024
REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / (
    "experiments/qwen38-flash-next-fp8-b70/data/"
    "runtime-stage-padding-guard-loadable.sha256"
)


class StageError(ValueError):
    """A fail-closed stage or archive validation error."""


@dataclass(frozen=True)
class ManifestEntry:
    path: str
    sha256: str


@dataclass(frozen=True)
class ValidatedFile:
    path: str
    sha256: str
    size_bytes: int


def sha256_stream(handle: BinaryIO) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    while chunk := handle.read(CHUNK_BYTES):
        digest.update(chunk)
        size += len(chunk)
    return digest.hexdigest(), size


def sha256_path(path: Path) -> tuple[str, int]:
    with path.open("rb", buffering=0) as handle:
        return sha256_stream(handle)


def _validate_relative_path(value: str) -> str:
    if "\\" in value:
        raise StageError(f"manifest path uses a backslash: {value!r}")
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise StageError(f"manifest path is not a clean relative path: {value!r}")
    if value != path.as_posix():
        raise StageError(f"manifest path is not canonical: {value!r}")
    if not (value.endswith(".py") or value.endswith(".so")):
        raise StageError(f"manifest contains a non-runtime file: {value!r}")
    return value


def parse_sha256_manifest(raw: bytes) -> tuple[ManifestEntry, ...]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StageError("manifest is not UTF-8") from exc
    entries: list[ManifestEntry] = []
    seen: set[str] = set()
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line:
            raise StageError(f"blank manifest line at {line_number}")
        parts = line.split("  ", 1)
        if len(parts) != 2:
            raise StageError(f"invalid manifest line {line_number}")
        digest, raw_path = parts
        if len(digest) != 64 or digest.lower() != digest:
            raise StageError(f"invalid SHA-256 on manifest line {line_number}")
        try:
            int(digest, 16)
        except ValueError as exc:
            raise StageError(
                f"invalid SHA-256 on manifest line {line_number}"
            ) from exc
        path = _validate_relative_path(raw_path)
        if path in seen:
            raise StageError(f"duplicate manifest path: {path}")
        seen.add(path)
        entries.append(ManifestEntry(path=path, sha256=digest))
    if not entries:
        raise StageError("manifest is empty")
    if tuple(entry.path for entry in entries) != tuple(
        sorted(entry.path for entry in entries)
    ):
        raise StageError("manifest paths are not in canonical lexical order")
    return tuple(entries)


def load_production_manifest() -> tuple[bytes, tuple[ManifestEntry, ...]]:
    raw = MANIFEST_PATH.read_bytes()
    actual_sha256 = hashlib.sha256(raw).hexdigest()
    if actual_sha256 != EXPECTED_MANIFEST_SHA256:
        raise StageError(
            "tracked runtime-stage manifest identity changed: "
            f"expected {EXPECTED_MANIFEST_SHA256}, got {actual_sha256}"
        )
    entries = parse_sha256_manifest(raw)
    if len(entries) != EXPECTED_FILE_COUNT:
        raise StageError(
            f"expected {EXPECTED_FILE_COUNT} manifest files, got {len(entries)}"
        )
    return raw, entries


def _walk_stage(stage: Path) -> tuple[set[str], list[str]]:
    relevant: set[str] = set()
    excluded: list[str] = []
    for root_text, directory_names, file_names in os.walk(
        stage, topdown=True, followlinks=False
    ):
        root = Path(root_text)
        for name in list(directory_names):
            path = root / name
            relative = path.relative_to(stage).as_posix()
            if name == "__pycache__":
                excluded.append(relative + "/")
            if path.is_symlink():
                raise StageError(f"stage contains a directory symlink: {relative}")
        for name in file_names:
            path = root / name
            relative = path.relative_to(stage).as_posix()
            if name.endswith((".pyc", ".pyo")):
                excluded.append(relative)
            if name.endswith(".py") or name.endswith(".so"):
                relevant.add(relative)
    return relevant, excluded


def validate_stage(
    stage: Path, entries: Iterable[ManifestEntry]
) -> tuple[ValidatedFile, ...]:
    stage = stage.resolve()
    if not stage.is_dir():
        raise StageError(f"stage is not a directory: {stage}")
    expected = {entry.path: entry.sha256 for entry in entries}
    relevant, excluded = _walk_stage(stage)
    if excluded:
        raise StageError(
            "stage contains excluded Python cache artifacts: " + ", ".join(excluded)
        )
    missing = sorted(set(expected) - relevant)
    extras = sorted(relevant - set(expected))
    if missing or extras:
        details = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if extras:
            details.append("extra=" + ",".join(extras))
        raise StageError("runtime file inventory mismatch: " + "; ".join(details))

    validated: list[ValidatedFile] = []
    for relative in sorted(expected):
        path = stage / relative
        metadata = path.lstat()
        if not stat.S_ISREG(metadata.st_mode) or path.is_symlink():
            raise StageError(f"manifest path is not a regular file: {relative}")
        digest, size = sha256_path(path)
        if digest != expected[relative]:
            raise StageError(
                f"SHA-256 mismatch for {relative}: expected {expected[relative]}, "
                f"got {digest}"
            )
        validated.append(
            ValidatedFile(path=relative, sha256=digest, size_bytes=size)
        )
    return tuple(validated)


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def archive_metadata(
    manifest_sha256: str, validated: Iterable[ValidatedFile]
) -> dict[str, object]:
    files = [
        {
            "path": item.path,
            "sha256": item.sha256,
            "size_bytes": item.size_bytes,
        }
        for item in validated
    ]
    return {
        "format": FORMAT,
        "archive_prefix": ARCHIVE_PREFIX,
        "manifest_sha256": manifest_sha256,
        "file_count": len(files),
        "total_file_bytes": sum(int(item["size_bytes"]) for item in files),
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


def _tar_info(name: str, size: int, mode: int) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name=name)
    info.size = size
    info.mode = mode
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.type = tarfile.REGTYPE
    return info


class _HashingReader:
    def __init__(self, handle: BinaryIO) -> None:
        self.handle = handle
        self.digest = hashlib.sha256()
        self.size = 0

    def read(self, size: int = -1) -> bytes:
        chunk = self.handle.read(size)
        self.digest.update(chunk)
        self.size += len(chunk)
        return chunk


def _add_bytes(archive: tarfile.TarFile, name: str, payload: bytes) -> None:
    archive.addfile(_tar_info(name, len(payload), 0o644), io.BytesIO(payload))


def build_archive(
    stage: Path,
    archive_path: Path,
    manifest_raw: bytes,
    validated: tuple[ValidatedFile, ...],
) -> dict[str, object]:
    manifest_sha256 = hashlib.sha256(manifest_raw).hexdigest()
    metadata = archive_metadata(manifest_sha256, validated)
    metadata_raw = canonical_json_bytes(metadata)
    with tarfile.open(archive_path, mode="w", format=tarfile.GNU_FORMAT) as archive:
        _add_bytes(
            archive,
            f"{ARCHIVE_PREFIX}/ARCHIVE-METADATA.json",
            metadata_raw,
        )
        _add_bytes(
            archive,
            f"{ARCHIVE_PREFIX}/runtime-stage.sha256",
            manifest_raw,
        )
        for item in validated:
            source = stage / item.path
            mode = 0o755 if item.path.endswith(".so") else 0o644
            with source.open("rb", buffering=0) as source_handle:
                hashing_handle = _HashingReader(source_handle)
                archive.addfile(
                    _tar_info(
                        f"{ARCHIVE_PREFIX}/{item.path}", item.size_bytes, mode
                    ),
                    hashing_handle,
                )
            actual = hashing_handle.digest.hexdigest()
            if hashing_handle.size != item.size_bytes or actual != item.sha256:
                raise StageError(
                    f"source changed while archiving {item.path}: expected "
                    f"{item.size_bytes} bytes/{item.sha256}, got "
                    f"{hashing_handle.size} bytes/{actual}"
                )
    return metadata


def _expected_member_names(validated: Iterable[ValidatedFile]) -> list[str]:
    return [
        f"{ARCHIVE_PREFIX}/ARCHIVE-METADATA.json",
        f"{ARCHIVE_PREFIX}/runtime-stage.sha256",
        *(f"{ARCHIVE_PREFIX}/{item.path}" for item in validated),
    ]


def verify_archive_extraction(
    archive_path: Path,
    manifest_raw: bytes,
    entries: tuple[ManifestEntry, ...],
    validated: tuple[ValidatedFile, ...],
    work_dir: Path,
) -> None:
    expected_names = _expected_member_names(validated)
    expected_metadata = canonical_json_bytes(
        archive_metadata(hashlib.sha256(manifest_raw).hexdigest(), validated)
    )
    work_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".qwen38-runtime-verify-", dir=work_dir
    ) as temporary_text:
        temporary = Path(temporary_text)
        with tarfile.open(archive_path, mode="r:") as archive:
            members = archive.getmembers()
            names = [member.name for member in members]
            if len(names) != len(set(names)):
                raise StageError("archive contains duplicate member names")
            if names != expected_names:
                missing = sorted(set(expected_names) - set(names))
                extras = sorted(set(names) - set(expected_names))
                raise StageError(
                    "archive inventory/order mismatch: "
                    f"missing={missing}; extra={extras}"
                )
            for index, member in enumerate(members):
                if not member.isreg():
                    raise StageError(f"archive member is not regular: {member.name}")
                expected_mode = (
                    0o755
                    if index >= 2 and member.name.endswith(".so")
                    else 0o644
                )
                deterministic_fields = (
                    member.mtime == 0,
                    member.uid == 0,
                    member.gid == 0,
                    member.uname == "",
                    member.gname == "",
                    member.mode == expected_mode,
                )
                if not all(deterministic_fields):
                    raise StageError(
                        f"archive member metadata mismatch: {member.name}"
                    )
                relative = PurePosixPath(member.name)
                if relative.is_absolute() or ".." in relative.parts:
                    raise StageError(f"unsafe archive member path: {member.name}")
                destination = temporary.joinpath(*relative.parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                source = archive.extractfile(member)
                if source is None:
                    raise StageError(f"cannot read archive member: {member.name}")
                with destination.open("xb") as output:
                    while chunk := source.read(CHUNK_BYTES):
                        output.write(chunk)

        root = temporary / ARCHIVE_PREFIX
        if (root / "ARCHIVE-METADATA.json").read_bytes() != expected_metadata:
            raise StageError("embedded archive metadata does not match payload")
        if (root / "runtime-stage.sha256").read_bytes() != manifest_raw:
            raise StageError("embedded SHA-256 manifest does not match")
        extracted = validate_stage(root, entries)
        if extracted != validated:
            raise StageError("extracted stage metadata differs from source validation")


def split_and_hash_archive(
    archive_path: Path, split_bytes: int
) -> tuple[str, int, list[dict[str, object]]]:
    if split_bytes < 0:
        raise StageError("split size cannot be negative")
    archive_digest = hashlib.sha256()
    archive_size = 0
    parts: list[dict[str, object]] = []
    part_index = 0
    part_handle: BinaryIO | None = None
    part_path: Path | None = None
    part_digest = hashlib.sha256()
    part_size = 0
    created_part_paths: list[Path] = []

    def finish_part() -> None:
        nonlocal part_handle, part_path, part_digest, part_size
        if part_handle is None or part_path is None:
            return
        part_handle.close()
        parts.append(
            {
                "name": part_path.name,
                "index": len(parts),
                "size_bytes": part_size,
                "sha256": part_digest.hexdigest(),
            }
        )
        part_handle = None
        part_path = None
        part_digest = hashlib.sha256()
        part_size = 0

    try:
        with archive_path.open("rb", buffering=0) as source:
            while chunk := source.read(CHUNK_BYTES):
                archive_digest.update(chunk)
                archive_size += len(chunk)
                if split_bytes == 0:
                    continue
                offset = 0
                while offset < len(chunk):
                    if part_handle is None:
                        part_path = archive_path.with_name(
                            f"{archive_path.name}.part-{part_index:04d}"
                        )
                        part_handle = part_path.open("xb", buffering=0)
                        created_part_paths.append(part_path)
                        part_index += 1
                    remaining = split_bytes - part_size
                    piece = chunk[offset : offset + remaining]
                    part_handle.write(piece)
                    part_digest.update(piece)
                    part_size += len(piece)
                    offset += len(piece)
                    if part_size == split_bytes:
                        finish_part()
        finish_part()
    except Exception:
        if part_handle is not None:
            part_handle.close()
        for created in created_part_paths:
            created.unlink(missing_ok=True)
        raise
    return archive_digest.hexdigest(), archive_size, parts


def atomic_json_write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    reserved = False
    try:
        temporary.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
        reserved = True
        os.replace(temporary, path)
        reserved = False
    finally:
        temporary.unlink(missing_ok=True)
        if reserved:
            path.unlink(missing_ok=True)


def package(
    stage: Path,
    archive_path: Path,
    receipt_path: Path,
    split_bytes: int,
    verification_dir: Path,
) -> dict[str, object]:
    stage = stage.resolve()
    archive_path = archive_path.resolve()
    receipt_path = receipt_path.resolve()
    if archive_path.exists():
        raise FileExistsError(f"archive already exists: {archive_path}")
    if receipt_path.exists():
        raise FileExistsError(f"receipt already exists: {receipt_path}")
    if archive_path == receipt_path:
        raise StageError("archive and receipt paths must differ")
    for existing in archive_path.parent.glob(f"{archive_path.name}.part-[0-9][0-9][0-9][0-9]"):
        raise FileExistsError(f"split part already exists: {existing}")

    manifest_raw, entries = load_production_manifest()
    validated = validate_stage(stage, entries)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_archive = archive_path.with_name(
        f".{archive_path.name}.tmp-{os.getpid()}"
    )
    parts: list[dict[str, object]] = []
    archive_installed = False
    archive_reserved = False
    try:
        build_archive(stage, temporary_archive, manifest_raw, validated)
        verify_archive_extraction(
            temporary_archive,
            manifest_raw,
            entries,
            validated,
            verification_dir.resolve(),
        )
        descriptor = os.open(
            archive_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600
        )
        os.close(descriptor)
        archive_reserved = True
        os.replace(temporary_archive, archive_path)
        archive_reserved = False
        archive_installed = True
        archive_sha256, archive_size, parts = split_and_hash_archive(
            archive_path, split_bytes
        )
        receipt: dict[str, object] = {
            "format": RECEIPT_FORMAT,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": "verified",
            "source_stage_at_capture": str(stage),
            "tracked_manifest": str(MANIFEST_PATH.relative_to(REPO_ROOT)),
            "manifest_sha256": EXPECTED_MANIFEST_SHA256,
            "file_count": len(validated),
            "total_file_bytes": sum(item.size_bytes for item in validated),
            "files": [
                {
                    "path": item.path,
                    "size_bytes": item.size_bytes,
                    "sha256": item.sha256,
                }
                for item in validated
            ],
            "archive": {
                "name": archive_path.name,
                "path_at_creation": str(archive_path),
                "size_bytes": archive_size,
                "sha256": archive_sha256,
                "compression": "none",
                "extraction_verified": True,
            },
            "split": {
                "enabled": split_bytes > 0,
                "part_size_bytes": split_bytes,
                "reassembly": "concatenate parts in ascending index order",
                "parts": parts,
            },
        }
        atomic_json_write(receipt_path, receipt)
        return receipt
    except Exception:
        temporary_archive.unlink(missing_ok=True)
        if archive_reserved or archive_installed:
            archive_path.unlink(missing_ok=True)
        for part in parts:
            archive_path.with_name(str(part["name"])).unlink(missing_ok=True)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument(
        "--receipt",
        type=Path,
        help="default: <archive>.receipt.json",
    )
    parser.add_argument(
        "--split-bytes",
        type=int,
        default=DEFAULT_SPLIT_BYTES,
        help="fixed part size; use 0 to keep only the uncompressed tar",
    )
    parser.add_argument(
        "--verification-dir",
        type=Path,
        help="temporary extraction parent (default: archive directory)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    archive = args.archive.resolve()
    receipt = (
        args.receipt.resolve()
        if args.receipt
        else archive.with_name(f"{archive.name}.receipt.json")
    )
    verification_dir = (
        args.verification_dir.resolve()
        if args.verification_dir
        else archive.parent
    )
    try:
        result = package(
            args.stage, archive, receipt, args.split_bytes, verification_dir
        )
        print(
            json.dumps(
                {
                    "status": result["status"],
                    "archive": str(archive),
                    "receipt": str(receipt),
                    "archive_sha256": result["archive"]["sha256"],
                    "part_count": len(result["split"]["parts"]),
                },
                sort_keys=True,
            )
        )
        return 0
    except (FileNotFoundError, OSError, StageError, tarfile.TarError) as exc:
        print(f"package-qwen38-runtime-stage: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
