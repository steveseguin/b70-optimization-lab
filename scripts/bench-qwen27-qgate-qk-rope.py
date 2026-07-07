#!/usr/bin/env python3
"""Microbench Qwen3.6 27B q-gate Q/K RMSNorm+RoPE paths on XPU.

This is a diagnostic benchmark only. It uses synthetic tensors with the
webhie/Intel Qwen3.6-27B text-config attention shape:

  q_gate: [T, 24 * 256 * 2], k/v: [T, 4 * 256]

The goal is to decide whether the existing fused_qk_norm_rope op is useful for
Qwen3Next's gated Q layout via a temporary packed [q,k,v] buffer, or whether the
pack/copy overhead means a real q-gate-layout native kernel is required.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

import torch


NUM_HEADS_Q = 24
NUM_HEADS_KV = 4
HEAD_DIM = 256
ROTARY_DIM = 64
EPS = 1e-6
Q_SIZE = NUM_HEADS_Q * HEAD_DIM
KV_SIZE = NUM_HEADS_KV * HEAD_DIM
QGATE_SIZE = Q_SIZE * 2
QKV_WITH_GATE_SIZE = QGATE_SIZE + 2 * KV_SIZE
PACKED_QKV_SIZE = Q_SIZE + 2 * KV_SIZE


@dataclass
class Timing:
    name: str
    median_ms: float
    mean_ms: float
    p10_ms: float
    p90_ms: float
    repeats: int


def env_snapshot() -> dict[str, str]:
    keys = [
        "ONEAPI_DEVICE_SELECTOR",
        "ZE_AFFINITY_MASK",
        "PYTHONPATH",
        "LD_LIBRARY_PATH",
        "VLLM_TARGET_DEVICE",
    ]
    return {k: os.environ[k] for k in keys if k in os.environ}


def sync() -> None:
    torch.xpu.synchronize()


def bench_fn(fn: Callable[[], object], warmup: int, repeats: int) -> Timing:
    for _ in range(warmup):
        fn()
    sync()

    samples: list[float] = []
    for _ in range(repeats):
        sync()
        start = time.perf_counter_ns()
        fn()
        sync()
        samples.append((time.perf_counter_ns() - start) / 1_000_000.0)

    ordered = sorted(samples)
    p10_idx = max(0, int(0.10 * (len(ordered) - 1)))
    p90_idx = min(len(ordered) - 1, int(0.90 * (len(ordered) - 1)))
    return Timing(
        name="",
        median_ms=float(statistics.median(samples)),
        mean_ms=float(statistics.mean(samples)),
        p10_ms=float(ordered[p10_idx]),
        p90_ms=float(ordered[p90_idx]),
        repeats=repeats,
    )


def make_cos_sin_cache(
    max_position: int,
    dtype: torch.dtype,
    device: torch.device,
) -> torch.Tensor:
    # vLLM-style cache: [max_position, rotary_dim], first half cos, second sin.
    theta = 10_000_000.0
    half = ROTARY_DIM // 2
    inv_freq = 1.0 / (theta ** (torch.arange(0, half, device=device).float() / half))
    positions = torch.arange(max_position, device=device, dtype=torch.float32)
    freqs = torch.outer(positions, inv_freq)
    return torch.cat([freqs.cos(), freqs.sin()], dim=-1).to(dtype)


def split_qgate(
    qkv: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    q_gate, k, v = qkv.split([QGATE_SIZE, KV_SIZE, KV_SIZE], dim=-1)
    orig_shape = q_gate.shape[:-1]
    q_gate_heads = q_gate.view(*orig_shape, NUM_HEADS_Q, HEAD_DIM * 2)
    q, gate = torch.chunk(q_gate_heads, 2, dim=-1)
    q = q.reshape(*orig_shape, Q_SIZE)
    gate = gate.reshape(*orig_shape, Q_SIZE)
    return q, gate, k, v


def native_baseline(
    qkv: torch.Tensor,
    positions: torch.Tensor,
    q_weight: torch.Tensor,
    k_weight: torch.Tensor,
    cos_sin_cache: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    q, gate, k, v = split_qgate(qkv)
    q_heads = q.view(-1, NUM_HEADS_Q, HEAD_DIM)
    k_heads = k.view(-1, NUM_HEADS_KV, HEAD_DIM)
    q_out = torch.empty_like(q_heads)
    k_out = torch.empty_like(k_heads)
    torch.ops._C.rms_norm(q_out, q_heads, q_weight, EPS)
    torch.ops._C.rms_norm(k_out, k_heads, k_weight, EPS)
    q_flat = q_out.view(-1, Q_SIZE)
    k_flat = k_out.view(-1, KV_SIZE)
    torch.ops._C.rotary_embedding(
        positions, q_flat, k_flat, HEAD_DIM, cos_sin_cache, True
    )
    return q_flat, k_flat, v, gate


def temp_pack_fused(
    qkv: torch.Tensor,
    positions: torch.Tensor,
    q_weight: torch.Tensor,
    k_weight: torch.Tensor,
    cos_sin_cache: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    q, gate, k, v = split_qgate(qkv)
    packed = torch.cat([q, k, v], dim=-1)
    torch.ops._C.fused_qk_norm_rope(
        packed,
        NUM_HEADS_Q,
        NUM_HEADS_KV,
        NUM_HEADS_KV,
        HEAD_DIM,
        EPS,
        q_weight,
        k_weight,
        cos_sin_cache,
        True,
        positions,
        -1,
    )
    q_out, k_out, v_out = packed.split([Q_SIZE, KV_SIZE, KV_SIZE], dim=-1)
    return q_out, k_out, v_out, gate


def temp_pack_only(qkv: torch.Tensor) -> torch.Tensor:
    q, _, k, v = split_qgate(qkv)
    return torch.cat([q, k, v], dim=-1)


def direct_qgate_fused(
    qkv: torch.Tensor,
    positions: torch.Tensor,
    q_weight: torch.Tensor,
    k_weight: torch.Tensor,
    cos_sin_cache: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    q_gate, k, v = qkv.split([QGATE_SIZE, KV_SIZE, KV_SIZE], dim=-1)
    q_out = torch.empty(qkv.shape[0], Q_SIZE, device=qkv.device, dtype=qkv.dtype)
    gate_out = torch.empty_like(q_out)
    k_out = torch.empty(qkv.shape[0], KV_SIZE, device=qkv.device, dtype=qkv.dtype)
    torch.ops._C.fused_qgate_qk_norm_rope(
        q_gate,
        k,
        q_out,
        gate_out,
        k_out,
        NUM_HEADS_Q,
        NUM_HEADS_KV,
        HEAD_DIM,
        EPS,
        q_weight,
        k_weight,
        cos_sin_cache,
        True,
        positions,
    )
    return q_out, k_out, v, gate_out


def prepacked_fused_only(
    packed_template: torch.Tensor,
    positions: torch.Tensor,
    q_weight: torch.Tensor,
    k_weight: torch.Tensor,
    cos_sin_cache: torch.Tensor,
) -> torch.Tensor:
    packed = packed_template.clone()
    torch.ops._C.fused_qk_norm_rope(
        packed,
        NUM_HEADS_Q,
        NUM_HEADS_KV,
        NUM_HEADS_KV,
        HEAD_DIM,
        EPS,
        q_weight,
        k_weight,
        cos_sin_cache,
        True,
        positions,
        -1,
    )
    return packed


def check_correctness(
    qkv: torch.Tensor,
    positions: torch.Tensor,
    q_weight: torch.Tensor,
    k_weight: torch.Tensor,
    q_weight_raw: torch.Tensor,
    k_weight_raw: torch.Tensor,
    cos_sin_cache: torch.Tensor,
) -> dict[str, float | bool]:
    q1, k1, v1, gate1 = native_baseline(
        qkv, positions, q_weight, k_weight, cos_sin_cache
    )
    q2, k2, v2, gate2 = temp_pack_fused(
        qkv, positions, q_weight, k_weight, cos_sin_cache
    )
    if hasattr(torch.ops._C, "fused_qgate_qk_norm_rope"):
        q3, k3, v3, gate3 = direct_qgate_fused(
            qkv, positions, q_weight_raw, k_weight_raw, cos_sin_cache
        )
    else:
        q3 = k3 = v3 = gate3 = None
    sync()
    result: dict[str, float | bool | str] = {
        "q_max_abs": float((q1 - q2).abs().max().item()),
        "k_max_abs": float((k1 - k2).abs().max().item()),
        "v_max_abs": float((v1 - v2).abs().max().item()),
        "gate_max_abs": float((gate1 - gate2).abs().max().item()),
        "allclose_atol_1e_2": bool(
            torch.allclose(q1, q2, atol=1e-2, rtol=1e-2)
            and torch.allclose(k1, k2, atol=1e-2, rtol=1e-2)
            and torch.equal(v1, v2)
            and torch.equal(gate1, gate2)
        ),
    }
    if q3 is not None and k3 is not None and v3 is not None and gate3 is not None:
        result.update(
            {
                "direct_q_max_abs": float((q1 - q3).abs().max().item()),
                "direct_k_max_abs": float((k1 - k3).abs().max().item()),
                "direct_v_max_abs": float((v1 - v3).abs().max().item()),
                "direct_gate_max_abs": float((gate1 - gate3).abs().max().item()),
                "direct_allclose_atol_1e_2": bool(
                    torch.allclose(q1, q3, atol=1e-2, rtol=1e-2)
                    and torch.allclose(k1, k3, atol=1e-2, rtol=1e-2)
                    and torch.equal(v1, v3)
                    and torch.equal(gate1, gate3)
                ),
            }
        )
    return result


def run(args: argparse.Namespace) -> dict[str, object]:
    # Import after env is set so the local XPU extension registers torch.ops._C.
    import vllm._custom_ops  # noqa: F401

    if not torch.xpu.is_available():
        raise SystemExit("torch.xpu is not available")

    device = torch.device("xpu")
    torch.manual_seed(args.seed)
    dtype = getattr(torch, args.dtype)
    cache_dtype = getattr(torch, args.cache_dtype)

    q_weight_raw = torch.randn(HEAD_DIM, device=device, dtype=dtype) * 0.05
    k_weight_raw = torch.randn(HEAD_DIM, device=device, dtype=dtype) * 0.05
    q_weight = (q_weight_raw.float() + 1.0).to(dtype)
    k_weight = (k_weight_raw.float() + 1.0).to(dtype)
    cos_sin_cache = make_cos_sin_cache(args.max_position, cache_dtype, device)

    results: dict[str, object] = {
        "env": env_snapshot(),
        "torch_version": torch.__version__,
        "shape": {
            "num_heads_q": NUM_HEADS_Q,
            "num_heads_kv": NUM_HEADS_KV,
            "head_dim": HEAD_DIM,
            "rotary_dim": ROTARY_DIM,
            "qkv_with_gate_size": QKV_WITH_GATE_SIZE,
            "packed_qkv_size": PACKED_QKV_SIZE,
        },
        "dtype": args.dtype,
        "cache_dtype": args.cache_dtype,
        "warmup": args.warmup,
        "repeats": args.repeats,
        "tokens": {},
    }

    for tokens in args.tokens:
        qkv = torch.randn(
            tokens, QKV_WITH_GATE_SIZE, device=device, dtype=dtype
        )
        positions = torch.arange(tokens, device=device, dtype=torch.int64)
        packed_template = temp_pack_only(qkv)
        sync()

        correctness = check_correctness(
            qkv,
            positions,
            q_weight,
            k_weight,
            q_weight_raw,
            k_weight_raw,
            cos_sin_cache,
        )

        timings: dict[str, Timing] = {}
        variants: dict[str, Callable[[], object]] = {
            "split_qgate_only": lambda qkv=qkv: split_qgate(qkv),
            "temp_pack_only": lambda qkv=qkv: temp_pack_only(qkv),
            "native_baseline_rms_rms_rotary": (
                lambda qkv=qkv, positions=positions: native_baseline(
                    qkv, positions, q_weight, k_weight, cos_sin_cache
                )
            ),
            "temp_pack_fused_qk_rope": (
                lambda qkv=qkv, positions=positions: temp_pack_fused(
                    qkv, positions, q_weight, k_weight, cos_sin_cache
                )
            ),
            "prepacked_fused_only_lower_bound": (
                lambda packed_template=packed_template, positions=positions: (
                    prepacked_fused_only(
                        packed_template,
                        positions,
                        q_weight,
                        k_weight,
                        cos_sin_cache,
                    )
                )
            ),
        }
        if hasattr(torch.ops._C, "fused_qgate_qk_norm_rope"):
            variants["direct_qgate_fused_qk_rope"] = (
                lambda qkv=qkv, positions=positions: direct_qgate_fused(
                    qkv, positions, q_weight_raw, k_weight_raw, cos_sin_cache
                )
            )
        for name, fn in variants.items():
            timing = bench_fn(fn, args.warmup, args.repeats)
            timing.name = name
            timings[name] = timing

        token_result = {
            "correctness": correctness,
            "timings_ms": {name: asdict(value) for name, value in timings.items()},
        }
        base = timings["native_baseline_rms_rms_rotary"].median_ms
        candidate = timings["temp_pack_fused_qk_rope"].median_ms
        token_result["candidate_vs_baseline_median_delta_ms"] = candidate - base
        token_result["candidate_vs_baseline_median_ratio"] = (
            candidate / base if base > 0 else None
        )
        results["tokens"][str(tokens)] = token_result

    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tokens", type=int, nargs="+", default=[1, 2, 4, 8, 16])
    parser.add_argument("--warmup", type=int, default=50)
    parser.add_argument("--repeats", type=int, default=200)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--dtype", choices=["bfloat16", "float16"], default="bfloat16")
    parser.add_argument(
        "--cache-dtype", choices=["bfloat16", "float16", "float32"], default="bfloat16"
    )
    parser.add_argument("--max-position", type=int, default=4096)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    result = run(args)
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
