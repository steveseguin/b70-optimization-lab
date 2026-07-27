#!/usr/bin/env python3
"""Verify the exact Laguna native/runtime identity without allocating an XPU."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import sys
from importlib.metadata import version
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_hash(path: Path, expected: str) -> None:
    if not path.is_file():
        raise SystemExit(f"missing runtime file: {path}")
    actual = sha256(path)
    if actual != expected:
        raise SystemExit(
            f"runtime SHA256 mismatch for {path}: expected {expected}, got {actual}"
        )


def resolved(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=True)


def mapped_shared_objects() -> dict[str, set[Path]]:
    mapped: dict[str, set[Path]] = {}
    for line in Path("/proc/self/maps").read_text(encoding="utf-8").splitlines():
        parts = line.split(maxsplit=5)
        if len(parts) != 6 or not parts[5].startswith("/"):
            continue
        path_text = parts[5].removesuffix(" (deleted)")
        path = Path(path_text).resolve()
        if ".so" not in path.name:
            continue
        mapped.setdefault(path.name, set()).add(path)
    return mapped


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", required=True, type=Path)
    parser.add_argument("--vllm-tree", required=True, type=Path)
    parser.add_argument("--kernel-tree", required=True, type=Path)
    parser.add_argument("--venv-root", required=True, type=Path)
    parser.add_argument("--xpumem-module", required=True, type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    lock = json.loads(args.lock.read_text(encoding="utf-8"))
    if lock.get("schema") != "laguna-s-2.1-b70-runtime-lock-v1":
        raise SystemExit("runtime lock schema mismatch")

    vllm_tree = args.vllm_tree.resolve(strict=True)
    kernel_tree = args.kernel_tree.resolve(strict=True)
    kernel_package = (kernel_tree / "vllm_xpu_kernels").resolve(strict=True)
    venv_root = args.venv_root.resolve(strict=True)
    xpumem_module = args.xpumem_module.resolve(strict=True)

    python_expected = (venv_root / "bin/python").resolve(strict=True)
    if Path(sys.executable).resolve() != python_expected:
        raise SystemExit(
            f"wrong Python: expected {python_expected}, got {Path(sys.executable).resolve()}"
        )
    if sys.version_info[:3] != (3, 12, 13):
        raise SystemExit(f"wrong Python version: {sys.version.split()[0]}")

    ld_entries = [
        resolved(item)
        for item in os.environ.get("LD_LIBRARY_PATH", "").split(":")
        if item
    ]
    if not ld_entries or ld_entries[0] != kernel_package:
        raise SystemExit(
            "kernel package must be first in LD_LIBRARY_PATH so an absolute "
            "extension RUNPATH cannot select an external helper DSO"
        )

    for item in lock["runtime_files"]:
        path = Path(
            item["path_template"].format(venv=str(venv_root))
        ).resolve(strict=True)
        require_hash(path, item["sha256"])

    expected_packages = lock["python_packages"]
    package_versions = {
        "torch": version("torch"),
        "triton-xpu": version("triton-xpu"),
        "oneccl": version("oneccl"),
        "compressed-tensors": version("compressed-tensors"),
        "transformers": version("transformers"),
        "safetensors": version("safetensors"),
    }
    for package, actual in package_versions.items():
        expected = expected_packages[package]
        if actual != expected:
            raise SystemExit(
                f"package version mismatch for {package}: "
                f"expected {expected}, got {actual}"
            )

    module_origins: dict[str, str] = {}
    for item in lock["native_modules"]:
        expected_path = (kernel_package / item["path"]).resolve(strict=True)
        require_hash(expected_path, item["sha256"])
        module = importlib.import_module(item["module"])
        actual_path = resolved(module.__file__)
        if actual_path != expected_path:
            raise SystemExit(
                f"module origin mismatch for {item['module']}: "
                f"expected {expected_path}, got {actual_path}"
            )
        module_origins[item["module"]] = str(actual_path)

    external = lock["external_native_module"]
    require_hash(xpumem_module, external["sha256"])
    xpumem = importlib.import_module(external["module"])
    xpumem_origin = resolved(xpumem.__file__)
    if xpumem_origin != xpumem_module:
        raise SystemExit(
            f"xpumem module origin mismatch: expected {xpumem_module}, "
            f"got {xpumem_origin}"
        )
    module_origins[external["module"]] = str(xpumem_origin)

    vllm = importlib.import_module("vllm")
    vllm_origin = resolved(vllm.__file__)
    try:
        vllm_origin.relative_to(vllm_tree)
    except ValueError as error:
        raise SystemExit(
            f"vLLM imported outside the pinned source tree: {vllm_origin}"
        ) from error

    mapped = mapped_shared_objects()
    mapped_origins: dict[str, str] = {}
    for item in lock["mapped_kernel_libraries"]:
        expected_path = (kernel_package / item["path"]).resolve(strict=True)
        require_hash(expected_path, item["sha256"])
        origins = mapped.get(item["path"], set())
        if origins != {expected_path}:
            raise SystemExit(
                f"loaded DSO origin mismatch for {item['path']}: "
                f"expected {[str(expected_path)]}, "
                f"got {sorted(str(path) for path in origins)}"
            )
        mapped_origins[item["path"]] = str(expected_path)

    result: dict[str, Any] = {
        "schema": "laguna-s-2.1-runtime-verification-v1",
        "status": "PASS",
        "python": str(python_expected),
        "vllm_origin": str(vllm_origin),
        "kernel_package": str(kernel_package),
        "module_origins": module_origins,
        "mapped_kernel_libraries": mapped_origins,
        "package_versions": package_versions,
    }
    if args.json_out:
        args.json_out.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print("runtime_verification=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
