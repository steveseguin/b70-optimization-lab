#!/usr/bin/env python3
"""Create the one-shot TP4 context-KV runtime packet marker."""

from __future__ import annotations

import argparse
import json
import os
import stat
from pathlib import Path


AUTHORIZATION_ROOT = Path(
    "/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/authorizations"
)
RUN_ROOT = Path("/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs")
VLLM_COMMIT = "94de2d07a40c64f91f52b17654a1f287ef7b3359"
KERNEL_COMMIT = "4772f727590c51b72add79350b913d098cf67872"
HEX = set("0123456789abcdef")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"Laguna context-KV runtime consumption: {message}")


def valid_hex(value: str, length: int) -> bool:
    return len(value) == length and all(character in HEX for character in value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--marker", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--main-commit", required=True)
    parser.add_argument("--packet-sha256", required=True)
    args = parser.parse_args()

    authorization_metadata = AUTHORIZATION_ROOT.lstat()
    authorization = AUTHORIZATION_ROOT.resolve(strict=True)
    run_root = args.run_root.resolve(strict=True)
    require(
        authorization == AUTHORIZATION_ROOT
        and not AUTHORIZATION_ROOT.is_symlink()
        and stat.S_ISDIR(authorization_metadata.st_mode)
        and stat.S_IMODE(authorization_metadata.st_mode) == 0o700
        and authorization_metadata.st_uid == os.getuid(),
        "authorization root identity or mode drift",
    )
    require(
        run_root == args.run_root
        and run_root.is_relative_to(RUN_ROOT.resolve(strict=True))
        and not run_root.is_symlink()
        and stat.S_ISDIR(run_root.lstat().st_mode)
        and stat.S_IMODE(run_root.lstat().st_mode) == 0o700,
        "run root identity or mode drift",
    )
    expected = AUTHORIZATION_ROOT / (
        "laguna-dflash-context-kv-runtime-"
        f"{args.main_commit}-{args.packet_sha256}.consumed.json"
    )
    require(
        args.marker == expected
        and args.marker.parent == AUTHORIZATION_ROOT
        and not args.marker.exists()
        and not args.marker.is_symlink(),
        "marker path is not fresh and canonical",
    )
    require(
        valid_hex(args.main_commit, 40) and valid_hex(args.packet_sha256, 64),
        "commit or packet digest is invalid",
    )

    payload = {
        "schema": "laguna-dflash-context-kv-runtime-consumption-v1",
        "main_commit": args.main_commit,
        "vllm_commit": VLLM_COMMIT,
        "kernel_commit": KERNEL_COMMIT,
        "run_root": str(run_root),
        "packet_sha256": args.packet_sha256,
        "authority": "one_non_timing_tp4_selector_off_on_exactness_gate",
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
        os.O_RDONLY
        | os.O_DIRECTORY
        | os.O_CLOEXEC
        | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    print(args.marker)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
