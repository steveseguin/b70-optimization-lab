#!/usr/bin/env python3
"""Verify compressed TP2/MTP2 receipts against uncompressed SHA-256 hashes."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.manifest.read_text(encoding="utf-8"))
    failures = []
    for artifact in payload["artifacts"]:
        path = args.manifest.parent / artifact["path"]
        digest = hashlib.sha256()
        try:
            with gzip.open(path, "rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
        except (OSError, EOFError) as exc:
            failures.append(f"{artifact['path']}: {exc}")
            continue
        if digest.hexdigest() != artifact["uncompressed_sha256"]:
            failures.append(f"{artifact['path']}: sha256 mismatch")
    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1
    print(f"PASS artifacts={len(payload['artifacts'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
