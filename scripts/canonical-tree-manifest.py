#!/usr/bin/env python3
"""Create or verify a portable, content-addressed directory manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
from pathlib import Path
from typing import Any


CHUNK_BYTES = 16 * 1024 * 1024
FORMAT = "b70-canonical-tree-manifest-v1"


def hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb", buffering=0) as handle:
        while chunk := handle.read(CHUNK_BYTES):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def entry_for(root: Path, path: Path) -> dict[str, Any]:
    relative = path.relative_to(root).as_posix()
    metadata = path.lstat()
    mode = stat.S_IMODE(metadata.st_mode)
    if path.is_symlink():
        return {
            "path": relative,
            "type": "symlink",
            "mode": mode,
            "target": os.readlink(path),
        }
    if path.is_dir():
        return {"path": relative, "type": "directory", "mode": mode}
    if path.is_file():
        sha256, size = hash_file(path)
        return {
            "path": relative,
            "type": "file",
            "mode": mode,
            "size_bytes": size,
            "sha256": sha256,
        }
    raise ValueError(f"unsupported filesystem entry: {path}")


def scan(root: Path) -> tuple[list[dict[str, Any]], str, int]:
    if not root.is_dir():
        raise FileNotFoundError(f"manifest root is not a directory: {root}")
    paths = sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix())
    entries = [entry_for(root, path) for path in paths]
    aggregate = hashlib.sha256()
    total_bytes = 0
    for entry in entries:
        encoded = json.dumps(
            entry, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        aggregate.update(encoded)
        aggregate.update(b"\n")
        if entry["type"] == "file":
            total_bytes += int(entry["size_bytes"])
    return entries, aggregate.hexdigest(), total_bytes


def create(root: Path, output: Path) -> int:
    root = root.resolve()
    output = output.resolve()
    if output == root or output.is_relative_to(root):
        raise ValueError("output manifest must be outside the manifested tree")
    entries, tree_sha256, total_bytes = scan(root)
    manifest = {
        "format": FORMAT,
        "root_at_capture": str(root),
        "tree_sha256": tree_sha256,
        "entry_count": len(entries),
        "file_count": sum(entry["type"] == "file" for entry in entries),
        "total_file_bytes": total_bytes,
        "entries": entries,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp-{os.getpid()}")
    temporary.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, output)
    print(
        json.dumps(
            {
                "status": "created",
                "manifest": str(output),
                "root": str(root),
                "tree_sha256": tree_sha256,
                "entry_count": len(entries),
                "total_file_bytes": total_bytes,
            },
            sort_keys=True,
        )
    )
    return 0


def verify(root: Path, manifest_path: Path) -> int:
    root = root.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format") != FORMAT:
        raise ValueError(f"unsupported manifest format: {manifest.get('format')!r}")
    entries, tree_sha256, total_bytes = scan(root)
    expected = {
        "tree_sha256": manifest.get("tree_sha256"),
        "entry_count": manifest.get("entry_count"),
        "file_count": manifest.get("file_count"),
        "total_file_bytes": manifest.get("total_file_bytes"),
        "entries": manifest.get("entries"),
    }
    actual = {
        "tree_sha256": tree_sha256,
        "entry_count": len(entries),
        "file_count": sum(entry["type"] == "file" for entry in entries),
        "total_file_bytes": total_bytes,
        "entries": entries,
    }
    okay = actual == expected
    print(
        json.dumps(
            {
                "status": "verified" if okay else "mismatch",
                "manifest": str(manifest_path.resolve()),
                "root": str(root),
                "expected_tree_sha256": expected["tree_sha256"],
                "actual_tree_sha256": tree_sha256,
                "expected_entry_count": expected["entry_count"],
                "actual_entry_count": len(entries),
                "expected_total_file_bytes": expected["total_file_bytes"],
                "actual_total_file_bytes": total_bytes,
            },
            sort_keys=True,
        )
    )
    return 0 if okay else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("--root", type=Path, required=True)
    create_parser.add_argument("--output", type=Path, required=True)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--root", type=Path, required=True)
    verify_parser.add_argument("--manifest", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "create":
            return create(args.root, args.output)
        return verify(args.root, args.manifest)
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"canonical-tree-manifest: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
