#!/usr/bin/env python3
"""Verify a neural.download GGUF manifest through direct and ordinary reads.

Usage:
  verify-neural-download-model.py MANIFEST_JSON MODEL_DIR [--json RESULT_JSON]

The backing-store digest and the ordinary page-cache digest must both match the
manifest and each other. Exit 2 means that the host cannot bypass its page
cache, so verification fails closed rather than certifying an unknown view.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import mmap
import os
from pathlib import Path
import re
import subprocess
import sys


DIRECT_BLOCK = 4096
DIRECT_CHUNK = 4 * 1024 * 1024


class DirectUnavailable(Exception):
    """The current filesystem cannot be read with a page-cache bypass."""


def hash_ordinary(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb", buffering=0) as source:
        for chunk in iter(lambda: source.read(DIRECT_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_odirect(path: Path) -> str:
    size = path.stat().st_size
    try:
        fd = os.open(path, os.O_RDONLY | os.O_DIRECT)
    except OSError as exc:
        raise DirectUnavailable(f"O_DIRECT open failed: {exc}") from exc

    buffer = mmap.mmap(-1, DIRECT_CHUNK)
    view = memoryview(buffer)
    digest = hashlib.sha256()
    try:
        offset = 0
        while offset < size:
            remaining = size - offset
            request = min(
                DIRECT_CHUNK,
                ((remaining + DIRECT_BLOCK - 1) // DIRECT_BLOCK) * DIRECT_BLOCK,
            )
            try:
                count = os.preadv(fd, [view[:request]], offset)
            except OSError as exc:
                raise DirectUnavailable(f"O_DIRECT read failed at {offset}: {exc}") from exc
            if count <= 0:
                raise DirectUnavailable(f"O_DIRECT read stalled at {offset}/{size}")
            digest.update(view[:count])
            offset += count
        return digest.hexdigest()
    finally:
        view.release()
        buffer.close()
        os.close(fd)


def hash_dd_direct(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        process = subprocess.Popen(
            ["dd", f"if={path}", "iflag=direct", "bs=4M", "status=none"],
            stdout=subprocess.PIPE,
        )
    except (FileNotFoundError, OSError) as exc:
        raise DirectUnavailable(f"dd iflag=direct unavailable: {exc}") from exc
    assert process.stdout is not None
    for chunk in iter(lambda: process.stdout.read(DIRECT_CHUNK), b""):
        digest.update(chunk)
    if process.wait() != 0:
        raise DirectUnavailable("dd iflag=direct failed")
    return digest.hexdigest()


def hash_direct(path: Path) -> tuple[str, str]:
    try:
        return hash_odirect(path), "odirect"
    except DirectUnavailable:
        return hash_dd_direct(path), "dd-iflag-direct"


def validate_manifest(value: object) -> list[str]:
    if not isinstance(value, dict):
        return ["manifest must be a JSON object"]
    errors: list[str] = []
    if value.get("format") != "neural-download-model-manifest-v1":
        errors.append("format must be neural-download-model-manifest-v1")
    for key in ("repository", "revision"):
        if not isinstance(value.get(key), str) or not value[key].strip():
            errors.append(f"{key} must be a non-empty string")
    files = value.get("files")
    if not isinstance(files, list) or not files:
        errors.append("files must be a non-empty list")
        return errors
    seen: set[str] = set()
    for index, item in enumerate(files):
        label = f"files[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} must be an object")
            continue
        name = item.get("name")
        if (
            not isinstance(name, str)
            or not name
            or name != os.path.basename(name)
            or name in {".", ".."}
            or "\\" in name
            or "\0" in name
        ):
            errors.append(f"{label}.name must be a safe file name")
        elif name in seen:
            errors.append(f"duplicate file name: {name}")
        else:
            seen.add(name)
        digest = item.get("sha256")
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            errors.append(f"{label}.sha256 must be a lowercase SHA-256 digest")
    return errors


def write_json(path: Path | None, result: dict[str, object]) -> None:
    if path is not None:
        path.write_text(json.dumps(result, indent=2) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("model_dir", type=Path)
    parser.add_argument("--json", dest="json_out", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result: dict[str, object] = {
        "manifest": str(args.manifest),
        "model_dir": str(args.model_dir),
        "verification": "direct-and-ordinary-sha256",
        "files": [],
    }
    try:
        manifest = json.loads(args.manifest.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        result.update(status="config-error", errors=[str(exc)])
        write_json(args.json_out, result)
        print(f"invalid manifest: {exc}", file=sys.stderr)
        return 3
    errors = validate_manifest(manifest)
    if errors:
        result.update(status="config-error", errors=errors)
        write_json(args.json_out, result)
        for error in errors:
            print(f"invalid manifest: {error}", file=sys.stderr)
        return 3
    if not args.model_dir.is_dir():
        result.update(status="mismatch", errors=["model directory is missing"])
        write_json(args.json_out, result)
        print(f"missing model directory: {args.model_dir}", file=sys.stderr)
        return 1

    failures = False
    entries: list[dict[str, object]] = []
    result["files"] = entries
    direct_work: list[tuple[dict[str, object], Path]] = []
    for item in manifest["files"]:
        path = args.model_dir / item["name"]
        entry: dict[str, object] = {
            "name": item["name"],
            "expected": item["sha256"],
        }
        entries.append(entry)
        if not path.is_file():
            entry["error"] = "missing"
            failures = True
            continue
        entry["size_bytes"] = path.stat().st_size
        try:
            direct_digest, direct_mode = hash_direct(path)
        except DirectUnavailable as exc:
            entry["error"] = str(exc)
            result["status"] = "unverifiable"
            write_json(args.json_out, result)
            print(f"cannot bypass page cache for {item['name']}: {exc}", file=sys.stderr)
            return 2
        entry["direct_mode"] = direct_mode
        entry["direct_sha256"] = direct_digest
        entry["direct_ok"] = direct_digest == item["sha256"]
        direct_work.append((entry, path))

    # Ordinary reads intentionally happen after every direct read so the final
    # verified view matches the cache path an imminent mmap load will observe.
    for entry, path in direct_work:
        try:
            ordinary_digest = hash_ordinary(path)
        except OSError as exc:
            entry["error"] = f"ordinary read failed: {exc}"
            failures = True
            continue
        entry["ordinary_sha256"] = ordinary_digest
        entry["ordinary_ok"] = ordinary_digest == entry["expected"]
        entry["views_coherent"] = ordinary_digest == entry["direct_sha256"]
        entry["ok"] = bool(entry["direct_ok"] and entry["ordinary_ok"] and entry["views_coherent"])
        failures = failures or not entry["ok"]
        print(("OK " if entry["ok"] else "BAD"), entry["name"], entry["direct_mode"])

    result["status"] = "mismatch" if failures else "verified"
    write_json(args.json_out, result)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
