#!/usr/bin/env python3
"""Bitwise and timing gate for Laguna's decode-only 128-GRF INT4 GEMM."""

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
EXPECTED_CANDIDATE_HEAD = "e4163f93574326b2772742e0f51372a5a3777aa5"
EXPECTED_CANDIDATE_SHA256 = (
    "df2f63a04630c3b50d3ffe2d61db3e3d68914436ba14270dcc45ddfec6b3467f"
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
    if os.environ.get("VLLM_XPU_LAGUNA_DECODE_GRF128") != args.mode:
        raise RuntimeError("GRF128 selector drift")

    candidate_so = Path(args.candidate_so).resolve()
    mapped = mapped_grouped_gemm()
    if mapped != [str(candidate_so)]:
        raise RuntimeError(
            f"mapped grouped-GEMM drift: expected {[str(candidate_so)]}, got {mapped}"
        )

    results: list[dict[str, Any]] = []
    for case_index, (name, n, k) in enumerate(CASES):
        generator = torch.Generator(device="cpu")
        generator.manual_seed(731_000 + case_index)
        weight_cpu = torch.randint(
            -128,
            128,
            (LOCAL_EXPERTS, n, k // 2),
            dtype=torch.int8,
            generator=generator,
        )
        scale_cpu = torch.empty(
            (LOCAL_EXPERTS, n, k // 32), dtype=torch.bfloat16
        ).uniform_(0.0001, 0.02, generator=generator)
        route_ids = torch.randint(
            0, LOCAL_EXPERTS, (ROUTES,), dtype=torch.int64, generator=generator
        )
        rows_cpu = torch.bincount(route_ids, minlength=LOCAL_EXPERTS).to(
            torch.int32
        )
        if int(rows_cpu.sum()) != ROUTES:
            raise RuntimeError("route corpus sum drift")

        identity = {
            "weight_sha256": tensor_sha256(weight_cpu),
            "scale_sha256": tensor_sha256(scale_cpu),
            "rows_sha256": tensor_sha256(rows_cpu),
            "rows_max": int(rows_cpu.max()),
            "rows_nonzero": int(torch.count_nonzero(rows_cpu)),
        }
        weight = weight_cpu.to("xpu")
        scales = scale_cpu.to("xpu")
        rows = rows_cpu.to("xpu")
        del weight_cpu, scale_cpu, route_ids

        output_hashes: list[str] = []
        input_hashes: list[str] = []
        last_input = None
        output = torch.empty((ROUTES, n), dtype=torch.bfloat16, device="xpu")

        def launch(input_a: Any) -> None:
            torch.ops._xpu_C.cutlass_grouped_gemm_interface(
                ptr_A=input_a,
                ptr_A_scale=None,
                ptr_B=weight,
                ptr_B_scale=scales,
                ptr_bias=None,
                ptr_D=output,
                rows_per_expert=rows,
                N=n,
                K=k,
                num_experts=LOCAL_EXPERTS,
            )

        for input_index in range(3):
            input_generator = torch.Generator(device="cpu")
            input_generator.manual_seed(732_000 + case_index * 100 + input_index)
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
        for _ in range(8):
            launch(last_input)
        torch.xpu.synchronize()
        timing_ms: list[float] = []
        for _ in range(9):
            start = time.perf_counter_ns()
            for _ in range(20):
                launch(last_input)
            torch.xpu.synchronize()
            timing_ms.append((time.perf_counter_ns() - start) / 20_000_000.0)

        results.append(
            {
                "name": name,
                "n": n,
                "k": k,
                "total_m": ROUTES,
                "identity": identity,
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
        "selector": os.environ.get("VLLM_XPU_LAGUNA_DECODE_GRF128"),
        "scale_vec": os.environ.get("VLLM_XPU_LAGUNA_SCALE_VEC"),
        "dequant_mad": os.environ.get("VLLM_XPU_LAGUNA_DEQUANT_MAD"),
        "scale_fold": os.environ.get("VLLM_XPU_LAGUNA_SCALE_FOLD"),
        "prefetch_dist": os.environ.get("VLLM_XPU_LAGUNA_PREFETCH_DIST"),
        "ze_affinity_mask": os.environ.get("ZE_AFFINITY_MASK"),
        "oneapi_device_selector": os.environ.get("ONEAPI_DEVICE_SELECTOR"),
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
    if sha256_file(candidate_so) != EXPECTED_CANDIDATE_SHA256:
        raise RuntimeError("candidate DSO SHA-256 drift")
    if git_head(Path(args.candidate_tree).resolve()) != EXPECTED_CANDIDATE_HEAD:
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
    env_base["LD_LIBRARY_PATH"] = str(candidate_so.parent) + (
        ":" + env_base["LD_LIBRARY_PATH"]
        if env_base.get("LD_LIBRARY_PATH")
        else ""
    )
    env_base["ZE_AFFINITY_MASK"] = str(args.rank)
    env_base["ONEAPI_DEVICE_SELECTOR"] = "level_zero:0"
    env_base["VLLM_XPU_LAGUNA_SCALE_VEC"] = "1"
    env_base["VLLM_XPU_LAGUNA_DEQUANT_MAD"] = "0"
    env_base["VLLM_XPU_LAGUNA_SCALE_FOLD"] = "0"
    env_base["VLLM_XPU_LAGUNA_PREFETCH_DIST"] = "6"
    env_base.pop("VLLM_XPU_MXFP4_SMALL_M_N", None)

    records: dict[str, Any] = {}
    for mode in ("0", "1"):
        worker_output = output_dir / f"mode-{mode}.json"
        stdout_path = output_dir / f"mode-{mode}.stdout"
        stderr_path = output_dir / f"mode-{mode}.stderr"
        env = env_base.copy()
        env["VLLM_XPU_LAGUNA_DECODE_GRF128"] = mode
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--worker",
            "--mode",
            mode,
            "--candidate-so",
            str(candidate_so),
            "--worker-output",
            str(worker_output),
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
            control["identity"] == candidate["identity"]
            and control["input_sha256"] == candidate["input_sha256"]
        )
        outputs_equal = control["output_sha256"] == candidate["output_sha256"]
        if not inputs_equal:
            raise RuntimeError(f"input corpus drift for {control['name']}")
        exact_count += sum(
            left == right
            for left, right in zip(
                control["output_sha256"], candidate["output_sha256"]
            )
        )
        comparisons.append(
            {
                "name": control["name"],
                "inputs_equal": inputs_equal,
                "outputs_equal": outputs_equal,
                "control_median_ms": control["timing_median_ms"],
                "candidate_median_ms": candidate["timing_median_ms"],
                "speedup": control["timing_median_ms"]
                / candidate["timing_median_ms"],
            }
        )
    total_exact = sum(len(case["output_sha256"]) for case in records["0"]["cases"])
    passed = exact_count == total_exact
    summary = {
        "status": "pass" if passed else "fail",
        "candidate_source_head": EXPECTED_CANDIDATE_HEAD,
        "candidate_so": str(candidate_so),
        "candidate_sha256": EXPECTED_CANDIDATE_SHA256,
        "kernel_tree": str(kernel_tree),
        "rank": args.rank,
        "exact": exact_count,
        "total": total_exact,
        "comparisons": comparisons,
        "workers": records,
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(
        f"PROBE_RESULT={'PASS' if passed else 'FAIL'} "
        f"exact={exact_count}/{total_exact}"
    )
    for comparison in comparisons:
        print(
            f"{comparison['name']} control_ms={comparison['control_median_ms']:.6f} "
            f"candidate_ms={comparison['candidate_median_ms']:.6f} "
            f"speedup={comparison['speedup']:.6f}"
        )
    return 0 if passed else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-so")
    parser.add_argument("--candidate-tree")
    parser.add_argument("--kernel-tree")
    parser.add_argument("--output-dir")
    parser.add_argument("--rank", type=int, default=0)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--mode", choices=("0", "1"))
    parser.add_argument("--worker-output")
    args = parser.parse_args()
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
