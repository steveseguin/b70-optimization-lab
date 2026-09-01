#!/usr/bin/env python3
"""Compare exact real-weight HC-up GEMMs under one-B70 XPU graph replay."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
import time

import torch
import torch.nn.functional as F


CORE = Path(__file__).with_name("benchmark-hc-m1-grouped-gemm.py")


def load_core():
    spec = importlib.util.spec_from_file_location("q38_hc_grouped_core", CORE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import component core: {CORE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tensor_sha256(tensor: torch.Tensor) -> str:
    return hashlib.sha256(
        tensor.detach().contiguous().view(torch.uint8).cpu().numpy().tobytes()
    ).hexdigest()


def timed_replay(graph: torch.xpu.XPUGraph, batches: int, iterations: int) -> float:
    values: list[float] = []
    for _ in range(batches):
        started = time.perf_counter_ns()
        for _ in range(iterations):
            graph.replay()
        torch.xpu.synchronize()
        values.append((time.perf_counter_ns() - started) / iterations / 1000.0)
    return statistics.median(values)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-stage", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--model-revision", required=True)
    parser.add_argument("--seed", type=int, default=20260901)
    parser.add_argument("--exact-replays", type=int, default=100)
    parser.add_argument("--timing-batches", type=int, default=15)
    parser.add_argument("--iterations-per-batch", type=int, default=200)
    args = parser.parse_args()
    if args.exact_replays < 2 or args.timing_batches < 3:
        raise ValueError("insufficient replay count")

    core = load_core()
    core.refuse_active_server()
    library, runtime_manifest = core.verify_runtime_stage(args.runtime_stage)
    core.load_extension(library)
    if not hasattr(torch.ops._xpu_C, "cutlass_grouped_gemm_interface"):
        raise RuntimeError("runtime extension lacks grouped GEMM")
    if not torch.xpu.is_available() or torch.xpu.device_count() != 1:
        raise RuntimeError("selector must expose exactly one XPU")
    if args.model_revision != core.EXPECTED_MODEL_REVISION:
        raise RuntimeError("model revision drifted")

    model = args.model.resolve()
    index_sha256 = core.file_sha256(model / "model.safetensors.index.json")
    config_sha256 = core.file_sha256(model / "config.json")
    if index_sha256 != core.EXPECTED_MODEL_INDEX_SHA256:
        raise RuntimeError("model index drifted")
    if config_sha256 != core.EXPECTED_CONFIG_SHA256:
        raise RuntimeError("model config drifted")

    weight_cpu, logical_weight_cpu, shard, names = core.load_weight(
        model, 0, "up", "linear"
    )
    if core.file_sha256(shard) != core.EXPECTED_SHARD_SHA256[shard.name]:
        raise RuntimeError("checkpoint shard drifted")
    weight = weight_cpu.to("xpu")
    packed = weight.t().contiguous().unsqueeze(0)
    rows = torch.ones((1,), dtype=torch.int32, device="xpu")
    control_input = torch.empty((1, 320), dtype=torch.bfloat16, device="xpu")
    candidate_input = torch.empty_like(control_input)
    candidate_output = torch.empty((1, 10240), dtype=torch.bfloat16, device="xpu")

    generator = torch.Generator(device="cpu").manual_seed(args.seed)
    initial = torch.randn((1, 320), dtype=torch.bfloat16, generator=generator) * 0.01
    control_input.copy_(initial)
    candidate_input.copy_(initial)
    F.linear(control_input, weight)
    torch.ops._xpu_C.cutlass_grouped_gemm_interface(
        candidate_input,
        packed,
        None,
        None,
        candidate_output,
        rows,
        10240,
        320,
        1,
        False,
        False,
    )
    torch.xpu.synchronize()

    control_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(control_graph):
        control_output = F.linear(control_input, weight)
    candidate_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(candidate_graph):
        torch.ops._xpu_C.cutlass_grouped_gemm_interface(
            candidate_input,
            packed,
            None,
            None,
            candidate_output,
            rows,
            10240,
            320,
            1,
            False,
            False,
        )
    torch.xpu.synchronize()

    control_hashes: list[str] = []
    candidate_hashes: list[str] = []
    for _ in range(args.exact_replays):
        value = torch.randn((1, 320), dtype=torch.bfloat16, generator=generator) * 0.01
        authority = F.linear(value.to("xpu"), weight)
        control_input.copy_(value)
        candidate_input.copy_(value)
        control_graph.replay()
        candidate_graph.replay()
        torch.xpu.synchronize()
        if not torch.equal(control_output, authority):
            raise AssertionError("linear graph replay differs from eager authority")
        if not torch.equal(candidate_output, authority):
            raise AssertionError("grouped graph replay differs from eager authority")
        control_hashes.append(tensor_sha256(control_output))
        candidate_hashes.append(tensor_sha256(candidate_output))

    control_us = timed_replay(
        control_graph, args.timing_batches, args.iterations_per_batch
    )
    candidate_us = timed_replay(
        candidate_graph, args.timing_batches, args.iterations_per_batch
    )
    print(
        json.dumps(
            {
                "schema_version": 1,
                "status": "pass",
                "classification": "real_weight_hc_up_xpu_graph_component",
                "model": str(model),
                "model_revision": args.model_revision,
                "model_index_sha256": index_sha256,
                "model_config_sha256": config_sha256,
                "model_shard": shard.name,
                "weight_names": list(names),
                "logical_weight_sha256": tensor_sha256(logical_weight_cpu),
                "runtime_stage": str(args.runtime_stage.resolve()),
                "runtime_manifest": runtime_manifest,
                "runtime_extension_sha256": core.file_sha256(library),
                "shape": {"m": 1, "n": 10240, "k": 320},
                "dtype": "bfloat16",
                "exact_replays": args.exact_replays,
                "unique_control_hashes": len(set(control_hashes)),
                "unique_candidate_hashes": len(set(candidate_hashes)),
                "control_candidate_hash_lists_equal": control_hashes
                == candidate_hashes,
                "control_median_us": control_us,
                "candidate_median_us": candidate_us,
                "latency_reduction_percent": 100.0 * (1.0 - candidate_us / control_us),
                "graph_capture": "separate static XPU graphs with changing inputs",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
