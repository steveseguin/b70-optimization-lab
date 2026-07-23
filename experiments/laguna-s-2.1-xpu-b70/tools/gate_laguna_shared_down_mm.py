#!/usr/bin/env python3
"""Fail-closed component gate for Laguna shared-down native M=8 BF16 MM.

The control is the exact target verifier's stride-zero batch of eight M=1
BMMs.  The candidate changes only the shared-expert down projection core to a
native M=8 MM:

    control:   B=8, M=1, K=256, N=3072 stride-zero BF16 BMM
    candidate: M=8, K=256, N=3072 BF16 MM

Gate/up, the exact shared SiLU/multiply, shared+routed scale/add, and the
fixed-rank reduction boundaries are unchanged.  Synthetic downstream values
are checked here only to prove that an exact down output remains exact through
those literal boundaries; endpoint quality still requires the canonical
teacher.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Callable

import torch


ROWS = 8
K_DIM = 256
N_DIM = 3072
TARGET_LAYERS = 47
MIN_EXACT_EPOCHS = 128
POST_REPLAY_EPOCHS = 32
TIMING_BLOCKS = 31
CYCLES_PER_ARM = 64
WARM_CYCLES = 20
MIN_BLOCK_WINS = 28
MIN_CYCLE_SAVING_MS = 0.15
WEIGHT_SCALE = 0.02
EVICT_ELEMENTS = 33_554_432


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def raw_sha256(*tensors: torch.Tensor) -> str:
    digest = hashlib.sha256()
    for tensor in tensors:
        raw = tensor.detach().cpu().contiguous().view(torch.uint8)
        digest.update(raw.numpy().tobytes())
    return digest.hexdigest()


def cpu_bf16_random(
    shape: tuple[int, ...],
    *,
    seed: int,
    scale: float,
) -> torch.Tensor:
    generator = torch.Generator(device="cpu")
    generator.manual_seed(seed)
    return (
        torch.randn(shape, dtype=torch.float32, generator=generator)
        .mul_(scale)
        .to(torch.bfloat16)
    )


def make_fixture(
    *,
    rank: int,
    epoch: int,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, tuple[torch.Tensor, ...]]:
    # Every physical card receives the same rank-invariant changing corpus.
    # `rank` remains an explicit call argument so the result binds the observed
    # device identity without allowing the numerical fixture to drift by card.
    _ = rank
    seed = 730_000 + epoch * 10
    rows = cpu_bf16_random(
        (ROWS, K_DIM),
        seed=seed,
        scale=0.5,
    ).to("xpu")
    weight = cpu_bf16_random(
        (N_DIM, K_DIM),
        seed=seed + 1,
        scale=WEIGHT_SCALE,
    ).to("xpu")
    routed = cpu_bf16_random(
        (ROWS, N_DIM),
        seed=seed + 2,
        scale=0.1,
    ).to("xpu")
    other_ranks = tuple(
        cpu_bf16_random(
            (ROWS, N_DIM),
            seed=seed + 3 + peer,
            scale=0.1,
        ).to("xpu")
        for peer in range(3)
    )
    return rows, weight, routed, other_ranks


def incumbent_bmm(rows: torch.Tensor, weight: torch.Tensor) -> torch.Tensor:
    require(tuple(rows.shape) == (ROWS, K_DIM), "bad incumbent rows shape")
    require(tuple(weight.shape) == (N_DIM, K_DIM), "bad incumbent weight shape")
    weight_t = weight.t().unsqueeze(0).expand(ROWS, -1, -1)
    require(weight_t.stride(0) == 0, "incumbent lost stride-zero batch")
    output = torch.bmm(rows.unsqueeze(1), weight_t).squeeze(1)
    require(output.dtype == torch.bfloat16, "incumbent output is not BF16")
    return output


def candidate_mm(rows: torch.Tensor, weight: torch.Tensor) -> torch.Tensor:
    require(tuple(rows.shape) == (ROWS, K_DIM), "bad candidate rows shape")
    require(tuple(weight.shape) == (N_DIM, K_DIM), "bad candidate weight shape")
    output = torch.mm(rows, weight.t())
    require(output.dtype == torch.bfloat16, "candidate output is not BF16")
    return output


def downstream(
    down: torch.Tensor,
    routed: torch.Tensor,
    other_ranks: tuple[torch.Tensor, ...],
) -> tuple[torch.Tensor, torch.Tensor]:
    scaled = routed.clone()
    scaled.mul_(2.5)
    combined = down + scaled
    reduced = combined.clone()
    for peer in other_ranks:
        reduced.add_(peer)
    return combined, reduced


def compare_epoch(
    *,
    rank: int,
    epoch: int,
) -> dict[str, object]:
    rows, weight, routed, other_ranks = make_fixture(rank=rank, epoch=epoch)
    inputs_before = raw_sha256(rows, weight, routed, *other_ranks)
    control_down = incumbent_bmm(rows, weight)
    candidate_down = candidate_mm(rows, weight)
    candidate_repeat = candidate_mm(rows, weight)
    control_combined, control_reduced = downstream(
        control_down,
        routed,
        other_ranks,
    )
    candidate_combined, candidate_reduced = downstream(
        candidate_down,
        routed,
        other_ranks,
    )
    inputs_after = raw_sha256(rows, weight, routed, *other_ranks)

    pairs = {
        "down": (control_down, candidate_down),
        "candidate_repeat": (candidate_down, candidate_repeat),
        "shared_routed_add": (control_combined, candidate_combined),
        "fixed_rank_sum": (control_reduced, candidate_reduced),
    }
    equal = {
        name: torch.equal(control, candidate)
        and raw_sha256(control) == raw_sha256(candidate)
        for name, (control, candidate) in pairs.items()
    }
    require(all(equal.values()), f"rank {rank} epoch {epoch}: exactness failure")
    require(
        inputs_before == inputs_after,
        f"rank {rank} epoch {epoch}: candidate mutated an input",
    )
    require(
        bool(torch.isfinite(candidate_reduced).all().item()),
        f"rank {rank} epoch {epoch}: non-finite output",
    )
    return {
        "epoch": epoch,
        "equal": equal,
        "inputs_unchanged": True,
        "fixture_sha256": inputs_before,
        "output_sha256": raw_sha256(
            candidate_down,
            candidate_combined,
            candidate_reduced,
        ),
    }


def make_timing_corpus(
    rank: int,
) -> list[tuple[torch.Tensor, torch.Tensor]]:
    corpus = []
    for layer in range(TARGET_LAYERS):
        rows, weight, _routed, _other_ranks = make_fixture(
            rank=rank,
            epoch=10_000 + layer,
        )
        corpus.append((rows, weight))
    return corpus


def run_cycles(
    call: Callable[[torch.Tensor, torch.Tensor], torch.Tensor],
    corpus: list[tuple[torch.Tensor, torch.Tensor]],
    *,
    cycles: int,
    offset: int,
) -> torch.Tensor:
    output = None
    for cycle in range(cycles):
        start = (offset + cycle) % len(corpus)
        for index in range(len(corpus)):
            rows, weight = corpus[(start + index) % len(corpus)]
            output = call(rows, weight)
    require(output is not None, "timing arm did not execute")
    return output


def timed_arm_ms_per_cycle(
    call: Callable[[torch.Tensor, torch.Tensor], torch.Tensor],
    corpus: list[tuple[torch.Tensor, torch.Tensor]],
    evict: torch.Tensor,
    *,
    offset: int,
) -> float:
    evict.add_(1)
    torch.xpu.synchronize()
    started_ns = time.perf_counter_ns()
    output = run_cycles(
        call,
        corpus,
        cycles=CYCLES_PER_ARM,
        offset=offset,
    )
    torch.xpu.synchronize()
    require(output.numel() == ROWS * N_DIM, "timing output shape drift")
    elapsed_ms = (time.perf_counter_ns() - started_ns) / 1_000_000.0
    return elapsed_ms / CYCLES_PER_ARM


def run_timing(rank: int) -> dict[str, object]:
    corpus = make_timing_corpus(rank)
    evict = torch.zeros(EVICT_ELEMENTS, dtype=torch.float32, device="xpu")
    run_cycles(
        incumbent_bmm,
        corpus,
        cycles=WARM_CYCLES,
        offset=0,
    )
    run_cycles(
        candidate_mm,
        corpus,
        cycles=WARM_CYCLES,
        offset=0,
    )
    torch.xpu.synchronize()

    blocks = []
    savings = []
    for block in range(TIMING_BLOCKS):
        base_offset = (block * 11) % TARGET_LAYERS
        control_first = timed_arm_ms_per_cycle(
            incumbent_bmm,
            corpus,
            evict,
            offset=base_offset,
        )
        candidate_first = timed_arm_ms_per_cycle(
            candidate_mm,
            corpus,
            evict,
            offset=(base_offset + 13) % TARGET_LAYERS,
        )
        candidate_second = timed_arm_ms_per_cycle(
            candidate_mm,
            corpus,
            evict,
            offset=(base_offset + 29) % TARGET_LAYERS,
        )
        control_second = timed_arm_ms_per_cycle(
            incumbent_bmm,
            corpus,
            evict,
            offset=(base_offset + 41) % TARGET_LAYERS,
        )
        control = (control_first + control_second) / 2.0
        candidate = (candidate_first + candidate_second) / 2.0
        saving = control - candidate
        savings.append(saving)
        blocks.append(
            {
                "block": block,
                "A1_control_ms": control_first,
                "B1_candidate_ms": candidate_first,
                "B2_candidate_ms": candidate_second,
                "A2_control_ms": control_second,
                "paired_control_ms": control,
                "paired_candidate_ms": candidate,
                "saving_ms": saving,
            }
        )

    wins = sum(saving > 0.0 for saving in savings)
    median_saving = statistics.median(savings)
    control_median = statistics.median(block["paired_control_ms"] for block in blocks)
    candidate_median = statistics.median(
        block["paired_candidate_ms"] for block in blocks
    )
    passed = wins >= MIN_BLOCK_WINS and median_saving >= MIN_CYCLE_SAVING_MS
    return {
        "passed": passed,
        "target_layers_per_cycle": TARGET_LAYERS,
        "corpus_weight_bytes": TARGET_LAYERS * N_DIM * K_DIM * 2,
        "warm_cycles_per_arm": WARM_CYCLES,
        "blocks": TIMING_BLOCKS,
        "cycles_per_arm_per_block": CYCLES_PER_ARM,
        "minimum_block_wins": MIN_BLOCK_WINS,
        "minimum_cycle_saving_ms": MIN_CYCLE_SAVING_MS,
        "candidate_block_wins": wins,
        "control_median_ms_per_cycle": control_median,
        "candidate_median_ms_per_cycle": candidate_median,
        "median_saving_ms_per_cycle": median_saving,
        "median_relative_saving": (
            median_saving / control_median if control_median else 0.0
        ),
        "blocks_detail": blocks,
    }


def verify_vllm_dispatch(rank: int) -> dict[str, object]:
    from vllm.model_executor.layers import linear

    rows, weight, _routed, _other_ranks = make_fixture(
        rank=rank,
        epoch=20_000,
    )
    layer = SimpleNamespace(
        weight=weight,
        xpu_laguna_m8_shared_down_mm=True,
    )
    method = linear.UnquantizedLinearMethod()
    expected = candidate_mm(rows, weight)

    old_exact = linear._xpu_is_exact_decode_or_verifier_rows
    old_flag = os.environ.get("VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM")
    old_exact_flag = os.environ.get("VLLM_XPU_EXACT_SPEC_ATTN")
    old_bmm = torch.bmm
    try:
        linear._xpu_is_exact_decode_or_verifier_rows = lambda _: True
        os.environ["VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM"] = "1"
        os.environ["VLLM_XPU_EXACT_SPEC_ATTN"] = "1"

        def forbidden_bmm(*_args, **_kwargs):
            raise AssertionError("candidate silently dispatched incumbent BMM")

        torch.bmm = forbidden_bmm
        actual = linear._xpu_apply_batched_m1_method(
            layer,
            method,
            rows,
            None,
        )
        dispatch_exact = torch.equal(actual, expected)
        require(dispatch_exact, "vLLM candidate dispatch output mismatch")

        layer.weight = weight.t().contiguous().t()
        require(not layer.weight.is_contiguous(), "bad-contract weight is contiguous")
        try:
            linear._xpu_apply_batched_m1_method(
                layer,
                method,
                rows,
                None,
            )
        except RuntimeError as error:
            fail_closed = "weight is not contiguous" in str(error)
        else:
            fail_closed = False
        require(fail_closed, "vLLM bad-layout dispatch did not fail closed")
    finally:
        linear._xpu_is_exact_decode_or_verifier_rows = old_exact
        torch.bmm = old_bmm
        if old_flag is None:
            os.environ.pop("VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM", None)
        else:
            os.environ["VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM"] = old_flag
        if old_exact_flag is None:
            os.environ.pop("VLLM_XPU_EXACT_SPEC_ATTN", None)
        else:
            os.environ["VLLM_XPU_EXACT_SPEC_ATTN"] = old_exact_flag

    return {
        "candidate_dispatched_without_bmm": True,
        "candidate_output_raw_exact": dispatch_exact,
        "bad_layout_failed_closed": fail_closed,
        "passed": dispatch_exact and fail_closed,
    }


def run_counter(rank: int, candidate: bool, calls: int) -> dict[str, object]:
    rows, weight, _routed, _other_ranks = make_fixture(
        rank=rank,
        epoch=30_000,
    )
    evict = torch.zeros(EVICT_ELEMENTS, dtype=torch.float32, device="xpu")
    call = candidate_mm if candidate else incumbent_bmm
    output_hashes = []
    for _ in range(calls):
        evict.add_(1)
        output = call(rows, weight)
        torch.xpu.synchronize()
        output_hashes.append(raw_sha256(output))
    require(
        len(set(output_hashes)) == 1,
        "counter-mode output was not repeat deterministic",
    )
    return {
        "rank": rank,
        "treatment": "candidate-native-mm" if candidate else "control-bmm",
        "calls": calls,
        "completion_boundary_per_call": True,
        "eviction_bytes_per_call": EVICT_ELEMENTS * 4,
        "output_sha256": output_hashes[0],
        "passed": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rank", type=int, choices=range(4), required=True)
    parser.add_argument(
        "--mode",
        choices=("full", "counter-control", "counter-candidate"),
        default="full",
    )
    parser.add_argument("--epochs", type=int, default=MIN_EXACT_EPOCHS)
    parser.add_argument("--counter-calls", type=int, default=13)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    require(args.epochs >= MIN_EXACT_EPOCHS, "too few exactness epochs")
    require(args.counter_calls >= 13, "too few counter calls")
    torch.xpu.set_device(0)
    require("Arc Pro B70" in torch.xpu.get_device_name(0), "device is not B70")

    if args.mode != "full":
        payload = {
            "format": "laguna-shared-down-mm-counter-v1",
            "mode": args.mode,
            "counter": run_counter(
                args.rank,
                candidate=args.mode == "counter-candidate",
                calls=args.counter_calls,
            ),
        }
    else:
        epochs = [
            compare_epoch(rank=args.rank, epoch=epoch) for epoch in range(args.epochs)
        ]
        fixture_hashes = [epoch["fixture_sha256"] for epoch in epochs]
        output_hashes = [epoch["output_sha256"] for epoch in epochs]
        require(
            len(set(fixture_hashes)) == args.epochs,
            "changing fixture corpus is not unique",
        )
        require(
            len(set(output_hashes)) == args.epochs,
            "changing output corpus is not unique",
        )
        dispatch = verify_vllm_dispatch(args.rank)
        timing = run_timing(args.rank)
        post_replay = [
            compare_epoch(rank=args.rank, epoch=epoch)
            for epoch in range(POST_REPLAY_EPOCHS)
        ]
        replay_matches = all(
            post["fixture_sha256"] == epochs[index]["fixture_sha256"]
            and post["output_sha256"] == epochs[index]["output_sha256"]
            for index, post in enumerate(post_replay)
        )
        require(replay_matches, "post-timing replay changed exact outputs")
        payload = {
            "format": "laguna-shared-down-mm-component-v1",
            "rank": args.rank,
            "device": torch.xpu.get_device_name(0),
            "geometry": {
                "rows": ROWS,
                "k": K_DIM,
                "n": N_DIM,
                "target_layers": TARGET_LAYERS,
                "control": "stride-zero B=8 M=1 BF16 BMM",
                "candidate": "native M=8 BF16 MM",
            },
            "exactness": {
                "epochs": args.epochs,
                "checks_per_epoch": 4,
                "all_raw_exact": True,
                "candidate_repeat_deterministic": True,
                "inputs_unchanged": True,
                "unique_fixture_hashes": len(set(fixture_hashes)),
                "unique_output_hashes": len(set(output_hashes)),
                "post_timing_replay_epochs": POST_REPLAY_EPOCHS,
                "post_timing_replay_exact": replay_matches,
                "aggregate_fixture_sha256": hashlib.sha256(
                    "".join(fixture_hashes).encode()
                ).hexdigest(),
                "aggregate_output_sha256": hashlib.sha256(
                    "".join(output_hashes).encode()
                ).hexdigest(),
            },
            "vllm_dispatch": dispatch,
            "timing": timing,
            "passed": timing["passed"] and dispatch["passed"] and replay_matches,
        }

    require(not args.out.exists(), f"refusing to overwrite {args.out}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    args.out.write_text(encoded)
    print(encoded, end="")


if __name__ == "__main__":
    main()
