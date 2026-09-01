#!/usr/bin/env python3
"""CPU-only contract tests for the W13 M1 XPU graph component gate."""

from __future__ import annotations

import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest


GATE_PATH = Path(__file__).with_name("w13-m1-xpu-graph-gate.py")
SPEC = importlib.util.spec_from_file_location("q38_w13_graph_gate", GATE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {GATE_PATH}")
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class ConfigContractTests(unittest.TestCase):
    @staticmethod
    def make_control_authority() -> tuple[dict[str, object], dict[str, object]]:
        identity = {"layer": 0, "ep_rank": 0, "seed": 20260827}
        hashes = [f"{index:064x}" for index in range(GATE.EXACT_REPLAYS)]
        authority = {
            "status": "pass",
            "classification": "qwen38_flash_next_w13_m1_xpu_graph_component",
            "identity": identity.copy(),
            "config_receipt": {
                "requested": {},
                "resolved_w1": GATE.PROTECTED_BASE_CONFIG.copy(),
                "resolved_w2": GATE.PROTECTED_BASE_CONFIG.copy(),
                "w2_unchanged": True,
            },
            "correctness": {
                "config_local_eager_output_sha256": hashes,
                "graph_output_sha256": hashes.copy(),
            },
        }
        return authority, identity

    def test_control_keeps_both_phases_at_protected_base(self) -> None:
        effective, w1, w2, requested = GATE.parse_candidate_config("{}")
        self.assertEqual(effective, GATE.PROTECTED_BASE_CONFIG)
        self.assertEqual(w1, GATE.PROTECTED_BASE_CONFIG)
        self.assertEqual(w2, GATE.PROTECTED_BASE_CONFIG)
        self.assertEqual(requested, {})

    def test_w13_delta_does_not_change_w2(self) -> None:
        effective, w1, w2, _ = GATE.parse_candidate_config(
            '{"W1_CONFIG":{"BLOCK_SIZE_N":128,"num_warps":4}}'
        )
        self.assertEqual(effective["W1_CONFIG"]["BLOCK_SIZE_N"], 128)
        self.assertEqual(w1["BLOCK_SIZE_N"], 128)
        self.assertEqual(w1["num_warps"], 4)
        self.assertEqual(w2, GATE.PROTECTED_BASE_CONFIG)

    def test_rejects_w2_and_flat_deltas(self) -> None:
        for encoded in (
            '{"W2_CONFIG":{"BLOCK_SIZE_N":32}}',
            '{"num_warps":4}',
            '{"W1_CONFIG":{},"W2_CONFIG":{}}',
        ):
            with self.subTest(encoded=encoded), self.assertRaises(ValueError):
                GATE.parse_candidate_config(encoded)

    def test_rejects_unknown_invalid_and_boolean_values(self) -> None:
        for encoded in (
            '{"W1_CONFIG":{"BLOCK_SIZE_M":32}}',
            '{"W1_CONFIG":{"BLOCK_SIZE_N":96}}',
            '{"W1_CONFIG":{"num_warps":true}}',
            '{"W1_CONFIG":[]}',
        ):
            with self.subTest(encoded=encoded), self.assertRaises(ValueError):
                GATE.parse_candidate_config(encoded)

    def test_accepts_exact_control_authority(self) -> None:
        authority, identity = self.make_control_authority()
        hashes = GATE.validate_control_authority(authority, identity)
        self.assertEqual(len(hashes), GATE.EXACT_REPLAYS)

    def test_rejects_candidate_or_identity_drift_as_control_authority(self) -> None:
        authority, identity = self.make_control_authority()
        authority["config_receipt"]["requested"] = {"W1_CONFIG": {"BLOCK_SIZE_N": 128}}
        with self.assertRaisesRegex(ValueError, "not the protected control"):
            GATE.validate_control_authority(authority, identity)
        authority, identity = self.make_control_authority()
        identity["layer"] = 47
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            GATE.validate_control_authority(authority, identity)

    def test_rejects_stale_or_nonunique_control_authority(self) -> None:
        authority, identity = self.make_control_authority()
        authority["correctness"]["graph_output_sha256"][2] = "f" * 64
        with self.assertRaisesRegex(ValueError, "stale or differs"):
            GATE.validate_control_authority(authority, identity)
        authority, identity = self.make_control_authority()
        repeated = ["a" * 64] * GATE.EXACT_REPLAYS
        authority["correctness"]["config_local_eager_output_sha256"] = repeated
        authority["correctness"]["graph_output_sha256"] = repeated.copy()
        with self.assertRaisesRegex(ValueError, "stale or differs"):
            GATE.validate_control_authority(authority, identity)


class WeightAndRouteContractTests(unittest.TestCase):
    @staticmethod
    def make_index(layer: int, ep_rank: int) -> dict[str, object]:
        first = ep_rank * GATE.LOCAL_EXPERTS
        weight_map: dict[str, str] = {}
        for expert in range(first, first + GATE.LOCAL_EXPERTS):
            for role, name in GATE.expert_weight_names(layer, expert).items():
                suffix = "down" if role.startswith("down") else "gate-up"
                weight_map[name] = f"layer-{layer}-{suffix}.safetensors"
        return {"weight_map": weight_map}

    def test_index_plan_selects_exact_rank_expert_range(self) -> None:
        plan, shards = GATE.resolve_weight_plan(self.make_index(47, 3), 47, 3)
        self.assertEqual(len(plan), GATE.LOCAL_EXPERTS)
        self.assertEqual(plan[0]["global_expert"], "384")
        self.assertEqual(plan[-1]["global_expert"], "511")
        self.assertEqual(
            shards,
            ["layer-47-down.safetensors", "layer-47-gate-up.safetensors"],
        )

    def test_index_plan_rejects_missing_tensor(self) -> None:
        index = self.make_index(0, 0)
        missing = GATE.expert_weight_names(0, 0)["gate_weight"]
        del index["weight_map"][missing]
        with self.assertRaisesRegex(ValueError, "model index is missing"):
            GATE.resolve_weight_plan(index, 0, 0)

    def test_model_shape_receipt_requires_exact_fp8_identity(self) -> None:
        config = {
            "text_config": GATE.EXPECTED_TEXT_CONFIG.copy(),
            "quantization_config": {
                "quant_method": "fp8",
                "activation_scheme": "dynamic",
                "weight_block_size": GATE.BLOCK_SHAPE.copy(),
            },
        }
        receipt = GATE.validate_model_config(config)
        self.assertEqual(receipt["text_config"], GATE.EXPECTED_TEXT_CONFIG)
        config["text_config"]["num_experts"] = 128
        with self.assertRaisesRegex(ValueError, "protected Flash-Next shape"):
            GATE.validate_model_config(config)

    def test_model_shape_receipt_rejects_non_fp8_quantization(self) -> None:
        config = {
            "text_config": GATE.EXPECTED_TEXT_CONFIG.copy(),
            "quantization_config": {
                "quant_method": "int8",
                "activation_scheme": "dynamic",
                "weight_block_size": GATE.BLOCK_SHAPE.copy(),
            },
        }
        with self.assertRaisesRegex(ValueError, "protected block-FP8 shape"):
            GATE.validate_model_config(config)

    def test_route_series_changes_and_covers_every_rank(self) -> None:
        series = [
            GATE.route_ids_for_replay(replay) for replay in range(GATE.EXACT_REPLAYS)
        ]
        self.assertEqual(len({tuple(row) for row in series}), GATE.EXACT_REPLAYS)
        self.assertTrue(all(len(row) == GATE.TOP_K for row in series))
        self.assertTrue(all(len(set(row)) == GATE.TOP_K for row in series))
        self.assertTrue(
            all(0 <= expert < GATE.GLOBAL_EXPERTS for row in series for expert in row)
        )
        for rank in range(4):
            counts = [GATE.local_route_count(row, rank) for row in series]
            self.assertGreater(min(counts), 0)
            self.assertLess(max(counts), GATE.TOP_K)

    def test_accepts_frozen_checkpoint_receipt_without_rehashing_shard(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            shard = root / "model-00002-of-00131.safetensors"
            shard.write_bytes(b"checkpoint bytes")
            receipt = root / "receipt.json"
            value = {
                "schema_version": 1,
                "status": "pass",
                "classification": "qwen38_w13_checkpoint_checksum_receipt",
                "model_path": str(root),
                "model_revision": GATE.MODEL_REVISION,
                "model_index_sha256": "1" * 64,
                "model_config_sha256": "2" * 64,
                "checkpoint_shards": {
                    shard.name: {
                        "path": str(shard),
                        "size": shard.stat().st_size,
                        "sha256": hashlib.sha256(shard.read_bytes()).hexdigest(),
                        "stat_identity": {
                            "device": shard.stat().st_dev,
                            "inode": shard.stat().st_ino,
                            "mtime_ns": shard.stat().st_mtime_ns,
                            "ctime_ns": shard.stat().st_ctime_ns,
                        },
                    }
                },
            }
            receipt.write_text(json.dumps(value), encoding="utf-8")
            receipt_digest = hashlib.sha256(receipt.read_bytes()).hexdigest()
            selected = GATE.validate_checkpoint_receipt(
                receipt,
                receipt_digest,
                model=root,
                model_revision=GATE.MODEL_REVISION,
                index_sha256="1" * 64,
                config_sha256="2" * 64,
                shard_paths={shard.name: shard},
            )
            self.assertEqual(
                selected[shard.name]["sha256"],
                value["checkpoint_shards"][shard.name]["sha256"],
            )

    def test_rejects_tampered_or_size_drifted_checkpoint_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            shard = root / "model-00002-of-00131.safetensors"
            shard.write_bytes(b"checkpoint bytes")
            receipt = root / "receipt.json"
            value = {
                "schema_version": 1,
                "status": "pass",
                "classification": "qwen38_w13_checkpoint_checksum_receipt",
                "model_path": str(root),
                "model_revision": GATE.MODEL_REVISION,
                "model_index_sha256": "1" * 64,
                "model_config_sha256": "2" * 64,
                "checkpoint_shards": {
                    shard.name: {
                        "path": str(shard),
                        "size": shard.stat().st_size,
                        "sha256": hashlib.sha256(shard.read_bytes()).hexdigest(),
                        "stat_identity": {
                            "device": shard.stat().st_dev,
                            "inode": shard.stat().st_ino,
                            "mtime_ns": shard.stat().st_mtime_ns,
                            "ctime_ns": shard.stat().st_ctime_ns,
                        },
                    }
                },
            }
            receipt.write_text(json.dumps(value), encoding="utf-8")
            digest = hashlib.sha256(receipt.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                GATE.validate_checkpoint_receipt(
                    receipt,
                    "0" * 64,
                    model=root,
                    model_revision=GATE.MODEL_REVISION,
                    index_sha256="1" * 64,
                    config_sha256="2" * 64,
                    shard_paths={shard.name: shard},
                )
            shard.write_bytes(b"tampered payload")
            with self.assertRaisesRegex(ValueError, "stat identity mismatch"):
                GATE.validate_checkpoint_receipt(
                    receipt,
                    digest,
                    model=root,
                    model_revision=GATE.MODEL_REVISION,
                    index_sha256="1" * 64,
                    config_sha256="2" * 64,
                    shard_paths={shard.name: shard},
                )


if __name__ == "__main__":
    unittest.main()
