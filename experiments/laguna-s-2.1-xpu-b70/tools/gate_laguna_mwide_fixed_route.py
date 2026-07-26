#!/usr/bin/env python3
"""Exactness and timing gate for Laguna's width-12 fixed-route MoE path."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import torch

import vllm
import vllm._custom_ops  # noqa: F401  # loads the XPU extension libraries
import vllm_xpu_kernels._xpu_C as xpu_extension


HIDDEN = 3072
INTERMEDIATE = 1024
LOCAL_EXPERTS = 64
GLOBAL_EXPERTS = 256
TOPK = 10
ROWS = 12
ROUTES = ROWS * TOPK
TARGET_LAYERS = 47
MIN_SAVING_MS_PER_CYCLE = 0.60
MIN_WIN_FRACTION = 0.75
SCRATCH_SENTINEL = -123.0

EXPECTED_VLLM_ROOT = Path(
    "/home/steve/src/laguna-vllm-runtime-graph-20260724"
).resolve()
EXPECTED_KERNEL_ROOT = Path(
    "/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc"
).resolve()
EXPECTED_SELECTORS = {
    "VLLM_XPU_LAGUNA_MWIDE_FUSED_W1_ROUTE_W2": "1",
    "VLLM_XPU_LAGUNA_EXACT_MAX_M": "12",
    "VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE": "1",
    "VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2": "1",
    "VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE": "1",
    "VLLM_XPU_LAGUNA_M8_W1_N_TILE": "64",
}


@dataclass
class ModelTensors:
    w13: torch.Tensor
    s13: torch.Tensor
    w2: torch.Tensor
    s2: torch.Tensor
    expert_map: torch.Tensor


@dataclass
class FixedBuffers:
    gemm1: torch.Tensor
    activation: torch.Tensor
    gemm2: torch.Tensor
    output: torch.Tensor


@dataclass
class GenericBuffers:
    remapped: torch.Tensor
    rows_per_expert: torch.Tensor
    unpermuted_map: torch.Tensor
    gemm1: torch.Tensor
    activation: torch.Tensor
    gemm2: torch.Tensor
    output: torch.Tensor


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tensor_hash(tensor: torch.Tensor) -> str:
    raw = tensor.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes()
    return hashlib.sha256(raw).hexdigest()


def exact_comparison(left: torch.Tensor, right: torch.Tensor) -> dict[str, Any]:
    left_cpu = left.detach().cpu().contiguous()
    right_cpu = right.detach().cpu().contiguous()
    differences = int(
        torch.count_nonzero(
            left_cpu.view(torch.uint16) != right_cpu.view(torch.uint16)
        ).item()
    )
    return {
        "raw_equal": differences == 0,
        "torch_equal": bool(torch.equal(left_cpu, right_cpu)),
        "raw_differences": differences,
    }


def git_head(root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def verify_runtime(rank: int) -> dict[str, Any]:
    selectors = {key: os.environ.get(key) for key in EXPECTED_SELECTORS}
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
            f"ZE_AFFINITY_MASK must be literal declared rank {rank}, got {affinity!r}"
        )
    vllm_root = Path(vllm.__file__).resolve().parents[1]
    kernel_root = Path(xpu_extension.__file__).resolve().parents[1]
    if vllm_root != EXPECTED_VLLM_ROOT:
        raise RuntimeError(f"vLLM import drift: {vllm_root} != {EXPECTED_VLLM_ROOT}")
    if kernel_root != EXPECTED_KERNEL_ROOT:
        raise RuntimeError(
            f"kernel import drift: {kernel_root} != {EXPECTED_KERNEL_ROOT}"
        )
    extension_path = Path(xpu_extension.__file__).resolve()
    grouped_path = extension_path.parent / "libgrouped_gemm_xe_2.so"
    return {
        "selectors": selectors,
        "ze_affinity_mask": affinity,
        "vllm_root": str(vllm_root),
        "vllm_head": git_head(vllm_root),
        "kernel_root": str(kernel_root),
        "kernel_head": git_head(kernel_root),
        "xpu_extension_path": str(extension_path),
        "xpu_extension_sha256": file_hash(extension_path),
        "grouped_gemm_path": str(grouped_path),
        "grouped_gemm_sha256": file_hash(grouped_path),
    }


def allocate_model(rank: int) -> ModelTensors:
    torch.manual_seed(412_000 + rank)
    w13 = torch.empty(
        (LOCAL_EXPERTS, 2 * INTERMEDIATE, HIDDEN // 2),
        dtype=torch.int8,
        device="xpu",
    )
    s13 = torch.empty(
        (LOCAL_EXPERTS, 2 * INTERMEDIATE, HIDDEN // 32),
        dtype=torch.bfloat16,
        device="xpu",
    )
    w2 = torch.empty(
        (LOCAL_EXPERTS, HIDDEN, INTERMEDIATE // 2),
        dtype=torch.int8,
        device="xpu",
    )
    s2 = torch.empty(
        (LOCAL_EXPERTS, HIDDEN, INTERMEDIATE // 32),
        dtype=torch.bfloat16,
        device="xpu",
    )
    w13.random_(-128, 128)
    s13.uniform_(0.0001, 0.02)
    w2.random_(-128, 128)
    s2.uniform_(0.0001, 0.02)
    expert_map = torch.full((GLOBAL_EXPERTS,), -1, dtype=torch.int32, device="xpu")
    expert_map[rank * LOCAL_EXPERTS : (rank + 1) * LOCAL_EXPERTS] = torch.arange(
        LOCAL_EXPERTS, dtype=torch.int32, device="xpu"
    )
    return ModelTensors(w13, s13, w2, s2, expert_map)


def allocate_fixed(rows: int = ROWS) -> FixedBuffers:
    routes = rows * TOPK
    return FixedBuffers(
        gemm1=torch.empty(
            (routes, 2 * INTERMEDIATE),
            dtype=torch.bfloat16,
            device="xpu",
        ),
        activation=torch.empty(
            (routes, INTERMEDIATE), dtype=torch.bfloat16, device="xpu"
        ),
        gemm2=torch.empty((routes, HIDDEN), dtype=torch.bfloat16, device="xpu"),
        output=torch.empty((rows, HIDDEN), dtype=torch.bfloat16, device="xpu"),
    )


def allocate_generic() -> GenericBuffers:
    return GenericBuffers(
        remapped=torch.empty((ROUTES, HIDDEN), dtype=torch.bfloat16, device="xpu"),
        rows_per_expert=torch.empty((LOCAL_EXPERTS,), dtype=torch.int32, device="xpu"),
        unpermuted_map=torch.empty((ROWS, TOPK), dtype=torch.int32, device="xpu"),
        gemm1=torch.empty(
            (ROUTES, 2 * INTERMEDIATE),
            dtype=torch.bfloat16,
            device="xpu",
        ),
        activation=torch.empty(
            (ROUTES, INTERMEDIATE), dtype=torch.bfloat16, device="xpu"
        ),
        gemm2=torch.empty((ROUTES, HIDDEN), dtype=torch.bfloat16, device="xpu"),
        output=torch.empty((ROWS, HIDDEN), dtype=torch.bfloat16, device="xpu"),
    )


def make_inputs(
    rank: int, epoch: int
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    torch.manual_seed(512_000 + rank * 10_000 + epoch)
    hidden = torch.randn((ROWS, HIDDEN), dtype=torch.bfloat16, device="xpu")
    weights = torch.rand((ROWS, TOPK), dtype=torch.float32, device="xpu")
    weights /= weights.sum(dim=1, keepdim=True)
    local_base = rank * LOCAL_EXPERTS
    routes: list[list[int]] = []
    for row in range(ROWS):
        remote_rank = (rank + 1 + row + epoch) % 4
        if remote_rank == rank:
            remote_rank = (remote_rank + 1) % 4
        routes.append(
            [
                local_base,
                local_base + 63,
                local_base,
                remote_rank * LOCAL_EXPERTS + ((epoch * 17 + row * 7) % LOCAL_EXPERTS),
                (epoch * 29 + row * 11) % GLOBAL_EXPERTS,
                0,
                63,
                64,
                255,
                local_base + ((epoch * 13 + row * 5 + 19) % LOCAL_EXPERTS),
            ]
        )
    ids = torch.tensor(routes, dtype=torch.int32, device="xpu")
    return hidden, weights, ids


def initialize_fixed_for_correctness(buffers: FixedBuffers, rows: int) -> None:
    routes = rows * TOPK
    buffers.gemm1[:routes].fill_(SCRATCH_SENTINEL)
    buffers.activation[:routes].fill_(SCRATCH_SENTINEL)
    buffers.gemm2[:routes].zero_()
    buffers.output[:rows].zero_()


def run_fixed(
    hidden: torch.Tensor,
    weights: torch.Tensor,
    ids: torch.Tensor,
    model: ModelTensors,
    buffers: FixedBuffers,
    *,
    initialize: bool = False,
) -> None:
    rows = hidden.shape[0]
    routes = rows * TOPK
    if initialize:
        initialize_fixed_for_correctness(buffers, rows)
    torch.ops._xpu_C.laguna_m8_fused_expert_interface(
        hidden,
        model.w13,
        model.s13,
        None,
        model.w2,
        model.s2,
        None,
        buffers.gemm1[:routes],
        buffers.activation[:routes],
        buffers.gemm2[:routes],
        buffers.output[:rows],
        weights,
        ids,
        model.expert_map,
        LOCAL_EXPERTS,
        True,
        True,
        64,
    )
    buffers.gemm2[:routes].zero_()
    torch.ops._xpu_C.cutlass_grouped_gemm_m8_topk_int4_interface(
        buffers.activation[:routes],
        model.w2,
        model.s2,
        None,
        buffers.gemm2[:routes],
        ids,
        model.expert_map,
        HIDDEN,
        INTERMEDIATE,
        LOCAL_EXPERTS,
        False,
        False,
        True,
    )
    route_map = torch.arange(routes, dtype=torch.int32, device="xpu").view(rows, TOPK)
    torch.ops._moe_C.moe_gather(
        buffers.output[:rows],
        buffers.gemm2[:routes],
        weights,
        route_map,
        LOCAL_EXPERTS,
    )


def run_generic(
    hidden: torch.Tensor,
    weights: torch.Tensor,
    ids: torch.Tensor,
    model: ModelTensors,
    buffers: GenericBuffers,
) -> None:
    buffers.rows_per_expert.zero_()
    torch.ops._moe_C.remap_hidden_states(
        hidden,
        None,
        buffers.remapped,
        None,
        model.expert_map,
        buffers.rows_per_expert,
        buffers.unpermuted_map,
        ids,
        GLOBAL_EXPERTS,
        LOCAL_EXPERTS,
    )
    torch.ops._xpu_C.cutlass_grouped_gemm_interface(
        buffers.remapped,
        None,
        model.w13,
        model.s13,
        None,
        buffers.gemm1,
        buffers.rows_per_expert,
        2 * INTERMEDIATE,
        HIDDEN,
        LOCAL_EXPERTS,
    )
    torch.ops._C.silu_and_mul(buffers.activation, buffers.gemm1)
    torch.ops._xpu_C.cutlass_grouped_gemm_interface(
        buffers.activation,
        None,
        model.w2,
        model.s2,
        None,
        buffers.gemm2,
        buffers.rows_per_expert,
        HIDDEN,
        INTERMEDIATE,
        LOCAL_EXPERTS,
    )
    torch.ops._moe_C.moe_gather(
        buffers.output,
        buffers.gemm2,
        weights,
        buffers.unpermuted_map,
        LOCAL_EXPERTS,
    )


def run_oracle(
    hidden: torch.Tensor,
    weights: torch.Tensor,
    ids: torch.Tensor,
    model: ModelTensors,
    one_row: FixedBuffers,
    aggregate: FixedBuffers,
) -> None:
    initialize_fixed_for_correctness(aggregate, ROWS)
    for row in range(ROWS):
        run_fixed(
            hidden[row : row + 1],
            weights[row : row + 1],
            ids[row : row + 1],
            model,
            one_row,
            initialize=True,
        )
        start = row * TOPK
        end = start + TOPK
        aggregate.gemm1[start:end].copy_(one_row.gemm1)
        aggregate.activation[start:end].copy_(one_row.activation)
        aggregate.gemm2[start:end].copy_(one_row.gemm2)
        aggregate.output[row : row + 1].copy_(one_row.output)


def input_hashes(
    hidden: torch.Tensor,
    weights: torch.Tensor,
    ids: torch.Tensor,
    model: ModelTensors,
) -> dict[str, str]:
    return {
        "hidden": tensor_hash(hidden),
        "weights": tensor_hash(weights),
        "ids": tensor_hash(ids),
        "w13": tensor_hash(model.w13),
        "s13": tensor_hash(model.s13),
        "w2": tensor_hash(model.w2),
        "s2": tensor_hash(model.s2),
        "expert_map": tensor_hash(model.expert_map),
    }


def run_correctness(
    rank: int,
    epochs: int,
    model: ModelTensors,
    candidate: FixedBuffers,
    one_row: FixedBuffers,
    oracle: FixedBuffers,
    generic: GenericBuffers,
) -> dict[str, Any]:
    cases = []
    for epoch in range(epochs):
        hidden, weights, ids = make_inputs(rank, epoch)
        before = input_hashes(hidden, weights, ids, model)
        run_fixed(hidden, weights, ids, model, candidate, initialize=True)
        run_oracle(hidden, weights, ids, model, one_row, oracle)
        run_generic(hidden, weights, ids, model, generic)
        torch.xpu.synchronize()
        local = model.expert_map[ids].reshape(-1) >= 0
        comparisons = {
            "local_w1": exact_comparison(candidate.gemm1[local], oracle.gemm1[local]),
            "local_activation": exact_comparison(
                candidate.activation[local], oracle.activation[local]
            ),
            "local_w2": exact_comparison(candidate.gemm2[local], oracle.gemm2[local]),
            "output": exact_comparison(candidate.output, oracle.output),
        }
        generic_output = exact_comparison(candidate.output, generic.output)
        after = input_hashes(hidden, weights, ids, model)
        remote = ~local
        remote_untouched = (
            bool(torch.all(candidate.gemm1[remote] == SCRATCH_SENTINEL).item())
            and bool(torch.all(candidate.activation[remote] == SCRATCH_SENTINEL).item())
            and bool(torch.all(candidate.gemm2[remote] == 0).item())
        )
        passed = (
            all(
                item["raw_equal"] and item["torch_equal"]
                for item in comparisons.values()
            )
            and before == after
            and remote_untouched
        )
        cases.append(
            {
                "epoch": epoch,
                "passed": passed,
                "input_unchanged": before == after,
                "remote_scratch_untouched": remote_untouched,
                "comparisons": comparisons,
                "generic_output_comparison": generic_output,
                "input_sha256": before,
                "candidate_output_sha256": tensor_hash(candidate.output),
            }
        )
    changing = {
        key: len({case["input_sha256"][key] for case in cases}) == epochs
        for key in ("hidden", "weights", "ids")
    }
    return {
        "passed": all(case["passed"] for case in cases) and all(changing.values()),
        "epochs": epochs,
        "changing_inputs": changing,
        "cases": cases,
    }


def timed_cycle_ms(call: Callable[[], None], cycles: int) -> float:
    torch.xpu.synchronize()
    started = time.perf_counter()
    for _ in range(cycles):
        for _ in range(TARGET_LAYERS):
            call()
    torch.xpu.synchronize()
    return (time.perf_counter() - started) * 1000.0 / cycles


def run_timing(
    rank: int,
    blocks: int,
    cycles: int,
    warmup_cycles: int,
    model: ModelTensors,
    fixed: FixedBuffers,
    generic: GenericBuffers,
) -> dict[str, Any]:
    hidden, weights, ids = make_inputs(rank, 100_000)

    def fixed_call() -> None:
        run_fixed(hidden, weights, ids, model, fixed, initialize=False)

    def generic_call() -> None:
        run_generic(hidden, weights, ids, model, generic)

    for _ in range(warmup_cycles):
        fixed_call()
        generic_call()
    torch.xpu.synchronize()

    rows = []
    for block in range(blocks):
        if block % 2 == 0:
            order = (
                ("generic_a", generic_call),
                ("fixed_a", fixed_call),
                ("fixed_b", fixed_call),
                ("generic_b", generic_call),
            )
        else:
            order = (
                ("fixed_a", fixed_call),
                ("generic_a", generic_call),
                ("generic_b", generic_call),
                ("fixed_b", fixed_call),
            )
        measured = {name: timed_cycle_ms(call, cycles) for name, call in order}
        generic_ms = statistics.mean((measured["generic_a"], measured["generic_b"]))
        fixed_ms = statistics.mean((measured["fixed_a"], measured["fixed_b"]))
        rows.append(
            {
                "block": block,
                "generic_ms_per_47_layers": generic_ms,
                "fixed_ms_per_47_layers": fixed_ms,
                "saving_ms_per_47_layers": generic_ms - fixed_ms,
                "raw_arms": measured,
            }
        )
    savings = [row["saving_ms_per_47_layers"] for row in rows]
    generic_values = [row["generic_ms_per_47_layers"] for row in rows]
    fixed_values = [row["fixed_ms_per_47_layers"] for row in rows]
    wins = sum(saving > 0 for saving in savings)
    required_wins = int(blocks * MIN_WIN_FRACTION + 0.999999)
    paired_median = statistics.median(savings)
    return {
        "passed": paired_median >= MIN_SAVING_MS_PER_CYCLE and wins >= required_wins,
        "blocks": blocks,
        "cycles_per_arm": cycles,
        "layers_per_cycle": TARGET_LAYERS,
        "generic_median_ms_per_47_layers": statistics.median(generic_values),
        "fixed_median_ms_per_47_layers": statistics.median(fixed_values),
        "paired_median_saving_ms_per_47_layers": paired_median,
        "paired_mean_saving_ms_per_47_layers": statistics.mean(savings),
        "minimum_saving_ms_per_47_layers": MIN_SAVING_MS_PER_CYCLE,
        "wins": wins,
        "required_wins": required_wins,
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rank", type=int, required=True, choices=range(4))
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--blocks", type=int, default=31)
    parser.add_argument("--cycles", type=int, default=32)
    parser.add_argument("--warmup-cycles", type=int, default=20)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.epochs < 2 or args.blocks < 3 or args.cycles < 1:
        raise RuntimeError("epochs>=2, blocks>=3, and cycles>=1 required")

    runtime = verify_runtime(args.rank)
    torch.xpu.set_device(0)
    model = allocate_model(args.rank)
    candidate = allocate_fixed()
    one_row = allocate_fixed(1)
    oracle = allocate_fixed()
    generic = allocate_generic()

    correctness = run_correctness(
        args.rank,
        args.epochs,
        model,
        candidate,
        one_row,
        oracle,
        generic,
    )
    timing = None
    if correctness["passed"]:
        timing = run_timing(
            args.rank,
            args.blocks,
            args.cycles,
            args.warmup_cycles,
            model,
            candidate,
            generic,
        )
    result = {
        "rank": args.rank,
        "device": torch.xpu.get_device_name(0),
        "runtime": runtime,
        "correctness": correctness,
        "timing": timing,
        "formal_component_pass": bool(
            correctness["passed"] and timing and timing["passed"]
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    summary = {
        "rank": result["rank"],
        "device": result["device"],
        "correctness_pass": correctness["passed"],
        "timing_pass": None if timing is None else timing["passed"],
        "paired_median_saving_ms_per_47_layers": (
            None if timing is None else timing["paired_median_saving_ms_per_47_layers"]
        ),
        "wins": None if timing is None else timing["wins"],
        "formal_component_pass": result["formal_component_pass"],
        "out": str(args.out),
    }
    print(json.dumps(summary, sort_keys=True))
    if not result["formal_component_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
