#!/usr/bin/env python3
"""Changing-input exactness/timing gate for Laguna QKNorm+RoPE."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import torch

from vllm import _custom_ops as ops


HEAD_DIM = 128
KV_HEADS = 2
CASES = {
    "full": {"q_heads": 12, "rotary_dim": 64, "layers": 12},
    "sliding": {"q_heads": 18, "rotary_dim": 128, "layers": 36},
}


def tensor_hash(tensor: torch.Tensor) -> str:
    raw = tensor.cpu().contiguous().view(torch.uint8).numpy().tobytes()
    return hashlib.sha256(raw).hexdigest()


def baseline(
    q: torch.Tensor,
    k: torch.Tensor,
    q_weight: torch.Tensor,
    k_weight: torch.Tensor,
    cache: torch.Tensor,
    positions: torch.Tensor,
    eps: float,
    rows: int,
) -> tuple[torch.Tensor, torch.Tensor]:
    q_out = torch.empty_like(q)
    k_out = torch.empty_like(k)
    ops.rms_norm(
        q_out.view(rows, -1, HEAD_DIM),
        q.view(rows, -1, HEAD_DIM),
        q_weight,
        eps,
    )
    ops.rms_norm(
        k_out.view(rows, -1, HEAD_DIM),
        k.view(rows, -1, HEAD_DIM),
        k_weight,
        eps,
    )
    ops.rotary_embedding(positions, q_out, k_out, HEAD_DIM, cache, True)
    return q_out, k_out


def candidate(
    q: torch.Tensor,
    k: torch.Tensor,
    q_weight: torch.Tensor,
    k_weight: torch.Tensor,
    cache: torch.Tensor,
    positions: torch.Tensor,
    eps: float,
) -> tuple[torch.Tensor, torch.Tensor]:
    q_out = torch.empty_like(q)
    k_out = torch.empty_like(k)
    ops.laguna_m8_qk_norm_rope_out(
        q_out,
        k_out,
        q,
        k,
        q_weight,
        k_weight,
        cache,
        positions,
        eps,
    )
    return q_out, k_out


def timed_ms(call, iterations: int) -> float:
    for _ in range(10):
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
    parser.add_argument("--rows", type=int, default=8, choices=(8, 12))
    parser.add_argument("--epochs", type=int, default=16)
    parser.add_argument("--timing-iterations", type=int, default=200)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    torch.xpu.set_device(0)
    eps = 1e-6
    exact = 0
    checks = 0
    results: dict[str, object] = {}

    for case_index, (name, case) in enumerate(CASES.items()):
        q_heads = case["q_heads"]
        rotary_dim = case["rotary_dim"]
        last_inputs = None
        hashes = []
        case_exact = 0
        case_checks = 0

        for epoch in range(args.epochs):
            torch.manual_seed(72200 + args.rank * 1000 + case_index * 100 + epoch)
            width = (q_heads + 2 * KV_HEADS) * HEAD_DIM
            qkv = torch.randn((args.rows, width), dtype=torch.bfloat16, device="xpu")
            q_weight = torch.randn((HEAD_DIM,), dtype=torch.bfloat16, device="xpu")
            k_weight = torch.randn((HEAD_DIM,), dtype=torch.bfloat16, device="xpu")
            cache = torch.randn((2048, rotary_dim), dtype=torch.bfloat16, device="xpu")
            positions = (
                torch.arange(args.rows, dtype=torch.int64, device="xpu") * 17
                + 31
                + epoch
            )
            q, k, _ = qkv.split(
                [q_heads * HEAD_DIM, KV_HEADS * HEAD_DIM, KV_HEADS * HEAD_DIM],
                dim=-1,
            )
            base_q, base_k = baseline(
                q, k, q_weight, k_weight, cache, positions, eps, args.rows
            )
            cand_q, cand_k = candidate(q, k, q_weight, k_weight, cache, positions, eps)
            torch.xpu.synchronize()
            for component, base, cand in (
                ("q", base_q, cand_q),
                ("k", base_k, cand_k),
            ):
                equal = torch.equal(base, cand)
                exact += int(equal)
                checks += 1
                case_exact += int(equal)
                case_checks += 1
                if not equal:
                    mismatch = int((base != cand).sum().item())
                    raise AssertionError(
                        f"{name} epoch {epoch} {component} has "
                        f"{mismatch} non-identical BF16 values"
                    )
            hashes.append({"q": tensor_hash(cand_q), "k": tensor_hash(cand_k)})
            last_inputs = (q, k, q_weight, k_weight, cache, positions)

        assert last_inputs is not None
        q, k, q_weight, k_weight, cache, positions = last_inputs
        base_ms = timed_ms(
            lambda: baseline(
                q, k, q_weight, k_weight, cache, positions, eps, args.rows
            ),
            args.timing_iterations,
        )
        candidate_ms = timed_ms(
            lambda: candidate(q, k, q_weight, k_weight, cache, positions, eps),
            args.timing_iterations,
        )
        results[name] = {
            "q_heads": q_heads,
            "kv_heads": KV_HEADS,
            "head_dim": HEAD_DIM,
            "rotary_dim": rotary_dim,
            "layers": case["layers"],
            "exact": f"{case_exact}/{case_checks}",
            "baseline_ms_per_layer": base_ms,
            "candidate_ms_per_layer": candidate_ms,
            "baseline_launches_per_layer": 3,
            "candidate_launches_per_layer": 1,
            "last_hashes": hashes[-1],
        }

    baseline_cycle_ms = sum(
        row["layers"] * row["baseline_ms_per_layer"] for row in results.values()
    )
    candidate_cycle_ms = sum(
        row["layers"] * row["candidate_ms_per_layer"] for row in results.values()
    )
    payload = {
        "rank": args.rank,
        "device": torch.xpu.get_device_name(0),
        "rows": args.rows,
        "epochs": args.epochs,
        "passed": exact == checks,
        "exact": f"{exact}/{checks}",
        "cases": results,
        "weighted_48_layer_cycle": {
            "baseline_ms": baseline_cycle_ms,
            "candidate_ms": candidate_cycle_ms,
            "baseline_launches": 144,
            "candidate_launches": 48,
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
