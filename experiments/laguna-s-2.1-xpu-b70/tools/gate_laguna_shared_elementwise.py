#!/usr/bin/env python3
"""Gate exact Laguna M=8 shared-elementwise XPU fusions on one B70."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import statistics
import subprocess
import tempfile
import time
import traceback
from collections.abc import Callable
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import torch
import torch.nn.functional as F

import vllm_xpu_kernels._C as xpu_kernel_extension


ROWS = 8
ACT_WIDTH = 256
HIDDEN_WIDTH = 3072
LAYERS_PER_CYCLE = 47
RANDOM_EPOCHS = 256
WARMUP_CYCLES = 20
TIMING_BLOCKS = 31
TIMING_CYCLES_PER_ARM = 64
ACT_OP = "laguna_m8_silu_mul"
SCALE_ADD_OP = "laguna_m8_scale_add"
ACTIVATION_MIN_WINS = 24
SCALE_ADD_MIN_WINS = 24
COMBINED_MIN_WINS = 28
INDIVIDUAL_MIN_SAVING_MS = 0.0
COMBINED_MIN_SAVING_MS = 0.15
EXPECTED_CONTROL_LAUNCHES_PER_CYCLE = 4 * LAYERS_PER_CYCLE
EXPECTED_CANDIDATE_LAUNCHES_PER_CYCLE = 2 * LAYERS_PER_CYCLE
EXPECTED_LAUNCH_REDUCTION_PER_CYCLE = (
    EXPECTED_CONTROL_LAUNCHES_PER_CYCLE
    - EXPECTED_CANDIDATE_LAUNCHES_PER_CYCLE
)
RECORD_ENVIRONMENT_NAMES = (
    "VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE",
    "VLLM_XPU_EXACT_SPEC_ATTN",
    "VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE",
    "VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2",
    "VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE",
    "VLLM_XPU_ENABLE_XPU_GRAPH",
    "VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH",
    "VLLM_XPU_FORCE_GRAPH_WITH_COMM",
    "VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE",
    "VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK",
    "VLLM_XPU_LAGUNA_M8_QKNORM_ROPE",
    "VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM",
    "XPU_GRAPH",
    "VLLM_USE_AOT_COMPILE",
    "UR_L0_USE_IMMEDIATE_COMMANDLISTS",
    "SYCL_PI_LEVEL_ZERO_USE_IMMEDIATE_COMMANDLISTS",
    "SYCL_UR_USE_LEVEL_ZERO_V2",
    "ONEAPI_DEVICE_SELECTOR",
    "ZE_AFFINITY_MASK",
    "PYTHONPATH",
)
EXPECTED_RECORD_ENVIRONMENT = {
    "VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE": "1",
    "VLLM_XPU_EXACT_SPEC_ATTN": "1",
    "VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE": "1",
    "VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2": "1",
    "VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE": "1",
    "VLLM_XPU_ENABLE_XPU_GRAPH": "0",
    "VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH": "0",
    "XPU_GRAPH": "0",
    "VLLM_USE_AOT_COMPILE": "0",
}

FROZEN_PROTOCOL = {
    "rows": ROWS,
    "activation_width": ACT_WIDTH,
    "hidden_width": HIDDEN_WIDTH,
    "layers_per_cycle": LAYERS_PER_CYCLE,
    "random_epochs": RANDOM_EPOCHS,
    "warmup_cycles_per_arm": WARMUP_CYCLES,
    "timing_blocks": TIMING_BLOCKS,
    "timing_cycles_per_arm": TIMING_CYCLES_PER_ARM,
    "activation_min_wins": ACTIVATION_MIN_WINS,
    "scale_add_min_wins": SCALE_ADD_MIN_WINS,
    "combined_min_wins": COMBINED_MIN_WINS,
    "individual_min_saving_ms_exclusive": INDIVIDUAL_MIN_SAVING_MS,
    "combined_min_saving_ms_inclusive": COMBINED_MIN_SAVING_MS,
    "expected_control_launches_per_cycle": EXPECTED_CONTROL_LAUNCHES_PER_CYCLE,
    "expected_candidate_launches_per_cycle": (
        EXPECTED_CANDIDATE_LAUNCHES_PER_CYCLE
    ),
    "expected_launch_reduction_per_cycle": EXPECTED_LAUNCH_REDUCTION_PER_CYCLE,
    "required_record_environment": EXPECTED_RECORD_ENVIRONMENT,
    "timing_order": "A-B-B-A",
}


@dataclass(slots=True)
class TimingFixture:
    gate: torch.Tensor
    up: torch.Tensor
    shared: torch.Tensor
    routed: torch.Tensor
    silu_buffer: torch.Tensor
    activation_control_out: torch.Tensor
    activation_candidate_out: torch.Tensor
    scaled_buffer: torch.Tensor
    scale_control_out: torch.Tensor
    scale_candidate_out: torch.Tensor
    input_sha256: str


TensorCall = Callable[[TimingFixture], torch.Tensor]
CheckpointCall = Callable[[str], None]


def raw_sha256(*tensors: torch.Tensor) -> str:
    digest = hashlib.sha256()
    for tensor in tensors:
        raw = tensor.detach().cpu().contiguous().view(torch.uint8)
        digest.update(raw.numpy().tobytes())
    return digest.hexdigest()


def raw_equal(reference: torch.Tensor, candidate: torch.Tensor) -> bool:
    return torch.equal(
        reference.contiguous().view(torch.uint16),
        candidate.contiguous().view(torch.uint16),
    )


def require_raw_equal(
    label: str,
    reference: torch.Tensor,
    candidate: torch.Tensor,
) -> None:
    reference_bits = reference.contiguous().view(torch.uint16)
    candidate_bits = candidate.contiguous().view(torch.uint16)
    mismatch = reference_bits != candidate_bits
    mismatch_count = int(mismatch.sum().item())
    if mismatch_count:
        first = mismatch.nonzero()[0].tolist()
        index = tuple(int(value) for value in first)
        raise AssertionError(
            f"{label}: {mismatch_count} raw BF16 mismatches; first={index}, "
            f"reference=0x{int(reference_bits[index].item()):04x}, "
            f"candidate=0x{int(candidate_bits[index].item()):04x}"
        )
    if not torch.equal(reference, candidate):
        raise AssertionError(f"{label}: torch.equal failed after raw equality")


def candidate_activation(
    gate: torch.Tensor,
    up: torch.Tensor,
    out: torch.Tensor,
) -> torch.Tensor:
    getattr(torch.ops._C, ACT_OP)(out, gate, up)
    return out


def candidate_scale_add(
    shared: torch.Tensor,
    routed: torch.Tensor,
    out: torch.Tensor,
) -> torch.Tensor:
    getattr(torch.ops._C, SCALE_ADD_OP)(out, shared, routed)
    return out


def reference_activation(
    gate: torch.Tensor,
    up: torch.Tensor,
) -> torch.Tensor:
    return F.silu(gate) * up


def reference_scale_add(
    shared: torch.Tensor,
    routed: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    scaled = routed.clone()
    scaled.mul_(2.5)
    return scaled, shared + scaled


def finite_bf16_values() -> torch.Tensor:
    bits = torch.arange(1 << 16, dtype=torch.int32)
    finite_bits = bits[(bits & 0x7F80) != 0x7F80].to(torch.uint16)
    if finite_bits.numel() != 65_280:
        raise AssertionError("finite BF16 enumeration is incomplete")
    return finite_bits.view(torch.bfloat16).to("xpu")


def pad_to_multiple(values: torch.Tensor, multiple: int) -> torch.Tensor:
    padding = (-values.numel()) % multiple
    if padding == 0:
        return values
    return torch.cat((values, torch.zeros(padding, dtype=values.dtype, device="xpu")))


def check_activation_exhaustive() -> dict[str, Any]:
    finite = finite_bf16_values()
    padded = pad_to_multiple(finite, ROWS * ACT_WIDTH)
    gate_batches = padded.reshape(-1, ROWS, ACT_WIDTH)
    finite_reversed = finite.flip(0)
    reversed_padded = pad_to_multiple(finite_reversed, ROWS * ACT_WIDTH)
    positions = torch.arange(padded.numel(), device="xpu")
    signed_zeros = torch.where(
        positions % 2 == 0,
        torch.zeros_like(padded),
        -torch.zeros_like(padded),
    )
    up_modes = {
        "ones": torch.ones_like(padded),
        "reversed_finite": reversed_padded,
        "signed_zeros": signed_zeros,
    }
    gate_before = raw_sha256(gate_batches)
    mode_results: dict[str, Any] = {}

    for mode, up_flat in up_modes.items():
        up_batches = up_flat.reshape_as(gate_batches)
        up_before = raw_sha256(up_batches)
        reference_hash = hashlib.sha256()
        candidate_hash = hashlib.sha256()
        for batch_index, (gate, up) in enumerate(
            zip(gate_batches, up_batches, strict=True)
        ):
            reference = reference_activation(gate, up)
            output = torch.empty_like(gate)
            repeated = torch.empty_like(gate)
            candidate_activation(gate, up, output)
            candidate_activation(gate, up, repeated)
            require_raw_equal(f"{mode}[{batch_index}]", reference, output)
            require_raw_equal(f"{mode}-repeat[{batch_index}]", output, repeated)
            reference_hash.update(
                reference.cpu().contiguous().view(torch.uint8).numpy().tobytes()
            )
            candidate_hash.update(
                output.cpu().contiguous().view(torch.uint8).numpy().tobytes()
            )
        if raw_sha256(up_batches) != up_before:
            raise AssertionError(f"{mode}: activation candidate mutated up")
        mode_results[mode] = {
            "batches": gate_batches.shape[0],
            "finite_gate_patterns": finite.numel(),
            "reference_sha256": reference_hash.hexdigest(),
            "candidate_sha256": candidate_hash.hexdigest(),
            "raw_equal": reference_hash.digest() == candidate_hash.digest(),
        }

    if raw_sha256(gate_batches) != gate_before:
        raise AssertionError("activation candidate mutated gate")

    midpoint = torch.tensor([[5.9375]], dtype=torch.bfloat16, device="xpu")
    midpoint_bits = int(F.silu(midpoint).view(torch.uint16).item())
    if midpoint_bits != 0x40BD:
        raise AssertionError(
            f"incumbent 5.9375 SiLU identity changed to 0x{midpoint_bits:04x}"
        )
    return {
        "passed": True,
        "finite_gate_patterns": finite.numel(),
        "midpoint_gate_bits": "0x40be",
        "midpoint_reference_silu_bits": f"0x{midpoint_bits:04x}",
        "modes": mode_results,
    }


def check_activation_random() -> dict[str, Any]:
    input_hashes: set[str] = set()
    output_hashes: set[str] = set()
    for epoch in range(RANDOM_EPOCHS):
        torch.manual_seed(20_260_723 + epoch)
        gate = torch.randn((ROWS, ACT_WIDTH), dtype=torch.bfloat16, device="xpu").mul_(
            3.0
        )
        up = torch.randn((ROWS, ACT_WIDTH), dtype=torch.bfloat16, device="xpu")
        gate[0, 0] = 5.9375
        before = raw_sha256(gate, up)
        reference = reference_activation(gate, up)
        output = torch.empty_like(gate)
        candidate_activation(gate, up, output)
        require_raw_equal(f"activation-random[{epoch}]", reference, output)
        if raw_sha256(gate, up) != before:
            raise AssertionError(f"activation-random[{epoch}] mutated input")
        input_hashes.add(before)
        output_hashes.add(raw_sha256(output))
    if len(input_hashes) != RANDOM_EPOCHS:
        raise AssertionError("activation random inputs did not all change")
    return {
        "passed": True,
        "epochs": RANDOM_EPOCHS,
        "unique_input_hashes": len(input_hashes),
        "unique_output_hashes": len(output_hashes),
    }


def check_scale_add_exhaustive() -> dict[str, Any]:
    finite = finite_bf16_values()
    block = ROWS * HIDDEN_WIDTH
    routed_flat = pad_to_multiple(finite, block)
    routed_batches = routed_flat.reshape(-1, ROWS, HIDDEN_WIDTH)
    reversed_shared = pad_to_multiple(finite.flip(0), block)
    positions = torch.arange(routed_flat.numel(), device="xpu")
    shared_modes = {
        "zeros": torch.zeros_like(routed_flat),
        "ones": torch.ones_like(routed_flat),
        "reversed_finite": reversed_shared,
        "signed_zeros": torch.where(
            positions % 2 == 0,
            torch.zeros_like(routed_flat),
            -torch.zeros_like(routed_flat),
        ),
    }
    routed_before = raw_sha256(routed_batches)
    results: dict[str, Any] = {}
    for mode, shared_flat in shared_modes.items():
        shared_batches = shared_flat.reshape_as(routed_batches)
        shared_before = raw_sha256(shared_batches)
        reference_hash = hashlib.sha256()
        candidate_hash = hashlib.sha256()
        for batch_index, (shared, routed) in enumerate(
            zip(shared_batches, routed_batches, strict=True)
        ):
            _, reference = reference_scale_add(shared, routed)
            output = torch.empty_like(shared)
            repeated = torch.empty_like(shared)
            candidate_scale_add(shared, routed, output)
            candidate_scale_add(shared, routed, repeated)
            require_raw_equal(f"scale-{mode}[{batch_index}]", reference, output)
            require_raw_equal(f"scale-{mode}-repeat[{batch_index}]", output, repeated)
            reference_hash.update(
                reference.cpu().contiguous().view(torch.uint8).numpy().tobytes()
            )
            candidate_hash.update(
                output.cpu().contiguous().view(torch.uint8).numpy().tobytes()
            )
        if raw_sha256(shared_batches) != shared_before:
            raise AssertionError(f"scale-{mode}: candidate mutated shared")
        results[mode] = {
            "batches": routed_batches.shape[0],
            "finite_routed_patterns": finite.numel(),
            "reference_sha256": reference_hash.hexdigest(),
            "candidate_sha256": candidate_hash.hexdigest(),
            "raw_equal": reference_hash.digest() == candidate_hash.digest(),
        }
    if raw_sha256(routed_batches) != routed_before:
        raise AssertionError("scale+add candidate mutated routed")
    return {
        "passed": True,
        "finite_routed_patterns": finite.numel(),
        "modes": results,
    }


def check_scale_add_random() -> dict[str, Any]:
    input_hashes: set[str] = set()
    output_hashes: set[str] = set()
    for epoch in range(RANDOM_EPOCHS):
        torch.manual_seed(20_261_723 + epoch)
        shared = torch.randn((ROWS, HIDDEN_WIDTH), dtype=torch.bfloat16, device="xpu")
        routed = torch.randn((ROWS, HIDDEN_WIDTH), dtype=torch.bfloat16, device="xpu")
        before = raw_sha256(shared, routed)
        _, reference = reference_scale_add(shared, routed)
        output = torch.empty_like(shared)
        candidate_scale_add(shared, routed, output)
        require_raw_equal(f"scale-random[{epoch}]", reference, output)
        if raw_sha256(shared, routed) != before:
            raise AssertionError(f"scale-random[{epoch}] mutated input")
        input_hashes.add(before)
        output_hashes.add(raw_sha256(output))
    if len(input_hashes) != RANDOM_EPOCHS:
        raise AssertionError("scale+add random inputs did not all change")
    return {
        "passed": True,
        "epochs": RANDOM_EPOCHS,
        "unique_input_hashes": len(input_hashes),
        "unique_output_hashes": len(output_hashes),
    }


def expect_rejected(
    label: str,
    call: Callable[[], None],
    expected_message: str | tuple[str, ...],
) -> str:
    try:
        call()
    except (RuntimeError, ValueError) as error:
        message = str(error)
        expected = (
            (expected_message,)
            if isinstance(expected_message, str)
            else expected_message
        )
        if not any(fragment in message for fragment in expected):
            raise AssertionError(
                f"{label}: rejected for an unexpected reason: {message!r}; "
                f"expected one of {expected!r}"
            ) from error
        return message
    raise AssertionError(f"{label}: invalid contract was accepted")


def _noncontiguous_tensor(shape: tuple[int, int]) -> torch.Tensor:
    rows, width = shape
    return torch.empty(
        (rows, width * 2), dtype=torch.bfloat16, device="xpu"
    )[:, ::2]


def _misaligned_tensor(shape: tuple[int, int]) -> torch.Tensor:
    elements = math.prod(shape)
    return torch.empty(
        elements + 1, dtype=torch.bfloat16, device="xpu"
    )[1:].view(shape)


def _partial_overlap_tensors(
    shape: tuple[int, int],
) -> tuple[torch.Tensor, torch.Tensor]:
    elements = math.prod(shape)
    storage = torch.empty(
        elements + 8, dtype=torch.bfloat16, device="xpu"
    )
    input_tensor = storage[:elements].view(shape)
    output_tensor = storage[8:].view(shape)
    return input_tensor, output_tensor


def _check_native_invalid_op(
    *,
    op_name: str,
    shape: tuple[int, int],
    first_name: str,
    second_name: str,
) -> dict[str, str]:
    op = getattr(torch.ops._C, op_name)
    out = torch.empty(shape, dtype=torch.bfloat16, device="xpu")
    first = torch.zeros(shape, dtype=torch.bfloat16, device="xpu")
    second = torch.ones(shape, dtype=torch.bfloat16, device="xpu")
    shape_text = f"[{shape[0]}, {shape[1]}]"
    names_text = f"{first_name}, {second_name}, and out"
    results: dict[str, str] = {}

    def record(
        suffix: str,
        call: Callable[[], None],
        message: str | tuple[str, ...],
    ) -> None:
        label = f"{op_name}_{suffix}"
        results[suffix] = expect_rejected(label, call, message)

    wrong_shape = (shape[0] - 1, shape[1])
    wrong_out = torch.empty(wrong_shape, dtype=torch.bfloat16, device="xpu")
    wrong_first = torch.empty(
        wrong_shape, dtype=torch.bfloat16, device="xpu"
    )
    wrong_second = torch.empty_like(wrong_first)
    record(
        "out_wrong_shape",
        lambda: op(wrong_out, first, second),
        f"out must have exact shape {shape_text}",
    )
    record(
        f"{first_name}_wrong_shape",
        lambda: op(out, wrong_first, second),
        f"{first_name} must have exact shape {shape_text}",
    )
    record(
        f"{second_name}_wrong_shape",
        lambda: op(out, first, wrong_second),
        f"{second_name} must have exact shape {shape_text}",
    )

    record(
        "out_wrong_dtype",
        lambda: op(out.float(), first, second),
        f"{names_text} must be BF16",
    )
    record(
        f"{first_name}_wrong_dtype",
        lambda: op(out, first.float(), second),
        f"{names_text} must be BF16",
    )
    record(
        f"{second_name}_wrong_dtype",
        lambda: op(out, first, second.float()),
        f"{names_text} must be BF16",
    )

    record(
        "out_wrong_device",
        lambda: op(torch.empty(shape, dtype=torch.bfloat16), first, second),
        "out must be on XPU",
    )
    record(
        f"{first_name}_wrong_device",
        lambda: op(
            out,
            torch.empty(shape, dtype=torch.bfloat16),
            second,
        ),
        f"{first_name} must be on XPU",
    )
    record(
        f"{second_name}_wrong_device",
        lambda: op(
            out,
            first,
            torch.empty(shape, dtype=torch.bfloat16),
        ),
        f"{second_name} must be on XPU",
    )

    record(
        "out_noncontiguous",
        lambda: op(_noncontiguous_tensor(shape), first, second),
        f"{names_text} must be contiguous",
    )
    record(
        f"{first_name}_noncontiguous",
        lambda: op(out, _noncontiguous_tensor(shape), second),
        f"{names_text} must be contiguous",
    )
    record(
        f"{second_name}_noncontiguous",
        lambda: op(out, first, _noncontiguous_tensor(shape)),
        f"{names_text} must be contiguous",
    )

    record(
        "out_misaligned",
        lambda: op(_misaligned_tensor(shape), first, second),
        f"{names_text} pointers must be 16-byte aligned",
    )
    record(
        f"{first_name}_misaligned",
        lambda: op(out, _misaligned_tensor(shape), second),
        f"{names_text} pointers must be 16-byte aligned",
    )
    record(
        f"{second_name}_misaligned",
        lambda: op(out, first, _misaligned_tensor(shape)),
        f"{names_text} pointers must be 16-byte aligned",
    )

    overlap_message = (
        "unsupported operation",
        "single memory location",
        "overlap",
    )
    record(
        f"out_exact_alias_{first_name}",
        lambda: op(first, first, second),
        overlap_message,
    )
    record(
        f"out_exact_alias_{second_name}",
        lambda: op(second, first, second),
        overlap_message,
    )

    overlap_first, overlap_out_first = _partial_overlap_tensors(shape)
    overlap_second, overlap_out_second = _partial_overlap_tensors(shape)
    record(
        f"out_partial_overlap_{first_name}",
        lambda: op(overlap_out_first, overlap_first, second),
        overlap_message,
    )
    record(
        f"out_partial_overlap_{second_name}",
        lambda: op(overlap_out_second, first, overlap_second),
        overlap_message,
    )
    return results


def check_invalid_contracts() -> dict[str, dict[str, str]]:
    return {
        "activation": _check_native_invalid_op(
            op_name=ACT_OP,
            shape=(ROWS, ACT_WIDTH),
            first_name="gate",
            second_name="up",
        ),
        "scale_add": _check_native_invalid_op(
            op_name=SCALE_ADD_OP,
            shape=(ROWS, HIDDEN_WIDTH),
            first_name="shared",
            second_name="routed",
        ),
    }


def _record_runtime_config() -> tuple[SimpleNamespace, SimpleNamespace]:
    config = SimpleNamespace(
        model_type="laguna",
        hidden_size=HIDDEN_WIDTH,
        shared_expert_intermediate_size=1024,
        hidden_act="silu",
        num_experts=256,
        num_experts_per_tok=10,
        norm_topk_prob=True,
        moe_routed_scaling_factor=2.5,
    )
    vllm_config = SimpleNamespace(
        model_config=SimpleNamespace(
            enforce_eager=True,
            dtype=torch.bfloat16,
        ),
        parallel_config=SimpleNamespace(
            tensor_parallel_size=4,
            pipeline_parallel_size=1,
            data_parallel_size=1,
            enable_expert_parallel=True,
            enable_dbo=False,
        ),
        scheduler_config=SimpleNamespace(
            max_num_seqs=1,
            async_scheduling=False,
        ),
        speculative_config=SimpleNamespace(
            method="dflash",
            num_speculative_tokens=7,
        ),
        device_config=SimpleNamespace(device_type="xpu"),
        lora_config=None,
    )
    return config, vllm_config


def check_runtime_contracts() -> dict[str, Any]:
    from vllm.model_executor.layers.fused_moe.runner import moe_runner
    from vllm.model_executor.models import laguna

    config, vllm_config = _record_runtime_config()
    violations = laguna._laguna_m8_shared_elementwise_contract_violations(
        config,
        vllm_config,
        enable_eplb=False,
        num_redundant_experts=0,
    )
    if violations:
        raise AssertionError(
            "ambient Laguna shared-elementwise record contract drifted: "
            + "; ".join(violations)
        )

    bypass_cases = [
        ("target_m1", True, 1, True),
        *[
            (f"verifier_tail_m{rows}", True, rows, True)
            for rows in range(2, ROWS)
        ],
        ("prefill_m8", True, ROWS, False),
        ("draft_m8", False, ROWS, True),
    ]
    bypass_results: dict[str, Any] = {}

    def forbidden_dispatch(*_args: torch.Tensor) -> None:
        raise AssertionError("native treatment dispatched for a bypass case")

    for label, enabled, rows, verifier_marker in bypass_cases:
        gate = torch.randn((rows, ACT_WIDTH), dtype=torch.bfloat16)
        up = torch.randn_like(gate)
        reference = reference_activation(gate, up)
        runner = SimpleNamespace(
            use_laguna_m8_shared_elementwise=enabled,
            routed_scaling_factor=2.5,
            routed_output_transform=None,
        )
        shared = torch.randn((rows, HIDDEN_WIDTH), dtype=torch.bfloat16)
        routed = torch.randn_like(shared)
        with (
            patch.object(
                laguna,
                "_xpu_is_exact_decode_or_verifier_rows",
                return_value=verifier_marker,
            ),
            patch.object(
                moe_runner,
                "_xpu_is_exact_decode_or_verifier_rows",
                return_value=verifier_marker,
            ),
            patch.object(
                laguna.ops,
                "laguna_m8_silu_mul",
                side_effect=forbidden_dispatch,
            ),
            patch.object(
                moe_runner.ops,
                "laguna_m8_scale_add",
                side_effect=forbidden_dispatch,
            ),
        ):
            actual = laguna._laguna_m8_shared_silu_mul(
                gate,
                up,
                enabled=enabled,
            )
            scale_result = moe_runner.MoERunner._maybe_laguna_m8_scale_add(
                runner,
                shared,
                routed,
            )
        require_raw_equal(f"runtime-{label}-activation", reference, actual)
        if scale_result is not None:
            raise AssertionError(
                f"runtime-{label}: scale/add treatment did not bypass"
            )
        bypass_results[label] = {
            "rows": rows,
            "enabled": enabled,
            "verifier_marker": verifier_marker,
            "activation_sha256": raw_sha256(actual),
            "scale_add_returned_none": True,
        }

    gate = torch.empty((ROWS, ACT_WIDTH), dtype=torch.bfloat16, device="xpu")
    up = torch.empty_like(gate)
    shared = torch.empty(
        (ROWS, HIDDEN_WIDTH), dtype=torch.bfloat16, device="xpu"
    )
    routed = torch.empty_like(shared)
    runner = SimpleNamespace(
        use_laguna_m8_shared_elementwise=True,
        routed_scaling_factor=2.5,
        routed_output_transform=None,
    )

    with (
        patch.object(
            laguna,
            "_xpu_is_exact_decode_or_verifier_rows",
            return_value=True,
        ),
        patch.object(
            moe_runner,
            "_xpu_is_exact_decode_or_verifier_rows",
            return_value=True,
        ),
        patch.object(torch.compiler, "is_compiling", return_value=True),
    ):
        compiled_activation_error = expect_rejected(
            "runtime_compiled_activation",
            lambda: laguna._laguna_m8_shared_silu_mul(
                gate,
                up,
                enabled=True,
            ),
            "eager-only",
        )
        compiled_scale_error = expect_rejected(
            "runtime_compiled_scale_add",
            lambda: moe_runner.MoERunner._maybe_laguna_m8_scale_add(
                runner,
                shared,
                routed,
            ),
            "eager-only",
        )

    def missing_symbol(*_args: torch.Tensor) -> None:
        raise AttributeError("formal gate missing-symbol probe")

    with (
        patch.object(
            laguna,
            "_xpu_is_exact_decode_or_verifier_rows",
            return_value=True,
        ),
        patch.object(
            moe_runner,
            "_xpu_is_exact_decode_or_verifier_rows",
            return_value=True,
        ),
        patch.object(
            laguna.ops,
            "laguna_m8_silu_mul",
            side_effect=missing_symbol,
        ),
        patch.object(
            moe_runner.ops,
            "laguna_m8_scale_add",
            side_effect=missing_symbol,
        ),
    ):
        missing_activation_error = expect_rejected(
            "runtime_missing_activation",
            lambda: laguna._laguna_m8_shared_silu_mul(
                gate,
                up,
                enabled=True,
            ),
            "_C::laguna_m8_silu_mul",
        )
        missing_scale_error = expect_rejected(
            "runtime_missing_scale_add",
            lambda: moe_runner.MoERunner._maybe_laguna_m8_scale_add(
                runner,
                shared,
                routed,
            ),
            "_C::laguna_m8_scale_add",
        )

    torch.manual_seed(20_263_723)
    gate.normal_()
    up.normal_()
    shared.normal_()
    routed.normal_()
    activation_before = raw_sha256(gate, up)
    scale_before = raw_sha256(shared, routed)
    native_activation = laguna.ops.laguna_m8_silu_mul
    native_scale_add = moe_runner.ops.laguna_m8_scale_add
    dispatch_counts = {"activation": 0, "scale_add": 0}

    def counted_activation(
        out: torch.Tensor,
        gate_input: torch.Tensor,
        up_input: torch.Tensor,
    ) -> None:
        dispatch_counts["activation"] += 1
        native_activation(out, gate_input, up_input)

    def counted_scale_add(
        out: torch.Tensor,
        shared_input: torch.Tensor,
        routed_input: torch.Tensor,
    ) -> None:
        dispatch_counts["scale_add"] += 1
        native_scale_add(out, shared_input, routed_input)

    activation_reference = reference_activation(gate, up)
    _, scale_reference = reference_scale_add(shared, routed)
    with (
        patch.object(
            laguna,
            "_xpu_is_exact_decode_or_verifier_rows",
            return_value=True,
        ),
        patch.object(
            moe_runner,
            "_xpu_is_exact_decode_or_verifier_rows",
            return_value=True,
        ),
        patch.object(
            laguna.ops,
            "laguna_m8_silu_mul",
            side_effect=counted_activation,
        ),
        patch.object(
            moe_runner.ops,
            "laguna_m8_scale_add",
            side_effect=counted_scale_add,
        ),
    ):
        activation_output = laguna._laguna_m8_shared_silu_mul(
            gate,
            up,
            enabled=True,
        )
        scale_output = moe_runner.MoERunner._maybe_laguna_m8_scale_add(
            runner,
            shared,
            routed,
        )
    if scale_output is None:
        raise AssertionError("matching M8 scale/add wrapper silently bypassed")
    if dispatch_counts != {"activation": 1, "scale_add": 1}:
        raise AssertionError(
            f"matching M8 native dispatch counts are {dispatch_counts!r}"
        )
    require_raw_equal(
        "runtime-matching-m8-activation",
        activation_reference,
        activation_output,
    )
    require_raw_equal(
        "runtime-matching-m8-scale-add",
        scale_reference,
        scale_output,
    )
    if raw_sha256(gate, up) != activation_before:
        raise AssertionError("matching M8 activation wrapper mutated inputs")
    if raw_sha256(shared, routed) != scale_before:
        raise AssertionError("matching M8 scale/add wrapper mutated inputs")

    return {
        "passed": True,
        "ambient_record_contract_violations": violations,
        "bypass_cases": bypass_results,
        "compiled_rejections": {
            "activation": compiled_activation_error,
            "scale_add": compiled_scale_error,
        },
        "missing_symbol_rejections": {
            "activation": missing_activation_error,
            "scale_add": missing_scale_error,
        },
        "matching_m8_dispatch_counts": dispatch_counts,
        "matching_m8_output_sha256": {
            "activation": raw_sha256(activation_output),
            "scale_add": raw_sha256(scale_output),
        },
    }


def time_arm(
    call: TensorCall,
    fixture: TimingFixture,
    invocations: int,
) -> float:
    torch.xpu.synchronize()
    started_ns = time.perf_counter_ns()
    result = None
    for _ in range(invocations):
        result = call(fixture)
    torch.xpu.synchronize()
    if result is None:
        raise AssertionError("timed arm did not execute")
    elapsed_ms = (time.perf_counter_ns() - started_ns) / 1_000_000.0
    cycles = invocations / LAYERS_PER_CYCLE
    return elapsed_ms / cycles


def build_timing_fixture_bank() -> tuple[list[TimingFixture], dict[str, Any]]:
    fixtures: list[TimingFixture] = []
    input_hashes: set[str] = set()
    for fixture_index in range(TIMING_BLOCKS):
        torch.manual_seed(20_262_723 + fixture_index)
        gate = torch.randn(
            (ROWS, ACT_WIDTH), dtype=torch.bfloat16, device="xpu"
        )
        up = torch.randn_like(gate)
        shared = torch.randn(
            (ROWS, HIDDEN_WIDTH), dtype=torch.bfloat16, device="xpu"
        )
        routed = torch.randn_like(shared)
        input_sha256 = raw_sha256(gate, up, shared, routed)
        if input_sha256 in input_hashes:
            raise AssertionError("timing fixture bank contains duplicate inputs")
        input_hashes.add(input_sha256)
        fixtures.append(
            TimingFixture(
                gate=gate,
                up=up,
                shared=shared,
                routed=routed,
                silu_buffer=torch.empty_like(gate),
                activation_control_out=torch.empty_like(gate),
                activation_candidate_out=torch.empty_like(gate),
                scaled_buffer=torch.empty_like(routed),
                scale_control_out=torch.empty_like(shared),
                scale_candidate_out=torch.empty_like(shared),
                input_sha256=input_sha256,
            )
        )
    if len(input_hashes) != TIMING_BLOCKS:
        raise AssertionError("timing fixtures did not all change")
    bank_digest = hashlib.sha256()
    for fixture in fixtures:
        bank_digest.update(bytes.fromhex(fixture.input_sha256))
    return fixtures, {
        "fixtures": len(fixtures),
        "rotation": "one prebuilt fixture per ABBA block; identical within A/B",
        "unique_input_hashes": len(input_hashes),
        "fixture_input_sha256": [
            fixture.input_sha256 for fixture in fixtures
        ],
        "bank_sha256": bank_digest.hexdigest(),
    }


def activation_control(fixture: TimingFixture) -> torch.Tensor:
    torch.ops.aten.silu.out(fixture.gate, out=fixture.silu_buffer)
    torch.mul(
        fixture.silu_buffer,
        fixture.up,
        out=fixture.activation_control_out,
    )
    return fixture.activation_control_out


def activation_treatment(fixture: TimingFixture) -> torch.Tensor:
    return candidate_activation(
        fixture.gate,
        fixture.up,
        fixture.activation_candidate_out,
    )


def scale_control(fixture: TimingFixture) -> torch.Tensor:
    torch.mul(fixture.routed, 2.5, out=fixture.scaled_buffer)
    torch.add(
        fixture.shared,
        fixture.scaled_buffer,
        out=fixture.scale_control_out,
    )
    return fixture.scale_control_out


def scale_treatment(fixture: TimingFixture) -> torch.Tensor:
    return candidate_scale_add(
        fixture.shared,
        fixture.routed,
        fixture.scale_candidate_out,
    )


def combined_control(fixture: TimingFixture) -> torch.Tensor:
    activation_control(fixture)
    return scale_control(fixture)


def combined_treatment(fixture: TimingFixture) -> torch.Tensor:
    activation_treatment(fixture)
    return scale_treatment(fixture)


def _timing_summary(
    blocks: list[dict[str, Any]],
    *,
    complete: bool,
) -> dict[str, Any]:
    savings = [float(block["saving_ms"]) for block in blocks]
    control_values = [float(block["control_ms"]) for block in blocks]
    candidate_values = [float(block["candidate_ms"]) for block in blocks]
    summary: dict[str, Any] = {
        "inference_mode": torch.is_inference_mode_enabled(),
        "warmup_cycles_per_arm": WARMUP_CYCLES,
        "expected_blocks": TIMING_BLOCKS,
        "completed_blocks": len(blocks),
        "cycles_per_arm": TIMING_CYCLES_PER_ARM,
        "layers_per_cycle": LAYERS_PER_CYCLE,
        "candidate_block_wins": sum(value > 0.0 for value in savings),
        "blocks_detail": blocks,
        "complete": complete,
    }
    if blocks:
        summary.update(
            {
                "median_control_ms": statistics.median(control_values),
                "median_candidate_ms": statistics.median(candidate_values),
                "median_saving_ms": statistics.median(savings),
                "median_saving_percent": statistics.median(
                    float(block["saving_percent"]) for block in blocks
                ),
            }
        )
    return summary


def timing_family(
    control: TensorCall,
    candidate: TensorCall,
    fixtures: list[TimingFixture],
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    if not torch.is_inference_mode_enabled():
        raise AssertionError("timing must run under torch.inference_mode")
    if len(fixtures) != TIMING_BLOCKS:
        raise AssertionError("timing fixture bank must match block count")

    for call in (control, candidate):
        for cycle_index in range(WARMUP_CYCLES):
            fixture = fixtures[cycle_index % len(fixtures)]
            for _ in range(LAYERS_PER_CYCLE):
                call(fixture)
        torch.xpu.synchronize()

    invocations = TIMING_CYCLES_PER_ARM * LAYERS_PER_CYCLE
    blocks: list[dict[str, Any]] = []
    for block_index, fixture in enumerate(fixtures):
        a1 = time_arm(control, fixture, invocations)
        b1 = time_arm(candidate, fixture, invocations)
        b2 = time_arm(candidate, fixture, invocations)
        a2 = time_arm(control, fixture, invocations)
        control_ms = statistics.fmean((a1, a2))
        candidate_ms = statistics.fmean((b1, b2))
        saving_ms = control_ms - candidate_ms
        blocks.append(
            {
                "block_index": block_index,
                "fixture_input_sha256": fixture.input_sha256,
                "A1_ms": a1,
                "B1_ms": b1,
                "B2_ms": b2,
                "A2_ms": a2,
                "control_ms": control_ms,
                "candidate_ms": candidate_ms,
                "saving_ms": saving_ms,
                "saving_percent": 100.0 * saving_ms / control_ms,
            }
        )
        if progress is not None:
            progress(_timing_summary(blocks, complete=False))
    return _timing_summary(blocks, complete=True)


def _profile_xpu_kernel_events(
    label: str,
    call: TensorCall,
    fixture: TimingFixture,
) -> dict[str, Any]:
    torch.xpu.synchronize()
    with tempfile.TemporaryDirectory(
        prefix=f"laguna-shared-elementwise-{label}-"
    ) as temp_dir:
        trace_path = Path(temp_dir) / "trace.json"
        with torch.profiler.profile(
            activities=[torch.profiler.ProfilerActivity.XPU],
        ) as profiler:
            for _ in range(LAYERS_PER_CYCLE):
                call(fixture)
            torch.xpu.synchronize()
        profiler.export_chrome_trace(str(trace_path))
        trace_bytes = trace_path.read_bytes()
    trace = json.loads(trace_bytes)
    kernel_events = [
        event
        for event in trace.get("traceEvents", [])
        if event.get("cat") == "kernel" and "dur" in event
    ]
    names = Counter(str(event.get("name", "<unnamed>")) for event in kernel_events)
    return {
        "kernel_events": len(kernel_events),
        "kernel_name_counts": dict(sorted(names.items())),
        "trace_sha256": hashlib.sha256(trace_bytes).hexdigest(),
    }


def check_combined_launch_count(
    fixtures: list[TimingFixture],
) -> dict[str, Any]:
    if not torch.is_inference_mode_enabled():
        raise AssertionError("launch proof must run under torch.inference_mode")
    fixture = fixtures[0]
    for call in (combined_control, combined_treatment):
        for _ in range(2 * LAYERS_PER_CYCLE):
            call(fixture)
        torch.xpu.synchronize()
    control = _profile_xpu_kernel_events(
        "combined-control",
        combined_control,
        fixture,
    )
    candidate = _profile_xpu_kernel_events(
        "combined-candidate",
        combined_treatment,
        fixture,
    )
    reduction = control["kernel_events"] - candidate["kernel_events"]
    if control["kernel_events"] != EXPECTED_CONTROL_LAUNCHES_PER_CYCLE:
        raise AssertionError(
            "combined control profiler counted "
            f"{control['kernel_events']} kernels, expected "
            f"{EXPECTED_CONTROL_LAUNCHES_PER_CYCLE}"
        )
    if candidate["kernel_events"] != EXPECTED_CANDIDATE_LAUNCHES_PER_CYCLE:
        raise AssertionError(
            "combined candidate profiler counted "
            f"{candidate['kernel_events']} kernels, expected "
            f"{EXPECTED_CANDIDATE_LAUNCHES_PER_CYCLE}"
        )
    if reduction != EXPECTED_LAUNCH_REDUCTION_PER_CYCLE:
        raise AssertionError(
            f"combined launch reduction is {reduction}, expected "
            f"{EXPECTED_LAUNCH_REDUCTION_PER_CYCLE}"
        )
    return {
        "passed": True,
        "profiler_activity": "XPU",
        "profiled_layers": LAYERS_PER_CYCLE,
        "control": control,
        "candidate": candidate,
        "measured_launch_reduction_per_cycle": reduction,
        "expected_launch_reduction_per_cycle": (
            EXPECTED_LAUNCH_REDUCTION_PER_CYCLE
        ),
    }


def run_timing(
    fixtures: list[TimingFixture],
    progress: Callable[[str, dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    families: dict[str, dict[str, Any]] = {}
    calls = {
        "activation": (activation_control, activation_treatment),
        "scale_add": (scale_control, scale_treatment),
        "combined": (combined_control, combined_treatment),
    }
    for name, (control, candidate) in calls.items():
        family_progress = (
            None
            if progress is None
            else lambda partial, family=name: progress(family, partial)
        )
        families[name] = timing_family(
            control,
            candidate,
            fixtures,
            family_progress,
        )
        if progress is not None:
            progress(name, families[name])

    families["activation"]["gate_pass"] = (
        families["activation"]["candidate_block_wins"]
        >= ACTIVATION_MIN_WINS
        and families["activation"]["median_saving_ms"]
        > INDIVIDUAL_MIN_SAVING_MS
    )
    families["scale_add"]["gate_pass"] = (
        families["scale_add"]["candidate_block_wins"]
        >= SCALE_ADD_MIN_WINS
        and families["scale_add"]["median_saving_ms"]
        > INDIVIDUAL_MIN_SAVING_MS
    )
    families["combined"]["gate_pass"] = (
        families["combined"]["candidate_block_wins"] >= COMBINED_MIN_WINS
        and families["combined"]["median_saving_ms"]
        >= COMBINED_MIN_SAVING_MS
    )
    return families


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_text_command(
    command: list[str],
    *,
    env: dict[str, str] | None = None,
) -> str:
    completed = subprocess.run(
        command,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    return completed.stdout.strip()


def git_identity(repo: Path) -> dict[str, Any]:
    commit = run_text_command(["git", "-C", str(repo), "rev-parse", "HEAD"])
    status = run_text_command(
        [
            "git",
            "-C",
            str(repo),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ]
    )
    return {
        "path": str(repo),
        "commit": commit,
        "clean": not status,
        "status_porcelain": status.splitlines(),
        "status_sha256": hashlib.sha256(status.encode()).hexdigest(),
    }


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def parse_xpu_smi_devices(discovery: str) -> dict[str, dict[str, str]]:
    devices: dict[str, dict[str, str]] = {}
    current_id: str | None = None
    for line in discovery.splitlines():
        device_match = re.match(
            r"^\|\s*(\d+)\s*\|\s*Device Name:\s*(.*?)\s*\|$",
            line,
        )
        if device_match:
            current_id = device_match.group(1)
            devices[current_id] = {"name": device_match.group(2)}
            continue
        if current_id is None:
            continue
        uuid_match = re.search(r"\|\s*SOC UUID:\s*([0-9a-fA-F-]+)\s*\|$", line)
        if uuid_match:
            devices[current_id]["soc_uuid"] = uuid_match.group(1).lower()
            continue
        pci_match = re.search(
            r"\|\s*PCI BDF Address:\s*([0-9a-fA-F:.]+)\s*\|$",
            line,
        )
        if pci_match:
            devices[current_id]["pci_bdf"] = pci_match.group(1).lower()
    return devices


def collect_identity(args: argparse.Namespace) -> dict[str, Any]:
    from vllm.model_executor.models import laguna

    script_path = Path(__file__).resolve()
    vllm_repo = args.vllm_repo.resolve()
    kernel_repo = args.kernel_repo.resolve()
    requested_native = args.native_library.resolve()
    loaded_native = Path(xpu_kernel_extension.__file__).resolve()
    vllm_module = Path(laguna.__file__).resolve()
    xpu_smi_version = run_text_command(["xpu-smi", "-v"])
    visible_xpu_smi_discovery = run_text_command(["xpu-smi", "discovery"])
    unfiltered_env = dict(os.environ)
    unfiltered_env.pop("ZE_AFFINITY_MASK", None)
    unfiltered_env.pop("ONEAPI_DEVICE_SELECTOR", None)
    full_xpu_smi_discovery = run_text_command(
        ["xpu-smi", "discovery"],
        env=unfiltered_env,
    )
    affinity = os.environ.get("ZE_AFFINITY_MASK")
    actual_physical_card = (
        int(affinity)
        if affinity is not None and re.fullmatch(r"\d+", affinity)
        else None
    )
    return {
        "captured_utc": utc_now(),
        "script": {
            "path": str(script_path),
            "sha256": sha256_file(script_path),
        },
        "vllm_git": git_identity(vllm_repo),
        "kernel_git": git_identity(kernel_repo),
        "vllm_module_path": str(vllm_module),
        "native_library": {
            "requested_path": str(requested_native),
            "loaded_path": str(loaded_native),
            "sha256": sha256_file(loaded_native),
        },
        "physical_card": {
            "expected_index": args.expected_physical_card,
            "actual_affinity_index": actual_physical_card,
            "device_name": torch.xpu.get_device_name(0),
            "device_properties": repr(torch.xpu.get_device_properties(0)),
            "oneapi_device_selector": os.environ.get(
                "ONEAPI_DEVICE_SELECTOR"
            ),
            "ze_affinity_mask": affinity,
        },
        "record_environment": {
            name: os.environ.get(name) for name in RECORD_ENVIRONMENT_NAMES
        },
        "torch": torch.__version__,
        "xpu_smi": {
            "version": xpu_smi_version,
            "version_sha256": hashlib.sha256(
                xpu_smi_version.encode()
            ).hexdigest(),
            "visible_discovery": visible_xpu_smi_discovery,
            "visible_discovery_sha256": hashlib.sha256(
                visible_xpu_smi_discovery.encode()
            ).hexdigest(),
            "visible_devices": parse_xpu_smi_devices(
                visible_xpu_smi_discovery
            ),
            "full_discovery": full_xpu_smi_discovery,
            "full_discovery_sha256": hashlib.sha256(
                full_xpu_smi_discovery.encode()
            ).hexdigest(),
            "full_devices": parse_xpu_smi_devices(full_xpu_smi_discovery),
        },
        "activation_op": f"_C.{ACT_OP}",
        "scale_add_op": f"_C.{SCALE_ADD_OP}",
    }


def validate_identity(
    args: argparse.Namespace,
    identity: dict[str, Any],
) -> None:
    mismatches: list[str] = []
    if identity["script"]["sha256"] != args.expected_script_sha256:
        mismatches.append(
            "script SHA256 "
            f"{identity['script']['sha256']} != "
            f"{args.expected_script_sha256}"
        )
    if identity["vllm_git"]["commit"] != args.expected_vllm_commit:
        mismatches.append(
            "vLLM commit "
            f"{identity['vllm_git']['commit']} != "
            f"{args.expected_vllm_commit}"
        )
    if identity["kernel_git"]["commit"] != args.expected_kernel_commit:
        mismatches.append(
            "kernel commit "
            f"{identity['kernel_git']['commit']} != "
            f"{args.expected_kernel_commit}"
        )
    if identity["native_library"]["sha256"] != args.expected_native_sha256:
        mismatches.append(
            "native SHA256 "
            f"{identity['native_library']['sha256']} != "
            f"{args.expected_native_sha256}"
        )
    requested_native = Path(
        identity["native_library"]["requested_path"]
    )
    loaded_native = Path(identity["native_library"]["loaded_path"])
    if requested_native != loaded_native:
        mismatches.append(
            f"loaded native library {loaded_native} != requested "
            f"{requested_native}"
        )
    if not identity["vllm_git"]["clean"]:
        mismatches.append("vLLM git worktree is dirty")
    if not identity["kernel_git"]["clean"]:
        mismatches.append("kernel git worktree is dirty")
    if identity["physical_card"]["actual_affinity_index"] != (
        args.expected_physical_card
    ):
        mismatches.append(
            "physical card affinity "
            f"{identity['physical_card']['actual_affinity_index']!r} != "
            f"{args.expected_physical_card}"
        )
    expected_key = str(args.expected_physical_card)
    full_devices = identity["xpu_smi"]["full_devices"]
    visible_devices = identity["xpu_smi"]["visible_devices"]
    if expected_key not in full_devices:
        mismatches.append(
            "expected physical card is absent from unfiltered xpu-smi discovery"
        )
    if set(visible_devices) != {"0"}:
        mismatches.append(
            "affinity-filtered xpu-smi discovery did not expose exactly "
            "logical device 0"
        )
    if expected_key in full_devices and set(visible_devices) == {"0"}:
        expected_device = full_devices[expected_key]
        visible_device = visible_devices["0"]
        for field in ("soc_uuid", "pci_bdf"):
            if expected_device.get(field) != visible_device.get(field):
                mismatches.append(
                    f"visible physical-card {field} "
                    f"{visible_device.get(field)!r} != expected "
                    f"{expected_device.get(field)!r}"
                )
    if not _path_is_within(
        Path(identity["vllm_module_path"]),
        args.vllm_repo.resolve(),
    ):
        mismatches.append("loaded Laguna module is outside the vLLM repo")
    if not _path_is_within(
        loaded_native,
        args.kernel_repo.resolve(),
    ):
        mismatches.append("loaded native library is outside the kernel repo")
    for name, expected in EXPECTED_RECORD_ENVIRONMENT.items():
        actual = identity["record_environment"].get(name)
        if actual != expected:
            mismatches.append(
                f"record environment {name}={actual!r}, expected {expected!r}"
            )
    if mismatches:
        raise RuntimeError("identity gate failed: " + "; ".join(mismatches))


def json_checkpoint_value(value: Any) -> Any:
    """Keep error checkpoints serializable even if a timer returns NaN/Inf."""
    if isinstance(value, float) and not math.isfinite(value):
        return {"nonfinite_float": repr(value)}
    if isinstance(value, dict):
        return {
            str(key): json_checkpoint_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [json_checkpoint_value(item) for item in value]
    if isinstance(value, tuple):
        return [json_checkpoint_value(item) for item in value]
    return value


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    serialized = json.dumps(
        json_checkpoint_value(payload),
        indent=2,
        sort_keys=True,
        allow_nan=False,
    )
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(serialized)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def checkpoint_result(
    output: Path,
    result: dict[str, Any],
    phase: str,
) -> None:
    result["last_checkpoint"] = {
        "phase": phase,
        "utc": utc_now(),
    }
    atomic_write_json(output, result)


def execute_gate(
    args: argparse.Namespace,
    result: dict[str, Any],
    checkpoint: CheckpointCall,
) -> None:
    if not torch.is_inference_mode_enabled():
        raise AssertionError("formal gate must run under torch.inference_mode")
    if not torch.xpu.is_available() or torch.xpu.device_count() != 1:
        raise RuntimeError("gate requires exactly one visible XPU device")

    identity = collect_identity(args)
    result["identity"] = identity
    checkpoint("identity-captured")
    validate_identity(args, identity)
    result["identity_validated"] = True
    checkpoint("identity-validated")

    for op_name in (ACT_OP, SCALE_ADD_OP):
        if not hasattr(torch.ops._C, op_name):
            raise RuntimeError(f"rebuilt native symbol _C.{op_name} is missing")

    result["correctness"] = {}
    correctness_checks: list[tuple[str, Callable[[], Any]]] = [
        ("activation_exhaustive", check_activation_exhaustive),
        ("activation_random", check_activation_random),
        ("scale_add_exhaustive", check_scale_add_exhaustive),
        ("scale_add_random", check_scale_add_random),
        ("native_invalid_contracts", check_invalid_contracts),
        ("vllm_runtime_contracts", check_runtime_contracts),
    ]
    for name, call in correctness_checks:
        result["correctness"][name] = call()
        checkpoint(f"correctness:{name}")

    fixtures, fixture_identity = build_timing_fixture_bank()
    result["timing_fixture_bank"] = fixture_identity
    checkpoint("timing-fixtures-built")

    result["launch_proof"] = check_combined_launch_count(fixtures)
    checkpoint("launch-proof")

    result["timing"] = {}

    def timing_progress(name: str, partial: dict[str, Any]) -> None:
        result["timing"][name] = partial
        checkpoint(
            f"timing:{name}:blocks-{partial['completed_blocks']}"
        )

    result["timing"] = run_timing(fixtures, timing_progress)
    checkpoint("timing-complete")

    if not all(
        math.isfinite(result["timing"][name]["median_saving_ms"])
        for name in ("activation", "scale_add", "combined")
    ):
        raise AssertionError("non-finite timing result")

    result["post_timing"] = {}
    for name, call in (
        ("activation_exhaustive", check_activation_exhaustive),
        ("scale_add_exhaustive", check_scale_add_exhaustive),
    ):
        result["post_timing"][name] = call()
        checkpoint(f"post-timing:{name}")

    passed = all(
        result["timing"][name]["gate_pass"]
        for name in ("activation", "scale_add", "combined")
    )
    result["status"] = "passed" if passed else "failed"
    result["passed"] = passed


def sha256_argument(value: str) -> str:
    normalized = value.lower()
    if not re.fullmatch(r"[0-9a-f]{64}", normalized):
        raise argparse.ArgumentTypeError("expected a 64-digit SHA256")
    return normalized


def commit_argument(value: str) -> str:
    normalized = value.lower()
    if not re.fullmatch(r"[0-9a-f]{40,64}", normalized):
        raise argparse.ArgumentTypeError(
            "expected a full 40- or 64-digit git commit"
        )
    return normalized


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--expected-script-sha256",
        type=sha256_argument,
        required=True,
    )
    parser.add_argument("--vllm-repo", type=Path, required=True)
    parser.add_argument(
        "--expected-vllm-commit",
        type=commit_argument,
        required=True,
    )
    parser.add_argument("--kernel-repo", type=Path, required=True)
    parser.add_argument(
        "--expected-kernel-commit",
        type=commit_argument,
        required=True,
    )
    parser.add_argument("--native-library", type=Path, required=True)
    parser.add_argument(
        "--expected-native-sha256",
        type=sha256_argument,
        required=True,
    )
    parser.add_argument(
        "--expected-physical-card",
        type=int,
        choices=range(4),
        required=True,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result: dict[str, Any] = {
        "schema_version": 2,
        "status": "running",
        "passed": False,
        "started_utc": utc_now(),
        "expected_identity": {
            "script_sha256": args.expected_script_sha256,
            "vllm_repo": str(args.vllm_repo.resolve()),
            "vllm_commit": args.expected_vllm_commit,
            "kernel_repo": str(args.kernel_repo.resolve()),
            "kernel_commit": args.expected_kernel_commit,
            "native_library": str(args.native_library.resolve()),
            "native_sha256": args.expected_native_sha256,
            "physical_card": args.expected_physical_card,
        },
        "frozen_protocol": FROZEN_PROTOCOL,
    }

    def checkpoint(phase: str) -> None:
        checkpoint_result(args.output, result, phase)

    checkpoint("initialized")
    try:
        with torch.inference_mode():
            execute_gate(args, result, checkpoint)
        result["completed_utc"] = utc_now()
        checkpoint("complete")
    except BaseException as error:
        result.update(
            {
                "status": "error",
                "passed": False,
                "completed_utc": utc_now(),
                "error_type": type(error).__name__,
                "error": str(error),
                "traceback": traceback.format_exc(),
            }
        )
        checkpoint("error")
        raise
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
