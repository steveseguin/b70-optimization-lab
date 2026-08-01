#!/usr/bin/env python3
"""Real-weight one-B70 screen for local TP4-emulated Laguna DFlash.

This is deliberately not an endpoint benchmark. It validates the four-shard
projection arithmetic and measures the extra projection work introduced by
local TP4 emulation. Attention and inter-rank collective time are reported as
out of scope, so this tool cannot by itself authorize a scored run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

import torch
from safetensors import safe_open

import vllm_xpu_kernels._C  # noqa: F401 - registers the frozen XPU operators.
from vllm import _custom_ops as ops
from vllm.model_executor.models import laguna_dflash


PROJECTIONS = ("qkv_proj", "o_proj", "gate_proj", "up_proj", "down_proj")
WEIGHT_NAMES = {
    projection: f"layers.0.{'self_attn' if projection in ('qkv_proj', 'o_proj') else 'mlp'}.{projection}.weight"
    for projection in PROJECTIONS
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _vllm_commit() -> str:
    root = Path(laguna_dflash.__file__).resolve().parents[3]
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _quantize_shards(
    weight: torch.Tensor,
    projection: str,
) -> tuple[torch.Tensor, torch.Tensor]:
    quantized = []
    scales = []
    for shard in laguna_dflash._split_laguna_dflash_local_tp4_weight(
        weight,
        projection=projection,
    ):
        q, scale = ops.scaled_fp8_quant(
            shard,
            use_per_token_if_dynamic=True,
        )
        quantized.append(q.t().contiguous())
        scales.append(scale.reshape(-1).float().contiguous())
    return (
        torch.stack(quantized, dim=0).contiguous(),
        torch.stack(scales, dim=0).contiguous(),
    )


def _method(projection: str) -> laguna_dflash._LagunaDFlashLocalTP4FP8LinearMethod:
    return laguna_dflash._LagunaDFlashLocalTP4FP8LinearMethod(projection)


def _manual(
    projection: str,
    inputs: torch.Tensor,
    weight: torch.Tensor,
    scale: torch.Tensor,
) -> torch.Tensor:
    gemm = torch.ops._xpu_C.fp8_gemm_w8a16
    if projection == "qkv_proj":
        locals_ = [gemm(inputs, weight[rank], scale[rank], None) for rank in range(4)]
        components = [local.split((2304, 256, 256), dim=-1) for local in locals_]
        return torch.cat(
            tuple(
                components[rank][component]
                for component in range(3)
                for rank in range(4)
            ),
            dim=-1,
        )
    if projection in ("gate_proj", "up_proj"):
        return torch.cat(
            tuple(gemm(inputs, weight[rank], scale[rank], None) for rank in range(4)),
            dim=-1,
        )
    split_size = 2304 if projection == "o_proj" else 3072
    parts = inputs.split(split_size, dim=-1)
    outputs = [
        gemm(parts[rank].contiguous(), weight[rank], scale[rank], None)
        for rank in range(4)
    ]
    result = outputs[0]
    result.add_(outputs[1])
    result.add_(outputs[2])
    result.add_(outputs[3])
    return result


def _candidate_projection(
    projection: str,
    inputs: torch.Tensor,
    weights: dict[str, torch.Tensor],
    scales: dict[str, torch.Tensor],
) -> torch.Tensor:
    layer = SimpleNamespace(weight=weights[projection], weight_scale=scales[projection])
    return _method(projection).apply(layer, inputs)


def _time_ms(callable_, *, warmups: int, samples: int) -> dict[str, float]:
    for _ in range(warmups):
        callable_()
    torch.xpu.synchronize()
    values = []
    for _ in range(samples):
        start = time.perf_counter_ns()
        callable_()
        torch.xpu.synchronize()
        values.append((time.perf_counter_ns() - start) / 1_000_000)
    ordered = sorted(values)
    return {
        "median_ms": ordered[len(ordered) // 2],
        "minimum_ms": ordered[0],
        "maximum_ms": ordered[-1],
        "mean_ms": sum(values) / len(values),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rows", type=int, default=12)
    parser.add_argument("--warmups", type=int, default=8)
    parser.add_argument("--samples", type=int, default=31)
    args = parser.parse_args()
    if args.rows != 12 or args.warmups < 1 or args.samples < 5:
        raise SystemExit("sealed gate requires rows=12, warmups>=1, samples>=5")
    if torch.xpu.device_count() < 1:
        raise SystemExit("no XPU available")

    device = torch.device("xpu:0")
    weights: dict[str, torch.Tensor] = {}
    scales: dict[str, torch.Tensor] = {}
    with safe_open(args.checkpoint, framework="pt", device="cpu") as handle:
        for projection in PROJECTIONS:
            source = handle.get_tensor(WEIGHT_NAMES[projection])
            if source.dtype != torch.bfloat16:
                raise RuntimeError(f"{projection} source is not BF16")
            weight, scale = _quantize_shards(source.contiguous().to(device), projection)
            weights[projection] = weight
            scales[projection] = scale
            del source
            torch.xpu.synchronize()

    generator = torch.Generator(device=device).manual_seed(20260731)
    hidden = torch.randn(
        (args.rows, 3072),
        dtype=torch.bfloat16,
        device=device,
        generator=generator,
    )
    attention_input = torch.randn(
        (args.rows, 9216),
        dtype=torch.bfloat16,
        device=device,
        generator=generator,
    )

    parity: dict[str, bool] = {}
    for projection in PROJECTIONS:
        inputs = attention_input if projection == "o_proj" else hidden
        if projection == "down_proj":
            inputs = torch.randn(
                (args.rows, 12288),
                dtype=torch.bfloat16,
                device=device,
                generator=generator,
            )
        expected = _manual(projection, inputs, weights[projection], scales[projection])
        actual = _candidate_projection(
            projection,
            inputs,
            weights,
            scales,
        )
        parity[projection] = bool(
            torch.equal(actual.view(torch.int16), expected.view(torch.int16))
        )
        if not parity[projection]:
            raise RuntimeError(f"raw parity failed for {projection}")

    def candidate_body() -> None:
        _candidate_projection("qkv_proj", hidden, weights, scales)
        _candidate_projection("o_proj", attention_input, weights, scales)
        gate = _candidate_projection("gate_proj", hidden, weights, scales)
        up = _candidate_projection("up_proj", hidden, weights, scales)
        activated = torch.nn.functional.silu(gate) * up
        _candidate_projection("down_proj", activated, weights, scales)

    def incumbent_rank_body(rank: int) -> None:
        gemm = torch.ops._xpu_C.fp8_gemm_w8a16
        gemm(hidden, weights["qkv_proj"][rank], scales["qkv_proj"][rank], None)
        attn_part = attention_input[:, rank * 2304 : (rank + 1) * 2304].contiguous()
        gemm(attn_part, weights["o_proj"][rank], scales["o_proj"][rank], None)
        gate = gemm(
            hidden,
            weights["gate_proj"][rank],
            scales["gate_proj"][rank],
            None,
        )
        up = gemm(
            hidden,
            weights["up_proj"][rank],
            scales["up_proj"][rank],
            None,
        )
        activated = torch.nn.functional.silu(gate) * up
        gemm(
            activated,
            weights["down_proj"][rank],
            scales["down_proj"][rank],
            None,
        )

    candidate_timing = _time_ms(
        candidate_body,
        warmups=args.warmups,
        samples=args.samples,
    )
    incumbent_rank_timing = {
        str(rank): _time_ms(
            lambda rank=rank: incumbent_rank_body(rank),
            warmups=args.warmups,
            samples=args.samples,
        )
        for rank in range(4)
    }
    incumbent_max_median = max(
        record["median_ms"] for record in incumbent_rank_timing.values()
    )
    extra_projection_ms = candidate_timing["median_ms"] - incumbent_max_median
    output = {
        "schema": "laguna-dflash-local-tp4-projection-gate-v1",
        "status": "PASS" if all(parity.values()) else "FAIL",
        "scope": "one-layer real-weight projections; attention and TP collectives omitted",
        "authorizes_endpoint": False,
        "checkpoint": str(args.checkpoint),
        "checkpoint_sha256": _sha256(args.checkpoint),
        "vllm_commit": _vllm_commit(),
        "device": str(torch.xpu.get_device_name(0)),
        "rows": args.rows,
        "warmups": args.warmups,
        "samples": args.samples,
        "raw_parity": parity,
        "candidate_projection_body": candidate_timing,
        "incumbent_rank_projection_body": incumbent_rank_timing,
        "incumbent_max_rank_median_ms": incumbent_max_median,
        "candidate_extra_projection_ms_per_layer": extra_projection_ms,
        "six_layer_extra_projection_ms": extra_projection_ms * 6,
        "component_net_saving_gate_ms": 1.4,
        "next_gate": "TP4 complete draft timing including collectives and attention",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
