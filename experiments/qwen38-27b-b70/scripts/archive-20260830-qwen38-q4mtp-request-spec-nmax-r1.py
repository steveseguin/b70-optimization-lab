#!/usr/bin/env python3
"""Archive the request-level MTP safety and order receipts deterministically."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
from pathlib import Path


CAMPAIGNS = {
    "strict-mtp0": "qwen38-q4mtp-request-spec-nmax-20260830-r1-strict-mtp0",
    "strict-mtp2": "qwen38-q4mtp-request-spec-nmax-20260830-r1-strict-mtp2",
    "hybrid-r1": "qwen38-q4mtp-request-spec-nmax-20260830-r1-hybrid-r1",
    "hybrid-r2": "qwen38-q4mtp-request-spec-nmax-20260830-r1-hybrid-r2",
    "order-explicit-default": "qwen38-q4mtp-request-nmax-order-20260830-r1-explicit-default",
    "order-default-explicit": "qwen38-q4mtp-request-nmax-order-20260830-r1-default-explicit",
    "order-pre-stress-post": "qwen38-q4mtp-request-nmax-order-20260830-r1-pre-stress-post",
}

COMMON = ("sha256sums.txt", "server-command.txt", "runtime-environment.txt", "server.log")
FILES = {
    "strict-mtp0": COMMON
    + ("strict/performance.json", "strict/canaries.json", "qualification.json", "metrics-after.txt"),
    "strict-mtp2": COMMON
    + ("strict/performance.json", "strict/canaries.json", "qualification.json", "metrics-after.txt"),
    "hybrid-r1": COMMON
    + (
        "nmax0-performance.json",
        "nmax2-performance.json",
        "nmax0-concurrent-quality-canary.json",
        "default-mtp2-canaries.json",
        "qualification.json",
        "metrics-before-nmax0.txt",
        "metrics-after-nmax0.txt",
        "metrics-after-nmax2.txt",
    ),
    "hybrid-r2": COMMON
    + (
        "nmax0-performance.json",
        "nmax2-performance.json",
        "nmax0-concurrent-quality-canary.json",
        "default-mtp2-canaries.json",
        "qualification.json",
        "metrics-before-nmax0.txt",
        "metrics-after-nmax0.txt",
        "metrics-after-nmax2.txt",
    ),
    "order-explicit-default": COMMON
    + ("explicit-first.json", "default-second.json", "qualification.json", "metrics-after.txt"),
    "order-default-explicit": COMMON
    + ("default-first.json", "explicit-second.json", "qualification.json", "metrics-after.txt"),
    "order-pre-stress-post": COMMON
    + ("default-pre.json", "nmax0-stress.json", "default-post.json", "qualification.json", "metrics-after.txt"),
}


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
    for label, directory in CAMPAIGNS.items():
        source_root = args.bench_root / directory
        for relative in FILES[label]:
            source = source_root / relative
            if not source.is_file():
                raise SystemExit(f"missing source artifact: {source}")
            archived_relative = Path(label) / f"{relative}.gz"
            archived = args.out_dir / archived_relative
            gzip_file(source, archived)
            source_hash = sha256(source)
            if uncompressed_sha256(archived) != source_hash:
                raise SystemExit(f"archive verification failed: {archived}")
            artifacts.append(
                {
                    "campaign": label,
                    "source_relative_to_bench_root": str(Path(directory) / relative),
                    "path": str(archived_relative),
                    "uncompressed_size": source.stat().st_size,
                    "uncompressed_sha256": source_hash,
                    "compressed_size": archived.stat().st_size,
                    "compressed_sha256": sha256(archived),
                }
            )

    manifest = {
        "schema": "neural.download.compressed-evidence-manifest.v1",
        "campaign": "qwen38-q4mtp-request-spec-nmax-20260830-r1",
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
