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
GUARD_ELEMENTS = 8
GUARD_VALUE = 123.5
WIDE_ROWS = (1024, 4096, 8064, 8192)
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
    op_name: str,
    *,
    guarded: bool = False,
) -> tuple[torch.Tensor, torch.Tensor, bool]:
    if guarded:
        q_storage = torch.full(
            (q.numel() + 2 * GUARD_ELEMENTS,),
            GUARD_VALUE,
            dtype=q.dtype,
            device=q.device,
        )
        k_storage = torch.full(
            (k.numel() + 2 * GUARD_ELEMENTS,),
            GUARD_VALUE,
            dtype=k.dtype,
            device=k.device,
        )
        q_out = q_storage[GUARD_ELEMENTS : GUARD_ELEMENTS + q.numel()].view_as(q)
        k_out = k_storage[GUARD_ELEMENTS : GUARD_ELEMENTS + k.numel()].view_as(k)
    else:
        q_storage = k_storage = None
        q_out = torch.empty_like(q)
        k_out = torch.empty_like(k)
    op = getattr(ops, op_name)
    op(
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
    guards_ok = True
    if guarded:
        assert q_storage is not None and k_storage is not None
        guard = torch.full(
            (GUARD_ELEMENTS,), GUARD_VALUE, dtype=q.dtype, device=q.device
        )
        guards_ok = all(
            torch.equal(actual, guard)
            for actual in (
                q_storage[:GUARD_ELEMENTS],
                q_storage[-GUARD_ELEMENTS:],
                k_storage[:GUARD_ELEMENTS],
                k_storage[-GUARD_ELEMENTS:],
            )
        )
    return q_out, k_out, guards_ok


def position_starts(rows: int, mode: str) -> tuple[int, ...]:
    if mode == "exact-verifier":
        return (0,)
    starts = [start for start in (0, 8192, 16384, 24576) if start + rows <= 32768]
    starts.append(32768 - rows)
    return tuple(sorted(set(starts)))


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
    parser.add_argument(
        "--mode",
        choices=("exact-verifier", "wide-prefill"),
        default="exact-verifier",
    )
    parser.add_argument("--rows", type=int)
    parser.add_argument("--epochs", type=int, default=16)
    parser.add_argument("--timing-iterations", type=int, default=200)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    rows = args.rows
    if rows is None:
        rows = 8 if args.mode == "exact-verifier" else 8192
    allowed_rows = (8, 12) if args.mode == "exact-verifier" else WIDE_ROWS
    if rows not in allowed_rows:
        parser.error(f"--rows must be one of {allowed_rows} for mode {args.mode}")
    op_name = (
        "laguna_m8_qk_norm_rope_out"
        if args.mode == "exact-verifier"
        else "laguna_wide_prefill_qk_norm_rope_out"
    )
    starts = position_starts(rows, args.mode)
    cache_rows = 2048 if args.mode == "exact-verifier" else 32768

    torch.xpu.set_device(0)
    eps = 1e-6
    exact = 0
    checks = 0
    failures: list[str] = []
    results: dict[str, object] = {}

    for case_index, (name, case) in enumerate(CASES.items()):
        q_heads = case["q_heads"]
        rotary_dim = case["rotary_dim"]
        last_inputs = None
        hashes = []
        case_exact = 0
        case_checks = 0
        case_guards_ok = True
        case_inputs_immutable = True
        case_outputs_separate = True

        for epoch in range(args.epochs):
            torch.manual_seed(72200 + args.rank * 1000 + case_index * 100 + epoch)
            width = (q_heads + 2 * KV_HEADS) * HEAD_DIM
            qkv = torch.randn((rows, width), dtype=torch.bfloat16, device="xpu")
            q_weight = torch.randn((HEAD_DIM,), dtype=torch.bfloat16, device="xpu")
            k_weight = torch.randn((HEAD_DIM,), dtype=torch.bfloat16, device="xpu")
            cache = torch.randn(
                (cache_rows, rotary_dim), dtype=torch.bfloat16, device="xpu"
            )
            if args.mode == "exact-verifier":
                positions = (
                    torch.arange(rows, dtype=torch.int64, device="xpu") * 17
                    + 31
                    + epoch
                )
            else:
                start = starts[epoch % len(starts)]
                positions = torch.arange(
                    start, start + rows, dtype=torch.int64, device="xpu"
                )
            q, k, _ = qkv.split(
                [q_heads * HEAD_DIM, KV_HEADS * HEAD_DIM, KV_HEADS * HEAD_DIM],
                dim=-1,
            )
            immutable_inputs = tuple(
                tensor.clone()
                for tensor in (q, k, q_weight, k_weight, cache, positions)
            )
            base_q, base_k = baseline(
                q, k, q_weight, k_weight, cache, positions, eps, rows
            )
            cand_q, cand_k, guards_ok = candidate(
                q,
                k,
                q_weight,
                k_weight,
                cache,
                positions,
                eps,
                op_name,
                guarded=True,
            )
            torch.xpu.synchronize()
            inputs_immutable = all(
                torch.equal(actual, expected)
                for actual, expected in zip(
                    (q, k, q_weight, k_weight, cache, positions),
                    immutable_inputs,
                    strict=True,
                )
            )
            input_storages = {
                tensor.untyped_storage().data_ptr()
                for tensor in (q, k, q_weight, k_weight, cache, positions)
            }
            outputs_separate = (
                cand_q.untyped_storage().data_ptr() not in input_storages
                and cand_k.untyped_storage().data_ptr() not in input_storages
                and cand_q.untyped_storage().data_ptr()
                != cand_k.untyped_storage().data_ptr()
            )
            case_guards_ok &= guards_ok
            case_inputs_immutable &= inputs_immutable
            case_outputs_separate &= outputs_separate
            if not guards_ok:
                failures.append(f"{name} epoch {epoch} output guard changed")
            if not inputs_immutable:
                failures.append(f"{name} epoch {epoch} input mutated")
            if not outputs_separate:
                failures.append(f"{name} epoch {epoch} output alias detected")
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
                    failures.append(
                        f"{name} epoch {epoch} {component} has "
                        f"{mismatch} non-identical BF16 values"
                    )
            hashes.append({"q": tensor_hash(cand_q), "k": tensor_hash(cand_k)})
            last_inputs = (q, k, q_weight, k_weight, cache, positions)

        assert last_inputs is not None
        q, k, q_weight, k_weight, cache, positions = last_inputs
        base_ms = timed_ms(
            lambda: baseline(q, k, q_weight, k_weight, cache, positions, eps, rows),
            args.timing_iterations,
        )
        candidate_ms = timed_ms(
            lambda: candidate(
                q,
                k,
                q_weight,
                k_weight,
                cache,
                positions,
                eps,
                op_name,
            ),
            args.timing_iterations,
        )
        timing_ratio = candidate_ms / base_ms
        if args.mode == "wide-prefill" and timing_ratio > 0.95:
            failures.append(
                f"{name} candidate timing ratio {timing_ratio:.6f} exceeds 0.95"
            )
        results[name] = {
            "q_heads": q_heads,
            "kv_heads": KV_HEADS,
            "head_dim": HEAD_DIM,
            "rotary_dim": rotary_dim,
            "layers": case["layers"],
            "position_starts": starts,
            "exact": f"{case_exact}/{case_checks}",
            "inputs_immutable": case_inputs_immutable,
            "outputs_separate": case_outputs_separate,
            "output_guards_intact": case_guards_ok,
            "baseline_ms_per_layer": base_ms,
            "candidate_ms_per_layer": candidate_ms,
            "candidate_to_baseline_ratio": timing_ratio,
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
    cycle_saving_ms = baseline_cycle_ms - candidate_cycle_ms
    aligned_multiplicity = 3 if rows == 8192 else 1 if rows == 8064 else 0
    payload = {
        "rank": args.rank,
        "device": torch.xpu.get_device_name(0),
        "mode": args.mode,
        "native_op": op_name,
        "rows": rows,
        "position_starts": starts,
        "epochs": args.epochs,
        "passed": exact == checks and not failures,
        "exact": f"{exact}/{checks}",
        "failures": failures,
        "cases": results,
        "weighted_48_layer_cycle": {
            "baseline_ms": baseline_cycle_ms,
            "candidate_ms": candidate_cycle_ms,
            "saving_ms": cycle_saving_ms,
            "baseline_launches": 144,
            "candidate_launches": 48,
        },
        "aligned_32640_projection_contribution": {
            "chunk_multiplicity": aligned_multiplicity,
            "saving_ms": aligned_multiplicity * cycle_saving_ms,
            "aggregate_requirement": (
                "sum three 8192-token chunks and one 8064-token chunk; "
                "require at least 25 ms"
            ),
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))
    if failures:
        raise AssertionError(f"Laguna QKNorm+RoPE gate failed: {failures}")


if __name__ == "__main__":
    main()
