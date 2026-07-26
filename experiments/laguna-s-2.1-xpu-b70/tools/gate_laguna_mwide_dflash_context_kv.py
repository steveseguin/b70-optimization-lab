#!/usr/bin/env python3
"""Exact one-card gate for Laguna DFlash context-KV widths 9 through 12."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


MAIN_ROOT = Path("/home/steve/llm-optimizations").resolve()
VLLM_ROOT = Path("/home/steve/src/laguna-vllm-runtime-graph-20260724").resolve()
KERNEL_ROOT = Path("/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc").resolve()
BASE_COMPONENT = (
    MAIN_ROOT
    / "experiments/laguna-s-2.1-xpu-b70/tools"
    / "run_laguna_dflash_context_kv_component.py"
)
WIDTHS = (9, 10, 11, 12)
EXPECTED_SELECTORS = {
    "VLLM_XPU_EXACT_SPEC_ATTN": "1",
    "VLLM_XPU_LAGUNA_EXACT_MAX_M": "12",
    "VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE": "1",
    "VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK": "1",
    "VLLM_XPU_LAGUNA_MWIDE_BF16_ROUTER_TOPK": "1",
    "VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE": "1",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_identity(root: Path) -> dict[str, Any]:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    ).stdout
    require(not status, f"dirty worktree: {root}")
    return {"root": str(root), "head": head}


def load_base() -> Any:
    spec = importlib.util.spec_from_file_location(
        "laguna_mwide_dflash_base_component", BASE_COMPONENT
    )
    require(spec is not None and spec.loader is not None, "cannot load base component")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rank", type=int, required=True, choices=range(4))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    require(not args.out.exists(), "fresh output path required")
    require(
        os.environ.get("ZE_AFFINITY_MASK") == str(args.rank),
        "ZE_AFFINITY_MASK must equal the physical rank",
    )
    selectors = {name: os.environ.get(name) for name in EXPECTED_SELECTORS}
    require(selectors == EXPECTED_SELECTORS, "selector contract drift")

    main_identity = git_identity(MAIN_ROOT)
    vllm_identity = git_identity(VLLM_ROOT)
    kernel_identity = git_identity(KERNEL_ROOT)

    import torch
    from safetensors import safe_open
    from torch import nn

    import vllm
    import vllm_xpu_kernels
    from vllm import _custom_ops as ops
    from vllm.config import VllmConfig, set_current_vllm_config
    from vllm.model_executor.layers.rotary_embedding import get_rope
    from vllm.model_executor.models import laguna_dflash
    from vllm.v1.attention.backend import AttentionType
    from vllm.v1.attention.backends.flash_attn import FlashAttentionImpl

    require(
        Path(vllm.__file__).resolve().parents[1] == VLLM_ROOT,
        "vLLM import root drift",
    )
    require(
        Path(vllm_xpu_kernels.__file__).resolve().parent
        == KERNEL_ROOT / "vllm_xpu_kernels",
        "kernel import root drift",
    )
    require(
        torch.xpu.is_available() and torch.xpu.device_count() == 1,
        "exactly one visible XPU is required",
    )
    torch.xpu.set_device(0)
    require(
        "Arc(TM) Pro B70" in torch.xpu.get_device_name(0),
        "visible device is not an Arc Pro B70",
    )
    require(
        not torch.xpu.is_current_stream_capturing(),
        "component must begin outside capture",
    )

    base = load_base()
    base.torch = torch
    base.nn = nn
    base.safe_open = safe_open
    base.WIDTHS = WIDTHS
    base.REPEATS = 2
    base.VLLM_ROOT = VLLM_ROOT
    base.KERNEL_ROOT = KERNEL_ROOT

    config = base.validated_config()
    device = torch.device("xpu:0")
    layer_fixtures, weight_source = base.load_rank_weights(args.rank, device)
    kv_weights, input_norms, k_norms, build_proof = base.build_actual_context_buffers(
        layer_fixtures, laguna_dflash
    )
    del layer_fixtures

    with set_current_vllm_config(VllmConfig()):
        rope = get_rope(
            base.HEAD_DIM,
            max_position=config["max_position_embeddings"],
            rope_parameters=config["rope_parameters"],
        )
    cache_impl = FlashAttentionImpl.__new__(FlashAttentionImpl)
    cache_impl.attn_type = AttentionType.DECODER
    cache_impl.head_size = base.HEAD_DIM
    cache_impl.kv_cache_dtype = "bfloat16"
    cache_impl._xpu_persistent_kv_cache_views = None

    capture_rejection = base.run_capture_rejection(
        rank=args.rank,
        kv_weights=kv_weights,
        input_norms=input_norms,
        k_norms=k_norms,
        rope=rope,
        cache_impl=cache_impl,
        device=device,
        laguna_dflash=laguna_dflash,
    )
    no_bias = base.run_branch(
        rank=args.rank,
        branch="actual_no_bias",
        bias=None,
        kv_weights=kv_weights,
        input_norms=input_norms,
        k_norms=k_norms,
        rope=rope,
        cache_impl=cache_impl,
        device=device,
        laguna_dflash=laguna_dflash,
        ops=ops,
    )
    generator = torch.Generator(device=device).manual_seed(990000 + args.rank)
    bias = torch.randn(
        (base.LAYERS, 2 * base.LOCAL_KV),
        generator=generator,
        dtype=torch.bfloat16,
        device=device,
    )
    with_bias = base.run_branch(
        rank=args.rank,
        branch="synthetic_bias",
        bias=bias,
        kv_weights=kv_weights,
        input_norms=input_norms,
        k_norms=k_norms,
        rope=rope,
        cache_impl=cache_impl,
        device=device,
        laguna_dflash=laguna_dflash,
        ops=ops,
    )
    for branch in (no_bias, with_bias):
        require(
            branch["workspace_widths"] == list(WIDTHS),
            f"{branch['branch']}: workspace width drift",
        )
        require(
            len(branch["rows"]) == len(WIDTHS) * 2,
            f"{branch['branch']}: row coverage drift",
        )
        branch["post_reuse_widths"] = branch.pop("fallback_widths")

    package = KERNEL_ROOT / "vllm_xpu_kernels"
    native_hashes = {
        name: sha256_file(package / name)
        for name in (
            "_C.abi3.so",
            "_xpu_C.abi3.so",
            "_moe_C.abi3.so",
            "libgrouped_gemm_xe_2.so",
        )
    }
    result = {
        "schema": "laguna-mwide-dflash-context-kv-component-v1",
        "status": "exact_component_pass",
        "rank": args.rank,
        "device": torch.xpu.get_device_name(0),
        "selectors": selectors,
        "identities": {
            "main": main_identity,
            "vllm": vllm_identity,
            "kernel": kernel_identity,
            "base_component": str(BASE_COMPONENT),
            "base_component_sha256": sha256_file(BASE_COMPONENT),
            "worker_sha256": sha256_file(Path(__file__).resolve()),
            "native_hashes": native_hashes,
        },
        "widths": list(WIDTHS),
        "repeats": 2,
        "weight_source": weight_source,
        "buffer_build_proof": build_proof,
        "capture_rejection": capture_rejection,
        "actual_no_bias": no_bias,
        "synthetic_bias": with_bias,
        "generation": False,
        "service": False,
        "timing": False,
    }
    require(
        not torch.xpu.is_current_stream_capturing(),
        "component ended inside capture",
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "rank": args.rank,
                "device": result["device"],
                "widths": result["widths"],
                "branches": 2,
                "rows": len(no_bias["rows"]) + len(with_bias["rows"]),
                "status": result["status"],
                "out": str(args.out),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
