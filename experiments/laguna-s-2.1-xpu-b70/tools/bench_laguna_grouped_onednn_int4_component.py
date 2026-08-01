#!/usr/bin/env python3
"""Paired component timing gate for Laguna grouped oneDNN INT4."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
from typing import Any, Callable


EXPERTS = 64
ROUTES = 120
CASES = (("w13", 2048, 3072), ("w2", 3072, 1024))
EXPECTED_SOURCE_HEAD = "00fbed32f69b7e6288c656ae866c4bff3be33996"
EXPECTED_PROTECTED_EXTENSION_SHA256 = (
    "f5f672130cc1b1d550646f732a6d576952c49514eba7a10db60fc1c361938fd8"
)
EXPECTED_GROUPED_SHA256 = (
    "c4845ed7704a9afcf59e12f9d51e288f293f2e39966e283e2a7e322fed68b839"
)
FROZEN_REFERENCE_SUM_MS = 0.504706
FROZEN_CANDIDATE_MAX_SUM_MS = 0.480070


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
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


def tensor_sha256(tensor: Any) -> str:
    import torch

    raw = tensor.detach().cpu().contiguous().view(torch.uint8).numpy()
    return hashlib.sha256(raw).hexdigest()


def run_worker(args: argparse.Namespace) -> int:
    import torch

    torch.ops.load_library(str(Path(args.protected_extension).resolve()))
    torch.ops.load_library(str(Path(args.extension).resolve()))
    if torch.xpu.device_count() != 1:
        raise RuntimeError("worker requires exactly one visible XPU")

    results: list[dict[str, Any]] = []
    for case_index, (name, n, k) in enumerate(CASES):
        generator = torch.Generator(device="cpu")
        generator.manual_seed(751_000 + case_index)
        weight_cpu = torch.randint(
            -128,
            128,
            (EXPERTS, n, k // 2),
            dtype=torch.int8,
            generator=generator,
        )
        scale_cpu = torch.empty(
            (EXPERTS, n, k // 32), dtype=torch.bfloat16
        ).uniform_(0.0001, 0.02, generator=generator)
        route_ids = torch.randint(
            0, EXPERTS, (ROUTES,), dtype=torch.int64, generator=generator
        )
        rows_cpu = torch.bincount(route_ids, minlength=EXPERTS).to(torch.int32)
        offsets_cpu = torch.cumsum(rows_cpu, dim=0, dtype=torch.int32)
        input_generator = torch.Generator(device="cpu")
        input_generator.manual_seed(752_000 + case_index * 100 + 2)
        input_cpu = torch.randn(
            (ROUTES, k), dtype=torch.bfloat16, generator=input_generator
        )

        source = input_cpu.to("xpu")
        weight = weight_cpu.to("xpu")
        scales = scale_cpu.permute(0, 2, 1).contiguous().to("xpu")
        rows = rows_cpu.to("xpu")
        offsets = offsets_cpu.to("xpu")
        incumbent_output = torch.empty(
            (ROUTES, n), dtype=torch.bfloat16, device="xpu"
        )
        candidate_outputs = {
            mode: torch.empty((ROUTES, n), dtype=torch.bfloat16, device="xpu")
            for mode in (0, 1)
        }

        def incumbent() -> None:
            torch.ops._xpu_C.cutlass_grouped_gemm_interface(
                source, None, weight, scales, None, incumbent_output,
                rows, n, k, EXPERTS
            )

        def candidate(mode: int) -> None:
            torch.ops._xpu_C.laguna_grouped_int4_onednn_out(
                source, weight, scales, offsets, candidate_outputs[mode], mode
            )

        incumbent()
        candidate(0)
        candidate(1)
        torch.xpu.synchronize()
        for mode in (0, 1):
            if not torch.equal(
                incumbent_output.view(torch.uint16),
                candidate_outputs[mode].view(torch.uint16),
            ):
                raise RuntimeError(f"pre-timing exactness failure for {name}/{mode}")

        arms: dict[str, Callable[[], None]] = {
            "incumbent": incumbent,
            "strict": lambda: candidate(0),
            "bf16": lambda: candidate(1),
        }
        for launch in arms.values():
            for _ in range(args.warmup_launches):
                launch()
            torch.xpu.synchronize()

        samples: dict[str, list[float]] = {arm: [] for arm in arms}
        arm_names = tuple(arms)
        for sample_index in range(args.timing_samples):
            order = arm_names[sample_index % len(arm_names) :] + arm_names[
                : sample_index % len(arm_names)
            ]
            for arm in order:
                torch.xpu.synchronize()
                start_ns = time.perf_counter_ns()
                for _ in range(args.launches_per_sample):
                    arms[arm]()
                torch.xpu.synchronize()
                samples[arm].append(
                    (time.perf_counter_ns() - start_ns)
                    / (args.launches_per_sample * 1_000_000.0)
                )

        medians = {arm: statistics.median(values) for arm, values in samples.items()}
        results.append(
            {
                "name": name,
                "n": n,
                "k": k,
                "total_m": ROUTES,
                "identity": {
                    "input_sha256": tensor_sha256(input_cpu),
                    "weight_sha256": tensor_sha256(weight_cpu),
                    "logical_scale_sha256": tensor_sha256(scale_cpu),
                    "rows_sha256": tensor_sha256(rows_cpu),
                    "offsets_sha256": tensor_sha256(offsets_cpu),
                },
                "samples_ms_per_call": samples,
                "medians_ms": medians,
            }
        )

    sums = {
        arm: sum(case["medians_ms"][arm] for case in results)
        for arm in ("incumbent", "strict", "bf16")
    }
    evaluations: dict[str, dict[str, Any]] = {}
    for mode in ("strict", "bf16"):
        shape_speedups = {
            case["name"]: case["medians_ms"]["incumbent"]
            / case["medians_ms"][mode]
            for case in results
        }
        evaluations[mode] = {
            "shape_speedups": shape_speedups,
            "sum_speedup": sums["incumbent"] / sums[mode],
            "no_shape_regression": min(shape_speedups.values()) >= 0.99,
            "paired_sum_pass": sums["incumbent"] / sums[mode] >= 1.05,
            "frozen_absolute_pass": sums[mode] <= FROZEN_CANDIDATE_MAX_SUM_MS,
        }
        evaluations[mode]["gate_pass"] = all(
            evaluations[mode][key]
            for key in (
                "no_shape_regression",
                "paired_sum_pass",
                "frozen_absolute_pass",
            )
        )

    payload = {
        "source_head": EXPECTED_SOURCE_HEAD,
        "extension": str(Path(args.extension).resolve()),
        "extension_sha256": sha256_file(Path(args.extension)),
        "protected_extension": str(Path(args.protected_extension).resolve()),
        "protected_extension_sha256": sha256_file(Path(args.protected_extension)),
        "grouped_dso": str(Path(args.grouped_dso).resolve()),
        "grouped_dso_sha256": sha256_file(Path(args.grouped_dso)),
        "timing_protocol": {
            "warmup_launches": args.warmup_launches,
            "timing_samples": args.timing_samples,
            "launches_per_sample": args.launches_per_sample,
            "rotated_arm_order": True,
        },
        "frozen_reference_sum_ms": FROZEN_REFERENCE_SUM_MS,
        "frozen_candidate_max_sum_ms": FROZEN_CANDIDATE_MAX_SUM_MS,
        "cases": results,
        "sum_medians_ms": sums,
        "evaluations": evaluations,
        "gate_pass": any(item["gate_pass"] for item in evaluations.values()),
    }
    Path(args.worker_output).write_text(json.dumps(payload, indent=2) + "\n")
    return 0


def run_parent(args: argparse.Namespace) -> int:
    extension = Path(args.extension).resolve()
    protected_extension = Path(args.protected_extension).resolve()
    grouped_dso = Path(args.grouped_dso).resolve()
    source_tree = Path(args.source_tree).resolve()
    output_dir = Path(args.output_dir).resolve()
    if sha256_file(protected_extension) != EXPECTED_PROTECTED_EXTENSION_SHA256:
        raise RuntimeError("protected extension hash drift")
    if sha256_file(grouped_dso) != EXPECTED_GROUPED_SHA256:
        raise RuntimeError("protected grouped-GEMM DSO hash drift")
    if git_head(source_tree) != EXPECTED_SOURCE_HEAD:
        raise RuntimeError("candidate source HEAD drift")
    if output_dir.exists():
        raise RuntimeError(f"refusing existing output directory: {output_dir}")
    output_dir.mkdir(parents=True)

    worker_output = output_dir / "summary.json"
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker",
        "--extension", str(extension),
        "--protected-extension", str(protected_extension),
        "--grouped-dso", str(grouped_dso),
        "--worker-output", str(worker_output),
        "--warmup-launches", str(args.warmup_launches),
        "--timing-samples", str(args.timing_samples),
        "--launches-per-sample", str(args.launches_per_sample),
    ]
    environment = os.environ.copy()
    environment.update(
        {
            "ZE_AFFINITY_MASK": str(args.rank),
            "ONEAPI_DEVICE_SELECTOR": "level_zero:0",
            "DNNL_VERBOSE": "0",
            "VLLM_XPU_LAGUNA_DECODE_GRF128": "1",
            "VLLM_XPU_LAGUNA_DECODE_TRANSPOSED_SCALES": "1",
            "VLLM_XPU_LAGUNA_DECODE_EXACT_SPECIALIZED": "0",
            "VLLM_XPU_LAGUNA_SCALE_VEC": "1",
            "VLLM_XPU_LAGUNA_DEQUANT_MAD": "0",
            "VLLM_XPU_LAGUNA_SCALE_FOLD": "0",
        }
    )
    environment["LD_LIBRARY_PATH"] = ":".join(
        (
            str(protected_extension.parent),
            str(extension.parent),
            "/home/steve/.venvs/deepseek-v4-xpu/lib",
            "/opt/intel/oneapi/umf/1.1/lib",
            "/opt/intel/oneapi/compiler/2025.3/lib",
            "/opt/intel/oneapi/compiler/2025.3/opt/compiler/lib",
        )
    )
    completed = subprocess.run(command, env=environment, text=True, capture_output=True)
    (output_dir / "worker.stdout").write_text(completed.stdout)
    (output_dir / "worker.stderr").write_text(completed.stderr)
    if completed.returncode != 0 or not worker_output.is_file():
        raise RuntimeError(f"worker failed with exit {completed.returncode}")
    payload = json.loads(worker_output.read_text())
    print(
        f"COMPONENT_RESULT={'PASS' if payload['gate_pass'] else 'STOP'} "
        f"incumbent={payload['sum_medians_ms']['incumbent']:.6f}ms "
        f"strict={payload['sum_medians_ms']['strict']:.6f}ms "
        f"bf16={payload['sum_medians_ms']['bf16']:.6f}ms"
    )
    return 0 if payload["gate_pass"] else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--extension", required=True)
    parser.add_argument("--protected-extension", required=True)
    parser.add_argument("--grouped-dso", required=True)
    parser.add_argument("--source-tree")
    parser.add_argument("--output-dir")
    parser.add_argument("--worker-output")
    parser.add_argument("--rank", type=int, default=0)
    parser.add_argument("--warmup-launches", type=int, default=200)
    parser.add_argument("--timing-samples", type=int, default=15)
    parser.add_argument("--launches-per-sample", type=int, default=40)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.worker:
        if not args.worker_output:
            raise RuntimeError("worker requires --worker-output")
        return run_worker(args)
    if not args.source_tree or not args.output_dir:
        raise RuntimeError("parent requires --source-tree and --output-dir")
    return run_parent(args)


if __name__ == "__main__":
    raise SystemExit(main())
