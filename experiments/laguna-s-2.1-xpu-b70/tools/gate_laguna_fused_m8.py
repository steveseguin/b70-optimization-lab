#!/usr/bin/env python3
"""Bitwise/timing gate for Laguna fused-W1 + route-parallel-W2 path."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import torch

import vllm._custom_ops  # noqa: F401  # loads the XPU extension libraries


HIDDEN = 3072
INTERMEDIATE = 1024
LOCAL_EXPERTS = 64
GLOBAL_EXPERTS = 256
TOPK = 10


def tensor_hash(tensor: torch.Tensor) -> str:
    raw = tensor.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes()
    return hashlib.sha256(raw).hexdigest()


def make_routes(rank: int, rows: int, epoch: int) -> torch.Tensor:
    routes = []
    local_base = rank * LOCAL_EXPERTS
    for row in range(rows):
        row_routes = []
        for slot in range(TOPK):
            if (row + slot + epoch) % 3:
                expert = local_base + ((epoch * 19 + row * 13 + slot * 7) % 64)
            else:
                remote_rank = (rank + 1 + (slot % 3)) % 4
                expert = remote_rank * LOCAL_EXPERTS + (
                    (epoch * 23 + row * 11 + slot * 5) % 64
                )
            row_routes.append(expert)
        routes.append(row_routes)
    return torch.tensor(routes, dtype=torch.int64, device="xpu")


def baseline(
    hidden: torch.Tensor,
    w13: torch.Tensor,
    s13: torch.Tensor,
    w2: torch.Tensor,
    s2: torch.Tensor,
    topk_weights: torch.Tensor,
    topk_ids: torch.Tensor,
    expert_map: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    rows = hidden.shape[0]
    routes = rows * TOPK
    gemm1 = torch.zeros((routes, 2 * INTERMEDIATE), dtype=torch.bfloat16, device="xpu")
    torch.ops._xpu_C.cutlass_grouped_gemm_m8_topk_int4_interface(
        hidden,
        w13,
        s13,
        None,
        gemm1,
        topk_ids,
        expert_map,
        2 * INTERMEDIATE,
        HIDDEN,
        LOCAL_EXPERTS,
        True,
        False,
    )
    act = torch.empty((routes, INTERMEDIATE), dtype=torch.bfloat16, device="xpu")
    torch.ops._C.silu_and_mul(act, gemm1)
    gemm2 = torch.zeros((routes, HIDDEN), dtype=torch.bfloat16, device="xpu")
    torch.ops._xpu_C.cutlass_grouped_gemm_m8_topk_int4_interface(
        act,
        w2,
        s2,
        None,
        gemm2,
        topk_ids,
        expert_map,
        HIDDEN,
        INTERMEDIATE,
        LOCAL_EXPERTS,
        False,
        False,
    )
    output = torch.empty((rows, HIDDEN), dtype=torch.bfloat16, device="xpu")
    route_map = torch.arange(routes, dtype=torch.int32, device="xpu").view(rows, TOPK)
    torch.ops._moe_C.moe_gather(
        output, gemm2, topk_weights, route_map, LOCAL_EXPERTS
    )
    return output, gemm1, act, gemm2


def candidate(
    hidden: torch.Tensor,
    w13: torch.Tensor,
    s13: torch.Tensor,
    w2: torch.Tensor,
    s2: torch.Tensor,
    topk_weights: torch.Tensor,
    topk_ids: torch.Tensor,
    expert_map: torch.Tensor,
    scratch: tuple[torch.Tensor, torch.Tensor, torch.Tensor],
) -> torch.Tensor:
    rows = hidden.shape[0]
    routes = rows * TOPK
    gemm1, act, gemm2 = (buffer[:routes] for buffer in scratch)
    output = torch.empty((rows, HIDDEN), dtype=torch.bfloat16, device="xpu")
    torch.ops._xpu_C.laguna_m8_fused_expert_interface(
        hidden,
        w13,
        s13,
        None,
        w2,
        s2,
        None,
        gemm1,
        act,
        gemm2,
        output,
        topk_weights,
        topk_ids,
        expert_map,
        LOCAL_EXPERTS,
        True,
    )
    gemm2.zero_()
    torch.ops._xpu_C.cutlass_grouped_gemm_m8_topk_int4_interface(
        act,
        w2,
        s2,
        None,
        gemm2,
        topk_ids,
        expert_map,
        HIDDEN,
        INTERMEDIATE,
        LOCAL_EXPERTS,
        False,
        False,
    )
    route_map = torch.arange(
        routes, dtype=torch.int32, device="xpu"
    ).view(rows, TOPK)
    torch.ops._moe_C.moe_gather(
        output, gemm2, topk_weights, route_map, LOCAL_EXPERTS
    )
    return output


def timed_ms(call, iterations: int) -> float:
    for _ in range(3):
        call()
    torch.xpu.synchronize()
    started = time.perf_counter()
    for _ in range(iterations):
        call()
    torch.xpu.synchronize()
    return (time.perf_counter() - started) * 1000.0 / iterations


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rank", type=int, required=True, choices=range(4))
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--timing-iterations", type=int, default=20)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    torch.manual_seed(7300 + args.rank)
    torch.xpu.set_device(0)
    w13 = torch.randint(
        -128,
        128,
        (LOCAL_EXPERTS, 2 * INTERMEDIATE, HIDDEN // 2),
        dtype=torch.int8,
        device="xpu",
    )
    s13 = (
        torch.rand(
            (LOCAL_EXPERTS, 2 * INTERMEDIATE, HIDDEN // 32),
            dtype=torch.bfloat16,
            device="xpu",
        )
        * 0.02
    )
    w2 = torch.randint(
        -128,
        128,
        (LOCAL_EXPERTS, HIDDEN, INTERMEDIATE // 2),
        dtype=torch.int8,
        device="xpu",
    )
    s2 = (
        torch.rand(
            (LOCAL_EXPERTS, HIDDEN, INTERMEDIATE // 32),
            dtype=torch.bfloat16,
            device="xpu",
        )
        * 0.02
    )
    expert_map = torch.full((GLOBAL_EXPERTS,), -1, dtype=torch.int32, device="xpu")
    expert_map[
        args.rank * LOCAL_EXPERTS : (args.rank + 1) * LOCAL_EXPERTS
    ] = torch.arange(LOCAL_EXPERTS, dtype=torch.int32, device="xpu")
    scratch = (
        torch.empty((8 * TOPK, 2 * INTERMEDIATE), dtype=torch.bfloat16, device="xpu"),
        torch.empty((8 * TOPK, INTERMEDIATE), dtype=torch.bfloat16, device="xpu"),
        torch.empty((8 * TOPK, HIDDEN), dtype=torch.bfloat16, device="xpu"),
    )

    cases = []
    total_equal = 0
    for rows in (1, 8):
        for epoch in range(args.epochs):
            hidden = torch.randn((rows, HIDDEN), dtype=torch.bfloat16, device="xpu")
            topk_ids = make_routes(args.rank, rows, epoch)
            weights = torch.rand((rows, TOPK), dtype=torch.float32, device="xpu")
            weights /= weights.sum(dim=1, keepdim=True)
            ref, ref_w1, ref_act, ref_w2 = baseline(
                hidden, w13, s13, w2, s2, weights, topk_ids, expert_map
            )
            got = candidate(
                hidden,
                w13,
                s13,
                w2,
                s2,
                weights,
                topk_ids,
                expert_map,
                scratch,
            )
            torch.xpu.synchronize()
            mapped = expert_map[topk_ids].reshape(-1)
            local = mapped >= 0
            route_count = rows * TOPK
            equal = torch.equal(ref, got)
            local_w1_equal = torch.equal(ref_w1[local], scratch[0][:route_count][local])
            local_act_equal = torch.equal(ref_act[local], scratch[1][:route_count][local])
            local_w2_equal = torch.equal(ref_w2[local], scratch[2][:route_count][local])
            if equal:
                total_equal += 1
            cases.append(
                {
                    "rows": rows,
                    "epoch": epoch,
                    "output_equal": equal,
                    "different_elements": int(torch.count_nonzero(ref != got).item()),
                    "local_w1_equal": local_w1_equal,
                    "local_activation_equal": local_act_equal,
                    "local_w2_equal": local_w2_equal,
                    "input_sha256": tensor_hash(hidden),
                    "routes_sha256": tensor_hash(topk_ids),
                    "output_sha256": tensor_hash(got),
                }
            )

    rows = 8
    hidden = torch.randn((rows, HIDDEN), dtype=torch.bfloat16, device="xpu")
    topk_ids = make_routes(args.rank, rows, args.epochs + 1)
    weights = torch.rand((rows, TOPK), dtype=torch.float32, device="xpu")
    weights /= weights.sum(dim=1, keepdim=True)
    baseline_ms = timed_ms(
        lambda: baseline(hidden, w13, s13, w2, s2, weights, topk_ids, expert_map),
        args.timing_iterations,
    )
    candidate_ms = timed_ms(
        lambda: candidate(
            hidden,
            w13,
            s13,
            w2,
            s2,
            weights,
            topk_ids,
            expert_map,
            scratch,
        ),
        args.timing_iterations,
    )
    result = {
        "rank": args.rank,
        "device": torch.xpu.get_device_name(0),
        "epochs_per_shape": args.epochs,
        "shapes": [1, 8],
        "passed": total_equal == len(cases)
        and all(
            row["local_w1_equal"]
            and row["local_activation_equal"]
            and row["local_w2_equal"]
            for row in cases
        ),
        "output_equal": f"{total_equal}/{len(cases)}",
        "baseline_m8_ms_per_layer": baseline_ms,
        "candidate_m8_ms_per_layer": candidate_ms,
        "delta_m8_ms_per_layer": candidate_ms - baseline_ms,
        "baseline_routed_device_ops_per_layer": 6,
        "candidate_routed_device_ops_per_layer": 4,
        "cases": cases,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "cases"}))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
