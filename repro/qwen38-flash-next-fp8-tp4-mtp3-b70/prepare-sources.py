#!/usr/bin/env python3
"""Reconstruct and verify the exact Flash-Next vLLM and kernel source trees."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any


SCRIPT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_ROOT.parents[1]
VERIFIER_PATH = (
    REPO_ROOT / "patches/qwen38-flash-next-fp8-b70/verify-certified-source-series.py"
)
RECEIPT_FORMAT = "qwen38-flash-next-source-restore-receipt-v1"


class SourceRestoreError(RuntimeError):
    """The exact source trees could not be reconstructed."""


def load_verifier() -> ModuleType:
    specification = importlib.util.spec_from_file_location(
        "qwen38_certified_source_verifier", VERIFIER_PATH
    )
    if specification is None or specification.loader is None:
        raise SourceRestoreError(f"cannot load source verifier: {VERIFIER_PATH}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb", buffering=0) as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def full_clone(
    verifier: ModuleType, source: Path, destination: Path, base: str
) -> None:
    # `--no-local` avoids Git alternates, so the reconstructed checkout does
    # not depend on the caller's source repository remaining in place.
    verifier.run(
        "git",
        "clone",
        "--quiet",
        "--no-local",
        "--no-checkout",
        "--",
        str(source),
        str(destination),
    )
    verifier.run("git", "checkout", "--quiet", "--detach", base, cwd=destination)


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise SourceRestoreError(f"receipt already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    reserved = False
    try:
        temporary.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
        reserved = True
        os.replace(temporary, path)
        reserved = False
    finally:
        temporary.unlink(missing_ok=True)
        if reserved:
            path.unlink(missing_ok=True)


def restore(
    vllm_source: Path,
    kernel_source: Path,
    output_root: Path,
    receipt_path: Path,
) -> dict[str, Any]:
    verifier = load_verifier()
    vllm_source = verifier.require_source(
        vllm_source, verifier.VLLM_BASE, "vLLM source"
    )
    kernel_source = verifier.require_source(
        kernel_source, verifier.KERNEL_BASE, "kernel source"
    )
    output_root = output_root.resolve()
    receipt_path = receipt_path.resolve()
    if output_root.exists():
        raise SourceRestoreError(f"output root already exists: {output_root}")
    if receipt_path.exists():
        raise SourceRestoreError(f"receipt already exists: {receipt_path}")
    if receipt_path == output_root or receipt_path.is_relative_to(output_root):
        raise SourceRestoreError("receipt must be outside the reconstructed trees")

    vllm_patches = tuple(
        verifier.PACKET_ROOT / "vllm" / name for name in verifier.VLLM_PATCHES
    )
    kernel_patches = verifier.verify_kernel_patch_bytes(
        verifier.PACKET_ROOT / "vllm-xpu-kernels-certified-2f829747"
    )
    output_root.parent.mkdir(parents=True, exist_ok=True)
    temporary_root = Path(
        tempfile.mkdtemp(prefix=f".{output_root.name}.restore-", dir=output_root.parent)
    )
    try:
        vllm_output = temporary_root / "vllm"
        kernel_output = temporary_root / "vllm-xpu-kernels"
        full_clone(verifier, vllm_source, vllm_output, verifier.VLLM_BASE)
        full_clone(verifier, kernel_source, kernel_output, verifier.KERNEL_BASE)
        vllm_tree = verifier.apply_and_assert(
            vllm_output, vllm_patches, verifier.VLLM_TREE
        )
        kernel_tree = verifier.apply_and_assert(
            kernel_output, kernel_patches, verifier.KERNEL_TREE
        )
        os.rename(temporary_root, output_root)
    except Exception:
        shutil.rmtree(temporary_root, ignore_errors=True)
        raise

    receipt = {
        "completed_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "format": RECEIPT_FORMAT,
        "kernel": {
            "base": verifier.KERNEL_BASE,
            "output_path": str(output_root / "vllm-xpu-kernels"),
            "patch_count": len(kernel_patches),
            "tree": kernel_tree,
        },
        "source_verifier": {
            "path": str(VERIFIER_PATH.relative_to(REPO_ROOT)),
            "sha256": sha256_path(VERIFIER_PATH),
        },
        "status": "pass",
        "vllm": {
            "base": verifier.VLLM_BASE,
            "measured_commit": "1372c62d975c554f4b465c8299bc5f3295301ceb",
            "output_path": str(output_root / "vllm"),
            "patch_count": len(vllm_patches),
            "tree": vllm_tree,
        },
    }
    try:
        atomic_json(receipt_path, receipt)
    except Exception:
        # This invocation exclusively created output_root. Keep reconstruction
        # fail-closed if its receipt cannot be installed atomically.
        shutil.rmtree(output_root, ignore_errors=True)
        raise
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vllm-source", type=Path, required=True)
    parser.add_argument("--kernel-source", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = restore(
            args.vllm_source, args.kernel_source, args.output_root, args.receipt
        )
    except (OSError, SourceRestoreError, RuntimeError) as exc:
        print(f"prepare-sources: FAIL: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "kernel_tree": result["kernel"]["tree"],
                "status": "pass",
                "vllm_tree": result["vllm"]["tree"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
