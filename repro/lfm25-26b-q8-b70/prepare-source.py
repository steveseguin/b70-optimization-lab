#!/usr/bin/env python3
"""Prepare authenticated source bytes, never build or run a model.

Only writes a new output directory and a temporary archive beside it. Partial
output survives failures for inspection. Initial free-space admission is not a
reservation. No dependencies beyond Python's standard library are required.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tarfile
import tempfile
import time
import urllib.parse
import urllib.request

GIB = 1024 ** 3
MAX_ADDITIONAL_BYTES = 512 * 1024 ** 2
DEFAULT_MANIFEST = Path(__file__).with_name("source-inputs.json")


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def admission(output, spec, min_free_bytes):
    if type(min_free_bytes) is not int or min_free_bytes < 0:
        raise ValueError("minimum free bytes must be a nonnegative integer")
    output = Path(os.path.abspath(output))
    for path in (output, *output.parents):
        if path.is_symlink():
            raise ValueError("symlink output or ancestor refused")
    if output.exists() or not output.parent.is_dir():
        raise ValueError("output must be absent and its parent must already exist")
    fs = os.statvfs(output.parent)
    if fs.f_flag & os.ST_RDONLY:
        raise ValueError("destination filesystem is read-only")
    block = max(4096, fs.f_frsize, fs.f_bsize)
    # Both download and unpacked tree coexist; charge a block plus metadata per
    # archive entry, and 16 MiB for inventory/temporary metadata.
    planned = spec["bytes"] + spec["file_bytes"] + spec["members"] * 3 * block + 16 * 1024 ** 2
    available = fs.f_bavail * fs.f_frsize
    if planned > MAX_ADDITIONAL_BYTES:
        raise ValueError("preparation exceeds the 512 MiB additional-space cap")
    if available < min_free_bytes + planned:
        raise ValueError("insufficient free space for preparation plus reserve")
    return output, {"planned_bytes": planned, "available_bytes": available,
                    "min_free_bytes": min_free_bytes, "filesystem_parent": str(output.parent)}


def download(spec, target):
    if urllib.parse.urlparse(spec["url"]).scheme != "https":
        raise ValueError("download requires HTTPS")
    deadline = time.monotonic() + 180
    count = 0
    request = urllib.request.Request(spec["url"], headers={"User-Agent": "neural-download-source-preparation"})
    with urllib.request.urlopen(request, timeout=20) as response, target.open("wb") as stream:
        if urllib.parse.urlparse(response.url).scheme != "https":
            raise ValueError("non-HTTPS redirect refused")
        while chunk := response.read(1024 * 1024):
            count += len(chunk)
            if count > spec["bytes"] or time.monotonic() > deadline:
                raise ValueError("download exceeded pinned size or time bound")
            stream.write(chunk)
        stream.flush()
        os.fsync(stream.fileno())


def checked_members(archive, spec):
    members = archive.getmembers()
    if len(members) != spec["members"] or sum(m.size for m in members) != spec["file_bytes"]:
        raise ValueError("archive census differs from manifest")
    rows = []
    names = set()
    files = set()
    for member in members:
        parts = PurePosixPath(member.name).parts
        if (not parts or parts[0] != spec["prefix"] or
                any(p in ("..", ".") for p in member.name.rstrip("/").split("/")) or
                "\\" in member.name or not (member.isfile() or member.isdir())):
            raise ValueError("unsafe archive path or member type")
        relative = PurePosixPath(*parts[1:])
        if not parts[1:]:
            if not member.isdir():
                raise ValueError("archive root must be a directory")
            continue
        if str(relative) in names:
            raise ValueError("duplicate archive member")
        names.add(str(relative))
        if member.isfile():
            files.add(relative)
        rows.append((member, relative))
    for _, relative in rows:
        if any(parent in files for parent in relative.parents):
            raise ValueError("file used as archive directory")
    return rows


def prepare(manifest, output, *, archive_path=None, min_free_bytes=50 * GIB):
    spec = manifest["archive"]
    output, space = admission(output, spec, min_free_bytes)
    with tempfile.TemporaryDirectory(prefix=".lfm-source-", dir=output.parent) as scratch:
        if archive_path is None:
            archive_path = Path(scratch) / "source.tar.gz"
            download(spec, archive_path)
        else:
            archive_path = Path(archive_path)
        if archive_path.is_symlink() or not stat.S_ISREG(archive_path.stat().st_mode):
            raise ValueError("archive must be a regular file, not a symlink")
        if archive_path.stat().st_size != spec["bytes"] or sha256(archive_path) != spec["sha256"]:
            raise ValueError("archive size or SHA-256 mismatch")
        with tarfile.open(archive_path, "r:gz") as archive:
            rows = checked_members(archive, spec)
            # Recheck immediately before output creation; no runtime/build step follows.
            admission(output, spec, min_free_bytes)
            output.mkdir(mode=0o700)
            inventory = []
            for member, relative in rows:
                destination = output / relative
                if member.isdir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                with archive.extractfile(member) as source, destination.open("xb") as target:
                    while chunk := source.read(1024 * 1024):
                        target.write(chunk)
                        digest.update(chunk)
                    target.flush()
                    os.fsync(target.fileno())
                destination.chmod(0o755 if member.mode & 0o111 else 0o644)
                if destination.stat().st_size != member.size or sha256(destination) != digest.hexdigest():
                    raise ValueError("extracted source readback mismatch")
                inventory.append({"path": str(relative), "bytes": member.size, "sha256": digest.hexdigest()})
            for name, expected in manifest["critical_files"].items():
                if sha256(output / name) != expected:
                    raise ValueError("critical source input mismatch: " + name)
            receipt = {"schema": "neural.download.source-preparation-receipt.v1",
                       "status": "source-prepared-only", "created_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                       "revision": manifest["revision"], "archive": spec, "admission": space,
                       "source_files": len(inventory), "source_bytes": sum(x["bytes"] for x in inventory),
                       "files": inventory, "build_performed": False, "runtime_qualified": False,
                       "clean_host_certified": False}
            with (output / "SOURCE-PREPARATION.json").open("x") as stream:
                json.dump(receipt, stream, indent=2, ensure_ascii=False)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            fd = os.open(output, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="new source directory; parent must already exist")
    parser.add_argument("--archive", type=Path, help="reuse an already downloaded pinned archive, without network access")
    parser.add_argument("--download", action="store_true", help="explicitly allow one bounded public source download")
    parser.add_argument("--min-free-gib", type=int, default=50, help="free-space reserve after source preparation (default: 50)")
    args = parser.parse_args()
    if bool(args.archive) == args.download:
        parser.error("choose exactly one of --archive or --download")
    manifest = json.loads(DEFAULT_MANIFEST.read_text())
    try:
        receipt = prepare(manifest, args.output, archive_path=args.archive, min_free_bytes=args.min_free_gib * GIB)
    except (OSError, ValueError, tarfile.TarError) as exc:
        parser.exit(1, f"FAIL: {exc}\n")
    print(json.dumps({key: value for key, value in receipt.items() if key != "files"}, indent=2))


if __name__ == "__main__":
    main()
