#!/usr/bin/env python3
"""Prepare a non-executable historical client/verifier review artifact on CPU.

The destination must be a new directory outside this repository. No frozen file
is changed, and no runtime, GPU, historical shell script or verifier is invoked.
This does not reconstruct the parent hash chain or authorize a model launch.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from historical_verifiers import prepare_client


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("client", help="repository-relative frozen client path")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--manifest", type=Path,
                        default=root / "audits/repository-cleanup/2026-10-10/pin-audit.json")
    args = parser.parse_args()
    try:
        receipt = prepare_client(root, args.manifest, args.client, args.output_dir)
    except (OSError, ValueError) as exc:
        print(f"historical preparation refused: {exc}", file=sys.stderr)
        return 1
    print(f"prepared for review only: {args.output_dir}")
    print(f"client SHA256: {receipt['source_sha256']} -> {receipt['derivative_sha256']}")
    print("Frozen parent hash chains remain unchanged. Read receipt.json before deriving any successor.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
