#!/usr/bin/env python3
"""Exactness-only gate for the Laguna grouped oneDNN INT4 oracle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


HIDDEN = 3072
INTERMEDIATE = 1024
EXPERTS = 64
ROUTES = 120
EXPECTED_SOURCE_HEAD = "c168f9e28a5cd508f9a195d7e9ef15dfecbe20ed"
EXPECTED_PROTECTED_EXTENSION_SHA256 = (
    "f5f672130cc1b1d550646f732a6d576952c49514eba7a10db60fc1c361938fd8"
)
EXPECTED_GROUPED_SHA256 = (
    "c4845ed7704a9afcf59e12f9d51e288f293f2e39966e283e2a7e322fed68b839"
)
CASES = (("w13", 2 * INTERMEDIATE, HIDDEN), ("w2", HIDDEN, INTERMEDIATE))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tensor_sha256(tensor: Any) -> str:
    import torch

    raw = tensor.detach().cpu().contiguous().view(torch.uint8).numpy()
    return hashlib.sha256(raw).hexdigest()


def mapped_grouped_gemm() -> list[str]:
    paths: set[str] = set()
    for line in Path("/proc/self/maps").read_text().splitlines():
        if "libgrouped_gemm_xe_2.so" not in line:
            continue
        path = line.split()[-1]
        if path.startswith("/"):
            paths.add(str(Path(path).resolve()))
    return sorted(paths)


def run_worker(args: argparse.Namespace) -> int:
    import torch

    torch.ops.load_library(str(Path(args.protected_extension).resolve()))
    torch.ops.load_library(str(Path(args.extension).resolve()))
    if torch.xpu.device_count() != 1:
        raise RuntimeError("worker requires exactly one visible XPU")

    mapped = mapped_grouped_gemm()
    expected_grouped = str(Path(args.grouped_dso).resolve())
    if mapped != [expected_grouped]:
        raise RuntimeError(
            f"grouped-GEMM mapping drift: expected {[expected_grouped]}, got {mapped}"
        )

    cases: list[dict[str, Any]] = []
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
        logical_scale_cpu = torch.empty(
            (EXPERTS, n, k // 32), dtype=torch.bfloat16
        ).uniform_(0.0001, 0.02, generator=generator)
        route_ids = torch.randint(
            0, EXPERTS, (ROUTES,), dtype=torch.int64, generator=generator
        )
        rows_cpu = torch.bincount(route_ids, minlength=EXPERTS).to(torch.int32)
        offsets_cpu = torch.cumsum(rows_cpu, dim=0, dtype=torch.int32)
        if int(offsets_cpu[-1]) != ROUTES:
            raise RuntimeError("grouped offsets do not end at total M")

        identity_before = {
            "weight": tensor_sha256(weight_cpu),
            "logical_scale": tensor_sha256(logical_scale_cpu),
            "rows": tensor_sha256(rows_cpu),
            "offsets": tensor_sha256(offsets_cpu),
            "rows_max": int(rows_cpu.max()),
            "rows_nonzero": int(torch.count_nonzero(rows_cpu)),
        }
        weight = weight_cpu.to("xpu")
        scales = logical_scale_cpu.permute(0, 2, 1).contiguous().to("xpu")
        rows = rows_cpu.to("xpu")
        offsets = offsets_cpu.to("xpu")

        modes: dict[str, list[dict[str, Any]]] = {"strict": [], "bf16": []}
        for input_index in range(3):
            input_generator = torch.Generator(device="cpu")
            input_generator.manual_seed(752_000 + case_index * 100 + input_index)
            input_cpu = torch.randn(
                (ROUTES, k), dtype=torch.bfloat16, generator=input_generator
            )
            input_hash = tensor_sha256(input_cpu)
            source = input_cpu.to("xpu")
            control = torch.empty(
                (ROUTES, n), dtype=torch.bfloat16, device="xpu"
            )
            torch.ops._xpu_C.cutlass_grouped_gemm_interface(
                source, None, weight, scales, None, control, rows, n, k, EXPERTS
            )
            for mode_index, mode_name in enumerate(("strict", "bf16")):
                candidate = torch.ops._xpu_C.laguna_grouped_int4_onednn_oracle(
                    source, weight, scales, offsets, mode_index
                )
                torch.xpu.synchronize()
                control_bits = control.view(torch.uint16)
                candidate_bits = candidate.view(torch.uint16)
                difference = (control.float() - candidate.float()).abs()
                modes[mode_name].append(
                    {
                        "input_sha256": input_hash,
                        "control_sha256": tensor_sha256(control),
                        "candidate_sha256": tensor_sha256(candidate),
                        "raw_bf16_exact": bool(torch.equal(control_bits, candidate_bits)),
                        "different_elements": int(
                            torch.count_nonzero(control_bits != candidate_bits).cpu()
                        ),
                        "max_abs_difference": float(difference.max().cpu()),
                        "mean_abs_difference": float(difference.mean().cpu()),
                    }
                )
            if tensor_sha256(source) != input_hash:
                raise RuntimeError("source tensor mutated")

        identity_after = {
            "weight": tensor_sha256(weight),
            "logical_scale": tensor_sha256(scales.permute(0, 2, 1)),
            "rows": tensor_sha256(rows),
            "offsets": tensor_sha256(offsets),
            "rows_max": int(rows.max().cpu()),
            "rows_nonzero": int(torch.count_nonzero(rows).cpu()),
        }
        if identity_after != identity_before:
            raise RuntimeError(f"immutable input drift for {name}")
        cases.append(
            {
                "name": name,
                "n": n,
                "k": k,
                "total_m": ROUTES,
                "identity": identity_before,
                "modes": modes,
            }
        )

    result = {
        "extension": str(Path(args.extension).resolve()),
        "extension_sha256": sha256_file(Path(args.extension)),
        "protected_extension": str(Path(args.protected_extension).resolve()),
        "protected_extension_sha256": sha256_file(Path(args.protected_extension)),
        "grouped_dso": expected_grouped,
        "grouped_dso_sha256": sha256_file(Path(args.grouped_dso)),
        "mapped_grouped_gemm": mapped,
        "source_head": EXPECTED_SOURCE_HEAD,
        "cases": cases,
    }
    Path(args.worker_output).write_text(json.dumps(result, indent=2) + "\n")
    return 0


def run_parent(args: argparse.Namespace) -> int:
    extension = Path(args.extension).resolve()
    protected_extension = Path(args.protected_extension).resolve()
    grouped_dso = Path(args.grouped_dso).resolve()
    output_dir = Path(args.output_dir).resolve()
    source_tree = Path(args.source_tree).resolve()
    if (
        not extension.is_file()
        or not protected_extension.is_file()
        or not grouped_dso.is_file()
    ):
        raise RuntimeError("missing oracle sidecar or protected extension/DSO")
    if sha256_file(protected_extension) != EXPECTED_PROTECTED_EXTENSION_SHA256:
        raise RuntimeError("protected extension hash drift")
    if sha256_file(grouped_dso) != EXPECTED_GROUPED_SHA256:
        raise RuntimeError("protected grouped-GEMM DSO hash drift")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=source_tree,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    if head != EXPECTED_SOURCE_HEAD:
        raise RuntimeError(f"candidate source HEAD drift: {head}")
    if output_dir.exists():
        raise RuntimeError(f"refusing existing output directory: {output_dir}")
    output_dir.mkdir(parents=True)

    worker_output = output_dir / "worker.json"
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker",
        "--extension",
        str(extension),
        "--protected-extension",
        str(protected_extension),
        "--grouped-dso",
        str(grouped_dso),
        "--worker-output",
        str(worker_output),
    ]
    environment = os.environ.copy()
    environment.update(
        {
            "ZE_AFFINITY_MASK": str(args.rank),
            "ONEAPI_DEVICE_SELECTOR": "level_zero:0",
            "DNNL_VERBOSE": "1",
            "VLLM_XPU_LAGUNA_DECODE_GRF128": "1",
            "VLLM_XPU_LAGUNA_DECODE_TRANSPOSED_SCALES": "1",
            "VLLM_XPU_LAGUNA_DECODE_EXACT_SPECIALIZED": "0",
            "VLLM_XPU_LAGUNA_SCALE_VEC": "1",
            "VLLM_XPU_LAGUNA_DEQUANT_MAD": "0",
            "VLLM_XPU_LAGUNA_SCALE_FOLD": "0",
        }
    )
    library_dirs = [
        str(protected_extension.parent),
        str(grouped_dso.parent),
        str(extension.parent),
        "/home/steve/.venvs/deepseek-v4-xpu/lib",
        "/opt/intel/oneapi/umf/1.1/lib",
        "/opt/intel/oneapi/compiler/2025.3/lib",
        "/opt/intel/oneapi/compiler/2025.3/opt/compiler/lib",
    ]
    environment["LD_LIBRARY_PATH"] = ":".join(library_dirs)
    completed = subprocess.run(command, env=environment, text=True, capture_output=True)
    (output_dir / "worker.stdout").write_text(completed.stdout)
    (output_dir / "worker.stderr").write_text(completed.stderr)
    if completed.returncode != 0 or not worker_output.is_file():
        raise RuntimeError(
            f"worker failed with exit {completed.returncode}; inspect {output_dir}"
        )

    result = json.loads(worker_output.read_text())
    exact = {
        mode: sum(
            int(trial["raw_bf16_exact"])
            for case in result["cases"]
            for trial in case["modes"][mode]
        )
        for mode in ("strict", "bf16")
    }
    result["exact_counts"] = exact
    result["gate_pass"] = any(count == 6 for count in exact.values())
    (output_dir / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        f"ORACLE_RESULT={'PASS' if result['gate_pass'] else 'STOP'} "
        f"strict={exact['strict']}/6 bf16={exact['bf16']}/6"
    )
    return 0 if result["gate_pass"] else 2


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
