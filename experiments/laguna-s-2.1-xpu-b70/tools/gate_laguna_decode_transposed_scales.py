#!/usr/bin/env python3
"""Exactness/timing gate for Laguna's transposed INT4 decode scales."""

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
from typing import Any


HIDDEN = 3072
INTERMEDIATE = 1024
LOCAL_EXPERTS = 64
ROUTES = 120
EXPECTED_CANDIDATE_HEAD = "2f0b0611b3999a76592c79a314d69f4b7ab8f285"
EXPECTED_CANDIDATE_SHA256 = (
    "c4845ed7704a9afcf59e12f9d51e288f293f2e39966e283e2a7e322fed68b839"
)
CASES = (
    ("w13", 2 * INTERMEDIATE, HIDDEN),
    ("w2", HIDDEN, INTERMEDIATE),
)


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
    import vllm_xpu_kernels._xpu_C as xpu_extension  # noqa: F401

    if torch.xpu.device_count() != 1:
        raise RuntimeError(
            f"worker requires exactly one visible XPU, got {torch.xpu.device_count()}"
        )
    transposed_mode = args.mode if args.selector == "transposed_scales" else "1"
    expected_env = {
        "VLLM_XPU_LAGUNA_DECODE_GRF128": "1",
        "VLLM_XPU_LAGUNA_DECODE_EXACT_SPECIALIZED": "0",
        "VLLM_XPU_LAGUNA_DECODE_TRANSPOSED_SCALES": transposed_mode,
        "VLLM_XPU_LAGUNA_DECODE_TRANSPOSED_MAD": (
            args.mode if args.selector == "dequant_mad_grf128_transposed" else "0"
        ),
        "VLLM_XPU_LAGUNA_SCALE_LANE_DEDUP": (
            args.mode if args.selector == "scale_lane_dedup" else "0"
        ),
        "VLLM_XPU_LAGUNA_DECODE_NO_KLOOP_BARRIERS": (
            args.mode if args.selector == "no_kloop_barriers" else "0"
        ),
        "VLLM_XPU_LAGUNA_DECODE_DIRECT_SCHEDULER": (
            args.mode if args.selector == "deterministic_scheduler" else "0"
        ),
        "VLLM_XPU_LAGUNA_DECODE_DIRECT_OFFSETS": (
            args.mode if args.selector == "direct_offsets" else "0"
        ),
        "VLLM_XPU_LAGUNA_DECODE_PERSISTENT_WORKLIST": (
            args.mode if args.selector == "persistent_worklist" else "0"
        ),
        "VLLM_XPU_LAGUNA_DECODE_PERSISTENT_CHUNK4": (
            args.mode if args.selector == "persistent_chunk4" else "0"
        ),
        "VLLM_XPU_LAGUNA_DECODE_LOSSLESS_PACKED_SCALES": (
            args.mode if args.selector == "lossless_packed_scales" else "0"
        ),
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

    results: list[dict[str, Any]] = []
    for case_index, (name, n, k) in enumerate(CASES):
        generator = torch.Generator(device="cpu")
        generator.manual_seed(751_000 + case_index)
        weight_cpu = torch.randint(
            -128,
            128,
            (LOCAL_EXPERTS, n, k // 2),
            dtype=torch.int8,
            generator=generator,
        )
        if args.selector == "lossless_packed_scales":
            scale_low = torch.randint(
                0,
                256,
                (LOCAL_EXPERTS, k // 32, n // 32, 32),
                dtype=torch.int32,
                generator=generator,
            )
            scale_base = torch.randint(
                57,
                59,
                (LOCAL_EXPERTS, k // 32, n // 32, 1),
                dtype=torch.int32,
                generator=generator,
            )
            scale_delta = torch.randint(
                0,
                4,
                (LOCAL_EXPERTS, k // 32, n // 32, 32),
                dtype=torch.int32,
                generator=generator,
            )
            scale_bits = scale_low | ((scale_base + scale_delta) << 8)
            physical_seed = (
                scale_bits.to(torch.uint16)
                .view(torch.bfloat16)
                .reshape(LOCAL_EXPERTS, k // 32, n)
            )
            logical_scale_cpu = physical_seed.permute(0, 2, 1).contiguous()
        else:
            logical_scale_cpu = torch.empty(
                (LOCAL_EXPERTS, n, k // 32), dtype=torch.bfloat16
            ).uniform_(0.0001, 0.02, generator=generator)
        route_ids = torch.randint(
            0, LOCAL_EXPERTS, (ROUTES,), dtype=torch.int64, generator=generator
        )
        rows_cpu = torch.bincount(route_ids, minlength=LOCAL_EXPERTS).to(torch.int32)
        if int(rows_cpu.sum()) != ROUTES:
            raise RuntimeError("route corpus sum drift")

        logical_identity = {
            "weight_sha256": tensor_sha256(weight_cpu),
            "logical_scale_sha256": tensor_sha256(logical_scale_cpu),
            "rows_sha256": tensor_sha256(rows_cpu),
            "rows_max": int(rows_cpu.max()),
            "rows_nonzero": int(torch.count_nonzero(rows_cpu)),
        }
        if args.selector == "persistent_worklist" and args.mode == "1":
            worklist = []
            pre_rows = 0
            for expert_id, expert_rows in enumerate(rows_cpu.tolist()):
                for expert_m_tile in range((expert_rows + 7) // 8):
                    worklist.extend((expert_id, pre_rows, expert_rows, expert_m_tile))
                pre_rows += expert_rows
            rows_arg_cpu = torch.tensor(
                (len(worklist) // 4, *worklist), dtype=torch.int32
            )
            scheduler_metadata = "persistent_m_tile_worklist_v1"
        elif args.selector == "direct_offsets" and args.mode == "1":
            rows_arg_cpu = torch.cat(
                (
                    torch.zeros(1, dtype=torch.int32),
                    torch.cumsum(rows_cpu, dim=0, dtype=torch.int32),
                )
            )
            scheduler_metadata = "exclusive_offsets_65"
        else:
            rows_arg_cpu = rows_cpu
            scheduler_metadata = "counts_64"
        if transposed_mode == "1":
            physical_scale_cpu = logical_scale_cpu.permute(0, 2, 1).contiguous()
            physical_layout = "expert_group_n"
        else:
            physical_scale_cpu = logical_scale_cpu
            physical_layout = "expert_n_group"
        packed_scale_bytes = None
        if args.selector == "lossless_packed_scales" and args.mode == "1":
            scale_bits = physical_scale_cpu.view(torch.uint16).to(torch.int32)
            scale_blocks = scale_bits.reshape(LOCAL_EXPERTS, k // 32, n // 32, 32)
            scale_high = scale_blocks >> 8
            scale_base = scale_high.amin(dim=-1)
            scale_delta = scale_high - scale_base.unsqueeze(-1)
            if int(scale_delta.amax()) > 3:
                raise RuntimeError("lossless scale record high-byte span exceeded 3")
            scale_low = (scale_blocks & 0xFF).to(torch.uint8)
            delta_quads = scale_delta.reshape(LOCAL_EXPERTS, k // 32, n // 32, 8, 4)
            shifts = torch.tensor((0, 2, 4, 6), dtype=torch.int32)
            scale_codes = torch.sum(delta_quads << shifts, dim=-1).to(torch.uint8)
            scale_records = torch.empty(
                (LOCAL_EXPERTS, k // 32, n // 32, 41), dtype=torch.uint8
            )
            scale_records[..., :32] = scale_low
            scale_records[..., 32:40] = scale_codes
            scale_records[..., 40] = scale_base.to(torch.uint8)
            packed = scale_records.flatten()
            packed_storage = torch.zeros_like(physical_scale_cpu)
            packed_storage.view(torch.uint8).flatten()[: packed.numel()].copy_(packed)
            physical_scale_cpu = packed_storage
            physical_layout = "expert_group_n_lossless_32x41"
            packed_scale_bytes = packed.numel()
        physical_scale = {
            "layout": physical_layout,
            "shape": list(physical_scale_cpu.shape),
            "sha256": tensor_sha256(physical_scale_cpu),
            "packed_bytes": packed_scale_bytes,
        }
        weight = weight_cpu.to("xpu")
        scales = physical_scale_cpu.to("xpu")
        rows = rows_arg_cpu.to("xpu")
        del (
            weight_cpu,
            logical_scale_cpu,
            physical_scale_cpu,
            route_ids,
            rows_arg_cpu,
        )

        output_hashes: list[str] = []
        input_hashes: list[str] = []
        last_input = None
        output = torch.empty((ROUTES, n), dtype=torch.bfloat16, device="xpu")

        def launch(
            input_a: Any,
            weight_arg: Any = weight,
            scales_arg: Any = scales,
            output_arg: Any = output,
            rows_arg: Any = rows,
        ) -> None:
            torch.ops._xpu_C.cutlass_grouped_gemm_interface(
                ptr_A=input_a,
                ptr_A_scale=None,
                ptr_B=weight_arg,
                ptr_B_scale=scales_arg,
                ptr_bias=None,
                ptr_D=output_arg,
                rows_per_expert=rows_arg,
                N=n,
                K=k,
                num_experts=LOCAL_EXPERTS,
            )

        for input_index in range(3):
            input_generator = torch.Generator(device="cpu")
            input_generator.manual_seed(752_000 + case_index * 100 + input_index)
            input_cpu = torch.randn(
                (ROUTES, k), dtype=torch.bfloat16, generator=input_generator
            )
            input_hashes.append(tensor_sha256(input_cpu))
            input_a = input_cpu.to("xpu")
            del input_cpu
            launch(input_a)
            torch.xpu.synchronize()
            output_hashes.append(tensor_sha256(output))
            last_input = input_a

        assert last_input is not None
        for _ in range(args.warmup_launches):
            launch(last_input)
        torch.xpu.synchronize()
        timing_ms: list[float] = []
        for _ in range(args.timing_samples):
            start = time.perf_counter_ns()
            for _ in range(args.launches_per_sample):
                launch(last_input)
            torch.xpu.synchronize()
            timing_ms.append(
                (time.perf_counter_ns() - start)
                / (args.launches_per_sample * 1_000_000.0)
            )

        results.append(
            {
                "name": name,
                "n": n,
                "k": k,
                "total_m": ROUTES,
                "logical_identity": logical_identity,
                "physical_scale": physical_scale,
                "scheduler_metadata": scheduler_metadata,
                "input_sha256": input_hashes,
                "output_sha256": output_hashes,
                "timing_ms_per_call": timing_ms,
                "timing_median_ms": statistics.median(timing_ms),
            }
        )
        del weight, scales, rows, output, last_input
        torch.xpu.empty_cache()

    payload = {
        "mode": args.mode,
        "selector": args.selector,
        "environment": {name: os.environ.get(name) for name in sorted(expected_env)},
        "prefetch_dist": os.environ.get("VLLM_XPU_LAGUNA_PREFETCH_DIST"),
        "ze_affinity_mask": os.environ.get("ZE_AFFINITY_MASK"),
        "oneapi_device_selector": os.environ.get("ONEAPI_DEVICE_SELECTOR"),
        "timing_protocol": {
            "warmup_launches": args.warmup_launches,
            "timing_samples": args.timing_samples,
            "launches_per_sample": args.launches_per_sample,
        },
        "candidate_so": str(candidate_so),
        "candidate_sha256": sha256_file(candidate_so),
        "mapped_grouped_gemm": mapped,
        "xpu_extension": str(Path(xpu_extension.__file__).resolve()),
        "cases": results,
    }
    Path(args.worker_output).write_text(json.dumps(payload, indent=2) + "\n")
    print(f"WORKER_RESULT=PASS mode={args.mode} cases={len(results)}")
    return 0


def run_gate(args: argparse.Namespace) -> int:
    candidate_so = Path(args.candidate_so).resolve()
    kernel_tree = Path(args.kernel_tree).resolve()
    output_dir = Path(args.output_dir).resolve()
    if not candidate_so.is_file():
        raise RuntimeError(f"missing candidate DSO: {candidate_so}")
    expected_sha256 = args.expected_sha256 or EXPECTED_CANDIDATE_SHA256
    expected_head = args.expected_head or EXPECTED_CANDIDATE_HEAD
    if sha256_file(candidate_so) != expected_sha256:
        raise RuntimeError("candidate DSO SHA-256 drift")
    if git_head(Path(args.candidate_tree).resolve()) != expected_head:
        raise RuntimeError("candidate source HEAD drift")
    extension = kernel_tree / "vllm_xpu_kernels/_xpu_C.abi3.so"
    if not extension.is_file():
        raise RuntimeError(f"missing incumbent XPU extension: {extension}")
    if output_dir.exists():
        raise RuntimeError(f"refusing existing output directory: {output_dir}")
    output_dir.mkdir(parents=True)

    env_base = os.environ.copy()
    env_base["PYTHONPATH"] = str(kernel_tree) + (
        ":" + env_base["PYTHONPATH"] if env_base.get("PYTHONPATH") else ""
    )
    env_base["LD_LIBRARY_PATH"] = ":".join(
        (
            str(candidate_so.parent),
            str(Path(sys.prefix) / "lib"),
            "/opt/intel/oneapi/umf/1.1/lib",
            "/opt/intel/oneapi/compiler/2025.3/lib",
            "/opt/intel/oneapi/compiler/2025.3/opt/compiler/lib",
        )
    )
    env_base["ZE_AFFINITY_MASK"] = str(args.rank)
    env_base["ONEAPI_DEVICE_SELECTOR"] = "level_zero:0"
    env_base["VLLM_XPU_LAGUNA_DECODE_GRF128"] = "1"
    env_base["VLLM_XPU_LAGUNA_DECODE_EXACT_SPECIALIZED"] = "0"
    env_base["VLLM_XPU_LAGUNA_SCALE_VEC"] = "1"
    env_base["VLLM_XPU_LAGUNA_DEQUANT_MAD"] = "0"
    env_base["VLLM_XPU_LAGUNA_SCALE_FOLD"] = "0"
    env_base["VLLM_XPU_LAGUNA_DECODE_TRANSPOSED_MAD"] = "0"
    env_base["VLLM_XPU_LAGUNA_SCALE_LANE_DEDUP"] = "0"
    env_base["VLLM_XPU_LAGUNA_DECODE_NO_KLOOP_BARRIERS"] = "0"
    env_base["VLLM_XPU_LAGUNA_DECODE_DIRECT_SCHEDULER"] = "0"
    env_base["VLLM_XPU_LAGUNA_DECODE_DIRECT_OFFSETS"] = "0"
    env_base["VLLM_XPU_LAGUNA_DECODE_PERSISTENT_WORKLIST"] = "0"
    env_base["VLLM_XPU_LAGUNA_DECODE_PERSISTENT_CHUNK4"] = "0"
    env_base["VLLM_XPU_LAGUNA_DECODE_LOSSLESS_PACKED_SCALES"] = "0"
    env_base["VLLM_XPU_LAGUNA_PREFETCH_DIST"] = "6"
    env_base.pop("VLLM_XPU_MXFP4_SMALL_M_N", None)

    records: dict[str, Any] = {}
    for mode in ("0", "1"):
        worker_output = output_dir / f"mode-{mode}.json"
        stdout_path = output_dir / f"mode-{mode}.stdout"
        stderr_path = output_dir / f"mode-{mode}.stderr"
        env = env_base.copy()
        env["VLLM_XPU_LAGUNA_DECODE_TRANSPOSED_SCALES"] = (
            mode if args.selector == "transposed_scales" else "1"
        )
        env["VLLM_XPU_LAGUNA_DECODE_TRANSPOSED_MAD"] = (
            mode if args.selector == "dequant_mad_grf128_transposed" else "0"
        )
        env["VLLM_XPU_LAGUNA_SCALE_LANE_DEDUP"] = (
            mode if args.selector == "scale_lane_dedup" else "0"
        )
        env["VLLM_XPU_LAGUNA_DECODE_NO_KLOOP_BARRIERS"] = (
            mode if args.selector == "no_kloop_barriers" else "0"
        )
        env["VLLM_XPU_LAGUNA_DECODE_DIRECT_SCHEDULER"] = (
            mode if args.selector == "deterministic_scheduler" else "0"
        )
        env["VLLM_XPU_LAGUNA_DECODE_DIRECT_OFFSETS"] = (
            mode if args.selector == "direct_offsets" else "0"
        )
        env["VLLM_XPU_LAGUNA_DECODE_PERSISTENT_WORKLIST"] = (
            mode if args.selector == "persistent_worklist" else "0"
        )
        env["VLLM_XPU_LAGUNA_DECODE_PERSISTENT_CHUNK4"] = (
            mode if args.selector == "persistent_chunk4" else "0"
        )
        env["VLLM_XPU_LAGUNA_DECODE_LOSSLESS_PACKED_SCALES"] = (
            mode if args.selector == "lossless_packed_scales" else "0"
        )
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--worker",
            "--mode",
            mode,
            "--selector",
            args.selector,
            "--candidate-so",
            str(candidate_so),
            "--worker-output",
            str(worker_output),
            "--warmup-launches",
            str(args.warmup_launches),
            "--timing-samples",
            str(args.timing_samples),
            "--launches-per-sample",
            str(args.launches_per_sample),
        ]
        with stdout_path.open("w") as stdout, stderr_path.open("w") as stderr:
            completed = subprocess.run(
                command, env=env, stdout=stdout, stderr=stderr, text=True
            )
        if completed.returncode != 0:
            raise RuntimeError(
                f"mode {mode} worker failed with {completed.returncode}; "
                f"see {stderr_path}"
            )
        records[mode] = json.loads(worker_output.read_text())

    comparisons: list[dict[str, Any]] = []
    exact_count = 0
    for control, candidate in zip(records["0"]["cases"], records["1"]["cases"]):
        if control["name"] != candidate["name"]:
            raise RuntimeError("case order drift")
        inputs_equal = (
            control["logical_identity"] == candidate["logical_identity"]
            and control["input_sha256"] == candidate["input_sha256"]
        )
        outputs_equal = control["output_sha256"] == candidate["output_sha256"]
        if not inputs_equal:
            raise RuntimeError(f"logical input corpus drift for {control['name']}")
        exact_count += sum(
            left == right
            for left, right in zip(control["output_sha256"], candidate["output_sha256"])
        )
        comparisons.append(
            {
                "name": control["name"],
                "inputs_equal": inputs_equal,
                "outputs_equal": outputs_equal,
                "control_median_ms": control["timing_median_ms"],
                "candidate_median_ms": candidate["timing_median_ms"],
                "speedup": control["timing_median_ms"] / candidate["timing_median_ms"],
            }
        )
    total_exact = sum(len(case["output_sha256"]) for case in records["0"]["cases"])
    control_sum_ms = sum(item["control_median_ms"] for item in comparisons)
    candidate_sum_ms = sum(item["candidate_median_ms"] for item in comparisons)
    summed_speedup = control_sum_ms / candidate_sum_ms
    exact_passed = exact_count == total_exact
    performance_passed = summed_speedup >= args.performance_threshold
    summary = {
        "status": "pass" if exact_passed and performance_passed else "stop",
        "exact_passed": exact_passed,
        "performance_passed": performance_passed,
        "performance_threshold_speedup": args.performance_threshold,
        "selector": args.selector,
        "candidate_source_head": expected_head,
        "candidate_so": str(candidate_so),
        "candidate_sha256": expected_sha256,
        "kernel_tree": str(kernel_tree),
        "rank": args.rank,
        "exact": exact_count,
        "total": total_exact,
        "control_sum_ms": control_sum_ms,
        "candidate_sum_ms": candidate_sum_ms,
        "summed_speedup": summed_speedup,
        "comparisons": comparisons,
        "workers": records,
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(
        f"PROBE_RESULT={'PASS' if exact_passed else 'FAIL'} "
        f"exact={exact_count}/{total_exact}"
    )
    for comparison in comparisons:
        print(
            f"{comparison['name']} control_ms={comparison['control_median_ms']:.6f} "
            f"candidate_ms={comparison['candidate_median_ms']:.6f} "
            f"speedup={comparison['speedup']:.6f}"
        )
    print(
        f"SUMMED_SPEEDUP={summed_speedup:.6f} "
        f"PERFORMANCE_GATE={'PASS' if performance_passed else 'STOP'}"
    )
    return 0 if exact_passed else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-so")
    parser.add_argument("--candidate-tree")
    parser.add_argument("--kernel-tree")
    parser.add_argument("--output-dir")
    parser.add_argument("--rank", type=int, default=0)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--mode", choices=("0", "1"))
    parser.add_argument(
        "--selector",
        choices=(
            "transposed_scales",
            "dequant_mad_grf128_transposed",
            "scale_lane_dedup",
            "no_kloop_barriers",
            "deterministic_scheduler",
            "direct_offsets",
            "persistent_worklist",
            "persistent_chunk4",
            "lossless_packed_scales",
        ),
        default="transposed_scales",
    )
    parser.add_argument("--expected-head")
    parser.add_argument("--expected-sha256")
    parser.add_argument("--performance-threshold", type=float, default=1.02)
    parser.add_argument("--worker-output")
    parser.add_argument("--warmup-launches", type=int, default=8)
    parser.add_argument("--timing-samples", type=int, default=9)
    parser.add_argument("--launches-per-sample", type=int, default=20)
    args = parser.parse_args()
    for name in ("warmup_launches", "timing_samples", "launches_per_sample"):
        if getattr(args, name) <= 0:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    if args.worker:
        required = (args.mode, args.candidate_so, args.worker_output)
    else:
        required = (
            args.candidate_so,
            args.candidate_tree,
            args.kernel_tree,
            args.output_dir,
        )
    if any(value is None for value in required):
        parser.error("missing required arguments for selected mode")
    return args


if __name__ == "__main__":
    parsed = parse_args()
    raise SystemExit(run_worker(parsed) if parsed.worker else run_gate(parsed))
