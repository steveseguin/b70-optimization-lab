#!/usr/bin/env python3
"""Four-card component leg for Laguna's exact width-12 BF16 router top-k."""

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


ROWS = 12
EXPERTS = 256
TOPK = 10
EXPECTED_KERNEL_ROOT = Path(
    "/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc"
).resolve()
EXPECTED_VLLM_ROOT = Path(
    "/home/steve/src/laguna-vllm-runtime-graph-20260724"
).resolve()
BASE_GATE = Path(__file__).resolve().parent / "gate_laguna_m8_bf16_router_topk.py"
EXPECTED_SELECTORS = {
    "VLLM_XPU_LAGUNA_MWIDE_BF16_ROUTER_TOPK": "1",
    "VLLM_XPU_LAGUNA_EXACT_MAX_M": "12",
    "VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE": "1",
    "VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK": "1",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_head(root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def load_base_gate() -> Any:
    spec = importlib.util.spec_from_file_location(
        "laguna_mwide_bf16_base_gate", BASE_GATE
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load base gate: {BASE_GATE}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.ROWS = ROWS
    module.MIN_SAVED_MS_PER_CYCLE = 0.60
    module.MIN_GAIN_PCT = 0.0
    module.MIN_CANDIDATE_WINS = 24
    module.WARMUP_CYCLES_PER_ARM = 20
    module.TIMING_BLOCKS = 31
    module.CYCLES_PER_ARM = 64
    return module


def verify_environment(rank: int) -> dict[str, Any]:
    selectors = {name: os.environ.get(name) for name in EXPECTED_SELECTORS}
    if selectors != EXPECTED_SELECTORS:
        raise RuntimeError(
            "selector drift: "
            + json.dumps(
                {"expected": EXPECTED_SELECTORS, "actual": selectors},
                sort_keys=True,
            )
        )
    affinity = os.environ.get("ZE_AFFINITY_MASK")
    if affinity != str(rank):
        raise RuntimeError(
            f"ZE_AFFINITY_MASK must be literal rank {rank}, got {affinity!r}"
        )
    return {
        "selectors": selectors,
        "ze_affinity_mask": affinity,
        "base_gate_path": str(BASE_GATE),
        "base_gate_sha256": sha256_file(BASE_GATE),
        "kernel_root": str(EXPECTED_KERNEL_ROOT),
        "kernel_head": git_head(EXPECTED_KERNEL_ROOT),
        "vllm_root": str(EXPECTED_VLLM_ROOT),
        "vllm_head": git_head(EXPECTED_VLLM_ROOT),
    }


def runtime_identity(torch: Any, vllm: Any) -> dict[str, Any]:
    import vllm_xpu_kernels._moe_C as moe_extension

    vllm_root = Path(vllm.__file__).resolve().parents[1]
    kernel_root = Path(moe_extension.__file__).resolve().parents[1]
    if vllm_root != EXPECTED_VLLM_ROOT:
        raise RuntimeError(f"vLLM import drift: {vllm_root} != {EXPECTED_VLLM_ROOT}")
    if kernel_root != EXPECTED_KERNEL_ROOT:
        raise RuntimeError(
            f"kernel import drift: {kernel_root} != {EXPECTED_KERNEL_ROOT}"
        )
    extension_path = Path(moe_extension.__file__).resolve()
    return {
        "device_count": torch.xpu.device_count(),
        "device_name": torch.xpu.get_device_name(0),
        "vllm_import_root": str(vllm_root),
        "kernel_import_root": str(kernel_root),
        "moe_extension_path": str(extension_path),
        "moe_extension_sha256": sha256_file(extension_path),
    }


def make_timing_fixtures(base: Any, torch: Any, synthetic: list[Any]) -> list[Any]:
    fixtures = [
        base.synthetic_fixture_to_xpu(torch, fixture)
        for fixture in synthetic[: base.PRODUCTION_CALLS]
    ]
    for layer, fixture in enumerate(fixtures, start=1):
        fixture.evidence = {
            "layer": layer,
            "trace_set": "synthetic-width12",
            "source_fixture": fixture.name,
        }
    return fixtures


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rank", type=int, required=True, choices=range(4))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    environment = verify_environment(args.rank)
    base = load_base_gate()
    synthetic = base.build_corpus()
    corpus = base.validate_corpus(synthetic)
    if corpus["rows"] != ROWS or corpus["total_epochs"] != len(synthetic):
        raise RuntimeError("width-12 synthetic corpus contract drift")

    import torch
    import vllm
    import vllm._custom_ops  # noqa: F401

    if not torch.xpu.is_available() or torch.xpu.device_count() != 1:
        raise RuntimeError("component leg requires exactly one visible XPU")
    torch.xpu.set_device(0)
    if not hasattr(torch.ops._moe_C, "laguna_m8_bf16_topk_sigmoid"):
        raise RuntimeError("candidate native router op is unavailable")
    runtime = runtime_identity(torch, vllm)

    synthetic_runtime = [
        base.synthetic_fixture_to_xpu(torch, fixture) for fixture in synthetic
    ]
    correctness = base.correctness_pass(
        torch,
        synthetic_runtime,
        phase="width12-pre-timing",
        include_detail=True,
        expected_epochs=len(synthetic_runtime),
    )
    timing_fixtures = make_timing_fixtures(base, torch, synthetic)
    timing = base.collect_timing(torch, timing_fixtures)
    post_fixtures = synthetic_runtime[-base.ADVERSARIAL_EPOCHS :]
    post_timing = base.correctness_pass(
        torch,
        post_fixtures,
        phase="width12-post-timing",
        include_detail=False,
        expected_epochs=len(post_fixtures),
    )
    formal_pass = bool(
        correctness["passed"] and timing["passed"] and post_timing["passed"]
    )
    result = {
        "schema": "laguna-mwide-bf16-router-topk-component-v1",
        "rank": args.rank,
        "environment": environment,
        "runtime": runtime,
        "corpus": corpus,
        "correctness": correctness,
        "timing": timing,
        "post_timing": post_timing,
        "formal_component_pass": formal_pass,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    summary = {
        "rank": args.rank,
        "device": runtime["device_name"],
        "correctness_pass": correctness["passed"],
        "paired_median_saved_ms_per_47_call_cycle": timing["summary"][
            "paired_median_saved_ms_per_47_call_cycle"
        ],
        "candidate_faster_blocks": timing["summary"]["candidate_faster_blocks"],
        "timing_pass": timing["passed"],
        "post_timing_pass": post_timing["passed"],
        "formal_component_pass": formal_pass,
        "out": str(args.out),
    }
    print(json.dumps(summary, sort_keys=True))
    if not formal_pass:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
