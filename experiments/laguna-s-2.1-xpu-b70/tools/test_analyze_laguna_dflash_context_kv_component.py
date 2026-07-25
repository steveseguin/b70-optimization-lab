#!/usr/bin/env python3
"""CPU-only tamper tests for the DFlash context-KV component analyzer."""

from __future__ import annotations

import copy
import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_laguna_dflash_context_kv_component as gate


def digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def record(shape: list[int], label: str, pointer: int) -> dict:
    return {
        "shape": shape,
        "stride": gate.contiguous_stride(shape),
        "dtype": "torch.bfloat16",
        "device": "xpu:0",
        "data_ptr": pointer,
        "storage_offset": 0,
        "nbytes": 2 * __import__("math").prod(shape),
        "sha256": digest(label),
    }


def comparison(shape: list[int], label: str, pointer: int) -> dict:
    tensor = record(shape, label, pointer)
    return {
        "equal": True,
        "actual": tensor,
        "expected_sha256": tensor["sha256"],
    }


def branch_fixture() -> dict:
    pointer_map = {
        str(width): [100000 + width * 10 + offset for offset in range(4)]
        for width in gate.EXPECTED_WIDTHS
    }
    rows = []
    for width in gate.EXPECTED_WIDTHS:
        for repeat in range(2):
            label = f"C{width}-r{repeat}"
            rows.append(
                {
                    "width": width,
                    "repeat": repeat,
                    "context_sha256": digest(label),
                    "workspace_pointers": pointer_map[str(width)],
                    "warnings": [],
                    "boundaries": {
                        "normed_context": comparison(
                            [6, width, 3072], f"{label}-normed", 200001
                        ),
                        "flat": comparison([6, width, 512], f"{label}-flat", 200002),
                        "projected_k": comparison(
                            [6, width, 2, 128], f"{label}-k", 200003
                        ),
                        "projected_v": comparison(
                            [6, width, 2, 128], f"{label}-v", 200004
                        ),
                        "normalized_k": comparison(
                            [6, width, 2, 128], f"{label}-knorm", 200005
                        ),
                        "rope_k": comparison(
                            [6, width, 2, 128], f"{label}-rope", 200006
                        ),
                    },
                    "cache_layers": [
                        comparison(
                            [4, 2, 16, 256],
                            f"{label}-cache-{layer}",
                            300000 + layer,
                        )
                        for layer in range(6)
                    ],
                }
            )
    return {
        "branch": "actual_no_bias",
        "bias": False,
        "rows": rows,
        "workspace_widths": gate.EXPECTED_WIDTHS,
        "workspace_pointers": pointer_map,
        "fallback_widths": [9],
    }


def test_valid_branch_fixture_passes() -> None:
    name, contexts = gate.validate_branch(branch_fixture(), rank=0)
    assert name == "actual_no_bias"
    assert len(contexts) == 16


@pytest.mark.parametrize(
    "mutation",
    [
        "digest",
        "shape",
        "pointer_alias",
        "pointer_reuse",
        "context_duplicate",
        "cache_count",
        "branch_label",
    ],
)
def test_branch_tampering_fails(mutation: str) -> None:
    value = copy.deepcopy(branch_fixture())
    if mutation == "digest":
        value["rows"][0]["boundaries"]["flat"]["expected_sha256"] = digest("wrong")
    elif mutation == "shape":
        value["rows"][0]["boundaries"]["projected_k"]["actual"]["shape"] = [1]
    elif mutation == "pointer_alias":
        value["rows"][0]["workspace_pointers"][1] = value["rows"][0][
            "workspace_pointers"
        ][0]
    elif mutation == "pointer_reuse":
        value["rows"][1]["workspace_pointers"] = [9, 10, 11, 12]
    elif mutation == "context_duplicate":
        value["rows"][1]["context_sha256"] = value["rows"][0]["context_sha256"]
    elif mutation == "cache_count":
        value["rows"][0]["cache_layers"].pop()
    elif mutation == "branch_label":
        value["branch"] = "invented"
    with pytest.raises(SystemExit):
        gate.validate_branch(value, rank=0)


def capture_fixture() -> dict:
    hashes = [digest(f"workspace-{index}") for index in range(4)]
    cache_hashes = [digest(f"cache-{index}") for index in range(6)]
    context_hash = digest("capture-context")
    return {
        "capture_rejection": {
            "eager_false_before": True,
            "capture_true": True,
            "rejection_type": "RuntimeError",
            "rejection_message": (
                "Laguna DFlash context-KV workspace is forbidden during capture"
            ),
            "workspace_widths_before_after": [[1], [1]],
            "workspace_pointers_before": [11, 12, 13, 14],
            "workspace_pointers_after": [11, 12, 13, 14],
            "workspace_hashes_before": list(hashes),
            "workspace_hashes_after": list(hashes),
            "cache_hashes_before": list(cache_hashes),
            "cache_hashes_after": list(cache_hashes),
            "context_sha256_before_after": [context_hash, context_hash],
            "eager_false_after": True,
        }
    }


def test_valid_capture_rejection_passes() -> None:
    gate.validate_capture_rejection(capture_fixture(), rank=0)


@pytest.mark.parametrize("field", ["capture_true", "workspace", "cache", "context"])
def test_capture_rejection_tampering_fails(field: str) -> None:
    value = copy.deepcopy(capture_fixture())
    record = value["capture_rejection"]
    if field == "capture_true":
        record["capture_true"] = False
    elif field == "workspace":
        record["workspace_hashes_after"][0] = digest("mutated")
    elif field == "cache":
        record["cache_hashes_after"][0] = digest("mutated")
    elif field == "context":
        record["context_sha256_before_after"][1] = digest("mutated")
    with pytest.raises(SystemExit):
        gate.validate_capture_rejection(value, rank=0)
