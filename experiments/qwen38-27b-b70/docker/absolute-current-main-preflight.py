#!/usr/bin/env python3
"""Fail-closed import and identity checks for current-main XPU images."""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import json
import os
from pathlib import Path

import torch


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


expected_vllm = os.environ["VLLM_EXPECTED_VERSION"]
vllm = importlib.import_module("vllm")
kernel_version = importlib.metadata.version("vllm-xpu-kernels")
package_dir = Path(vllm.__file__).resolve().parent
legacy_source_dir = Path("/workspace/vllm")
if vllm.__version__ != expected_vllm:
    raise SystemExit(f"vLLM version mismatch: {vllm.__version__} != {expected_vllm}")
if not str(package_dir).startswith("/opt/venv/lib/python3.12/site-packages/"):
    raise SystemExit(f"vLLM is shadowed by a source tree: {vllm.__file__}")
if legacy_source_dir.is_symlink():
    raise SystemExit(f"legacy source path is a symlink: {legacy_source_dir}")
if legacy_source_dir.exists() and (
    not legacy_source_dir.is_dir() or any(legacy_source_dir.iterdir())
):
    raise SystemExit(f"legacy source path is not absent or empty: {legacy_source_dir}")

batch_config_member = Path(os.environ["BATCH_INVARIANT_CONFIG_PATH_VALUE"])
if not batch_config_member.parts or batch_config_member.parts[0] != "vllm":
    raise SystemExit(f"invalid batch-invariant member path: {batch_config_member}")
batch_config = package_dir.joinpath(*batch_config_member.parts[1:])
batch_package = batch_config.parent
for required in (
    batch_package / "__init__.py",
    batch_package / "batch_invariant.py",
    batch_config,
):
    if not required.is_file():
        raise SystemExit(f"missing installed batch-invariance asset: {required}")
if sha256(batch_config) != os.environ["BATCH_INVARIANT_CONFIG_SHA256_EXPECTED"]:
    raise SystemExit("installed batch-invariant config hash mismatch")
for legacy_member in (
    package_dir / "model_executor/layers/batch_invariant.py",
    package_dir / "model_executor/layers/batch_invariant_configs.py",
):
    if legacy_member.exists():
        raise SystemExit(f"stale pre-refactor batch-invariance member: {legacy_member}")

rust_extension = package_dir / "_rust_tool_parser.abi3.so"
rust_frontend = package_dir / "vllm-rs"
if sha256(rust_extension) != os.environ["RUST_EXTENSION_EXPECTED"]:
    raise SystemExit("installed Rust extension hash mismatch")
if sha256(rust_frontend) != os.environ["RUST_FRONTEND_EXPECTED"]:
    raise SystemExit("installed Rust frontend hash mismatch")

for module in (
    "vllm_xpu_kernels._C",
    "vllm_xpu_kernels._moe_C",
    "vllm_xpu_kernels._vllm_fa2_C",
    "vllm_xpu_kernels._xpu_C",
    "vllm_xpu_kernels.xpumem_allocator",
):
    importlib.import_module(module)

required_schemas = [
    ("_C", "rms_norm"),
    ("_vllm_fa2_C", "varlen_fwd"),
    ("_xpu_C", "gdn_attention"),
    ("_xpu_C", "int4_gemm_w4a16"),
]
if os.environ["INSTALL_CURRENT_KERNEL_VALUE"] == "1":
    required_schemas.append(("_xpu_C", "fp8_gemm_out"))
for namespace, op_name in required_schemas:
    op = getattr(getattr(torch.ops, namespace), op_name)
    if not op._schemas:
        raise SystemExit(f"missing Torch schema: {namespace}::{op_name}")

receipt = {
    "build_lane": os.environ["BUILD_LANE_VALUE"],
    "batch_invariant_config_path": str(batch_config_member),
    "batch_invariant_config_sha256": sha256(batch_config),
    "kernel_head": os.environ["KERNEL_HEAD_VALUE"],
    "kernel_version": kernel_version,
    "rust_extension_sha256": sha256(rust_extension),
    "rust_frontend_sha256": sha256(rust_frontend),
    "vllm_file": vllm.__file__,
    "vllm_head": os.environ["VLLM_HEAD_VALUE"],
    "vllm_version": vllm.__version__,
}
Path("/opt/neural-download/import-receipt.json").write_text(
    json.dumps(receipt, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
