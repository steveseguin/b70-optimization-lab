#!/usr/bin/env python3
"""Fail-closed offline verifier for Laguna M=8 Phase-A evidence.

This module intentionally imports neither torch nor an XPU extension.  It
accepts a card only after independently rechecking the frozen authorization,
fixture grammar, native-origin records, every exactness checkpoint, and the
raw device-event timing arithmetic.  A successful result is deliberately only
a Phase-A timing/exactness pass: counters, a full component claim, generation,
and an endpoint claim remain unauthorized.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import sys
import uuid
from pathlib import Path
from typing import Any

import gate_laguna_m8_gather_finalize_component as contract


RESULT = "component-result.json"
PREIMPORT = "runtime-preimport-seal.json"
STARTED = "tensor-work-started-checkpoint.json"
RUNTIME_BINDING = "runtime-card-binding-checkpoint.json"
TIMING = "timing.json"
PRE_EPOCHS = "pre-epochs"
POST_EPOCHS = "post-epochs"

TOKENS = 8
TOPK = 10
HIDDEN = 3072
RANKS = 4
LAYERS = 47
WARM_CYCLES = 20
ABBA_BLOCKS = 31
CYCLES_PER_ARM = 64
BF16_NUMEL = TOKENS * HIDDEN
NAN_POLICY = (
    "torch.equal is inapplicable for tensors containing NaNs; raw uint16 "
    "equality and identical per-class counts are required"
)
NAN_COMPARISON_POLICY = (
    "inapplicable_when_nan_present_raw_bits_and_classification_required"
)
FINITE_COMPARISON_POLICY = "required_for_finite_and_infinite_values"


def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_sha(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


def _sha(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(), f"unsafe regular file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _regular(path: Path, label: str) -> Path:
    require(path.is_absolute(), f"{label} must be absolute")
    require(path.is_file() and not path.is_symlink(), f"unsafe {label}: {path}")
    resolved = path.resolve(strict=True)
    require(resolved == path and not resolved.is_symlink(), f"{label} aliases a path")
    return resolved


def _directory(path: Path, label: str) -> Path:
    require(path.is_absolute(), f"{label} must be absolute")
    require(path.is_dir() and not path.is_symlink(), f"unsafe {label}: {path}")
    resolved = path.resolve(strict=True)
    require(resolved == path and not resolved.is_symlink(), f"{label} aliases a path")
    return resolved


def _read(path: Path, label: str) -> dict[str, Any]:
    path = _regular(path, label)
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"{label} is not JSON: {path}") from error
    require(
        isinstance(value, dict) and raw == contract.canonical(value) + b"\n",
        f"{label} is noncanonical: {path}",
    )
    return value


def _strict(value: object, keys: set[str], label: str) -> dict[str, Any]:
    require(isinstance(value, dict) and set(value) == keys, f"{label} schema drift")
    return value


def _expected_specs(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Reconstruct the packet-bound runner grammar without importing torch."""
    seeds = manifest["random_full"]["seeds"]
    require(isinstance(seeds, list), "fixture seeds malformed")
    chunks = math.ceil(contract.FINITE_BF16_COUNT / (TOKENS * HIDDEN))
    specs: list[dict[str, Any]] = []
    for index, seed in enumerate(seeds):
        specs.append(
            {
                "id": f"random-full-{index:03d}",
                "kind": "random_full",
                "seed": seed,
                "coverage": ["random_full"],
            }
        )
    for slot in range(TOPK):
        for chunk in range(chunks):
            specs.append(
                {
                    "id": f"routed-finite-slot-{slot}-chunk-{chunk}",
                    "kind": "routed_finite",
                    "slot": slot,
                    "chunk": chunk,
                    "coverage": ["finite_bf16_routed", f"slot_{slot}"],
                }
            )
    for chunk in range(chunks):
        specs.append(
            {
                "id": f"shared-finite-chunk-{chunk}",
                "kind": "shared_finite",
                "chunk": chunk,
                "coverage": ["finite_bf16_shared"],
            }
        )
    specs.extend(
        [
            {
                "id": "special-bf16-classification",
                "kind": "special_classification",
                "coverage": [
                    "positive_zero",
                    "negative_zero",
                    "subnormal",
                    "infinity",
                    "nan",
                ],
            },
            {
                "id": "fp32-weight-edges",
                "kind": "weight_edges",
                "coverage": [
                    "fp32_zero",
                    "fp32_subnormal",
                    "fp32_near_one",
                ],
            },
            {
                "id": "tie-even-midpoints",
                "kind": "tie_even",
                "coverage": ["tie_even_midpoints"],
            },
            {
                "id": "all-local",
                "kind": "route_pattern",
                "pattern": "all_local",
                "coverage": ["all_local"],
            },
            {
                "id": "all-remote",
                "kind": "route_pattern",
                "pattern": "all_remote",
                "coverage": ["all_remote"],
            },
            {
                "id": "mixed-remote-zero",
                "kind": "route_pattern",
                "pattern": "mixed_remote_zero",
                "coverage": ["mixed_remote_zero"],
            },
        ]
    )
    for slot in range(TOPK):
        specs.append(
            {
                "id": f"canonical-slot-{slot}",
                "kind": "canonical_slot",
                "slot": slot,
                "coverage": ["all_ten_slots", f"slot_{slot}", "all_80_rows"],
            }
        )
    require(
        [item["id"] for item in specs] == contract.fixture_spec_ids(),
        "analyzer/packet corpus grammar drift",
    )
    require(len(specs) == 305, "unexpected corpus size")
    return specs


def _expected_zero_rows(spec: dict[str, Any]) -> list[int]:
    all_rows = list(range(TOKENS * TOPK))
    kind = spec["kind"]
    if kind in {"random_full", "weight_edges"}:
        return []
    if kind == "routed_finite":
        active_tokens = range(TOKENS if spec["chunk"] < 2 else 6)
        active = {spec["slot"] + token * TOPK for token in active_tokens}
        return [row for row in all_rows if row not in active]
    if kind in {"shared_finite"}:
        return all_rows
    if kind in {"special_classification", "tie_even", "canonical_slot"}:
        slot = 0 if kind != "canonical_slot" else spec["slot"]
        active = {slot + token * TOPK for token in range(TOKENS)}
        return [row for row in all_rows if row not in active]
    if kind != "route_pattern":
        raise RuntimeError(f"unknown corpus kind: {kind}")
    if spec["pattern"] == "all_local":
        return []
    if spec["pattern"] == "all_remote":
        return all_rows
    require(spec["pattern"] == "mixed_remote_zero", "route pattern drift")
    return [0, 9, 10, 19, 23, 31, 40, 47, 58, 70, 79]


def _input_hashes(value: object, label: str) -> dict[str, str]:
    keys = {
        "routes_bf16_le_sha256",
        "weights_fp32_le_sha256",
        "shared_bf16_le_sha256",
        "route_map_uint32_le_sha256",
    }
    result = _strict(value, keys, label)
    require(all(_is_sha(item) for item in result.values()), f"{label} hash drift")
    return result  # type: ignore[return-value]


def _classification(value: object, label: str) -> dict[str, Any]:
    keys = {
        "positive_zero",
        "negative_zero",
        "subnormal",
        "negative_subnormal",
        "finite_normal",
        "infinity",
        "positive_infinity",
        "negative_infinity",
        "nan",
        "positive_nan",
        "negative_nan",
        "sign_bit_set",
        "nan_payloads_sha256",
    }
    item = _strict(value, keys, label)
    for name in keys - {"nan_payloads_sha256"}:
        require(_is_int(item[name]) and item[name] >= 0, f"{label}/{name} drift")
    require(_is_sha(item["nan_payloads_sha256"]), f"{label}/nan payload digest drift")
    require(
        item["positive_zero"]
        + item["negative_zero"]
        + item["subnormal"]
        + item["finite_normal"]
        + item["infinity"]
        + item["nan"]
        == BF16_NUMEL,
        f"{label} cardinality drift",
    )
    require(
        item["negative_subnormal"] <= item["subnormal"]
        and item["positive_infinity"] + item["negative_infinity"] == item["infinity"]
        and item["positive_nan"] + item["negative_nan"] == item["nan"]
        and item["sign_bit_set"] <= BF16_NUMEL,
        f"{label} classification partition drift",
    )
    return item


def _comparison(value: object, label: str) -> dict[str, Any]:
    keys = {
        "left_raw_bf16_le_sha256",
        "right_raw_bf16_le_sha256",
        "raw_uint16_equal",
        "left_classification",
        "right_classification",
        "contains_nan",
        "torch_equal",
        "torch_equal_policy",
        "classification_equal",
        "passed",
    }
    item = _strict(value, keys, label)
    left = _classification(item["left_classification"], f"{label}/left")
    right = _classification(item["right_classification"], f"{label}/right")
    require(
        _is_sha(item["left_raw_bf16_le_sha256"])
        and _is_sha(item["right_raw_bf16_le_sha256"])
        and item["left_raw_bf16_le_sha256"] == item["right_raw_bf16_le_sha256"],
        f"{label} separate raw BF16 SHA proof failed",
    )
    require(
        item["raw_uint16_equal"] is True
        and item["classification_equal"] is True
        and left == right
        and item["passed"] is True,
        f"{label} raw/classification equality failed",
    )
    contains_nan = left["nan"] != 0 or right["nan"] != 0
    require(item["contains_nan"] is contains_nan, f"{label} NaN presence drift")
    if contains_nan:
        require(
            item["torch_equal"] is None
            and item["torch_equal_policy"] == NAN_COMPARISON_POLICY,
            f"{label} NaN torch.equal policy drift",
        )
    else:
        require(
            item["torch_equal"] is True
            and item["torch_equal_policy"] == FINITE_COMPARISON_POLICY,
            f"{label} finite torch.equal policy drift",
        )
    return item


def _epoch(
    value: object,
    epoch: int,
    expected_spec: dict[str, Any],
    expected_input_hashes: dict[str, str],
) -> dict[str, Any]:
    keys = {
        "fixture_id",
        "spec",
        "zero_rows",
        "input_hashes_before",
        "input_hashes_after",
        "comparisons",
        "all_equal",
        "nan_equality_policy",
    }
    item = _strict(value, keys, f"epoch {epoch}")
    require(
        item["fixture_id"] == expected_spec["id"]
        and item["spec"] == expected_spec
        and item["zero_rows"] == _expected_zero_rows(expected_spec),
        f"epoch {epoch} corpus identity/zero-route drift",
    )
    before = _input_hashes(item["input_hashes_before"], f"epoch {epoch}/before")
    after = _input_hashes(item["input_hashes_after"], f"epoch {epoch}/after")
    require(
        before == expected_input_hashes == after,
        f"epoch {epoch} manifest-bound input hashes mutated",
    )
    names = {
        "control_routed_vs_literal_oracle",
        "candidate_diagnostic_routed_vs_literal_oracle",
        "candidate_diagnostic_routed_vs_control",
        "candidate_diagnostic_scaled_vs_literal_oracle",
        "control_scaled_literal_vs_literal_oracle",
        "candidate_diagnostic_scaled_vs_control_literal",
        "control_final_vs_literal_oracle",
        "candidate_production_final_vs_literal_oracle",
        "candidate_diagnostic_final_vs_literal_oracle",
        "candidate_diagnostic_final_vs_control",
        "control_final_vs_candidate_production",
        "candidate_production_vs_diagnostic_final",
        "candidate_repeat",
        "rank_order_bf16_sum",
        "fused_add_rms_norm_hidden",
        "fused_add_rms_norm_residual",
    }
    comparisons = _strict(item["comparisons"], names, f"epoch {epoch}/comparisons")
    for name in sorted(names):
        _comparison(comparisons[name], f"epoch {epoch}/{name}")
    require(
        item["all_equal"] is True and item["nan_equality_policy"] == NAN_POLICY,
        f"epoch {epoch} exactness claim drift",
    )
    return item


def _metadata(
    value: object,
    label: str,
    shape: list[int],
    dtype: str,
    stride: list[int],
    element_size: int,
) -> dict[str, Any]:
    keys = {
        "data_ptr",
        "shape",
        "stride",
        "dtype",
        "device",
        "numel",
        "element_size",
    }
    item = _strict(value, keys, label)
    require(
        _is_int(item["data_ptr"])
        and item["data_ptr"] > 0
        and item["shape"] == shape
        and item["stride"] == stride
        and item["dtype"] == dtype
        and item["device"] == "xpu:0"
        and item["numel"] == math.prod(shape)
        and item["element_size"] == element_size,
        f"{label} storage metadata drift",
    )
    return item


def _tensor_record(
    value: object,
    label: str,
    shape: list[int],
    dtype: str,
    stride: list[int],
    element_size: int,
) -> dict[str, Any]:
    item = _strict(value, {"metadata", "raw_le_sha256"}, label)
    _metadata(item["metadata"], f"{label}/metadata", shape, dtype, stride, element_size)
    require(_is_sha(item["raw_le_sha256"]), f"{label} raw digest drift")
    return item


def _timing(
    value: object,
    packet: dict[str, Any],
    expected_specs: list[dict[str, Any]],
    expected_hashes: dict[str, dict[str, str]],
    expected_final_hashes: dict[str, str],
) -> dict[str, Any]:
    keys = {
        "timing_label",
        "clock",
        "warm_cycles_per_arm",
        "blocks",
        "arm_order",
        "cycles_per_arm",
        "layers_per_cycle",
        "control_calls_per_primitive_per_arm",
        "candidate_calls_per_arm",
        "scheduled_control_selected_launches_per_cycle",
        "scheduled_candidate_selected_launches_per_cycle",
        "scheduled_fixture_rotation",
        "synchronization",
        "cpu_work_inside_event_interval",
        "storage_proof",
        "buffer_metadata_and_hash_before",
        "buffer_metadata_and_hash_after",
        "timed_block_output_comparisons",
        "blocks_detail",
        "candidate_block_wins",
        "median_saving_ms_per_47_layer_cycle",
        "passed_timing_threshold",
        "counter_evidence",
    }
    item = _strict(value, keys, "timing")
    fixed = {
        "timing_label": "preallocated_incumbent_moe_gather_then_laguna_m8_scale_add_vs_candidate_only",
        "clock": "torch.xpu.Event device elapsed time",
        "warm_cycles_per_arm": WARM_CYCLES,
        "blocks": ABBA_BLOCKS,
        "arm_order": "A-B-B-A",
        "cycles_per_arm": CYCLES_PER_ARM,
        "layers_per_cycle": LAYERS,
        "control_calls_per_primitive_per_arm": CYCLES_PER_ARM * LAYERS,
        "candidate_calls_per_arm": CYCLES_PER_ARM * LAYERS,
        "scheduled_control_selected_launches_per_cycle": 2 * LAYERS,
        "scheduled_candidate_selected_launches_per_cycle": LAYERS,
        "scheduled_fixture_rotation": "prebuilt_outside_timed_arms",
        "synchronization": "arm_boundaries_only",
        "cpu_work_inside_event_interval": "native dispatch calls only",
        "counter_evidence": "pending_counter_evidence",
    }
    require(
        all(item[name] == expected for name, expected in fixed.items()),
        "timing protocol declaration drift",
    )
    protocol = packet["protocol"]
    require(
        protocol["warm_cycles_per_arm"] == WARM_CYCLES
        and protocol["abba_blocks"] == ABBA_BLOCKS
        and protocol["cycles_per_arm_per_block"] == CYCLES_PER_ARM
        and protocol["control_launches_per_cycle"] == 2 * LAYERS
        and protocol["candidate_launches_per_cycle"] == LAYERS,
        "packet/runner timing protocol drift",
    )
    snapshot_keys = {"inputs", "outputs"}
    before = _strict(
        item["buffer_metadata_and_hash_before"], snapshot_keys, "timing before"
    )
    after = _strict(
        item["buffer_metadata_and_hash_after"], snapshot_keys, "timing after"
    )
    require(
        isinstance(before["inputs"], list)
        and isinstance(after["inputs"], list)
        and len(before["inputs"]) == len(after["inputs"]) == len(expected_specs),
        "timing corpus allocation count drift",
    )
    input_pointers: list[int] = []
    for index, (left, right, spec) in enumerate(
        zip(before["inputs"], after["inputs"], expected_specs, strict=True)
    ):
        fields = {"fixture_id", "routes", "weights", "shared", "route_map"}
        left_item = _strict(left, fields, f"timing input before {index}")
        right_item = _strict(right, fields, f"timing input after {index}")
        require(
            left_item["fixture_id"] == spec["id"]
            and right_item["fixture_id"] == spec["id"],
            f"timing input fixture order drift: {index}",
        )
        expected = expected_hashes[spec["id"]]
        for name, shape, dtype, stride, size, hash_name in (
            (
                "routes",
                [80, HIDDEN],
                "torch.bfloat16",
                [HIDDEN, 1],
                2,
                "routes_bf16_le_sha256",
            ),
            (
                "weights",
                [TOKENS, TOPK],
                "torch.float32",
                [TOPK, 1],
                4,
                "weights_fp32_le_sha256",
            ),
            (
                "shared",
                [TOKENS, HIDDEN],
                "torch.bfloat16",
                [HIDDEN, 1],
                2,
                "shared_bf16_le_sha256",
            ),
            (
                "route_map",
                [TOKENS, TOPK],
                "torch.int32",
                [TOPK, 1],
                4,
                "route_map_uint32_le_sha256",
            ),
        ):
            left_record = _tensor_record(
                left_item[name],
                f"timing before {index}/{name}",
                shape,
                dtype,
                stride,
                size,
            )
            right_record = _tensor_record(
                right_item[name],
                f"timing after {index}/{name}",
                shape,
                dtype,
                stride,
                size,
            )
            require(
                left_record == right_record
                and left_record["raw_le_sha256"] == expected[hash_name],
                f"timing input mutation/fixture hash drift: {index}/{name}",
            )
            metadata = left_record["metadata"]
            input_pointers.append(metadata["data_ptr"])
    output_names = (
        "control_routed",
        "control_final",
        "candidate_final",
        "candidate_repeat",
    )
    require(
        isinstance(before["outputs"], list)
        and isinstance(after["outputs"], list)
        and len(before["outputs"]) == len(after["outputs"]) == LAYERS,
        "timing output preallocation count drift",
    )
    output_pointers: list[int] = []
    for slot, (left, right) in enumerate(
        zip(before["outputs"], after["outputs"], strict=True)
    ):
        fields = {"slot", *output_names}
        left_item = _strict(left, fields, f"timing output before {slot}")
        right_item = _strict(right, fields, f"timing output after {slot}")
        require(
            left_item["slot"] == right_item["slot"] == slot,
            f"timing output slot drift: {slot}",
        )
        for name in output_names:
            left_record = _tensor_record(
                left_item[name],
                f"timing output before {slot}/{name}",
                [TOKENS, HIDDEN],
                "torch.bfloat16",
                [HIDDEN, 1],
                2,
            )
            right_record = _tensor_record(
                right_item[name],
                f"timing output after {slot}/{name}",
                [TOKENS, HIDDEN],
                "torch.bfloat16",
                [HIDDEN, 1],
                2,
            )
            require(
                left_record["metadata"] == right_record["metadata"],
                f"timing output allocation/storage drift: {slot}/{name}",
            )
            output_pointers.append(left_record["metadata"]["data_ptr"])
        require(
            left_item["control_final"]["raw_le_sha256"]
            == left_item["candidate_final"]["raw_le_sha256"]
            == left_item["candidate_repeat"]["raw_le_sha256"],
            f"timing exactness preflight digest drift: {slot}",
        )
    require(
        len(set(input_pointers)) == len(input_pointers)
        and len(set(output_pointers)) == len(output_pointers)
        and set(input_pointers).isdisjoint(output_pointers),
        "timing buffers alias",
    )
    proof = _strict(
        item["storage_proof"],
        {
            "input_storage_count",
            "output_storage_count",
            "all_storage_unique_and_nonaliasing",
            "input_metadata_and_hashes_unchanged",
            "output_metadata_unchanged",
        },
        "timing storage proof",
    )
    require(
        proof
        == {
            "input_storage_count": len(input_pointers),
            "output_storage_count": len(output_pointers),
            "all_storage_unique_and_nonaliasing": True,
            "input_metadata_and_hashes_unchanged": True,
            "output_metadata_unchanged": True,
        },
        "timing storage proof contradicts evidence",
    )
    blocks = item["blocks_detail"]
    require(
        isinstance(blocks, list) and len(blocks) == ABBA_BLOCKS,
        "ABBA block count drift",
    )
    timed_outputs = item["timed_block_output_comparisons"]
    require(
        isinstance(timed_outputs, list) and len(timed_outputs) == ABBA_BLOCKS,
        "timed block output evidence count drift",
    )
    require(
        set(expected_final_hashes) == {spec["id"] for spec in expected_specs}
        and all(_is_sha(value) for value in expected_final_hashes.values()),
        "literal-oracle digest inventory drift",
    )
    savings: list[float] = []
    for block_index, block in enumerate(blocks):
        block_keys = {
            "block",
            "fixture_indices",
            "A1_control_elapsed_ns",
            "B1_candidate_elapsed_ns",
            "B2_candidate_elapsed_ns",
            "A2_control_elapsed_ns",
            "paired_control_ms_per_47_layer_cycle",
            "paired_candidate_ms_per_47_layer_cycle",
            "saving_ms_per_47_layer_cycle",
        }
        detail = _strict(block, block_keys, f"ABBA block {block_index}")
        expected_indices = [
            (block_index * LAYERS + slot) % len(expected_specs)
            for slot in range(LAYERS)
        ]
        require(
            detail["block"] == block_index
            and detail["fixture_indices"] == expected_indices,
            f"ABBA rotation/order drift: {block_index}",
        )
        raw_names = (
            "A1_control_elapsed_ns",
            "B1_candidate_elapsed_ns",
            "B2_candidate_elapsed_ns",
            "A2_control_elapsed_ns",
        )
        raw = [detail[name] for name in raw_names]
        require(
            all(_is_int(value) and value > 0 for value in raw),
            f"ABBA device-event nanoseconds malformed: {block_index}",
        )
        control = (raw[0] + raw[3]) / (2 * CYCLES_PER_ARM) / 1_000_000
        candidate = (raw[1] + raw[2]) / (2 * CYCLES_PER_ARM) / 1_000_000
        saving = control - candidate
        for name, expected in (
            ("paired_control_ms_per_47_layer_cycle", control),
            ("paired_candidate_ms_per_47_layer_cycle", candidate),
            ("saving_ms_per_47_layer_cycle", saving),
        ):
            observed = detail[name]
            require(
                isinstance(observed, (int, float))
                and not isinstance(observed, bool)
                and math.isfinite(float(observed))
                and abs(float(observed) - expected) <= 1e-12,
                f"ABBA device-ns arithmetic drift: {block_index}/{name}",
            )
        output_block = _strict(
            timed_outputs[block_index],
            {"block", "outputs"},
            f"timed block output evidence {block_index}",
        )
        output_records = output_block["outputs"]
        require(
            output_block["block"] == block_index
            and isinstance(output_records, list)
            and len(output_records) == LAYERS,
            f"timed block output inventory drift: {block_index}",
        )
        for slot, (record, fixture_index) in enumerate(
            zip(output_records, expected_indices, strict=True)
        ):
            output = _strict(
                record,
                {
                    "slot",
                    "fixture_index",
                    "fixture_id",
                    "literal_oracle_raw_bf16_le_sha256",
                    "control_final_vs_candidate_final",
                },
                f"timed block output {block_index}/{slot}",
            )
            fixture_id = expected_specs[fixture_index]["id"]
            comparison = _comparison(
                output["control_final_vs_candidate_final"],
                f"timed block output {block_index}/{slot}/control-vs-candidate",
            )
            require(
                output["slot"] == slot
                and output["fixture_index"] == fixture_index
                and output["fixture_id"] == fixture_id
                and output["literal_oracle_raw_bf16_le_sha256"]
                == expected_final_hashes[fixture_id]
                and comparison["left_raw_bf16_le_sha256"]
                == comparison["right_raw_bf16_le_sha256"]
                == expected_final_hashes[fixture_id],
                f"timed block output/literal-oracle binding drift: {block_index}/{slot}",
            )
        savings.append(saving)
    wins = sum(saving > 0 for saving in savings)
    median = statistics.median(savings)
    final_outputs = timed_outputs[-1]["outputs"]
    for slot, detail in enumerate(final_outputs):
        comparison = detail["control_final_vs_candidate_final"]
        require(
            comparison["left_raw_bf16_le_sha256"]
            == after["outputs"][slot]["control_final"]["raw_le_sha256"]
            and comparison["right_raw_bf16_le_sha256"]
            == after["outputs"][slot]["candidate_final"]["raw_le_sha256"],
            f"post-timed comparison is not bound to retained output buffers: {slot}",
        )
    require(
        item["candidate_block_wins"] == wins
        and isinstance(item["median_saving_ms_per_47_layer_cycle"], (int, float))
        and not isinstance(item["median_saving_ms_per_47_layer_cycle"], bool)
        and math.isfinite(float(item["median_saving_ms_per_47_layer_cycle"]))
        and abs(float(item["median_saving_ms_per_47_layer_cycle"]) - median) <= 1e-12,
        "timing aggregate arithmetic drift",
    )
    require(
        wins >= protocol["minimum_wins"] == 28
        and median >= protocol["minimum_median_saving_ms_per_47_layer_cycle"] == 0.15
        and item["passed_timing_threshold"] is True,
        "per-card timing threshold failed",
    )
    return {"candidate_block_wins": wins, "median_saving_ms_per_47_layer_cycle": median}


def _runtime_binding(
    value: object, physical: dict[str, Any], label: str
) -> dict[str, Any]:
    keys = {
        "torch_runtime_uuid",
        "torch_runtime_uuid_bytes_hex",
        "runtime_uuid",
        "runtime_uuid_bytes_hex",
        "runtime_uuid_mapping",
        "pci_bdf_address",
    }
    item = _strict(value, keys, label)
    try:
        torch_bytes = bytes.fromhex(item["torch_runtime_uuid_bytes_hex"])
        runtime_bytes = bytes.fromhex(item["runtime_uuid_bytes_hex"])
        torch_uuid = str(uuid.UUID(bytes=torch_bytes)).lower()
        runtime_uuid = str(uuid.UUID(bytes=runtime_bytes)).lower()
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"{label} UUID bytes malformed") from error
    require(
        len(torch_bytes) == len(runtime_bytes) == 16
        and item["torch_runtime_uuid"] == torch_uuid
        and item["runtime_uuid"] == runtime_uuid
        and runtime_bytes == torch_bytes[::-1]
        and runtime_uuid == physical["uuid"]
        and item["runtime_uuid_mapping"]
        == "xpu_smi_uuid_is_reverse_of_torch_level_zero_bytes"
        and item["pci_bdf_address"] == physical["pci_bdf_address"],
        f"{label} UUID/BDF binding drift",
    )
    return item


def _expected_runtime_environment(card: dict[str, Any]) -> dict[str, Any]:
    path_keys = (
        "HOME",
        "TMPDIR",
        "TMP",
        "TEMP",
        "XDG_CACHE_HOME",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "XDG_STATE_HOME",
        "HF_HOME",
        "TRANSFORMERS_CACHE",
        "VLLM_CACHE_ROOT",
        "TRITON_CACHE_DIR",
        "NUMBA_CACHE_DIR",
        "PYTHONPYCACHEPREFIX",
        "SYCL_CACHE_DIR",
        "TORCHINDUCTOR_CACHE_DIR",
    )
    return {
        "runtime_root": card["runtime_root"],
        "environment_paths": {name: card["environment"][name] for name in path_keys},
    }


def _runtime_artifacts(
    root: Path,
    packet: dict[str, Any],
    card: dict[str, Any],
    packet_sha: str,
    fixture_sha: str,
    native_modules: dict[str, Any],
) -> None:
    rank = card["rank"]
    physical = card["physical"]
    expected_sysfs = {
        "drm_device": physical["drm_device"],
        "pci_bdf_address": physical["pci_bdf_address"],
        "vendor": "0x8086",
        "device": "0xe223",
        "sysfs_device": str(
            (
                Path("/sys/class/drm") / Path(physical["drm_device"]).name / "device"
            ).resolve(strict=True)
        ),
    }
    preimport = _read(root / PREIMPORT, "preimport seal")
    require(
        preimport
        == {
            "format": "laguna-m8-gather-finalize-preimport-seal-v2",
            "packet_sha256": packet_sha,
            "fixture_manifest_sha256": fixture_sha,
            "rank": rank,
            "physical": physical,
            "sysfs": expected_sysfs,
            "evidence_directories": [
                ".",
                "home",
                "tmp",
                PRE_EPOCHS,
                POST_EPOCHS,
                "cache",
                "cache/pycache",
                "cache/sycl",
                "cache/torchinductor",
            ],
            "runtime_environment": _expected_runtime_environment(card),
            "torch_or_native_imported": False,
        },
        "preimport seal identity/runtime drift",
    )
    started = _read(root / STARTED, "tensor-start checkpoint")
    require(
        started
        == {
            "format": "laguna-m8-gather-finalize-tensor-start-v2",
            "packet_sha256": packet_sha,
            "rank": rank,
            "tensor_work_started": True,
            "native_modules": native_modules,
        },
        "tensor-start native-origin drift",
    )
    binding_checkpoint = _read(root / RUNTIME_BINDING, "runtime binding checkpoint")
    binding_keys = {"format", "packet_sha256", "rank", "physical", "sysfs", "torch"}
    binding = _strict(binding_checkpoint, binding_keys, "runtime binding checkpoint")
    require(
        binding["format"] == "laguna-m8-gather-finalize-runtime-card-binding-v2"
        and binding["packet_sha256"] == packet_sha
        and binding["rank"] == rank
        and binding["physical"] == physical
        and binding["sysfs"] == expected_sysfs,
        "runtime checkpoint identity drift",
    )
    _runtime_binding(binding["torch"], physical, "runtime binding checkpoint/torch")


def _native_modules(value: object, packet: dict[str, Any]) -> dict[str, Any]:
    names = {
        "vllm_xpu_kernels._C": "_C.abi3.so",
        "vllm_xpu_kernels._xpu_C": "_xpu_C.abi3.so",
        "vllm_xpu_kernels._moe_C": "_moe_C.abi3.so",
    }
    modules = _strict(value, set(names), "native module origins")
    installed = packet["binary_manifest"]["installed"]
    for module, filename in names.items():
        expected = installed[filename]
        require(
            modules[module]
            == {"path": expected["resolved_path"], "sha256": expected["sha256"]},
            f"loaded native module identity drift: {module}",
        )
    return modules


def _expected_checkpoints(expected_specs: list[dict[str, Any]]) -> list[str]:
    return [
        PREIMPORT,
        STARTED,
        RUNTIME_BINDING,
        *[
            f"{PRE_EPOCHS}/epoch-{index:03d}.json"
            for index in range(len(expected_specs))
        ],
        TIMING,
        *[
            f"{POST_EPOCHS}/epoch-{index:03d}.json"
            for index in range(len(expected_specs))
        ],
    ]


def _tree_inventory(root: Path, expected_checkpoints: list[str]) -> None:
    expected_dirs = {
        ".",
        "home",
        "tmp",
        PRE_EPOCHS,
        POST_EPOCHS,
        "cache",
        "cache/pycache",
        "cache/sycl",
        "cache/torchinductor",
    }
    actual_dirs: set[str] = set()
    actual_files: set[str] = set()
    for current, dirs, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        relative = "." if current_path == root else str(current_path.relative_to(root))
        require(
            not current_path.is_symlink(), f"symlinked evidence directory: {relative}"
        )
        actual_dirs.add(relative)
        for name in dirs + files:
            candidate = current_path / name
            require(not candidate.is_symlink(), f"symlinked evidence path: {candidate}")
        for name in files:
            candidate = current_path / name
            require(candidate.is_file(), f"nonregular evidence file: {candidate}")
            actual_files.add(str(candidate.relative_to(root)))
    require(
        actual_dirs == expected_dirs, "unexpected/missing card evidence directories"
    )
    require(
        actual_files == set(expected_checkpoints) | {RESULT},
        "unexpected/missing card evidence files",
    )


def validate_card(
    result_path: Path,
    packet: dict[str, Any],
    rank: int,
    packet_sha: str,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    cards = packet["cards"]
    require(_is_int(rank) and 0 <= rank < len(cards), "invalid card rank")
    card = cards[rank]
    expected_path = Path(card["result"])
    require(
        result_path == expected_path, f"result argv is not card {rank}'s canonical path"
    )
    root = _directory(expected_path.parent, f"card {rank} evidence root")
    result = _read(result_path, f"card {rank} result")
    expected_keys = {
        "format",
        "status",
        "passed",
        "timing_exactness_passed",
        "counter_phase_required",
        "counter_phase_complete",
        "full_component_pass",
        "endpoint_authorized",
        "authorization_packet",
        "fixture_manifest",
        "rank",
        "physical",
        "runtime_binding",
        "native_modules",
        "exactness",
        "timing",
        "post_timing_replay",
        "integration",
        "counter_evidence",
        "prior_incumbent_scale_add_exhaustive_evidence",
        "downstream",
        "terminal",
        "checkpoints",
        "checkpoint_sha256",
    }
    _strict(result, expected_keys, f"card {rank} result")
    fixture = packet["fixture"]
    require(
        result["format"] == "laguna-m8-gather-finalize-component-result-v2"
        and result["status"] == "component_timing_pass_pending_mandatory_counters"
        and result["passed"] is True
        and result["timing_exactness_passed"] is True
        and result["counter_phase_required"] is True
        and result["counter_phase_complete"] is False
        and result["full_component_pass"] is False
        and result["endpoint_authorized"] is False
        and result["authorization_packet"]
        == {"path": packet["packet_path"], "sha256": packet_sha}
        and result["fixture_manifest"]
        == {
            "path": fixture["path"],
            "sha256": fixture["sha256"],
            "corpus_version": manifest["corpus_version"],
        }
        and result["rank"] == rank
        and result["physical"] == card["physical"]
        and result["counter_evidence"] == "pending_counter_evidence"
        and result["downstream"] == contract.FALSE_ACTIONS
        and result["terminal"]
        == {
            "status": "component_timing_pass_pending_mandatory_counters",
            "passed": True,
            "full_component_pass": False,
        },
        f"card {rank} Phase-A status/identity drift",
    )
    native_modules = _native_modules(result["native_modules"], packet)
    _runtime_binding(
        result["runtime_binding"],
        card["physical"],
        f"card {rank} result runtime binding",
    )
    _runtime_artifacts(
        root, packet, card, packet_sha, fixture["sha256"], native_modules
    )
    expected_specs = _expected_specs(manifest)
    expected_hashes = manifest["expected_cpu_input_hashes"]
    checkpoints = _expected_checkpoints(expected_specs)
    require(
        result["checkpoints"] == checkpoints,
        f"card {rank} checkpoint inventory/order drift",
    )
    checkpoint_hashes = _strict(
        result["checkpoint_sha256"], set(checkpoints), f"card {rank} checkpoint hashes"
    )
    for relative in checkpoints:
        require(
            _is_sha(checkpoint_hashes[relative])
            and _sha(root / relative) == checkpoint_hashes[relative],
            f"card {rank} checkpoint digest drift: {relative}",
        )
    pre = _strict(
        result["exactness"],
        {
            "passed",
            "nan_equality_policy",
            "pre_epochs",
            "fixture_count",
            "random_full_fixture_count",
            "finite_bf16_values_per_boundary",
            "production_rmsnorm_static_input_hashes",
        },
        f"card {rank} exactness",
    )
    require(
        pre["passed"] is True
        and pre["nan_equality_policy"] == NAN_POLICY
        and pre["fixture_count"] == len(expected_specs)
        and pre["random_full_fixture_count"] == contract.RANDOM_FIXTURES
        and pre["finite_bf16_values_per_boundary"] == contract.FINITE_BF16_COUNT
        and pre["production_rmsnorm_static_input_hashes"]
        == manifest["downstream"]["expected_cpu_static_input_hashes"],
        f"card {rank} corpus/downstream exactness summary drift",
    )
    pre_epochs = pre["pre_epochs"]
    require(
        isinstance(pre_epochs, list) and len(pre_epochs) == len(expected_specs),
        "pre corpus count drift",
    )
    post = _strict(
        result["post_timing_replay"],
        {"required", "passed", "epochs"},
        f"card {rank} replay",
    )
    post_epochs = post["epochs"]
    require(
        post["required"] is True
        and post["passed"] is True
        and isinstance(post_epochs, list)
        and len(post_epochs) == len(expected_specs),
        f"card {rank} post replay count/status drift",
    )
    pre_final_digests: list[str] = []
    expected_final_hashes: dict[str, str] = {}
    for index, (pre_value, post_value, spec) in enumerate(
        zip(pre_epochs, post_epochs, expected_specs, strict=True)
    ):
        expected = expected_hashes[spec["id"]]
        pre_epoch = _epoch(pre_value, index, spec, expected)
        post_epoch = _epoch(post_value, index, spec, expected)
        require(
            contract.canonical(pre_epoch) == contract.canonical(post_epoch)
            and _read(
                root / PRE_EPOCHS / f"epoch-{index:03d}.json", f"pre epoch {index}"
            )
            == pre_epoch
            and _read(
                root / POST_EPOCHS / f"epoch-{index:03d}.json", f"post epoch {index}"
            )
            == post_epoch,
            f"card {rank} pre/post replay checkpoint mismatch: {index}",
        )
        final_digest = pre_epoch["comparisons"][
            "candidate_production_final_vs_literal_oracle"
        ]["left_raw_bf16_le_sha256"]
        pre_final_digests.append(final_digest)
        expected_final_hashes[spec["id"]] = final_digest
    timing = _timing(
        result["timing"],
        packet,
        expected_specs,
        expected_hashes,
        expected_final_hashes,
    )
    require(
        _read(root / TIMING, "timing checkpoint") == result["timing"],
        f"card {rank} timing split-brain",
    )
    integration = _strict(
        result["integration"],
        {"status", "evidence_ids", "contract"},
        f"card {rank} integration",
    )
    require(
        integration
        == {
            "status": "packet_bound_integration_evidence_only",
            "evidence_ids": packet["integration_evidence_ids"],
            "contract": packet["integration_contract"],
        }
        and result["prior_incumbent_scale_add_exhaustive_evidence"]
        == {
            "evidence_id": packet["prior_incumbent_scale_add_exhaustive_evidence"][
                "evidence_id"
            ],
            "path": packet["prior_incumbent_scale_add_exhaustive_evidence"]["path"],
            "sha256": packet["prior_incumbent_scale_add_exhaustive_evidence"]["sha256"],
        },
        f"card {rank} integration/W2 binding drift",
    )
    _tree_inventory(root, checkpoints)
    return {
        "rank": rank,
        "physical": card["physical"],
        "result_path": str(result_path),
        "result_sha256": _sha(result_path),
        "fixture_manifest_sha256": fixture["sha256"],
        "fixture_count": len(expected_specs),
        "pre_epoch_sequence_sha256": hashlib.sha256(
            "".join(pre_final_digests).encode()
        ).hexdigest(),
        "timing": timing,
    }


def _write_out(path: Path, value: dict[str, Any]) -> None:
    require(
        path.is_absolute() and path.parent.is_dir() and not path.parent.is_symlink(),
        "unsafe aggregate parent",
    )
    require(
        not path.exists() and not path.is_symlink(), "aggregate path already exists"
    )
    descriptor = os.open(
        path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644
    )
    try:
        payload = contract.canonical(value) + b"\n"
        offset = 0
        while offset < len(payload):
            written = os.write(descriptor, payload[offset:])
            require(written > 0, "short aggregate write")
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(parent)
    finally:
        os.close(parent)


def _authorization(path: Path) -> tuple[dict[str, Any], str, dict[str, Any]]:
    authorization = _regular(path, "authorization")
    packet = _read(authorization, "authorization")
    require(str(authorization) == packet.get("packet_path"), "authorization path drift")
    # The contract's own validator rechecks host, source, pinned modules,
    # binary archives, W2 identity, fixture location, and all no-action flags.
    contract.validate_execution_packet(packet, authorization)
    for name, record in packet["tools"].items():
        require(
            _sha(contract.MAIN / record["path"]) == record["sha256"],
            f"packet-bound tool hash drift: {name}",
        )
    fixture_path = _regular(Path(packet["fixture"]["path"]), "fixture manifest")
    manifest = contract.validate_fixture_manifest(fixture_path)
    require(
        _sha(fixture_path) == packet["fixture"]["sha256"], "fixture packet digest drift"
    )
    return packet, _sha(authorization), manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--card-result", type=Path, action="append", required=True)
    parser.add_argument("--single-card-rank", type=int)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    packet, packet_sha, manifest = _authorization(args.authorization)
    if args.single_card_rank is not None:
        rank = args.single_card_rank
        require(
            args.out is None and len(args.card_result) == 1,
            "single-card mode schema drift",
        )
        require(0 <= rank < len(packet["cards"]), "single-card rank drift")
        require(
            sys.argv == packet["cards"][rank]["validator_argv"][1:],
            "single-card argv drift",
        )
        validate_card(args.card_result[0], packet, rank, packet_sha, manifest)
        return 0

    require(
        args.out is not None and len(args.card_result) == 4,
        "four-card mode schema drift",
    )
    require(sys.argv == packet["analyzer_argv"][1:], "four-card analyzer argv drift")
    require(args.out == Path(packet["aggregate_path"]), "aggregate argv path drift")
    expected_paths = [Path(card["result"]) for card in packet["cards"]]
    require(
        set(args.card_result) == set(expected_paths), "four-card result inventory drift"
    )
    summaries = [
        validate_card(expected_paths[rank], packet, rank, packet_sha, manifest)
        for rank in range(4)
    ]
    aggregate = {
        "format": "laguna-m8-gather-finalize-four-card-timing-exactness-aggregate-v2",
        "status": "component_timing_pass_pending_mandatory_counters",
        "timing_exactness_passed": True,
        "counter_phase_required": True,
        "counter_phase_complete": False,
        "full_component_pass": False,
        "endpoint_authorized": False,
        "packet_sha256": packet_sha,
        "fixture_manifest": {
            "path": packet["fixture"]["path"],
            "sha256": packet["fixture"]["sha256"],
            "corpus_version": manifest["corpus_version"],
        },
        "cards": summaries,
        "downstream": contract.FALSE_ACTIONS,
    }
    _write_out(args.out, aggregate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
