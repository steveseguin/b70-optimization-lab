#!/usr/bin/env python3
"""Build and admit a shared-RAM cache of the Qwen27 GGUF files.

The cache is byte-identical to its source GGUF.  It removes repeated reads from
the external NTFS model disk; it does not replace llama.cpp's device-side
weight reorder and is not a decode optimization.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import mmap
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SPEC = ROOT / "experiments/qwen27-dflash-sycl-b70/harness/model-pack-manifest.json"
DEFAULT_CACHE_ROOT = Path("/dev/shm/qwen27-b70-model-cache")
COPY_CHUNK = 16 * 1024 * 1024


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def admission_record(path: Path, sha256: str) -> dict[str, Any]:
    stat = path.stat()
    return {
        "sha256": sha256,
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "ctime_ns": stat.st_ctime_ns,
        "verified_unix": time.time(),
    }


def git_identity(path: Path) -> dict[str, Any]:
    def git(*args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(path), *args], check=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
        return result.stdout

    try:
        commit = git("rev-parse", "HEAD").strip()
        diff = git("diff", "--binary", "HEAD")
        untracked = git("ls-files", "--others", "--exclude-standard").splitlines()
    except (OSError, subprocess.CalledProcessError):
        return {"path": str(path), "commit": None, "dirty_patch_sha256": None}
    dirty_digest = hashlib.sha256(diff.encode())
    for relative in sorted(untracked):
        dirty_digest.update(relative.encode())
        dirty_digest.update(b"\0")
        candidate = path / relative
        if candidate.is_file():
            dirty_digest.update(candidate.read_bytes())
    dirty = bool(diff or untracked)
    return {
        "path": str(path),
        "commit": commit,
        "dirty": dirty,
        "dirty_patch_sha256": dirty_digest.hexdigest() if dirty else None,
    }


def driver_identity() -> dict[str, Any]:
    packages: dict[str, str] = {}
    for package in ("intel-opencl-icd", "libze-intel-gpu1"):
        result = subprocess.run(
            ["dpkg-query", "-W", "-f=${Version}", package], text=True,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
        packages[package] = result.stdout.strip() if result.returncode == 0 else "unknown"
    return {"kernel": platform.release(), "packages": packages}


def cache_entry(root: Path, expected_sha: str, source: Path) -> tuple[Path, Path]:
    directory = root / expected_sha
    return directory / source.name, directory / "cache-entry.json"


def hash_file(path: Path) -> tuple[str, int, float]:
    digest = hashlib.sha256()
    total = 0
    started = time.monotonic()
    with path.open("rb", buffering=0) as handle:
        while chunk := handle.read(COPY_CHUNK):
            digest.update(chunk)
            total += len(chunk)
    return digest.hexdigest(), total, time.monotonic() - started


def spec_sources(spec: dict[str, Any], role: str) -> list[tuple[str, dict[str, Any]]]:
    all_sources = [("target", spec["source"]), ("draft", spec["draft_source"])]
    return all_sources if role == "all" else [item for item in all_sources if item[0] == role]


def validate_entry(source: dict[str, Any], cached: Path, metadata_path: Path,
                   deep: bool) -> tuple[bool, str, dict[str, Any] | None]:
    try:
        metadata = load_json(metadata_path)
        stat = cached.stat()
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        return False, f"absent-or-invalid: {exc}", None
    expected_sha = source["sha256"]
    expected_size = Path(source["path"]).stat().st_size
    identity_ok = (
        metadata.get("schema_version") == 1
        and metadata.get("format") == "byte-identical-gguf-ram-cache"
        and metadata.get("source", {}).get("sha256") == expected_sha
        and metadata.get("cached", {}).get("sha256") == expected_sha
        and metadata.get("cached", {}).get("size_bytes") == expected_size
        and stat.st_size == expected_size
    )
    if not identity_ok:
        return False, "identity-or-size-mismatch", metadata
    if deep:
        actual_sha, _, seconds = hash_file(cached)
        if actual_sha != expected_sha:
            return False, f"checksum-mismatch actual={actual_sha}", metadata
        return True, f"deep-checksum-ok seconds={seconds:.3f}", metadata
    return True, "identity-and-size-ok", metadata


def prepare_one(role: str, source: dict[str, Any], root: Path, force: bool) -> None:
    source_path = Path(source["path"])
    expected_sha = source["sha256"]
    cached, metadata_path = cache_entry(root, expected_sha, source_path)
    cached.parent.mkdir(parents=True, exist_ok=True)
    lock_path = cached.parent / ".prepare.lock"
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        valid, reason, metadata = validate_entry(source, cached, metadata_path, deep=False)
        if valid and not force:
            refresh_metadata = metadata is not None and (
                metadata.get("packing_tool", {}).get("revision") != 2
                or (cached.stat().st_mode & 0o777) != 0o444
            )
            if (cached.stat().st_mode & 0o777) != 0o444:
                cached.chmod(0o444)
            if refresh_metadata and metadata is not None:
                metadata["packing_tool"] = {
                    "path": str(Path(__file__).resolve()), "revision": 2
                }
                metadata["runtime"] = git_identity(Path("/home/steve/src/llama.cpp"))
                metadata["driver"] = driver_identity()
                metadata["metadata_refreshed_unix"] = time.time()
                metadata["admission"] = admission_record(cached, expected_sha)
                atomic_json(metadata_path, metadata)
                reason += ",metadata-refreshed"
            print(f"{role}: READY path={cached} reason={reason}")
            return
        needed = source_path.stat().st_size
        free = shutil.disk_usage(root).free
        if free < needed + 64 * 1024 * 1024:
            raise RuntimeError(
                f"{role}: cache needs {needed} bytes plus headroom; only {free} free at {root}"
            )
        temporary = cached.with_name(f".{cached.name}.tmp-{os.getpid()}")
        digest = hashlib.sha256()
        total = 0
        started = time.monotonic()
        try:
            with source_path.open("rb", buffering=0) as src, temporary.open("xb", buffering=0) as dst:
                while chunk := src.read(COPY_CHUNK):
                    digest.update(chunk)
                    dst.write(chunk)
                    total += len(chunk)
                dst.flush()
                os.fsync(dst.fileno())
            actual_sha = digest.hexdigest()
            if actual_sha != expected_sha:
                raise RuntimeError(
                    f"{role}: source checksum mismatch expected={expected_sha} actual={actual_sha}"
                )
            if total != needed:
                raise RuntimeError(f"{role}: short copy expected={needed} actual={total}")
            os.replace(temporary, cached)
            cached.chmod(0o444)
        finally:
            temporary.unlink(missing_ok=True)
        seconds = time.monotonic() - started
        metadata = {
            "schema_version": 1,
            "format": "byte-identical-gguf-ram-cache",
            "evidence_class": "development-initialization-only",
            "promotion_eligible": False,
            "role": role,
            "source": {"path": str(source_path), "sha256": expected_sha, "size_bytes": needed},
            "cached": {"path": str(cached), "sha256": expected_sha, "size_bytes": total},
            "created_unix": time.time(),
            "copy_seconds": seconds,
            "copy_mib_per_second": total / (1024 * 1024) / seconds,
            "packing_tool": {"path": str(Path(__file__).resolve()), "revision": 2},
            "runtime": git_identity(Path("/home/steve/src/llama.cpp")),
            "driver": driver_identity(),
            "target_architecture": "bmg-g31",
            "kernel_abi": "gguf-byte-stream-v1",
            "layout": "original-gguf-no-offline-reorder",
            "admission": admission_record(cached, expected_sha),
        }
        atomic_json(metadata_path, metadata)
        print(
            f"{role}: PREPARED path={cached} bytes={total} seconds={seconds:.3f} "
            f"MiB/s={metadata['copy_mib_per_second']:.1f}"
        )


def warm_one(role: str, source: dict[str, Any], root: Path) -> None:
    cached, metadata_path = cache_entry(root, source["sha256"], Path(source["path"]))
    valid, reason, _ = validate_entry(source, cached, metadata_path, deep=False)
    if not valid:
        raise RuntimeError(f"{role}: cache not admitted: {reason}")
    started = time.monotonic()
    checksum = 0
    with cached.open("rb", buffering=0) as handle:
        with mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as mapping:
            if hasattr(mapping, "madvise"):
                mapping.madvise(mmap.MADV_WILLNEED)
            # Touch every host page.  This is intentionally a page residency
            # checksum, not the cryptographic admission check.
            for offset in range(0, len(mapping), mmap.PAGESIZE):
                checksum ^= mapping[offset]
            if mapping:
                checksum ^= mapping[-1]
    seconds = time.monotonic() - started
    print(
        f"{role}: WARM path={cached} bytes={cached.stat().st_size} "
        f"seconds={seconds:.3f} residency_xor={checksum}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("prepare", "status", "verify", "warm", "path", "drop")
    )
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--role", choices=("target", "draft", "all"), default="all")
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--execute", action="store_true", help="required for the destructive drop command"
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    spec = load_json(args.spec)
    rows: list[dict[str, Any]] = []
    try:
        if args.command == "prepare":
            args.cache_root.mkdir(parents=True, exist_ok=True)
            for role, source in spec_sources(spec, args.role):
                prepare_one(role, source, args.cache_root, args.force)
            return 0
        if args.command == "drop":
            selected = spec_sources(spec, args.role)
            for role, source in selected:
                cached, metadata_path = cache_entry(
                    args.cache_root, source["sha256"], Path(source["path"])
                )
                directory = cached.parent
                if not args.execute:
                    print(f"{role}: DRY-RUN drop {directory}")
                elif directory.exists():
                    shutil.rmtree(directory)
                    print(f"{role}: DROPPED {directory}")
                else:
                    print(f"{role}: ABSENT {directory}")
            return 0
        for role, source in spec_sources(spec, args.role):
            cached, metadata_path = cache_entry(
                args.cache_root, source["sha256"], Path(source["path"])
            )
            if args.command == "warm":
                warm_one(role, source, args.cache_root)
                continue
            valid, reason, metadata = validate_entry(
                source, cached, metadata_path, deep=args.command == "verify"
            )
            if args.command == "verify" and valid and metadata is not None:
                metadata["admission"] = admission_record(cached, source["sha256"])
                atomic_json(metadata_path, metadata)
            row = {"role": role, "valid": valid, "reason": reason, "path": str(cached)}
            if metadata is not None:
                row["metadata"] = metadata
            rows.append(row)
            if args.command == "path":
                if not valid:
                    raise RuntimeError(f"{role}: cache not admitted: {reason}")
                print(cached)
        if args.command in ("status", "verify"):
            if args.json:
                print(json.dumps(rows, indent=2, sort_keys=True))
            else:
                for row in rows:
                    print(
                        f"{row['role']}: {'READY' if row['valid'] else 'NOT-READY'} "
                        f"path={row['path']} reason={row['reason']}"
                    )
            return 0 if all(row["valid"] for row in rows) else 1
        return 0
    except (OSError, RuntimeError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
