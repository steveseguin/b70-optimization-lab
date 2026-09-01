#!/usr/bin/env python3
"""CPU-only contracts for the HC exact-confirmation summarizer."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).with_name(
    "summarize-hc-combine-norm-exact-confirmation.py"
)
SPEC = importlib.util.spec_from_file_location("q38_hc_exact_summary", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _arm(sentinel: str, seed: int, arm: str, authority: str | None, timing: float):
    expected = MODULE.EXPECTED_SENTINELS[sentinel]
    hashes = [f"{index:064x}" for index in range(100)]
    return {
        "status": "pass",
        "classification": "qwen38_hc_combine_norm_exact_xpu_graph_component",
        "identity": {
            "model_path": MODULE.MODEL_PATH,
            "model_revision": MODULE.MODEL_REVISION,
            "model_index_sha256": MODULE.MODEL_INDEX_SHA256,
            "model_config_sha256": MODULE.MODEL_CONFIG_SHA256,
            "model_mount": {
                "source": "/dev/sda2",
                "fstype": "fuseblk",
                "target": "/mnt/usb-models",
            },
            "sentinel": sentinel,
            "layer": expected["layer"],
            "role": expected["role"],
            "seed": seed,
            "weight": {
                **expected,
                "shard_path": f"{MODULE.MODEL_PATH}/{expected['shard']}",
            },
            "authority_source": MODULE.AUTHORITY_SOURCE,
            "authority_source_sha256": MODULE.AUTHORITY_SOURCE_SHA256,
            "candidate_core": MODULE.CANDIDATE_CORE,
            "candidate_core_sha256": MODULE.CANDIDATE_CORE_SHA256,
            "shape": {
                "residual": [1, 10240],
                "block_output": [1, 2560],
                "injection_logits": [1, 4],
                "norm_weight": [10240],
                "hc_count": 4,
            },
            "dtype": "bfloat16",
        },
        "treatment": {
            "arm": arm,
            "sigmoid_changed": False,
            "rsqrt_changed": False,
            "arithmetic_order_changed": False,
            "explicit_bf16_combine_rounding_preserved": True,
        },
        "correctness": {
            "calls_per_graph_cycle": 95,
            "exact_replays": 100,
            "both_outputs_exact_to_eager_authority": True,
            "unique_graph_hashes": 100,
            "graph_hashes": hashes,
            "control_authority_path": authority,
            "matches_control_authority": True,
            "adversarial_bf16_passed": True,
            "adversarial_pair_sha256": "a" * 64,
            "cached_affine_validated_before_capture": True,
        },
        "graph": {
            "timing_excludes_input_copy_and_exactness_checks": True,
            "warmups": 10,
            "batches": 9,
            "iterations_per_batch": 50,
            "cycle_median_us": timing,
        },
    }


def _fixture(root: Path, *, candidate_us: float = 9000.0) -> None:
    for sentinel in MODULE.SENTINELS:
        for seed in MODULE.SEEDS:
            cell = f"{sentinel}-s{seed}"
            before = (root / f"{cell}-control-before.jsonl").resolve()
            for arm, timing in (
                ("control-before", 10000.0),
                ("candidate", candidate_us),
                ("control-after", 10050.0),
            ):
                authority = None if arm == "control-before" else str(before)
                (root / f"{cell}-{arm}.jsonl").write_text(
                    json.dumps(_arm(sentinel, seed, arm, authority, timing)) + "\n"
                )
                (root / f"{cell}-{arm}.exit-code").write_text("0\n")


def test_passes_exact_material_candidate(tmp_path: Path) -> None:
    _fixture(tmp_path)
    result = MODULE.summarize(tmp_path)
    assert result["status"] == "pass"
    assert result["gates"]["all_12_cells_exact"] is True
    assert result["gates"]["material_five_percent_or_one_ms"] is True


def test_rejects_hash_mismatch(tmp_path: Path) -> None:
    _fixture(tmp_path)
    path = tmp_path / "l0-attn-s20260826-candidate.jsonl"
    value = json.loads(path.read_text())
    value["correctness"]["graph_hashes"][1] = "f" * 64
    path.write_text(json.dumps(value) + "\n")
    assert MODULE.summarize(tmp_path)["status"] == "failed_closed"


def test_rejects_duplicate_graph_hashes_even_if_claimed_unique(tmp_path: Path) -> None:
    _fixture(tmp_path)
    path = tmp_path / "l0-attn-s20260826-candidate.jsonl"
    value = json.loads(path.read_text())
    value["correctness"]["graph_hashes"][1] = value["correctness"]["graph_hashes"][0]
    path.write_text(json.dumps(value) + "\n")
    assert value["correctness"]["unique_graph_hashes"] == 100
    assert MODULE.summarize(tmp_path)["status"] == "failed_closed"


def test_rejects_frozen_identity_drift_in_all_three_arms(tmp_path: Path) -> None:
    _fixture(tmp_path)
    for arm in MODULE.ARMS:
        path = tmp_path / f"l47-attn-s20260827-{arm}.jsonl"
        value = json.loads(path.read_text())
        value["identity"]["weight"]["weight_sha256"] = "0" * 64
        path.write_text(json.dumps(value) + "\n")
    assert MODULE.summarize(tmp_path)["status"] == "failed_closed"


def test_rejects_adversarial_hash_drift(tmp_path: Path) -> None:
    _fixture(tmp_path)
    path = tmp_path / "l0-mlp-s20260830-control-after.jsonl"
    value = json.loads(path.read_text())
    value["correctness"]["adversarial_pair_sha256"] = "b" * 64
    path.write_text(json.dumps(value) + "\n")
    assert MODULE.summarize(tmp_path)["status"] == "failed_closed"


def test_rejects_subthreshold_candidate(tmp_path: Path) -> None:
    _fixture(tmp_path, candidate_us=9800.0)
    result = MODULE.summarize(tmp_path)
    assert result["status"] == "failed_closed"
    assert result["gates"]["material_five_percent_or_one_ms"] is False


def test_rejects_control_drift(tmp_path: Path) -> None:
    _fixture(tmp_path)
    path = tmp_path / "l47-mlp-s20260830-control-after.jsonl"
    value = json.loads(path.read_text())
    value["graph"]["cycle_median_us"] = 11000.0
    path.write_text(json.dumps(value) + "\n")
    assert MODULE.summarize(tmp_path)["status"] == "failed_closed"


def test_rejects_nonzero_exit(tmp_path: Path) -> None:
    _fixture(tmp_path)
    (tmp_path / "l0-mlp-s20260827-candidate.exit-code").write_text("1\n")
    assert MODULE.summarize(tmp_path)["status"] == "failed_closed"


def test_refuses_missing_evidence(tmp_path: Path) -> None:
    _fixture(tmp_path)
    (tmp_path / "l0-attn-s20260826-candidate.jsonl").unlink()
    with pytest.raises(FileNotFoundError):
        MODULE.summarize(tmp_path)
