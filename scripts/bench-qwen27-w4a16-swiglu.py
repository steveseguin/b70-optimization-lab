#!/usr/bin/env python3
"""Gate Qwen27 TP2 W4A16 gate/up + SwiGLU fusion on real weights.

This is a diagnostic kernel microbenchmark, not endpoint throughput and not
LocalMaxxing eligible. It compares the production oneDNN gate/up GEMM,
``_C.silu_and_mul``, and down GEMM with the default-off experimental fused
gate/up-SwiGLU operation. Both paths use the exact rank-local packed weights
from one target layer and are timed eagerly and through XPU graph replay.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Callable


DEFAULT_MODEL = (
    "/mnt/fast-ai/llm-cache/hf/hub/"
    "models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/"
    "f5750c90b3776db658594df5fe8051098226dd8e"
)
DEFAULT_KERNEL_PREFIX = "/home/steve/src/vllm-xpu-kernels"
CANDIDATE_OP = "qwen27_w4a16_gateup_swiglu"
GROUP_SIZE = 128
HIDDEN = 5120
INTER_GLOBAL = 17408


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", default=DEFAULT_MODEL)
    parser.add_argument("--kernel-prefix", default=DEFAULT_KERNEL_PREFIX)
    parser.add_argument("--layer", type=int, default=0)
    parser.add_argument("--tp-rank", type=int, choices=(0, 1), default=0)
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--rows", type=int, default=4)
    parser.add_argument("--warmup", type=int, default=100)
    parser.add_argument("--iterations", type=int, default=2000)
    parser.add_argument("--calls-per-sample", type=int, default=16)
    parser.add_argument("--seed", type=int, default=20260711)
    parser.add_argument("--require-candidate", action="store_true")
    parser.add_argument("--require-graph", action="store_true")
    parser.add_argument("--output-json")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_tensor(model_dir: Path, name: str) -> Any:
    from safetensors import safe_open

    index_path = model_dir / "model.safetensors.index.json"
    index = json.loads(index_path.read_text())
    filename = index["weight_map"][name]
    with safe_open(model_dir / filename, framework="pt", device="cpu") as handle:
        return handle.get_tensor(name), filename


def nt_pack(torch: Any, qweight: Any, device: str) -> Any:
    return qweight.t().contiguous().t().to(device=device)


def load_rank_weights(torch: Any, args: argparse.Namespace) -> dict[str, Any]:
    model_dir = Path(args.model_dir).resolve()
    prefix = f"model.language_model.layers.{args.layer}.mlp"
    tensors: dict[str, Any] = {}
    files: set[str] = set()
    for short, name in (
        ("gate_q", f"{prefix}.gate_proj.qweight"),
        ("gate_s", f"{prefix}.gate_proj.scales"),
        ("up_q", f"{prefix}.up_proj.qweight"),
        ("up_s", f"{prefix}.up_proj.scales"),
        ("down_q", f"{prefix}.down_proj.qweight"),
        ("down_s", f"{prefix}.down_proj.scales"),
    ):
        tensors[short], filename = load_tensor(model_dir, name)
        files.add(filename)

    inter_local = INTER_GLOBAL // 2
    n0 = args.tp_rank * inter_local
    n1 = n0 + inter_local
    gate_q = tensors["gate_q"][:, n0:n1]
    up_q = tensors["up_q"][:, n0:n1]
    gate_s = tensors["gate_s"][:, n0:n1]
    up_s = tensors["up_s"][:, n0:n1]
    merged_q = torch.cat((gate_q, up_q), dim=1)
    merged_s = torch.cat((gate_s, up_s), dim=1).contiguous()

    packed_k_local = tensors["down_q"].shape[0] // 2
    group_k_local = tensors["down_s"].shape[0] // 2
    pk0 = args.tp_rank * packed_k_local
    gk0 = args.tp_rank * group_k_local
    down_q = tensors["down_q"][pk0:pk0 + packed_k_local, :]
    down_s = tensors["down_s"][gk0:gk0 + group_k_local, :].contiguous()

    return {
        "gate_up_q": nt_pack(torch, merged_q, args.device),
        "gate_up_s": merged_s.to(device=args.device),
        "down_q": nt_pack(torch, down_q, args.device),
        "down_s": down_s.to(device=args.device),
        "zp": torch.tensor([8], dtype=torch.int8, device=args.device),
        "source_files": {
            filename: {
                "path": str(model_dir / filename),
                "sha256": sha256(model_dir / filename),
            }
            for filename in sorted(files)
        },
    }


def compare(torch: Any, candidate: Any, reference: Any) -> dict[str, Any]:
    diff = (candidate.float() - reference.float()).abs()
    return {
        "exact": bool(torch.equal(candidate, reference)),
        "max_abs": float(diff.max().cpu().item()),
        "mean_abs": float(diff.mean().cpu().item()),
    }


def event_ms(torch: Any, fn: Callable[[], Any], calls: int) -> float:
    start = torch.xpu.Event(enable_timing=True)
    end = torch.xpu.Event(enable_timing=True)
    start.record()
    for _ in range(calls):
        fn()
    end.record()
    torch.xpu.synchronize()
    return float(start.elapsed_time(end)) / calls


def summarize(values: list[float]) -> dict[str, float | int]:
    return {
        "count": len(values),
        "median_ms": statistics.median(values),
        "mean_ms": statistics.fmean(values),
        "min_ms": min(values),
        "max_ms": max(values),
        "population_stdev_ms": statistics.pstdev(values),
    }


def bench(
    torch: Any,
    fn: Callable[[], Any],
    *,
    warmup: int,
    iterations: int,
    calls: int,
) -> dict[str, float | int]:
    for _ in range(warmup):
        fn()
    torch.xpu.synchronize()
    return summarize([event_ms(torch, fn, calls) for _ in range(iterations)])


def capture_graph(torch: Any, fn: Callable[[], Any]) -> tuple[Any | None, str | None]:
    if not hasattr(torch.xpu, "XPUGraph") or not hasattr(torch.xpu, "graph"):
        return None, "torch.xpu graph API unavailable"
    for _ in range(3):
        fn()
    torch.xpu.synchronize()
    graph = torch.xpu.XPUGraph()
    try:
        with torch.xpu.graph(graph):
            fn()
        torch.xpu.synchronize()
        return graph, None
    except Exception as exc:  # noqa: BLE001 - preserve graph failure as data.
        return None, f"{type(exc).__name__}: {exc}"


def main() -> int:
    args = parse_args()
    kernel_prefix = str(Path(args.kernel_prefix).resolve())
    sys.path.insert(0, kernel_prefix)
    import torch

    extension = importlib.import_module("vllm_xpu_kernels._xpu_C")
    importlib.import_module("vllm_xpu_kernels._C")
    torch.xpu.set_device(torch.device(args.device).index or 0)
    if args.rows != 4:
        raise ValueError("the candidate gate is specialized for --rows 4")
    weights = load_rank_weights(torch, args)
    torch.manual_seed(args.seed)
    x = torch.randn((args.rows, HIDDEN), dtype=torch.float16, device=args.device)
    act_ref = torch.empty(
        (args.rows, INTER_GLOBAL // 2), dtype=torch.float16, device=args.device
    )

    dense = torch.ops._xpu_C.int4_gemm_w4a16

    def control_gate_up() -> Any:
        return dense(
            x,
            weights["gate_up_q"],
            None,
            weights["gate_up_s"],
            weights["zp"],
            GROUP_SIZE,
            None,
        )

    gate_up_cached = control_gate_up()

    def control_silu_cached() -> Any:
        torch.ops._C.silu_and_mul(act_ref, gate_up_cached)
        return act_ref

    def control_act() -> Any:
        gate_up = control_gate_up()
        torch.ops._C.silu_and_mul(act_ref, gate_up)
        return act_ref

    def down(act: Any) -> Any:
        return dense(
            act,
            weights["down_q"],
            None,
            weights["down_s"],
            weights["zp"],
            GROUP_SIZE,
            None,
        )

    def control_pipeline() -> Any:
        return down(control_act())

    candidate_op = getattr(torch.ops._xpu_C, CANDIDATE_OP, None)
    if args.require_candidate and candidate_op is None:
        raise RuntimeError(f"missing torch.ops._xpu_C.{CANDIDATE_OP}")

    payload: dict[str, Any] = {
        "classification": "diagnostic_microbench_not_endpoint_not_localmaxxing",
        "candidate_op": CANDIDATE_OP,
        "model_dir": str(Path(args.model_dir).resolve()),
        "model_files": weights["source_files"],
        "layer": args.layer,
        "tp_rank": args.tp_rank,
        "shape": {
            "rows": args.rows,
            "hidden": HIDDEN,
            "intermediate_local": INTER_GLOBAL // 2,
            "gate_up_output": INTER_GLOBAL,
            "group_size": GROUP_SIZE,
            "dtype": "float16",
        },
        "environment": {
            key: os.environ.get(key)
            for key in (
                "ZE_AFFINITY_MASK",
                "ONEAPI_DEVICE_SELECTOR",
                "LD_LIBRARY_PATH",
                "VLLM_XPU_QWEN27_W4A16_GATEUP_SWIGLU",
            )
        },
        "extension": str(Path(extension.__file__).resolve()),
        "warmup": args.warmup,
        "iterations": args.iterations,
        "calls_per_sample": args.calls_per_sample,
        "control": {},
        "candidate": None,
    }

    control_act()
    control_down = control_pipeline().clone()
    torch.xpu.synchronize()
    payload["control"] = {
        "gate_up_eager": bench(
            torch, control_gate_up, warmup=args.warmup,
            iterations=args.iterations, calls=args.calls_per_sample
        ),
        "silu_cached_eager": bench(
            torch, control_silu_cached, warmup=args.warmup,
            iterations=args.iterations, calls=args.calls_per_sample
        ),
        "down_cached_eager": bench(
            torch, lambda: down(act_ref), warmup=args.warmup,
            iterations=args.iterations, calls=args.calls_per_sample
        ),
        "act_eager": bench(
            torch, control_act, warmup=args.warmup,
            iterations=args.iterations, calls=args.calls_per_sample
        ),
        "pipeline_eager": bench(
            torch, control_pipeline, warmup=args.warmup,
            iterations=args.iterations, calls=args.calls_per_sample
        ),
    }

    control_graph, control_graph_error = capture_graph(torch, control_pipeline)
    if control_graph is not None:
        payload["control"]["pipeline_graph"] = bench(
            torch, control_graph.replay, warmup=args.warmup,
            iterations=args.iterations, calls=args.calls_per_sample
        )
    else:
        payload["control"]["pipeline_graph_error"] = control_graph_error

    if candidate_op is not None:
        def candidate_act() -> Any:
            return candidate_op(
                x,
                weights["gate_up_q"],
                weights["gate_up_s"],
                weights["zp"],
                GROUP_SIZE,
            )

        def candidate_pipeline() -> Any:
            return down(candidate_act())

        candidate_act_out = candidate_act().clone()
        candidate_down = candidate_pipeline().clone()
        torch.xpu.synchronize()
        candidate_data: dict[str, Any] = {
            "parity": {
                "activation": compare(torch, candidate_act_out, act_ref),
                "partial_down": compare(torch, candidate_down, control_down),
            },
            "act_eager": bench(
                torch, candidate_act, warmup=args.warmup,
                iterations=args.iterations, calls=args.calls_per_sample
            ),
            "pipeline_eager": bench(
                torch, candidate_pipeline, warmup=args.warmup,
                iterations=args.iterations, calls=args.calls_per_sample
            ),
        }
        candidate_graph, candidate_graph_error = capture_graph(
            torch, candidate_pipeline
        )
        if candidate_graph is not None:
            candidate_data["pipeline_graph"] = bench(
                torch, candidate_graph.replay, warmup=args.warmup,
                iterations=args.iterations, calls=args.calls_per_sample
            )
        else:
            candidate_data["pipeline_graph_error"] = candidate_graph_error
        payload["candidate"] = candidate_data

    payload["gate"] = {
        "required_exact_activation_and_partial_down": True,
        "required_savings_ms_per_layer": 0.03125,
        "required_projected_savings_ms_per_64_layers": 2.0,
        "graph_required": args.require_graph,
    }
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output_json:
        output = Path(args.output_json)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text)
    print(text, end="")
    if args.require_graph and "pipeline_graph" not in payload["control"]:
        return 2
    return 0


if __name__ == "__main__":
    started = time.perf_counter()
    raise SystemExit(main())
