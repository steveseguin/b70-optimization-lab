#!/usr/bin/env python3
"""Qualify the exact staged HC gate mix under one-B70 XPU graph replay.

This is a component microgate, never an endpoint or throughput claim.  It
captures one target-token cycle (97 production-shape calls) for the unchanged
Torch authority and the experiment-local staged candidate, then requires exact
changing-input parity before evaluating a C-A-A-C timing bracket.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics
import time
from typing import Any, Callable

import torch


CORE_PATH = Path(__file__).with_name("hc_gate_mix_exact_staged.py")
CALLS_PER_TOKEN = 97
EXACT_REPLAYS = 100
TIMING_WARMUPS = 10
TIMING_BATCHES = 9
ITERATIONS_PER_BATCH = 50


def load_core() -> Any:
    spec = importlib.util.spec_from_file_location("q38_hc_gate_mix_exact", CORE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import candidate core: {CORE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_inputs(core: Any, seed: int, replay: int) -> tuple[torch.Tensor, torch.Tensor]:
    generator = torch.Generator(device="cpu").manual_seed(seed * 1000 + replay)
    scale = 0.125 + (replay % 17) / 8
    x = (
        torch.randn(
            (CALLS_PER_TOKEN, 1, core.HYPER_HIDDEN_SIZE),
            generator=generator,
            dtype=torch.bfloat16,
        )
        * scale
    ).contiguous()
    gate = (
        torch.randn(
            (CALLS_PER_TOKEN, 1, core.HYPER_HIDDEN_SIZE),
            generator=generator,
            dtype=torch.bfloat16,
        )
        * scale
    ).contiguous()
    return x, gate


def cycle(
    operation: Callable[[torch.Tensor, torch.Tensor], torch.Tensor],
    x: torch.Tensor,
    gate: torch.Tensor,
) -> list[torch.Tensor]:
    return [operation(x[index], gate[index]) for index in range(CALLS_PER_TOKEN)]


def series_sha256(values: list[torch.Tensor]) -> str:
    digest = hashlib.sha256()
    for tensor in values:
        digest.update(
            tensor.detach().contiguous().view(torch.uint8).cpu().numpy().tobytes()
        )
    return digest.hexdigest()


def assert_exact(
    actual: list[torch.Tensor], expected: list[torch.Tensor], label: str
) -> None:
    if len(actual) != CALLS_PER_TOKEN or len(expected) != CALLS_PER_TOKEN:
        raise AssertionError(f"{label}: incomplete 97-call cycle")
    for index, (left, right) in enumerate(zip(actual, expected)):
        left_bytes = left.detach().contiguous().view(torch.uint8).cpu()
        right_bytes = right.detach().contiguous().view(torch.uint8).cpu()
        if not torch.equal(left_bytes, right_bytes):
            maximum = (left.float() - right.float()).abs().max().item()
            raise AssertionError(
                f"{label}: output differs at call {index}; max_abs={maximum}"
            )


def capture_cycle(
    operation: Callable[[torch.Tensor, torch.Tensor], torch.Tensor],
    x: torch.Tensor,
    gate: torch.Tensor,
) -> tuple[torch.xpu.XPUGraph, list[torch.Tensor]]:
    graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(graph):
        outputs = cycle(operation, x, gate)
    torch.xpu.synchronize()
    return graph, outputs


def timed_graph(graph: torch.xpu.XPUGraph) -> dict[str, Any]:
    for _ in range(TIMING_WARMUPS):
        graph.replay()
    torch.xpu.synchronize()
    samples: list[float] = []
    for _ in range(TIMING_BATCHES):
        started = time.perf_counter_ns()
        for _ in range(ITERATIONS_PER_BATCH):
            graph.replay()
        torch.xpu.synchronize()
        samples.append((time.perf_counter_ns() - started) / ITERATIONS_PER_BATCH / 1000)
    return {"median_us": statistics.median(samples), "samples_us": samples}


def main() -> None:
    core = load_core()
    if not torch.xpu.is_available() or torch.xpu.device_count() != 1:
        raise RuntimeError("selector must expose exactly one XPU")
    if torch.is_grad_enabled():
        torch.set_grad_enabled(False)

    seed = 20260901
    x_cpu, gate_cpu = make_inputs(core, seed, 0)
    x = x_cpu.to("xpu")
    gate = gate_cpu.to("xpu")
    x_before = x.clone()
    gate_before = gate.clone()

    control_graph, control_outputs = capture_cycle(
        core.torch_authority_hc_gate_mix, x, gate
    )
    candidate_graph, candidate_outputs = capture_cycle(
        core.exact_staged_hc_gate_mix, x, gate
    )

    hashes: list[str] = []
    for replay in range(EXACT_REPLAYS):
        replay_x, replay_gate = make_inputs(core, seed, replay)
        x.copy_(replay_x)
        gate.copy_(replay_gate)
        eager_authority = cycle(core.torch_authority_hc_gate_mix, x, gate)
        eager_candidate = cycle(core.exact_staged_hc_gate_mix, x, gate)
        assert_exact(eager_candidate, eager_authority, "eager candidate")
        control_graph.replay()
        candidate_graph.replay()
        torch.xpu.synchronize()
        assert_exact(control_outputs, eager_authority, "control graph")
        assert_exact(candidate_outputs, eager_authority, "candidate graph")
        hashes.append(series_sha256(candidate_outputs))
    if len(set(hashes)) != EXACT_REPLAYS:
        raise AssertionError("changing-input graph hashes are not unique")

    # Restore the capture input and prove neither implementation mutates it.
    x.copy_(x_before)
    gate.copy_(gate_before)
    control_graph.replay()
    candidate_graph.replay()
    torch.xpu.synchronize()
    if not torch.equal(
        x.contiguous().view(torch.uint8), x_before.contiguous().view(torch.uint8)
    ) or not torch.equal(
        gate.contiguous().view(torch.uint8), gate_before.contiguous().view(torch.uint8)
    ):
        raise AssertionError("gate-mix operation mutated an input")

    c1 = timed_graph(control_graph)
    a1 = timed_graph(candidate_graph)
    a2 = timed_graph(candidate_graph)
    c2 = timed_graph(control_graph)
    control_center = statistics.median([c1["median_us"], c2["median_us"]])
    candidate_center = statistics.median([a1["median_us"], a2["median_us"]])
    control_drift = abs(c2["median_us"] - c1["median_us"]) / control_center * 100
    improvement = (control_center - candidate_center) / control_center * 100
    timing_passed = control_drift <= 2.0 and improvement >= 3.0
    if not all(
        math.isfinite(value) and value > 0
        for value in (control_center, candidate_center)
    ):
        raise AssertionError("timing result is invalid")

    result = {
        "schema_version": 1,
        "status": "passed" if timing_passed else "timing_gate_failed",
        "classification": "qwen38_hc_gate_mix_exact_staged_xpu_graph_component",
        "scope": {
            "shape": [1, core.HYPER_HIDDEN_SIZE],
            "hc_count": core.HC_COUNT,
            "calls_per_target_token": CALLS_PER_TOKEN,
            "dtype": "bfloat16",
        },
        "correctness": {
            "exact_replays": EXACT_REPLAYS,
            "unique_hashes": len(set(hashes)),
            "eager_exact": True,
            "graph_exact": True,
            "inputs_unchanged": True,
            "hash_series_sha256": hashlib.sha256(
                json.dumps(hashes, separators=(",", ":")).encode()
            ).hexdigest(),
        },
        "timing": {
            "order": ["control", "candidate", "candidate", "control"],
            "control_1": c1,
            "candidate_1": a1,
            "candidate_2": a2,
            "control_2": c2,
            "control_center_us": control_center,
            "candidate_center_us": candidate_center,
            "control_drift_percent": control_drift,
            "improvement_percent": improvement,
            "required_control_drift_max_percent": 2.0,
            "required_improvement_min_percent": 3.0,
            "passed": timing_passed,
        },
        "endpoint_authorized": False,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    if not timing_passed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
