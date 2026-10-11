#!/usr/bin/env python3
"""Verify or restore byte-identical research sources from a pinned tar.xz.

Nothing is extracted unless --destination is supplied. Historical paths and
hashes remain valid after restoration; existing different files are never
overwritten. This restores evidence, not a qualified runtime or permission to
launch one.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import tempfile


ROOT = Path(__file__).resolve().parents[1]
CHUNK = 1024 * 1024


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def load_manifest(path):
    manifest = json.loads(path.read_text())
    if manifest.get("schema") != "b70-source-archive-v1":
        raise ValueError("unsupported manifest schema")
    archive = manifest["archive"]
    if Path(archive["file"]).name != archive["file"]:
        raise ValueError("archive must be beside its manifest")
    members = {}
    for entry in manifest["members"]:
        name = entry["path"]
        parts = PurePosixPath(name).parts
        if (not parts or parts[0] != "patches" or ".." in parts
                or PurePosixPath(name).as_posix() != name or "\\" in name):
            raise ValueError(f"unsafe member path: {name}")
        if name in members or not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]):
            raise ValueError(f"duplicate member or invalid hash: {name}")
        if type(entry["size"]) is not int or entry["size"] < 0:
            raise ValueError(f"invalid member size: {name}")
        members[name] = entry
    if not members:
        raise ValueError("empty member inventory")
    return manifest, members


def verify_archive(path, manifest, members):
    expected = manifest["archive"]
    if path.stat().st_size != expected["size"] or digest(path) != expected["sha256"]:
        raise ValueError("archive size/hash mismatch")
    seen = set()
    with tarfile.open(path, "r|xz") as archive:
        for item in archive:
            if item.name not in members or item.name in seen or not item.isfile():
                raise ValueError(f"unexpected, duplicate or non-regular member: {item.name}")
            entry = members[item.name]
            if item.size != entry["size"]:
                raise ValueError(f"member size mismatch: {item.name}")
            h = hashlib.sha256()
            stream = archive.extractfile(item)
            for block in iter(lambda: stream.read(CHUNK), b""):
                h.update(block)
            if h.hexdigest() != entry["sha256"]:
                raise ValueError(f"member hash mismatch: {item.name}")
            seen.add(item.name)
    if seen != set(members):
        raise ValueError("archive is missing manifest members")


def target_path(root, name):
    target = root / name
    for part in (target, *target.parents):
        if part == root:
            break
        if part.is_symlink():
            raise ValueError(f"refusing symlink in destination: {part}")
    return target


def restore(path, members, destination, selected, require_mount=None):
    root = destination.resolve()
    pending = set()
    for name in selected:
        target = target_path(root, name)
        if target.exists():
            if (not target.is_file() or target.stat().st_size != members[name]["size"]
                    or digest(target) != members[name]["sha256"]):
                raise ValueError(f"refusing to overwrite different destination: {target}")
        else:
            pending.add(name)
    if not pending:
        return 0
    # Includes every new member, its temporary file and a 50 GiB reserve.
    # Only one temporary member exists at once; it becomes the final file.
    admission = [
        "python3", str(ROOT / "scripts/check-storage-headroom.py"), str(root),
        "--planned-write-bytes", str(sum(members[n]["size"] for n in pending)),
        "--min-free-bytes", "50GiB",
    ]
    if require_mount is not None:
        admission.extend(["--require-mount", str(require_mount)])
    subprocess.run(admission, check=True, stdout=subprocess.PIPE, text=True)
    root.mkdir(parents=True, exist_ok=True)
    restored = 0
    restored_names = set()
    seen = set()
    with tarfile.open(path, "r|xz") as archive:
        for item in archive:
            if (item.name not in members or item.name in seen or not item.isfile()
                    or item.size != members[item.name]["size"]):
                raise ValueError(f"archive member changed during restoration: {item.name}")
            seen.add(item.name)
            if item.name not in pending:
                continue
            target = target_path(root, item.name)
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".source-restore-",
                                                 delete=False) as output:
                    temporary = Path(output.name)
                    h = hashlib.sha256()
                    size = 0
                    stream = archive.extractfile(item)
                    for block in iter(lambda: stream.read(CHUNK), b""):
                        h.update(block)
                        output.write(block)
                        size += len(block)
                    output.flush()
                    os.fsync(output.fileno())
                if (size != members[item.name]["size"]
                        or h.hexdigest() != members[item.name]["sha256"]):
                    raise ValueError(f"member changed during restoration: {item.name}")
                temporary.chmod(0o644)
                # Atomic no-clobber publication, even if another writer appeared.
                os.link(temporary, target)
                restored += 1
                restored_names.add(item.name)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
    if restored_names != pending or seen != set(members):
        raise ValueError("archive members disappeared during restoration")
    return restored


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--destination", type=Path,
                        help="restore original repo-relative paths beneath this directory")
    parser.add_argument("--member", action="append", default=[],
                        help="restore only this original repo-relative path (repeatable)")
    parser.add_argument("--require-mount", type=Path,
                        help="require this external mount root during storage admission")
    parser.add_argument("--list", action="store_true", help="list original paths after verification")
    args = parser.parse_args()
    try:
        manifest, members = load_manifest(args.manifest)
        selected = set(args.member) if args.member else set(members)
        if not selected <= set(members):
            raise ValueError(f"unknown members: {sorted(selected - set(members))}")
        path = args.manifest.parent / manifest["archive"]["file"]
        verify_archive(path, manifest, members)
        restored = restore(path, members, args.destination, selected, args.require_mount) if args.destination else 0
        if args.list:
            print("\n".join(sorted(selected)))
        print(json.dumps({"verified_members": len(members), "restored_members": restored,
                          "archive_sha256": manifest["archive"]["sha256"]}))
    except (OSError, ValueError, KeyError, tarfile.TarError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"source archive verification/restoration failed: {error}\n")


if __name__ == "__main__":
    main()
