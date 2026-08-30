#!/usr/bin/env python3
"""Archive the Q4_K_M TP2 scheduler-screen receipts deterministically."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
from pathlib import Path


ARMS = (
    "b1024-u256-c32768-t8",
    "b2048-u256-c32768-t8",
    "b4096-u256-c32768-t8",
    "b2048-u512-c32768-t8",
    "b2048-u256-c16384-t8",
    "b2048-u256-c32768-t16",
)
PREFIX = "qwen38-q4km-tp2-scheduler-screen-20260830-r1"
FILES = (
    "input-sha256sums.txt",
    "source.diff",
    "source-status.txt",
    "server-command.txt",
    "runtime-environment.txt",
    "server.log",
    "result.json",
    "qualification.json",
    "screen-summary.json",
    "metrics-before.txt",
    "metrics-after.txt",
    "slots-before.json",
    "slots-after.json",
    "memory-before.txt",
    "memory-after.txt",
    "xpu-before.txt",
    "xpu-after.txt",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def gzip_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as src, destination.open("xb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as dst:
            shutil.copyfileobj(src, dst, length=1024 * 1024)


def uncompressed_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with gzip.open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bench-root", type=Path, default=Path("/mnt/fast-ai/bench-results"))
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.out_dir.exists():
        parser.error(f"refusing to overwrite {args.out_dir}")
    args.out_dir.mkdir(parents=True)

    artifacts = []
    for arm in ARMS:
        source_root = args.bench_root / f"{PREFIX}-{arm}-attempt1"
        for relative in FILES:
            source = source_root / relative
            if not source.is_file():
                raise SystemExit(f"missing source artifact: {source}")
            archived_relative = Path(arm) / f"{relative}.gz"
            archived = args.out_dir / archived_relative
            gzip_file(source, archived)
            source_hash = sha256(source)
            if uncompressed_sha256(archived) != source_hash:
                raise SystemExit(f"archive verification failed: {archived}")
            artifacts.append(
                {
                    "arm": arm,
                    "source_relative_to_bench_root": str(source.relative_to(args.bench_root)),
                    "path": str(archived_relative),
                    "uncompressed_size": source.stat().st_size,
                    "uncompressed_sha256": source_hash,
                    "compressed_size": archived.stat().st_size,
                    "compressed_sha256": sha256(archived),
                }
            )

    manifest = {
        "schema": "neural.download.compressed-evidence-manifest.v1",
        "campaign": PREFIX,
        "compression": "gzip mtime=0",
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
    }
    manifest_path = args.out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "manifest": str(manifest_path),
                "manifest_sha256": sha256(manifest_path),
                "artifacts": len(artifacts),
                "uncompressed_bytes": sum(item["uncompressed_size"] for item in artifacts),
                "compressed_bytes": sum(item["compressed_size"] for item in artifacts),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
