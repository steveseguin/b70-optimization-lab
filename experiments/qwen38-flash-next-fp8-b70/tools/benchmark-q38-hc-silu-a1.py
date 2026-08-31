#!/usr/bin/env python3
"""Exactness, dispatch, launch-count, and timing gate for native Qwen HC SiLU."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import time
from pathlib import Path

import torch


NATIVE_ENV = "VLLM_XPU_QWEN4_EXP_HC_SILU"
HC_COUNT = 4
WIDTH = 320
ROW_STRIDE = 336
WINDOW_CALLS = 97
WARMUP_WINDOWS = 8
TIMING_CYCLES = 60


def fail(message: str) -> None:
    raise RuntimeError(message)


def tensor_bits(tensor: torch.Tensor) -> torch.Tensor:
    return tensor.detach().to("cpu").contiguous().view(torch.uint16)


def tensor_hash(tensor: torch.Tensor) -> str:
    return hashlib.sha256(tensor_bits(tensor).numpy().tobytes()).hexdigest()


def is_nan_bits(bits: torch.Tensor) -> torch.Tensor:
    return ((bits & 0x7F80) == 0x7F80) & ((bits & 0x007F) != 0)


def require_frozen_parity(
    reference: torch.Tensor,
    candidate: torch.Tensor,
    *,
    label: str,
) -> dict[str, int]:
    reference_bits = tensor_bits(reference).flatten()
    candidate_bits = tensor_bits(candidate).flatten()
    if reference_bits.shape != candidate_bits.shape:
        fail(f"{label}: output shapes differ")
    reference_nan = is_nan_bits(reference_bits)
    candidate_nan = is_nan_bits(candidate_bits)
    if not torch.equal(reference_nan, candidate_nan):
        fail(f"{label}: NaN classification differs")
    exact_mask = ~reference_nan
    mismatch = reference_bits[exact_mask] != candidate_bits[exact_mask]
    mismatch_count = int(mismatch.sum().item())
    if mismatch_count:
        fail(f"{label}: {mismatch_count} non-NaN BF16 bit patterns differ")
    return {
        "elements": reference_bits.numel(),
        "exact_non_nan": int(exact_mask.sum().item()),
        "nan_class_only": int(reference_nan.sum().item()),
    }


def set_candidate(enabled: bool) -> None:
    if enabled:
        os.environ[NATIVE_ENV] = "1"
    else:
        os.environ.pop(NATIVE_ENV, None)


def production_input(values: torch.Tensor, device: torch.device) -> torch.Tensor:
    if values.numel() != WIDTH:
        fail(f"production input needs {WIDTH} elements")
    storage = torch.empty((1, ROW_STRIDE), dtype=torch.bfloat16, device=device)
    view = storage[:, :WIDTH]
    view.copy_(values.reshape(1, WIDTH).to(device=device, dtype=torch.bfloat16))
    if tuple(view.shape) != (1, WIDTH) or tuple(view.stride()) != (ROW_STRIDE, 1):
        fail(f"production stride drifted: shape={view.shape}, stride={view.stride()}")
    return view


def exhaustive_bf16_gate(hc_module, device: torch.device) -> dict[str, object]:
    raw = torch.arange(65536, dtype=torch.int32).to(torch.uint16)
    values = raw.view(torch.bfloat16)
    totals = {"elements": 0, "exact_non_nan": 0, "nan_class_only": 0}
    calls = 0
    input_hashes: list[str] = []
    output_hashes: list[str] = []
    for start in range(0, raw.numel(), WIDTH):
        count = min(WIDTH, raw.numel() - start)
        padded = torch.zeros(WIDTH, dtype=torch.bfloat16)
        padded[:count].copy_(values[start : start + count])
        x = production_input(padded, device)
        before = tensor_hash(x)
        reference = hc_module._hc_silu_torch(x, HC_COUNT)
        set_candidate(True)
        candidate = hc_module._hc_silu(x, HC_COUNT)
        torch.xpu.synchronize(device)
        stats = require_frozen_parity(
            reference[:, :count], candidate[:, :count], label=f"bf16-{start}"
        )
        after = tensor_hash(x)
        if before != after:
            fail(f"bf16-{start}: native call mutated input")
        for key in totals:
            totals[key] += stats[key]
        calls += 1
        input_hashes.append(before)
        output_hashes.append(tensor_hash(candidate[:, :count]))
    if calls != 205 or totals["elements"] != 65536:
        fail(f"exhaustive coverage drifted: calls={calls}, totals={totals}")
    return {
        "calls": calls,
        **totals,
        "input_sequence_sha256": hashlib.sha256(
            "\n".join(input_hashes).encode()
        ).hexdigest(),
        "output_sequence_sha256": hashlib.sha256(
            "\n".join(output_hashes).encode()
        ).hexdigest(),
    }


def dispatch_and_repeat_gate(hc_module, device: torch.device) -> dict[str, object]:
    generator = torch.Generator(device="cpu").manual_seed(20260831)
    finite = torch.randn(WIDTH, generator=generator, dtype=torch.float32).to(
        torch.bfloat16
    )
    x = production_input(finite, device)
    original_hash = tensor_hash(x)

    set_candidate(False)
    routed_control = hc_module._hc_silu(x, HC_COUNT)
    direct_control = hc_module._hc_silu_torch(x, HC_COUNT)
    torch.xpu.synchronize(device)
    require_frozen_parity(direct_control, routed_control, label="selector-off")

    fallback_cases = {
        "shape": torch.randn((2, WIDTH), dtype=torch.bfloat16, device=device),
        "dtype": torch.randn((1, WIDTH), dtype=torch.float16, device=device),
        "stride": torch.randn((1, WIDTH * 2), dtype=torch.bfloat16, device=device)[
            :, ::2
        ],
    }
    set_candidate(True)
    fallback_hashes: dict[str, str] = {}
    for name, value in fallback_cases.items():
        reference = hc_module._hc_silu_torch(value, HC_COUNT)
        routed = hc_module._hc_silu(value, HC_COUNT)
        torch.xpu.synchronize(device)
        require_frozen_parity(reference, routed, label=f"fallback-{name}")
        fallback_hashes[name] = tensor_hash(routed)
    reference_hc2 = hc_module._hc_silu_torch(x, 2)
    routed_hc2 = hc_module._hc_silu(x, 2)
    torch.xpu.synchronize(device)
    require_frozen_parity(reference_hc2, routed_hc2, label="fallback-hc-count")
    fallback_hashes["hc_count"] = tensor_hash(routed_hc2)

    expected = hc_module._hc_silu_torch(x, HC_COUNT)
    expected_hash = tensor_hash(expected)
    repeat_hashes: list[str] = []
    for _ in range(100):
        repeat_hashes.append(tensor_hash(hc_module._hc_silu(x, HC_COUNT)))
    torch.xpu.synchronize(device)
    if set(repeat_hashes) != {expected_hash}:
        fail("candidate repeat hashes differ from the reference")
    if tensor_hash(x) != original_hash:
        fail("dispatch/repeat gate mutated the production-stride input")
    return {
        "selector_off_sha256": tensor_hash(routed_control),
        "candidate_sha256": expected_hash,
        "repeat_count": len(repeat_hashes),
        "repeat_unique_sha256": sorted(set(repeat_hashes)),
        "fallback_sha256": fallback_hashes,
        "input_sha256": original_hash,
    }


def kernel_events(trace_path: Path) -> list[dict[str, object]]:
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    events = []
    for event in trace.get("traceEvents", []):
        category = str(event.get("cat", "")).lower()
        args = event.get("args", {})
        task_type = str(args.get("Task Type", "")).lower()
        if "kernel" in category or task_type == "kernel":
            events.append(event)
    return events


def profile_one(hc_module, x: torch.Tensor, candidate: bool, path: Path) -> dict:
    set_candidate(candidate)
    with torch.profiler.profile(
        activities=[torch.profiler.ProfilerActivity.XPU],
        record_shapes=True,
    ) as profile:
        output = hc_module._hc_silu(x, HC_COUNT)
        torch.xpu.synchronize(x.device)
    profile.export_chrome_trace(str(path))
    events = kernel_events(path)
    names = [str(event.get("name", "")) for event in events]
    expected_count = 1 if candidate else 5
    if len(events) != expected_count:
        fail(
            f"{'candidate' if candidate else 'control'} kernel count "
            f"{len(events)} != {expected_count}: {names}"
        )
    if candidate and not any("qwen4_exp_hc_silu_bf16_kernel" in name for name in names):
        fail(f"candidate native kernel name is absent: {names}")
    if candidate and any("barrier" in name.lower() for name in names):
        fail(f"candidate trace contains a barrier kernel: {names}")
    return {
        "trace": str(path),
        "kernel_count": len(events),
        "kernel_names": names,
        "output_sha256": tensor_hash(output),
    }


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = math.ceil(fraction * len(ordered)) - 1
    return ordered[max(0, min(index, len(ordered) - 1))]


def timed_window(hc_module, x: torch.Tensor, candidate: bool) -> tuple[float, str]:
    set_candidate(candidate)
    start = torch.xpu.Event(enable_timing=True)
    end = torch.xpu.Event(enable_timing=True)
    start.record()
    output = None
    for _ in range(WINDOW_CALLS):
        output = hc_module._hc_silu(x, HC_COUNT)
    end.record()
    torch.xpu.synchronize(x.device)
    if output is None:
        fail("timed window produced no output")
    return float(start.elapsed_time(end)), tensor_hash(output)


def timing_gate(hc_module, device: torch.device) -> dict[str, object]:
    values = torch.linspace(-8.0, 8.0, WIDTH, dtype=torch.float32).to(torch.bfloat16)
    x = production_input(values, device)
    for _ in range(WARMUP_WINDOWS):
        timed_window(hc_module, x, False)
        timed_window(hc_module, x, True)

    control_first: list[float] = []
    candidate_first: list[float] = []
    candidate_second: list[float] = []
    control_second: list[float] = []
    hashes: set[str] = set()
    rows: list[dict[str, float | int | str]] = []
    for cycle in range(TIMING_CYCLES):
        row: dict[str, float | int | str] = {"cycle": cycle}
        for label, enabled, bucket in (
            ("control_1", False, control_first),
            ("candidate_1", True, candidate_first),
            ("candidate_2", True, candidate_second),
            ("control_2", False, control_second),
        ):
            elapsed_ms, output_hash = timed_window(hc_module, x, enabled)
            bucket.append(elapsed_ms)
            hashes.add(output_hash)
            row[f"{label}_ms"] = elapsed_ms
            row[f"{label}_sha256"] = output_hash
        rows.append(row)
    if len(hashes) != 1:
        fail(f"timing arms produced different outputs: {sorted(hashes)}")

    controls = control_first + control_second
    candidates = candidate_first + candidate_second
    median_saving = 1.0 - statistics.median(candidates) / statistics.median(controls)
    p90_saving = percentile(controls, 0.90) - percentile(candidates, 0.90)
    paired_p10 = []
    for control, candidate in (
        (control_first, candidate_first),
        (control_second, candidate_second),
    ):
        paired = [c - a for c, a in zip(control, candidate, strict=True)]
        paired_p10.append(percentile(paired, 0.10))
    passed = median_saving >= 0.30 and p90_saving >= 0.0 and min(paired_p10) >= 0.0
    result = {
        "order": "C-A-A-C",
        "cycles": TIMING_CYCLES,
        "calls_per_window": WINDOW_CALLS,
        "warmup_windows_per_arm": WARMUP_WINDOWS,
        "control_median_ms": statistics.median(controls),
        "candidate_median_ms": statistics.median(candidates),
        "control_p90_ms": percentile(controls, 0.90),
        "candidate_p90_ms": percentile(candidates, 0.90),
        "median_saving_fraction": median_saving,
        "p90_saving_ms": p90_saving,
        "paired_saving_p10_ms": paired_p10,
        "required_median_saving_fraction": 0.30,
        "required_nonnegative_aggregate_p90": True,
        "required_nonnegative_paired_p10": True,
        "output_sha256": next(iter(hashes)),
        "rows": rows,
        "passed": passed,
    }
    if not passed:
        fail(f"timing gate did not pass: {result}")
    return result


def atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    if path.exists():
        fail(f"refusing to overwrite {path}")
    temporary = path.with_suffix(path.suffix + ".tmp")
    if temporary.exists():
        fail(f"refusing to overwrite {temporary}")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--candidate-dso", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        fail(f"refusing to overwrite {args.output_dir}")
    args.output_dir.mkdir(parents=True)

    torch.ops.load_library(str(args.candidate_dso))
    if not hasattr(torch.ops._xpu_C, "qwen4_exp_hc_silu"):
        fail("candidate DSO did not register qwen4_exp_hc_silu")
    from vllm.models.qwen4_exp.amd.ops import hc as hc_module

    if not torch.xpu.is_available() or torch.xpu.device_count() != 1:
        fail(f"expected exactly one visible XPU, got {torch.xpu.device_count()}")
    device = torch.device("xpu:0")
    torch.xpu.set_device(device)

    started = time.time()
    exhaustive = exhaustive_bf16_gate(hc_module, device)
    dispatch = dispatch_and_repeat_gate(hc_module, device)
    profile_control = profile_one(
        hc_module,
        production_input(torch.zeros(WIDTH), device),
        False,
        args.output_dir / "control-trace.json",
    )
    profile_candidate = profile_one(
        hc_module,
        production_input(torch.zeros(WIDTH), device),
        True,
        args.output_dir / "candidate-trace.json",
    )
    if profile_control["output_sha256"] != profile_candidate["output_sha256"]:
        fail("profile outputs differ")
    timing = timing_gate(hc_module, device)
    torch.xpu.synchronize(device)
    result: dict[str, object] = {
        "schema_version": 1,
        "status": "passed",
        "classification": "component_pass_endpoint_candidate",
        "scope": "Qwen3.8 Flash-Next exact decode-shape HC SiLU only",
        "device": str(torch.xpu.get_device_name(device)),
        "torch_version": torch.__version__,
        "candidate_dso": str(args.candidate_dso),
        "candidate_dso_sha256": hashlib.sha256(
            args.candidate_dso.read_bytes()
        ).hexdigest(),
        "exhaustive_bf16": exhaustive,
        "dispatch_and_repeat": dispatch,
        "profiles": {"control": profile_control, "candidate": profile_candidate},
        "timing": timing,
        "elapsed_s": time.time() - started,
        "protected_endpoint_results_changed": False,
        "endpoint_authorized": False,
    }
    atomic_write_json(args.output_dir / "summary.json", result)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
