#!/usr/bin/env python3
"""Raw-BF16 XpuFusedMoe integration gate for transposed Laguna scales."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


EXPECTED_SOURCE_HEAD = "8dd94f2307db3b830fe07f212c4b36f719652a5c"
EXPECTED_DSO_SHA256 = (
    "c4845ed7704a9afcf59e12f9d51e288f293f2e39966e283e2a7e322fed68b839"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tensor_sha256(tensor: Any) -> str:
    import torch

    raw = tensor.detach().cpu().contiguous().view(torch.uint8)
    return hashlib.sha256(raw.numpy()).hexdigest()


def git_head(path: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=path,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def mapped_grouped_gemm() -> list[str]:
    paths: set[str] = set()
    for line in Path("/proc/self/maps").read_text().splitlines():
        if "libgrouped_gemm_xe_2.so" not in line:
            continue
        candidate = line.split()[-1]
        if candidate.startswith("/"):
            paths.add(str(Path(candidate).resolve()))
    return sorted(paths)


def run_worker(args: argparse.Namespace) -> int:
    import torch
    import vllm_xpu_kernels._moe_C as moe_extension  # noqa: F401
    import vllm_xpu_kernels._xpu_C as xpu_extension  # noqa: F401
    from vllm_xpu_kernels.fused_moe_interface import XpuFusedMoe

    if torch.xpu.device_count() != 1:
        raise RuntimeError(
            f"worker requires exactly one visible XPU, got {torch.xpu.device_count()}"
        )
    expected_env = {
        "VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE": "1",
        "VLLM_XPU_LAGUNA_DECODE_GRF128": "1",
        "VLLM_XPU_LAGUNA_DECODE_EXACT_SPECIALIZED": "0",
        "VLLM_XPU_LAGUNA_DECODE_TRANSPOSED_SCALES": args.mode,
        "VLLM_XPU_LAGUNA_SCALE_VEC": "1",
        "VLLM_XPU_LAGUNA_DEQUANT_MAD": "0",
        "VLLM_XPU_LAGUNA_SCALE_FOLD": "0",
    }
    for name, expected in expected_env.items():
        if os.environ.get(name) != expected:
            raise RuntimeError(
                f"environment drift: {name}={os.environ.get(name)!r}, "
                f"expected {expected!r}"
            )

    candidate_so = Path(args.candidate_so).resolve()
    mapped = mapped_grouped_gemm()
    if mapped != [str(candidate_so)]:
        raise RuntimeError(
            f"mapped grouped-GEMM drift: expected {[str(candidate_so)]}, got {mapped}"
        )

    generator = torch.Generator(device="cpu")
    generator.manual_seed(753_000)
    w13 = torch.randint(
        0, 256, (64, 2048, 1536), dtype=torch.uint8, generator=generator
    ).to("xpu")
    w2 = torch.randint(
        0, 256, (64, 3072, 512), dtype=torch.uint8, generator=generator
    ).to("xpu")
    w13_scales_cpu = torch.empty(
        (64, 2048, 96), dtype=torch.bfloat16
    ).uniform_(0.0001, 0.02, generator=generator)
    w2_scales_cpu = torch.empty(
        (64, 3072, 32), dtype=torch.bfloat16
    ).uniform_(0.0001, 0.02, generator=generator)
    scale_identity = {
        "w13": tensor_sha256(w13_scales_cpu),
        "w2": tensor_sha256(w2_scales_cpu),
    }
    w13_scales = w13_scales_cpu.to("xpu")
    w2_scales = w2_scales_cpu.to("xpu")
    del w13_scales_cpu, w2_scales_cpu

    implementation = XpuFusedMoe(
        w13=w13,
        w13_scales=w13_scales,
        w13_bias=None,
        w2=w2,
        w2_scales=w2_scales,
        w2_bias=None,
        n_experts_per_token=10,
        activation="silu",
        num_experts=64,
        ep_rank=0,
        ep_size=4,
        expert_map=None,
    )
    physical_scale_shapes = {
        "ordinary_w13": list(implementation.gemm1_wei_scales.shape),
        "ordinary_w2": list(implementation.gemm2_wei_scales.shape),
        "transposed_w13": None,
        "transposed_w2": None,
    }
    if implementation._laguna_transposed_gemm1_wei_scales is not None:
        physical_scale_shapes["transposed_w13"] = list(
            implementation._laguna_transposed_gemm1_wei_scales.shape
        )
        physical_scale_shapes["transposed_w2"] = list(
            implementation._laguna_transposed_gemm2_wei_scales.shape
        )

    topk_ids = (
        torch.arange(120, dtype=torch.int64).remainder(64).reshape(12, 10).to("xpu")
    )
    topk_weights = torch.arange(
        1, 11, dtype=torch.float32
    ).repeat(12, 1)
    topk_weights /= topk_weights.sum(dim=1, keepdim=True)
    topk_weights = topk_weights.to("xpu")

    input_hashes: list[str] = []
    output_hashes: list[str] = []
    for input_index in range(3):
        input_generator = torch.Generator(device="cpu")
        input_generator.manual_seed(754_000 + input_index)
        hidden_cpu = torch.randn(
            (12, 3072), dtype=torch.bfloat16, generator=input_generator
        )
        input_hashes.append(tensor_sha256(hidden_cpu))
        hidden = hidden_cpu.to("xpu")
        output = torch.empty((12, 3072), dtype=torch.bfloat16, device="xpu")
        implementation.apply(output, hidden, topk_weights, topk_ids)
        torch.xpu.synchronize()
        output_hashes.append(tensor_sha256(output))

    payload = {
        "mode": args.mode,
        "environment": {name: os.environ.get(name) for name in expected_env},
        "candidate_so": str(candidate_so),
        "candidate_sha256": sha256_file(candidate_so),
        "mapped_grouped_gemm": mapped,
        "xpu_extension": str(Path(xpu_extension.__file__).resolve()),
        "fused_moe_source": str(
            Path(sys.modules[XpuFusedMoe.__module__].__file__).resolve()
        ),
        "scale_identity": scale_identity,
        "physical_scale_shapes": physical_scale_shapes,
        "input_sha256": input_hashes,
        "output_sha256": output_hashes,
    }
    Path(args.worker_output).write_text(json.dumps(payload, indent=2) + "\n")
    print(f"WORKER_RESULT=PASS mode={args.mode} exact_inputs=3")
    return 0


def assemble_runtime_package(
    output_dir: Path, binary_root: Path, source_root: Path
) -> Path:
    package_parent = output_dir / "runtime-package"
    package = package_parent / "vllm_xpu_kernels"
    shutil.copytree(binary_root / "vllm_xpu_kernels", package)
    shutil.copy2(
        source_root / "vllm_xpu_kernels/fused_moe_interface.py",
        package / "fused_moe_interface.py",
    )
    shutil.copy2(
        source_root / "vllm_xpu_kernels/moe_utils.py",
        package / "moe_utils.py",
    )
    return package_parent


def run_gate(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir).resolve()
    source_root = Path(args.source_root).resolve()
    binary_root = Path(args.binary_root).resolve()
    candidate_so = Path(args.candidate_so).resolve()
    if output_dir.exists():
        raise RuntimeError(f"refusing existing output directory: {output_dir}")
    if git_head(source_root) != EXPECTED_SOURCE_HEAD:
        raise RuntimeError("integration source HEAD drift")
    if sha256_file(candidate_so) != EXPECTED_DSO_SHA256:
        raise RuntimeError("candidate DSO SHA-256 drift")
    output_dir.mkdir(parents=True)
    package_parent = assemble_runtime_package(output_dir, binary_root, source_root)

    workers: dict[str, Any] = {}
    for mode in ("0", "1"):
        worker_output = output_dir / f"mode-{mode}.json"
        env = os.environ.copy()
        env.update(
            {
                "PYTHONNOUSERSITE": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPATH": str(package_parent),
                "ZE_AFFINITY_MASK": str(args.rank),
                "ONEAPI_DEVICE_SELECTOR": "level_zero:0",
                "VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE": "1",
                "VLLM_XPU_LAGUNA_DECODE_GRF128": "1",
                "VLLM_XPU_LAGUNA_DECODE_EXACT_SPECIALIZED": "0",
                "VLLM_XPU_LAGUNA_DECODE_TRANSPOSED_SCALES": mode,
                "VLLM_XPU_LAGUNA_SCALE_VEC": "1",
                "VLLM_XPU_LAGUNA_DEQUANT_MAD": "0",
                "VLLM_XPU_LAGUNA_SCALE_FOLD": "0",
                "VLLM_XPU_LAGUNA_PREFETCH_DIST": "6",
                "LD_LIBRARY_PATH": ":".join(
                    (
                        str(candidate_so.parent),
                        str(Path(sys.prefix) / "lib"),
                        "/opt/intel/oneapi/umf/1.1/lib",
                        "/opt/intel/oneapi/compiler/2025.3/lib",
                        "/opt/intel/oneapi/compiler/2025.3/opt/compiler/lib",
                    )
                ),
            }
        )
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--worker-mode",
            "--mode",
            mode,
            "--candidate-so",
            str(candidate_so),
            "--worker-output",
            str(worker_output),
        ]
        completed = subprocess.run(
            command, env=env, text=True, capture_output=True, timeout=600
        )
        (output_dir / f"mode-{mode}.stdout").write_text(completed.stdout)
        (output_dir / f"mode-{mode}.stderr").write_text(completed.stderr)
        if completed.returncode != 0:
            raise RuntimeError(
                f"mode {mode} failed with rc={completed.returncode}; "
                f"see {output_dir / f'mode-{mode}.stderr'}"
            )
        workers[mode] = json.loads(worker_output.read_text())

    control = workers["0"]
    candidate = workers["1"]
    identity_equal = (
        control["scale_identity"] == candidate["scale_identity"]
        and control["input_sha256"] == candidate["input_sha256"]
    )
    outputs_equal = control["output_sha256"] == candidate["output_sha256"]
    layout_correct = (
        control["physical_scale_shapes"]["transposed_w13"] is None
        and control["physical_scale_shapes"]["transposed_w2"] is None
        and candidate["physical_scale_shapes"]["transposed_w13"]
        == [64, 96, 2048]
        and candidate["physical_scale_shapes"]["transposed_w2"]
        == [64, 32, 3072]
    )
    passed = identity_equal and outputs_equal and layout_correct
    summary = {
        "status": "pass" if passed else "fail",
        "identity_equal": identity_equal,
        "raw_bf16_outputs_equal": outputs_equal,
        "layout_correct": layout_correct,
        "exact": sum(
            a == b
            for a, b in zip(
                control["output_sha256"], candidate["output_sha256"], strict=True
            )
        ),
        "total": len(control["output_sha256"]),
        "source_head": EXPECTED_SOURCE_HEAD,
        "candidate_sha256": EXPECTED_DSO_SHA256,
        "workers": workers,
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(
        f"INTEGRATION_RESULT={'PASS' if passed else 'FAIL'} "
        f"exact={summary['exact']}/{summary['total']} "
        f"layout_correct={layout_correct}"
    )
    return 0 if passed else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker-mode", action="store_true")
    parser.add_argument("--mode", choices=("0", "1"))
    parser.add_argument("--worker-output")
    parser.add_argument("--output-dir")
    parser.add_argument("--source-root")
    parser.add_argument("--binary-root")
    parser.add_argument("--candidate-so")
    parser.add_argument("--rank", type=int, default=1)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.worker_mode:
        return run_worker(args)
    return run_gate(args)


if __name__ == "__main__":
    raise SystemExit(main())
