#!/usr/bin/env python3
"""Raw-exact and matched timing gate for Laguna routed-W1 N128."""

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
from typing import Any

import torch

import vllm
import vllm._custom_ops  # noqa: F401  # loads all required XPU libraries
import vllm_xpu_kernels._xpu_C as xpu_extension


HIDDEN = 3072
INTERMEDIATE = 1024
LOCAL_EXPERTS = 64
GLOBAL_EXPERTS = 256
TOPK = 10
TARGET_LAYERS = 47
FORMAL_EPOCHS = 64
FORMAL_BLOCKS = 31
FORMAL_CYCLES_PER_ARM = 64
FORMAL_WARMUP_CYCLES = 20
FORMAL_MIN_WINS = 24
FORMAL_MIN_SAVING_MS = 0.15
COUNTER_CALLS = 12
SCRATCH_SENTINEL = -123.0
EXPECTED_VLLM_ROOT = Path(
    "/home/steve/src/deepseek-v4-vllm-xpu-dspark"
).resolve()
EXPECTED_KERNEL_ROOT = Path(
    "/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc"
).resolve()
DEFAULT_TIMING_FIXTURES = Path(
    "/media/steve/CorsairExternal/llm-optimization-artifacts/"
    "laguna-s-2.1/data/w1-real-m8-timing-fixtures-20260723.pt"
)


@dataclass
class Buffers:
    gemm1: torch.Tensor
    activation: torch.Tensor
    gemm2: torch.Tensor
    output: torch.Tensor


@dataclass
class ModelTensors:
    w13: torch.Tensor
    s13: torch.Tensor
    w2: torch.Tensor
    s2: torch.Tensor
    expert_map: torch.Tensor


def tensor_hash(tensor: torch.Tensor) -> str:
    raw = (
        tensor.detach()
        .cpu()
        .contiguous()
        .view(torch.uint8)
        .numpy()
        .tobytes()
    )
    return hashlib.sha256(raw).hexdigest()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def exact_comparison(left: torch.Tensor, right: torch.Tensor) -> dict[str, Any]:
    left_cpu = left.detach().cpu().contiguous()
    right_cpu = right.detach().cpu().contiguous()
    left_raw = left_cpu.view(torch.uint16)
    right_raw = right_cpu.view(torch.uint16)
    raw_differences = int(torch.count_nonzero(left_raw != right_raw).item())
    return {
        "torch_equal": bool(torch.equal(left_cpu, right_cpu)),
        "raw_equal": raw_differences == 0,
        "raw_differences": raw_differences,
    }


def make_routes(rank: int, rows: int, epoch: int) -> torch.Tensor:
    local_base = rank * LOCAL_EXPERTS
    remote_rank = (rank + 1 + epoch) % 4
    if remote_rank == rank:
        remote_rank = (remote_rank + 1) % 4
    routes: list[list[int]] = []
    for row in range(rows):
        pattern = [
            local_base,
            local_base + LOCAL_EXPERTS - 1,
            local_base,
            0,
            63,
            64,
            255,
            remote_rank * LOCAL_EXPERTS + ((epoch * 7 + row * 3) % 64),
            (epoch * 29 + row * 11 + rank * 5) % GLOBAL_EXPERTS,
            local_base + ((epoch * 13 + row * 5 + 17) % LOCAL_EXPERTS),
        ]
        routes.append(pattern)
    return torch.tensor(routes, dtype=torch.int32, device="xpu")


def allocate_buffers() -> Buffers:
    max_routes = 8 * TOPK
    return Buffers(
        gemm1=torch.empty(
            (max_routes, 2 * INTERMEDIATE),
            dtype=torch.bfloat16,
            device="xpu",
        ),
        activation=torch.empty(
            (max_routes, INTERMEDIATE),
            dtype=torch.bfloat16,
            device="xpu",
        ),
        gemm2=torch.empty(
            (max_routes, HIDDEN),
            dtype=torch.bfloat16,
            device="xpu",
        ),
        output=torch.empty(
            (8, HIDDEN),
            dtype=torch.bfloat16,
            device="xpu",
        ),
    )


def allocate_model_tensors(rank: int) -> ModelTensors:
    torch.manual_seed(128_000 + rank)
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
    expert_map = torch.full(
        (GLOBAL_EXPERTS,), -1, dtype=torch.int32, device="xpu"
    )
    expert_map[
        rank * LOCAL_EXPERTS : (rank + 1) * LOCAL_EXPERTS
    ] = torch.arange(LOCAL_EXPERTS, dtype=torch.int32, device="xpu")
    return ModelTensors(w13, s13, w2, s2, expert_map)


def initialize_buffers(buffers: Buffers, rows: int) -> None:
    routes = rows * TOPK
    buffers.gemm1[:routes].fill_(SCRATCH_SENTINEL)
    buffers.activation[:routes].fill_(SCRATCH_SENTINEL)
    buffers.gemm2[:routes].zero_()
    buffers.output[:rows].zero_()


def call_fused_w1(
    hidden: torch.Tensor,
    model: ModelTensors,
    topk_weights: torch.Tensor,
    topk_ids: torch.Tensor,
    buffers: Buffers,
    *,
    w1_only: bool,
    route_interleave: bool,
    w1_n_tile: int,
) -> None:
    rows = hidden.shape[0]
    routes = rows * TOPK
    if rows == 8:
        gemm1 = buffers.gemm1
        activation = buffers.activation
        gemm2 = buffers.gemm2
        output = buffers.output
    else:
        gemm1 = buffers.gemm1[:routes]
        activation = buffers.activation[:routes]
        gemm2 = buffers.gemm2[:routes]
        output = buffers.output[:rows]
    torch.ops._xpu_C.laguna_m8_fused_expert_interface(
        hidden,
        model.w13,
        model.s13,
        None,
        model.w2,
        model.s2,
        None,
        gemm1,
        activation,
        gemm2,
        output,
        topk_weights,
        topk_ids,
        model.expert_map,
        LOCAL_EXPERTS,
        w1_only,
        route_interleave,
        w1_n_tile,
    )


def run_incumbent_w2_and_gather(
    model: ModelTensors,
    topk_weights: torch.Tensor,
    topk_ids: torch.Tensor,
    buffers: Buffers,
) -> None:
    rows = topk_ids.shape[0]
    routes = rows * TOPK
    gemm2 = buffers.gemm2[:routes]
    gemm2.zero_()
    torch.ops._xpu_C.cutlass_grouped_gemm_m8_topk_int4_interface(
        buffers.activation[:routes],
        model.w2,
        model.s2,
        None,
        gemm2,
        topk_ids,
        model.expert_map,
        HIDDEN,
        INTERMEDIATE,
        LOCAL_EXPERTS,
        False,
        False,
        True,
    )
    route_map = torch.arange(
        routes, dtype=torch.int32, device="xpu"
    ).view(rows, TOPK)
    torch.ops._moe_C.moe_gather(
        buffers.output[:rows],
        gemm2,
        topk_weights,
        route_map,
        LOCAL_EXPERTS,
    )


def run_complete_path(
    hidden: torch.Tensor,
    model: ModelTensors,
    topk_weights: torch.Tensor,
    topk_ids: torch.Tensor,
    buffers: Buffers,
    w1_n_tile: int,
) -> None:
    initialize_buffers(buffers, hidden.shape[0])
    call_fused_w1(
        hidden,
        model,
        topk_weights,
        topk_ids,
        buffers,
        w1_only=True,
        route_interleave=True,
        w1_n_tile=w1_n_tile,
    )
    run_incumbent_w2_and_gather(model, topk_weights, topk_ids, buffers)


def make_epoch_inputs(
    rank: int,
    epoch: int,
    rows: int,
    model: ModelTensors,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    torch.manual_seed(256_000 + rank * 10_000 + epoch)
    model.w13.random_(-128, 128)
    model.s13.uniform_(0.0001, 0.02)
    hidden = torch.empty(
        (rows, HIDDEN), dtype=torch.bfloat16, device="xpu"
    )
    hidden.normal_()
    topk_weights = torch.rand(
        (rows, TOPK), dtype=torch.float32, device="xpu"
    )
    topk_weights /= topk_weights.sum(dim=1, keepdim=True)
    topk_ids = make_routes(rank, rows, epoch)
    return hidden, topk_weights, topk_ids


def input_hashes(
    hidden: torch.Tensor,
    model: ModelTensors,
    topk_weights: torch.Tensor,
    topk_ids: torch.Tensor,
) -> dict[str, str]:
    return {
        "hidden": tensor_hash(hidden),
        "w13": tensor_hash(model.w13),
        "s13": tensor_hash(model.s13),
        "topk_weights": tensor_hash(topk_weights),
        "topk_ids": tensor_hash(topk_ids),
    }


def remote_rows_untouched(
    buffers: Buffers,
    local_mask: torch.Tensor,
    rows: int,
) -> bool:
    routes = rows * TOPK
    remote = ~local_mask
    if not bool(torch.any(remote).item()):
        return True
    gemm1_ok = bool(
        torch.all(
            buffers.gemm1[:routes][remote] == SCRATCH_SENTINEL
        ).item()
    )
    activation_ok = bool(
        torch.all(
            buffers.activation[:routes][remote] == SCRATCH_SENTINEL
        ).item()
    )
    gemm2_ok = bool(torch.all(buffers.gemm2[:routes][remote] == 0).item())
    return gemm1_ok and activation_ok and gemm2_ok


def run_correctness_phase(
    rank: int,
    epochs: int,
    model: ModelTensors,
    control: Buffers,
    candidate: Buffers,
    repeat: Buffers,
    expected: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    for epoch in range(epochs):
        hidden, weights, ids = make_epoch_inputs(rank, epoch, 8, model)
        before = input_hashes(hidden, model, weights, ids)

        run_complete_path(hidden, model, weights, ids, control, 64)
        run_complete_path(hidden, model, weights, ids, candidate, 128)
        run_complete_path(hidden, model, weights, ids, repeat, 128)
        torch.xpu.synchronize()

        mapped = model.expert_map[ids].reshape(-1)
        local = mapped >= 0
        routes = 8 * TOPK
        w1 = exact_comparison(
            control.gemm1[:routes][local],
            candidate.gemm1[:routes][local],
        )
        activation = exact_comparison(
            control.activation[:routes][local],
            candidate.activation[:routes][local],
        )
        w2 = exact_comparison(
            control.gemm2[:routes][local],
            candidate.gemm2[:routes][local],
        )
        output = exact_comparison(
            control.output[:8],
            candidate.output[:8],
        )
        repeat_w1 = exact_comparison(
            candidate.gemm1[:routes][local],
            repeat.gemm1[:routes][local],
        )
        repeat_activation = exact_comparison(
            candidate.activation[:routes][local],
            repeat.activation[:routes][local],
        )
        repeat_output = exact_comparison(
            candidate.output[:8],
            repeat.output[:8],
        )
        after = input_hashes(hidden, model, weights, ids)
        hashes = {
            "inputs": before,
            "w1": tensor_hash(candidate.gemm1[:routes][local]),
            "activation": tensor_hash(candidate.activation[:routes][local]),
            "output": tensor_hash(candidate.output[:8]),
        }
        replay_equal = True
        if expected is not None:
            replay_equal = hashes == {
                "inputs": expected[epoch]["inputs"],
                "w1": expected[epoch]["w1"],
                "activation": expected[epoch]["activation"],
                "output": expected[epoch]["output"],
            }
        comparisons = [
            w1,
            activation,
            w2,
            output,
            repeat_w1,
            repeat_activation,
            repeat_output,
        ]
        untouched = all(
            remote_rows_untouched(buffers, local, 8)
            for buffers in (control, candidate, repeat)
        )
        passed = (
            all(item["raw_equal"] and item["torch_equal"] for item in comparisons)
            and before == after
            and untouched
            and replay_equal
        )
        cases.append(
            {
                "epoch": epoch,
                "passed": passed,
                "inputs": before,
                "w1": hashes["w1"],
                "activation": hashes["activation"],
                "output": hashes["output"],
                "input_unchanged": before == after,
                "remote_rows_untouched": untouched,
                "replay_equal": replay_equal,
                "comparisons": {
                    "n64_vs_n128_w1": w1,
                    "n64_vs_n128_activation": activation,
                    "n64_vs_n128_w2": w2,
                    "n64_vs_n128_output": output,
                    "n128_repeat_w1": repeat_w1,
                    "n128_repeat_activation": repeat_activation,
                    "n128_repeat_output": repeat_output,
                },
            }
        )

    changing = {
        key: len({case["inputs"][key] for case in cases}) == epochs
        for key in ("hidden", "w13", "s13", "topk_weights", "topk_ids")
    }
    required_experts = {0, 63, 64, 255}
    route_coverage = set()
    for epoch in range(epochs):
        route_coverage.update(
            make_routes(rank, 8, epoch).detach().cpu().reshape(-1).tolist()
        )
    coverage_ok = required_experts.issubset(route_coverage)
    return {
        "passed": (
            all(case["passed"] for case in cases)
            and all(changing.values())
            and coverage_ok
        ),
        "epochs": epochs,
        "changing_inputs": changing,
        "required_route_coverage": coverage_ok,
        "route_experts_seen": sorted(route_coverage),
        "cases": cases,
    }


def expect_rejection(call, pattern: str) -> dict[str, Any]:
    try:
        call()
        torch.xpu.synchronize()
    except RuntimeError as error:
        message = str(error)
        return {
            "passed": pattern in message,
            "pattern": pattern,
            "message": message,
        }
    return {
        "passed": False,
        "pattern": pattern,
        "message": "call unexpectedly succeeded",
    }


def run_tail_and_rejection_gate(
    rank: int,
    model: ModelTensors,
) -> dict[str, Any]:
    tail_cases = []
    for rows in range(1, 8):
        hidden, weights, ids = make_epoch_inputs(
            rank, 10_000 + rows, rows, model
        )
        control = allocate_buffers()
        effective = allocate_buffers()
        rejected = allocate_buffers()
        run_complete_path(hidden, model, weights, ids, control, 64)
        run_complete_path(hidden, model, weights, ids, effective, 64)
        torch.xpu.synchronize()
        routes = rows * TOPK
        local = model.expert_map[ids].reshape(-1) >= 0
        comparisons = {
            "w1": exact_comparison(
                control.gemm1[:routes][local],
                effective.gemm1[:routes][local],
            ),
            "activation": exact_comparison(
                control.activation[:routes][local],
                effective.activation[:routes][local],
            ),
            "output": exact_comparison(
                control.output[:rows],
                effective.output[:rows],
            ),
        }
        rejection = expect_rejection(
            lambda: call_fused_w1(
                hidden,
                model,
                weights,
                ids,
                rejected,
                w1_only=True,
                route_interleave=True,
                w1_n_tile=128,
            ),
            "M=8 W1-only route interleave",
        )
        tail_cases.append(
            {
                "rows": rows,
                "passed": (
                    all(
                        item["raw_equal"] and item["torch_equal"]
                        for item in comparisons.values()
                    )
                    and rejection["passed"]
                ),
                "comparisons": comparisons,
                "n128_rejection": rejection,
            }
        )

    hidden, weights, ids = make_epoch_inputs(rank, 20_000, 8, model)
    buffers = allocate_buffers()
    rejection_cases = {
        "tile_32": expect_rejection(
            lambda: call_fused_w1(
                hidden,
                model,
                weights,
                ids,
                buffers,
                w1_only=True,
                route_interleave=True,
                w1_n_tile=32,
            ),
            "must be 64 or 128",
        ),
        "tile_129": expect_rejection(
            lambda: call_fused_w1(
                hidden,
                model,
                weights,
                ids,
                buffers,
                w1_only=True,
                route_interleave=True,
                w1_n_tile=129,
            ),
            "must be 64 or 128",
        ),
        "n128_without_interleave": expect_rejection(
            lambda: call_fused_w1(
                hidden,
                model,
                weights,
                ids,
                buffers,
                w1_only=True,
                route_interleave=False,
                w1_n_tile=128,
            ),
            "M=8 W1-only route interleave",
        ),
        "n128_without_w1_only": expect_rejection(
            lambda: call_fused_w1(
                hidden,
                model,
                weights,
                ids,
                buffers,
                w1_only=False,
                route_interleave=True,
                w1_n_tile=128,
            ),
            "route interleave is only valid",
        ),
        "n128_without_ep4_map": expect_rejection(
            lambda: call_fused_w1(
                hidden,
                ModelTensors(
                    model.w13,
                    model.s13,
                    model.w2,
                    model.s2,
                    None,
                ),
                weights,
                ids,
                buffers,
                w1_only=True,
                route_interleave=True,
                w1_n_tile=128,
            ),
            "requires an EP4 expert map",
        ),
    }
    return {
        "passed": (
            all(case["passed"] for case in tail_cases)
            and all(case["passed"] for case in rejection_cases.values())
        ),
        "tail_cases": tail_cases,
        "rejection_cases": rejection_cases,
    }


def load_timing_fixture_sets(
    path: Path,
) -> tuple[
    list[list[tuple[torch.Tensor, torch.Tensor, torch.Tensor]]],
    dict[str, Any],
]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"missing real timing fixtures: {resolved}")
    payload = torch.load(resolved, map_location="cpu", weights_only=True)
    if (
        not isinstance(payload, dict)
        or payload.get("format")
        != "laguna-w1-real-m8-timing-fixtures-v1"
        or payload.get("fixture_count") != 3 * TARGET_LAYERS
        or payload.get("trace_sets") != 3
        or payload.get("layers_per_set") != TARGET_LAYERS
    ):
        raise RuntimeError("real timing fixture artifact contract drift")
    fixtures = payload.get("fixtures")
    if not isinstance(fixtures, list) or len(fixtures) != 3 * TARGET_LAYERS:
        raise RuntimeError("real timing fixture list contract drift")

    aggregate = hashlib.sha256()
    fixture_sets = [[] for _ in range(3)]
    fixture_layers = [[] for _ in range(3)]
    for fixture in fixtures:
        if not isinstance(fixture, dict):
            raise RuntimeError("real timing fixture is not a dictionary")
        trace_set = fixture.get("trace_set")
        layer = fixture.get("layer")
        hidden = fixture.get("hidden_states")
        weights = fixture.get("topk_weights")
        ids = fixture.get("topk_ids")
        source_rows = fixture.get("source_rows")
        hashes = fixture.get("hashes")
        if (
            trace_set not in (0, 1, 2)
            or not isinstance(layer, int)
            or not isinstance(hidden, torch.Tensor)
            or hidden.dtype != torch.bfloat16
            or tuple(hidden.shape) != (8, HIDDEN)
            or not isinstance(weights, torch.Tensor)
            or weights.dtype != torch.float32
            or tuple(weights.shape) != (8, TOPK)
            or not isinstance(ids, torch.Tensor)
            or ids.dtype != torch.int32
            or tuple(ids.shape) != (8, TOPK)
            or not isinstance(source_rows, torch.Tensor)
            or source_rows.dtype != torch.int32
            or tuple(source_rows.shape) != (8, TOPK)
            or not isinstance(hashes, dict)
        ):
            raise RuntimeError(
                f"real timing fixture tensor drift set={trace_set} "
                f"layer={layer}"
            )
        actual_hashes = {
            "hidden": tensor_hash(hidden),
            "topk_weights": tensor_hash(weights),
            "topk_ids": tensor_hash(ids),
            "source_rows": tensor_hash(source_rows),
        }
        if actual_hashes != hashes:
            raise RuntimeError(
                f"real timing fixture hash drift set={trace_set} "
                f"layer={layer}"
            )
        aggregate.update(
            (
                f"{trace_set}:{layer}:{hashes['hidden']}:"
                f"{hashes['topk_weights']}:{hashes['topk_ids']}:"
                f"{hashes['source_rows']}\n"
            ).encode("ascii")
        )
        fixture_sets[trace_set].append(
            (
                hidden.to(device="xpu"),
                weights.to(device="xpu"),
                ids.to(device="xpu"),
            )
        )
        fixture_layers[trace_set].append(layer)
    if any(len(fixture_set) != TARGET_LAYERS for fixture_set in fixture_sets):
        raise RuntimeError("real timing fixture sets are incomplete")
    if any(
        layers != list(range(1, TARGET_LAYERS + 1))
        for layers in fixture_layers
    ):
        raise RuntimeError("real timing fixture layers are not ordered 1..47")
    if aggregate.hexdigest() != payload.get("aggregate_tensor_sha256"):
        raise RuntimeError("real timing fixture aggregate hash drift")
    return fixture_sets, {
        "path": str(resolved),
        "sha256": file_hash(resolved),
        "format": payload["format"],
        "fixture_count": payload["fixture_count"],
        "trace_sets": payload["trace_sets"],
        "layers_per_set": payload["layers_per_set"],
        "aggregate_tensor_sha256": payload["aggregate_tensor_sha256"],
        "production_source_aggregate_sha256": payload[
            "production_source_aggregate_sha256"
        ],
    }


def execute_cycles(
    tile: int,
    fixture_set: list[tuple[torch.Tensor, torch.Tensor, torch.Tensor]],
    model: ModelTensors,
    buffers: Buffers,
    cycles: int,
) -> None:
    for _ in range(cycles):
        for hidden, weights, ids in fixture_set:
            call_fused_w1(
                hidden,
                model,
                weights,
                ids,
                buffers,
                w1_only=True,
                route_interleave=True,
                w1_n_tile=tile,
            )


def time_arm(
    tile: int,
    fixture_set: list[tuple[torch.Tensor, torch.Tensor, torch.Tensor]],
    model: ModelTensors,
    buffers: Buffers,
) -> float:
    torch.xpu.synchronize()
    started = time.perf_counter()
    execute_cycles(
        tile,
        fixture_set,
        model,
        buffers,
        FORMAL_CYCLES_PER_ARM,
    )
    torch.xpu.synchronize()
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return elapsed_ms / FORMAL_CYCLES_PER_ARM


def run_formal_timing(
    rank: int,
    model: ModelTensors,
    control: Buffers,
    candidate: Buffers,
    fixture_path: Path,
) -> dict[str, Any]:
    fixture_sets, fixture_identity = load_timing_fixture_sets(fixture_path)
    local_fractions = []
    for fixture_set in fixture_sets:
        local_routes = 0
        total_routes = 0
        for _, _, ids in fixture_set:
            local_routes += int(
                torch.count_nonzero(model.expert_map[ids] >= 0).item()
            )
            total_routes += ids.numel()
        local_fractions.append(local_routes / total_routes)
    representative_routes = all(
        0.20 <= fraction <= 0.30 for fraction in local_fractions
    )
    execute_cycles(
        64,
        fixture_sets[0],
        model,
        control,
        FORMAL_WARMUP_CYCLES,
    )
    execute_cycles(
        128,
        fixture_sets[0],
        model,
        candidate,
        FORMAL_WARMUP_CYCLES,
    )
    torch.xpu.synchronize()

    blocks = []
    for block_id in range(FORMAL_BLOCKS):
        fixture_set_id = block_id % len(fixture_sets)
        fixture_set = fixture_sets[fixture_set_id]
        a1 = time_arm(64, fixture_set, model, control)
        b1 = time_arm(128, fixture_set, model, candidate)
        b2 = time_arm(128, fixture_set, model, candidate)
        a2 = time_arm(64, fixture_set, model, control)
        control_ms = (a1 + a2) / 2.0
        candidate_ms = (b1 + b2) / 2.0
        blocks.append(
            {
                "block": block_id,
                "fixture_set": fixture_set_id,
                "a1_ms_per_47_layers": a1,
                "b1_ms_per_47_layers": b1,
                "b2_ms_per_47_layers": b2,
                "a2_ms_per_47_layers": a2,
                "control_ms_per_47_layers": control_ms,
                "candidate_ms_per_47_layers": candidate_ms,
                "saving_ms_per_47_layers": control_ms - candidate_ms,
            }
        )

    control_values = [
        block["control_ms_per_47_layers"] for block in blocks
    ]
    candidate_values = [
        block["candidate_ms_per_47_layers"] for block in blocks
    ]
    savings = [block["saving_ms_per_47_layers"] for block in blocks]
    control_median = statistics.median(control_values)
    candidate_median = statistics.median(candidate_values)
    median_saving = statistics.median(savings)
    mean_saving = statistics.fmean(savings)
    wins = sum(saving > 0 for saving in savings)
    relative = median_saving / statistics.median(control_values)
    passed = (
        wins >= FORMAL_MIN_WINS
        and median_saving >= FORMAL_MIN_SAVING_MS
        and mean_saving > 0
        and representative_routes
    )
    return {
        "passed": passed,
        "design": "31 A-B-B-A blocks",
        "warmup_cycles_per_arm": FORMAL_WARMUP_CYCLES,
        "cycles_per_arm_per_block": FORMAL_CYCLES_PER_ARM,
        "layers_per_cycle": TARGET_LAYERS,
        "changing_layer_fixtures_per_set": TARGET_LAYERS,
        "fixture_set_local_route_fractions": local_fractions,
        "representative_ep4_route_share": representative_routes,
        "real_production_fixture_identity": fixture_identity,
        "wins": wins,
        "required_wins": FORMAL_MIN_WINS,
        "control_median_ms_per_47_layers": control_median,
        "candidate_median_ms_per_47_layers": candidate_median,
        "paired_median_saving_ms_per_47_layers": median_saving,
        "mean_saving_ms_per_47_layers": mean_saving,
        "relative_median_improvement": relative,
        "required_saving_ms_per_47_layers": FORMAL_MIN_SAVING_MS,
        "blocks": blocks,
    }


def run_counter_mode(
    mode: str,
    rank: int,
    model: ModelTensors,
    fixture_path: Path,
) -> dict[str, Any]:
    tile = 64 if mode == "counter-n64" else 128
    fixture_sets, fixture_identity = load_timing_fixture_sets(fixture_path)
    hidden, weights, ids = fixture_sets[0][0]
    buffers = allocate_buffers()
    initialize_buffers(buffers, 8)
    call_fused_w1(
        hidden,
        model,
        weights,
        ids,
        buffers,
        w1_only=True,
        route_interleave=True,
        w1_n_tile=tile,
    )
    torch.xpu.synchronize()
    for _ in range(COUNTER_CALLS):
        call_fused_w1(
            hidden,
            model,
            weights,
            ids,
            buffers,
            w1_only=True,
            route_interleave=True,
            w1_n_tile=tile,
        )
        torch.xpu.synchronize()
    return {
        "mode": mode,
        "rank": rank,
        "tile": tile,
        "calls": COUNTER_CALLS,
        "completion_boundary_per_call": True,
        "real_production_fixture_identity": fixture_identity,
    }


def run_full_path_trace_mode(
    mode: str,
    rank: int,
    model: ModelTensors,
    fixture_path: Path,
) -> dict[str, Any]:
    tile = 64 if mode == "trace-n64" else 128
    fixture_sets, fixture_identity = load_timing_fixture_sets(fixture_path)
    hidden, weights, ids = fixture_sets[0][0]
    buffers = allocate_buffers()
    run_complete_path(hidden, model, weights, ids, buffers, tile)
    torch.xpu.synchronize()
    for _ in range(COUNTER_CALLS):
        run_complete_path(hidden, model, weights, ids, buffers, tile)
        torch.xpu.synchronize()
    return {
        "mode": mode,
        "rank": rank,
        "tile": tile,
        "calls": COUNTER_CALLS,
        "completion_boundary_per_complete_path": True,
        "expected_selected_kernels_per_call": {
            "w1": 1,
            "w2": 1,
            "gather": 1,
        },
        "real_production_fixture_identity": fixture_identity,
    }


def runtime_identity(rank: int) -> dict[str, Any]:
    extension_path = Path(xpu_extension.__file__).resolve()
    grouped_path = extension_path.parent / "libgrouped_gemm_xe_2.so"
    vllm_path = Path(vllm.__file__).resolve()
    expected_extension = (
        EXPECTED_KERNEL_ROOT / "vllm_xpu_kernels" / "_xpu_C.abi3.so"
    )
    if extension_path != expected_extension:
        raise RuntimeError(
            "wrong XPU extension resolved; set PYTHONPATH to the frozen "
            f"kernel tree, got {extension_path}"
        )
    if not vllm_path.is_relative_to(EXPECTED_VLLM_ROOT):
        raise RuntimeError(
            "wrong vLLM tree resolved; set PYTHONPATH to the frozen tree, "
            f"got {vllm_path}"
        )
    discovery_env = os.environ.copy()
    discovery_env.pop("ZE_AFFINITY_MASK", None)
    discovery_env.pop("ONEAPI_DEVICE_SELECTOR", None)
    discovery = subprocess.run(
        ["xpu-smi", "discovery", "-d", str(rank), "-j"],
        check=True,
        capture_output=True,
        env=discovery_env,
        text=True,
    )
    physical = json.loads(discovery.stdout)
    if physical.get("device_id") != rank:
        raise RuntimeError(
            f"xpu-smi physical identity mismatch for rank {rank}: {physical}"
        )
    return {
        "vllm_path": str(vllm_path),
        "extension_path": str(extension_path),
        "extension_sha256": file_hash(extension_path),
        "grouped_gemm_path": str(grouped_path),
        "grouped_gemm_sha256": file_hash(grouped_path),
        "schema": str(
            torch.ops._xpu_C.laguna_m8_fused_expert_interface.default._schema
        ),
        "ze_affinity_mask": os.environ.get("ZE_AFFINITY_MASK"),
        "oneapi_device_selector": os.environ.get("ONEAPI_DEVICE_SELECTOR"),
        "physical_device": {
            "device_id": physical.get("device_id"),
            "uuid": physical.get("uuid"),
            "pci_bdf_address": physical.get("pci_bdf_address"),
            "drm_device": physical.get("drm_device"),
            "device_name": physical.get("device_name"),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rank", type=int, required=True, choices=range(4))
    parser.add_argument(
        "--mode",
        required=True,
        choices=(
            "smoke",
            "formal",
            "counter-n64",
            "counter-n128",
            "trace-n64",
            "trace-n128",
        ),
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--timing-fixtures",
        type=Path,
        default=DEFAULT_TIMING_FIXTURES,
    )
    args = parser.parse_args()

    affinity = os.environ.get("ZE_AFFINITY_MASK")
    if affinity != str(args.rank):
        raise RuntimeError(
            f"--rank {args.rank} requires ZE_AFFINITY_MASK={args.rank}, "
            f"got {affinity!r}"
        )
    selector = os.environ.get("ONEAPI_DEVICE_SELECTOR")
    if selector != "level_zero:0":
        raise RuntimeError(
            "gate requires ONEAPI_DEVICE_SELECTOR=level_zero:0 after "
            f"physical affinity selection, got {selector!r}"
        )
    visible_devices = torch.xpu.device_count()
    if visible_devices != 1:
        raise RuntimeError(
            "gate requires exactly one visible XPU; set ZE_AFFINITY_MASK "
            f"for physical card {args.rank}, got {visible_devices} devices"
        )
    torch.xpu.set_device(0)
    model = allocate_model_tensors(args.rank)
    identity = runtime_identity(args.rank)

    if args.mode.startswith("counter-"):
        result = {
            "passed": None,
            "counter_gate_evaluated": False,
            "device": torch.xpu.get_device_name(0),
            "runtime": identity,
            "counter": run_counter_mode(
                args.mode,
                args.rank,
                model,
                args.timing_fixtures,
            ),
        }
    elif args.mode.startswith("trace-"):
        result = {
            "passed": None,
            "trace_gate_evaluated": False,
            "device": torch.xpu.get_device_name(0),
            "runtime": identity,
            "trace": run_full_path_trace_mode(
                args.mode,
                args.rank,
                model,
                args.timing_fixtures,
            ),
        }
    else:
        epochs = FORMAL_EPOCHS if args.mode == "formal" else 2
        constant_before = {
            "w2": tensor_hash(model.w2),
            "s2": tensor_hash(model.s2),
            "expert_map": tensor_hash(model.expert_map),
        }
        control = allocate_buffers()
        candidate = allocate_buffers()
        repeat = allocate_buffers()
        pre = run_correctness_phase(
            args.rank,
            epochs,
            model,
            control,
            candidate,
            repeat,
        )
        tails = run_tail_and_rejection_gate(args.rank, model)
        timing = (
            run_formal_timing(
                args.rank,
                model,
                control,
                candidate,
                args.timing_fixtures,
            )
            if args.mode == "formal"
            else None
        )
        post = run_correctness_phase(
            args.rank,
            epochs,
            model,
            control,
            candidate,
            repeat,
            expected=pre["cases"],
        )
        constant_after = {
            "w2": tensor_hash(model.w2),
            "s2": tensor_hash(model.s2),
            "expert_map": tensor_hash(model.expert_map),
        }
        constants_unchanged = constant_before == constant_after
        passed = (
            pre["passed"]
            and tails["passed"]
            and post["passed"]
            and constants_unchanged
            and (timing is None or timing["passed"])
        )
        result = {
            "passed": passed,
            "formal_component_pass": (
                passed if args.mode == "formal" else None
            ),
            "mode": args.mode,
            "rank": args.rank,
            "device": torch.xpu.get_device_name(0),
            "runtime": identity,
            "frozen_contract": {
                "control_tile": 64,
                "candidate_tile": 128,
                "epochs": epochs,
                "formal_blocks": FORMAL_BLOCKS,
                "formal_cycles_per_arm": FORMAL_CYCLES_PER_ARM,
                "target_layers": TARGET_LAYERS,
                "w2_tile": 64,
                "topk_ids_dtype": "torch.int32",
            },
            "constant_inputs_unchanged": constants_unchanged,
            "constant_input_hashes": constant_before,
            "pre_correctness": pre,
            "tail_and_rejection_gate": tails,
            "timing": timing,
            "post_correctness": post,
        }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: value
                for key, value in result.items()
                if key
                not in (
                    "pre_correctness",
                    "post_correctness",
                    "tail_and_rejection_gate",
                )
            },
            indent=2,
        )
    )
    if result["passed"] is False:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
