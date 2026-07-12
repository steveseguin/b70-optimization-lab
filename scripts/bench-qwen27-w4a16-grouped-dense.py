#!/usr/bin/env python3
"""Compare Xe2 grouped W4A16 with dense oneDNN on real Qwen27 weights.

Diagnostic-only microbenchmark. The grouped kernel is invoked as one expert
with four rows, which exercises its DPAS W4A16 M<=4 policy without changing
model math or endpoint code.
"""

from __future__ import annotations

import argparse
import importlib
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Callable


DEFAULT_MODEL = (
    "/mnt/fast-ai/llm-cache/hf/hub/"
    "models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/"
    "f5750c90b3776db658594df5fe8051098226dd8e"
)
DEFAULT_KERNEL_PREFIX = "/home/steve/src/vllm-xpu-kernels"
GROUP_SIZE = 128
HIDDEN = 5120
INTERMEDIATE = 17408


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", default=DEFAULT_MODEL)
    parser.add_argument("--kernel-prefix", default=DEFAULT_KERNEL_PREFIX)
    parser.add_argument("--layer", type=int, default=0)
    parser.add_argument("--tp-rank", type=int, choices=(0, 1), default=0)
    parser.add_argument("--projection", choices=("gate_up", "down"), default="gate_up")
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--rows", type=int, default=4)
    parser.add_argument("--warmup", type=int, default=50)
    parser.add_argument("--iterations", type=int, default=500)
    parser.add_argument("--calls-per-sample", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20260711)
    parser.add_argument("--output-json")
    return parser.parse_args()


def load_tensor(model_dir: Path, name: str) -> Any:
    from safetensors import safe_open

    index = json.loads((model_dir / "model.safetensors.index.json").read_text())
    with safe_open(model_dir / index["weight_map"][name], framework="pt", device="cpu") as handle:
        return handle.get_tensor(name)


def rank_projection(torch: Any, args: argparse.Namespace) -> tuple[Any, Any, int, int]:
    root = Path(args.model_dir)
    prefix = f"model.language_model.layers.{args.layer}.mlp"
    if args.projection == "gate_up":
        gate_q = load_tensor(root, f"{prefix}.gate_proj.qweight")
        gate_s = load_tensor(root, f"{prefix}.gate_proj.scales")
        up_q = load_tensor(root, f"{prefix}.up_proj.qweight")
        up_s = load_tensor(root, f"{prefix}.up_proj.scales")
        local = INTERMEDIATE // 2
        start = args.tp_rank * local
        qweight = torch.cat((gate_q[:, start:start + local], up_q[:, start:start + local]), dim=1)
        scales = torch.cat((gate_s[:, start:start + local], up_s[:, start:start + local]), dim=1)
        return qweight, scales.contiguous(), HIDDEN, INTERMEDIATE

    qweight = load_tensor(root, f"{prefix}.down_proj.qweight")
    scales = load_tensor(root, f"{prefix}.down_proj.scales")
    packed_local = qweight.shape[0] // 2
    group_local = scales.shape[0] // 2
    p0 = args.tp_rank * packed_local
    g0 = args.tp_rank * group_local
    return (
        qweight[p0:p0 + packed_local].contiguous(),
        scales[g0:g0 + group_local].contiguous(),
        INTERMEDIATE // 2,
        HIDDEN,
    )


def autoround_to_grouped(torch: Any, qweight: Any) -> Any:
    """Convert INC INT32 K-major U4 into Xe2 N-major signed-magnitude U4."""
    words = qweight.to(torch.int64)
    shifts = torch.arange(0, 32, 4, dtype=torch.int64)
    u4 = ((words.unsqueeze(-1) >> shifts) & 0xF).permute(1, 0, 2).reshape(qweight.shape[1], -1)
    signed = u4.to(torch.int8) - 8
    signmag = ((signed < 0).to(torch.uint8) << 3) | (signed.view(torch.uint8) & 0x7)
    packed = signmag[:, 0::2] | (signmag[:, 1::2] << 4)
    return packed.unsqueeze(0).contiguous()


def sample_ms(torch: Any, fn: Callable[[], Any], calls: int) -> float:
    start = torch.xpu.Event(enable_timing=True)
    end = torch.xpu.Event(enable_timing=True)
    start.record()
    for _ in range(calls):
        fn()
    end.record()
    torch.xpu.synchronize()
    return float(start.elapsed_time(end)) / calls


def bench(torch: Any, fn: Callable[[], Any], warmup: int, iterations: int, calls: int) -> dict[str, float]:
    for _ in range(warmup):
        fn()
    torch.xpu.synchronize()
    values = [sample_ms(torch, fn, calls) for _ in range(iterations)]
    return {
        "median_ms": statistics.median(values),
        "mean_ms": statistics.fmean(values),
        "min_ms": min(values),
        "max_ms": max(values),
        "stdev_ms": statistics.pstdev(values),
    }


def capture(torch: Any, fn: Callable[[], Any]) -> Any:
    for _ in range(3):
        fn()
    torch.xpu.synchronize()
    graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(graph):
        fn()
    torch.xpu.synchronize()
    return graph


def main() -> int:
    args = parse_args()
    sys.path.insert(0, str(Path(args.kernel_prefix).resolve()))
    import torch

    importlib.import_module("vllm_xpu_kernels._xpu_C")
    torch.xpu.set_device(torch.device(args.device).index or 0)
    torch.manual_seed(args.seed)

    qweight, scales, k, n = rank_projection(torch, args)
    dense_weight = qweight.t().contiguous().t().to(args.device)
    dense_scales = scales.to(args.device)
    grouped_weight = autoround_to_grouped(torch, qweight).to(args.device)
    grouped_scales = scales.t().unsqueeze(0).contiguous().to(args.device)
    zp = torch.tensor([8], dtype=torch.int8, device=args.device)
    rows = torch.tensor([args.rows], dtype=torch.int32, device=args.device)
    x = torch.randn((args.rows, k), dtype=torch.float16, device=args.device)
    grouped_out = torch.empty((args.rows, n), dtype=torch.float16, device=args.device)

    def dense() -> Any:
        return torch.ops._xpu_C.int4_gemm_w4a16(
            x, dense_weight, None, dense_scales, zp, GROUP_SIZE, None
        )

    def grouped() -> Any:
        return torch.ops._xpu_C.cutlass_grouped_gemm_interface(
            x, grouped_weight, grouped_scales, None, grouped_out, rows,
            n, k, 1, True, False,
        )

    reference = dense()
    grouped()
    torch.xpu.synchronize()
    diff = (grouped_out.float() - reference.float()).abs()
    parity = {
        "exact": bool(torch.equal(grouped_out, reference)),
        "max_abs": float(diff.max().cpu()),
        "mean_abs": float(diff.mean().cpu()),
        "rmse": float(torch.sqrt(torch.mean(diff.square())).cpu()),
    }

    dense_graph = capture(torch, dense)
    grouped_graph = capture(torch, grouped)
    result = {
        "classification": "diagnostic_real_weight_kernel_gate",
        "projection": args.projection,
        "shape": {"m": args.rows, "n": n, "k": k, "tp_rank": args.tp_rank},
        "parity": parity,
        "eager": {
            "onednn": bench(torch, dense, args.warmup, args.iterations, args.calls_per_sample),
            "xe2_grouped": bench(torch, grouped, args.warmup, args.iterations, args.calls_per_sample),
        },
        "graph": {
            "onednn": bench(torch, dense_graph.replay, args.warmup, args.iterations, args.calls_per_sample),
            "xe2_grouped": bench(torch, grouped_graph.replay, args.warmup, args.iterations, args.calls_per_sample),
        },
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.output_json:
        Path(args.output_json).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
