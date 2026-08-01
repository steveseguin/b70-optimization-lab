#!/usr/bin/env python3
"""Mint a Laguna runtime lock for a focused vLLM/native-module stack.

The input lock is never modified. Exactly the vLLM source commit, kernel
source commit, and selected native module identity are replaced; every other
runtime and mapped-library identity must round-trip unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def git_head(path: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=path,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--vllm-tree", type=Path, required=True)
    parser.add_argument("--kernel-tree", type=Path, required=True)
    parser.add_argument("--module", default="_C.abi3.so")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    base = args.base.resolve()
    output = args.output.resolve()
    if output == base:
        raise SystemExit("refusing to overwrite the base runtime lock")
    raw = base.read_text()
    lock = json.loads(raw)
    if json.dumps(lock, indent=2) + "\n" != raw:
        raise SystemExit("base runtime lock does not round-trip exactly")

    vllm_head = git_head(args.vllm_tree.resolve())
    kernel_head = git_head(args.kernel_tree.resolve())
    module_path = args.kernel_tree.resolve() / "vllm_xpu_kernels" / args.module
    if not module_path.is_file():
        raise SystemExit(f"missing native module: {module_path}")
    module_hash = sha256_file(module_path)

    lock["scope"]["sealed_result"] = (
        "exact Laguna deferred rank-sum/RMSNorm plus native-M12 attention "
        "candidate; endpoint disposition pending frozen gates"
    )
    lock["source"]["vllm"]["commit"] = vllm_head
    lock["source"]["kernel_record_tree"]["commit"] = kernel_head
    entries = [
        entry
        for entry in lock["native_modules"]
        if entry["path"] == args.module
    ]
    if len(entries) != 1:
        raise SystemExit(
            f"expected one native module entry for {args.module}, got {len(entries)}"
        )
    entries[0]["sha256"] = module_hash
    entries[0]["observed_build_source_commit"] = kernel_head

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(lock, indent=2) + "\n")
    print(f"vllm_commit={vllm_head}")
    print(f"kernel_commit={kernel_head}")
    print(f"module_sha256={module_hash}")
    print(f"lock_sha256={sha256_file(output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
