#!/usr/bin/env python3
"""Create the external one-shot context-KV packet consumption marker."""

from __future__ import annotations

import argparse
import json
import os
import stat
from pathlib import Path

AUTHORIZATION_ROOT = Path(
    "/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/authorizations"
)
VLLM_COMMIT = "4459910e2ac5a7b552887fc0a3f3e3cf9a4701c0"
KERNEL_COMMIT = "4772f727590c51b72add79350b913d098cf67872"
RUN_ROOT = Path("/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs")
HEX = set("0123456789abcdef")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"Laguna context-KV consumption marker: {message}")


def valid_sha(value: str, length: int) -> bool:
    return len(value) == length and all(character in HEX for character in value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--marker", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--main-commit", required=True)
    parser.add_argument("--packet-sha256", required=True)
    args = parser.parse_args()

    authorization = AUTHORIZATION_ROOT.resolve(strict=True)
    metadata = authorization.lstat()
    require(
        authorization == AUTHORIZATION_ROOT
        and not authorization.is_symlink()
        and stat.S_ISDIR(metadata.st_mode)
        and stat.S_IMODE(metadata.st_mode) == 0o700,
        "authorization root identity or mode drift",
    )
    run_root = args.run_root.resolve(strict=True)
    require(
        run_root.is_relative_to(RUN_ROOT)
        and run_root == args.run_root
        and stat.S_IMODE(run_root.lstat().st_mode) == 0o700,
        "campaign root identity or mode drift",
    )
    require(
        args.marker.parent == AUTHORIZATION_ROOT
        and args.marker
        == AUTHORIZATION_ROOT
        / (
            "laguna-dflash-context-kv-"
            f"{args.main_commit}-{args.packet_sha256}.consumed.json"
        )
        and not args.marker.exists()
        and not args.marker.is_symlink(),
        "marker path is not fresh and canonical",
    )
    require(
        valid_sha(args.main_commit, 40) and valid_sha(args.packet_sha256, 64),
        "commit or packet digest is invalid",
    )
    payload = {
        "schema": "laguna-dflash-context-kv-component-consumption-v1",
        "main_commit": args.main_commit,
        "vllm_commit": VLLM_COMMIT,
        "kernel_commit": KERNEL_COMMIT,
        "run_root": str(run_root),
        "packet_sha256": args.packet_sha256,
    }
    data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
    descriptor = os.open(
        args.marker,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | os.O_CLOEXEC
        | getattr(os, "O_NOFOLLOW", 0),
        0o400,
    )
    try:
        view = memoryview(data)
        while view:
            written = os.write(descriptor, view)
            require(written > 0, "short marker write")
            view = view[written:]
        os.fsync(descriptor)
        os.fchmod(descriptor, 0o400)
    finally:
        os.close(descriptor)
    directory = os.open(
        AUTHORIZATION_ROOT,
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC,
    )
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    print(args.marker)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
