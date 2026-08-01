#!/usr/bin/env python3
"""Exactness and timing gate for Laguna's M12 shared elementwise ops."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from dataclasses import dataclass
from pathlib import Path

import torch
import torch.nn.functional as F


ROWS = 12
ACT_WIDTH = 256
HIDDEN_WIDTH = 3072
LAYERS = 48
RANDOM_EPOCHS = 32
TIMING_BLOCKS = 15
TIMING_CYCLES = 20
WARMUP_CYCLES = 20


def raw_bytes(tensor: torch.Tensor) -> bytes:
    return tensor.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes()


def require_equal(label: str, expected: torch.Tensor, observed: torch.Tensor) -> None:
    expected_bits = expected.contiguous().view(torch.int16)
    observed_bits = observed.contiguous().view(torch.int16)
    mismatches = expected_bits != observed_bits
    count = int(mismatches.sum().item())
    if count:
        first = tuple(int(x) for x in mismatches.nonzero()[0].tolist())
        raise AssertionError(f"{label}: {count} raw BF16 mismatches; first={first}")


def finite_bf16() -> torch.Tensor:
    bits = torch.arange(65536, dtype=torch.int32).to(torch.int16)
    values = bits.view(torch.bfloat16)
    values = values[torch.isfinite(values)]
    if values.numel() != 65280:
        raise AssertionError("finite BF16 enumeration drifted")
    return values.xpu()


def pad(values: torch.Tensor, multiple: int) -> torch.Tensor:
    count = (-values.numel()) % multiple
    if not count:
        return values
    return torch.cat((values, torch.zeros(count, dtype=values.dtype, device="xpu")))


def incumbent_activation(gate: torch.Tensor, up: torch.Tensor) -> torch.Tensor:
    return F.silu(gate) * up


def incumbent_scale_add(
    shared: torch.Tensor, routed: torch.Tensor
) -> torch.Tensor:
    scaled = routed.clone()
    scaled.mul_(2.5)
    return shared + scaled


def candidate_activation(
    out: torch.Tensor, gate: torch.Tensor, up: torch.Tensor
) -> torch.Tensor:
    torch.ops._C.laguna_m12_silu_mul(out, gate, up)
    return out


def candidate_scale_add(
    out: torch.Tensor, shared: torch.Tensor, routed: torch.Tensor
) -> torch.Tensor:
    torch.ops._C.laguna_m12_scale_add(out, shared, routed)
    return out


def exhaustive_activation() -> dict[str, object]:
    finite = finite_bf16()
    full = pad(finite, ROWS * ACT_WIDTH)
    reverse = pad(finite.flip(0), ROWS * ACT_WIDTH)
    positions = torch.arange(full.numel(), device="xpu")
    modes = {
        "ones": torch.ones_like(full),
        "reversed": reverse,
        "signed_zero": torch.where(
            positions % 2 == 0, torch.zeros_like(full), -torch.zeros_like(full)
        ),
    }
    batches = full.view(-1, ROWS, ACT_WIDTH)
    hashes = {}
    for name, up_flat in modes.items():
        digest = hashlib.sha256()
        for index, (gate, up) in enumerate(
            zip(batches, up_flat.view_as(batches), strict=True)
        ):
            expected = incumbent_activation(gate, up)
            observed = torch.empty_like(gate)
            repeated = torch.empty_like(gate)
            candidate_activation(observed, gate, up)
            candidate_activation(repeated, gate, up)
            require_equal(f"activation-{name}-{index}", expected, observed)
            require_equal(f"activation-repeat-{name}-{index}", observed, repeated)
            digest.update(raw_bytes(observed))
        hashes[name] = digest.hexdigest()
    midpoint = torch.tensor([[5.9375]], dtype=torch.bfloat16, device="xpu")
    if int(F.silu(midpoint).view(torch.int16).item()) & 0xFFFF != 0x40BD:
        raise AssertionError("incumbent SiLU midpoint identity drifted")
    return {"finite_values": 65280, "modes": hashes, "passed": True}


def exhaustive_scale_add() -> dict[str, object]:
    finite = finite_bf16()
    full = pad(finite, ROWS * HIDDEN_WIDTH)
    reverse = pad(finite.flip(0), ROWS * HIDDEN_WIDTH)
    positions = torch.arange(full.numel(), device="xpu")
    modes = {
        "zeros": torch.zeros_like(full),
        "ones": torch.ones_like(full),
        "reversed": reverse,
        "signed_zero": torch.where(
            positions % 2 == 0, torch.zeros_like(full), -torch.zeros_like(full)
        ),
    }
    batches = full.view(-1, ROWS, HIDDEN_WIDTH)
    hashes = {}
    for name, shared_flat in modes.items():
        digest = hashlib.sha256()
        for index, (routed, shared) in enumerate(
            zip(batches, shared_flat.view_as(batches), strict=True)
        ):
            expected = incumbent_scale_add(shared, routed)
            observed = torch.empty_like(shared)
            repeated = torch.empty_like(shared)
            candidate_scale_add(observed, shared, routed)
            candidate_scale_add(repeated, shared, routed)
            require_equal(f"scale-add-{name}-{index}", expected, observed)
            require_equal(f"scale-add-repeat-{name}-{index}", observed, repeated)
            digest.update(raw_bytes(observed))
        hashes[name] = digest.hexdigest()
    return {"finite_values": 65280, "modes": hashes, "passed": True}


def random_exactness() -> dict[str, object]:
    activation_hashes = set()
    scale_hashes = set()
    for epoch in range(RANDOM_EPOCHS):
        generator = torch.Generator(device="cpu").manual_seed(0x512000 + epoch)
        gate = torch.randn((ROWS, ACT_WIDTH), generator=generator).to(
            torch.bfloat16
        ).xpu()
        up = torch.randn((ROWS, ACT_WIDTH), generator=generator).to(
            torch.bfloat16
        ).xpu()
        gate[0, 0] = 5.9375
        act_out = torch.empty_like(gate)
        expected_act = incumbent_activation(gate, up)
        candidate_activation(act_out, gate, up)
        require_equal(f"random-activation-{epoch}", expected_act, act_out)
        activation_hashes.add(hashlib.sha256(raw_bytes(act_out)).hexdigest())

        shared = torch.randn((ROWS, HIDDEN_WIDTH), generator=generator).to(
            torch.bfloat16
        ).xpu()
        routed = torch.randn((ROWS, HIDDEN_WIDTH), generator=generator).to(
            torch.bfloat16
        ).xpu()
        scale_out = torch.empty_like(shared)
        expected_scale = incumbent_scale_add(shared, routed)
        candidate_scale_add(scale_out, shared, routed)
        require_equal(f"random-scale-add-{epoch}", expected_scale, scale_out)
        scale_hashes.add(hashlib.sha256(raw_bytes(scale_out)).hexdigest())
    return {
        "epochs": RANDOM_EPOCHS,
        "activation_unique_outputs": len(activation_hashes),
        "scale_add_unique_outputs": len(scale_hashes),
        "passed": len(activation_hashes) == len(scale_hashes) == RANDOM_EPOCHS,
    }


@dataclass
class Fixture:
    gate: torch.Tensor
    up: torch.Tensor
    shared: torch.Tensor
    routed: torch.Tensor
    silu: torch.Tensor
    act_control: torch.Tensor
    act_candidate: torch.Tensor
    scaled: torch.Tensor
    scale_control: torch.Tensor
    scale_candidate: torch.Tensor


def make_fixture(seed: int) -> Fixture:
    torch.manual_seed(seed)
    gate = torch.randn((ROWS, ACT_WIDTH), dtype=torch.bfloat16, device="xpu")
    up = torch.randn_like(gate)
    shared = torch.randn((ROWS, HIDDEN_WIDTH), dtype=torch.bfloat16, device="xpu")
    routed = torch.randn_like(shared)
    return Fixture(
        gate, up, shared, routed,
        torch.empty_like(gate), torch.empty_like(gate), torch.empty_like(gate),
        torch.empty_like(routed), torch.empty_like(shared), torch.empty_like(shared),
    )


def activation_control(f: Fixture) -> None:
    torch.ops.aten.silu.out(f.gate, out=f.silu)
    torch.mul(f.silu, f.up, out=f.act_control)


def activation_candidate(f: Fixture) -> None:
    candidate_activation(f.act_candidate, f.gate, f.up)


def scale_control(f: Fixture) -> None:
    torch.mul(f.routed, 2.5, out=f.scaled)
    torch.add(f.shared, f.scaled, out=f.scale_control)


def scale_candidate(f: Fixture) -> None:
    candidate_scale_add(f.scale_candidate, f.shared, f.routed)


def combined_control(f: Fixture) -> None:
    activation_control(f)
    scale_control(f)


def combined_candidate(f: Fixture) -> None:
    activation_candidate(f)
    scale_candidate(f)


def time_arm(call, fixture: Fixture) -> float:
    torch.xpu.synchronize()
    start = time.perf_counter()
    for _ in range(TIMING_CYCLES * LAYERS):
        call(fixture)
    torch.xpu.synchronize()
    return (time.perf_counter() - start) * 1000.0 / TIMING_CYCLES


def time_family(control, candidate) -> dict[str, object]:
    blocks = []
    for index in range(TIMING_BLOCKS):
        fixture = make_fixture(0x512800 + index)
        for call in (control, candidate):
            for _ in range(WARMUP_CYCLES * LAYERS):
                call(fixture)
            torch.xpu.synchronize()
        a1 = time_arm(control, fixture)
        b1 = time_arm(candidate, fixture)
        b2 = time_arm(candidate, fixture)
        a2 = time_arm(control, fixture)
        a = statistics.fmean((a1, a2))
        b = statistics.fmean((b1, b2))
        blocks.append({"A1_ms": a1, "B1_ms": b1, "B2_ms": b2, "A2_ms": a2,
                       "control_ms": a, "candidate_ms": b, "saving_ms": a - b})
    savings = [float(block["saving_ms"]) for block in blocks]
    return {
        "blocks": blocks,
        "wins": sum(value > 0 for value in savings),
        "median_control_ms": statistics.median(
            float(block["control_ms"]) for block in blocks
        ),
        "median_candidate_ms": statistics.median(
            float(block["candidate_ms"]) for block in blocks
        ),
        "median_saving_ms": statistics.median(savings),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    torch.ops.load_library(str(args.library.resolve()))
    for name in ("laguna_m12_silu_mul", "laguna_m12_scale_add"):
        if not hasattr(torch.ops._C, name):
            raise SystemExit(f"missing candidate op: {name}")

    activation = exhaustive_activation()
    scale_add = exhaustive_scale_add()
    random = random_exactness()
    with torch.inference_mode():
        timing = {
            "activation": time_family(activation_control, activation_candidate),
            "scale_add": time_family(scale_control, scale_candidate),
            "combined": time_family(combined_control, combined_candidate),
        }
    post_timing = random_exactness()
    combined_saving = float(timing["combined"]["median_saving_ms"])
    passed = (
        bool(activation["passed"])
        and bool(scale_add["passed"])
        and bool(random["passed"])
        and bool(post_timing["passed"])
        and float(timing["activation"]["median_saving_ms"]) > 0
        and float(timing["scale_add"]["median_saving_ms"]) > 0
        and combined_saving >= 0.50
    )
    report = {
        "schema": "laguna-shared-elementwise-m12-component-v1",
        "library": str(args.library.resolve()),
        "library_sha256": hashlib.sha256(args.library.read_bytes()).hexdigest(),
        "device": torch.xpu.get_device_name(0),
        "protocol": {"rows": ROWS, "layers": LAYERS, "random_epochs": RANDOM_EPOCHS,
                     "timing_blocks": TIMING_BLOCKS, "timing_cycles": TIMING_CYCLES,
                     "warmup_cycles": WARMUP_CYCLES,
                     "control_launches_per_cycle": 4 * LAYERS,
                     "candidate_launches_per_cycle": 2 * LAYERS},
        "activation_exhaustive": activation,
        "scale_add_exhaustive": scale_add,
        "random_exactness": random,
        "timing": timing,
        "post_timing_exactness": post_timing,
        "passed": passed,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"timing": timing, "passed": passed}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
