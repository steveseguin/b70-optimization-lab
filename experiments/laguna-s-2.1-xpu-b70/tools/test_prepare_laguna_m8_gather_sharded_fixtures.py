#!/usr/bin/env python3
"""Tests for the CPU-only M8 gather-sharded fixture corpus tool."""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).with_name("prepare_laguna_m8_gather_sharded_fixtures.py")
SPEC = importlib.util.spec_from_file_location("laguna_fixture_tool", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


class LagunaGatherShardedFixtureTests(unittest.TestCase):
    def _fixture(self) -> tempfile.TemporaryDirectory[str]:
        return tempfile.TemporaryDirectory(prefix="laguna-fixture-test-", dir="/mnt/fast-ai")

    @staticmethod
    def _save_manifest(root: Path, value: dict[str, object]) -> None:
        (root / "manifest.json").write_text(
            json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )

    def test_small_internal_fixture_has_independent_full_coverage(self) -> None:
        with self._fixture() as directory:
            root = Path(directory) / "fixture"
            manifest = tool._write_test_fixture(root, epochs=16)
            self.assertTrue(manifest["production"] is False)
            report = tool._analyze_test_fixture(root)
            coverage = report["coverage"]
            self.assertTrue(report["hashes_match_manifest"])
            self.assertTrue(report["deterministic_bytes_match"])
            self.assertEqual(coverage["uint16_patterns_present"], 65536)
            self.assertTrue(coverage["all_65536"])
            self.assertTrue(coverage["canonical_route_map"])
            self.assertTrue(coverage["zero_rows_literal_uint16_zero"])
            self.assertTrue(coverage["local_rows_match_formula"])
            self.assertFalse(coverage["all_1024_local_zero_masks"])
            self.assertTrue(coverage["all_slots_independently_active"])
            self.assertTrue(coverage["ordered_cancellation_witness"])
            self.assertTrue(coverage["bf16_midpoint_witness"])
            self.assertEqual(
                set(manifest["classes"]["fp32_inventory"]),
                set(coverage["fp32_classes_present"]),
            )
            for record in report["tensors"].values():
                self.assertEqual(len(record["epoch_sha256"]), 16)

    def test_analyzer_detects_binary_tampering_without_manifest_trust(self) -> None:
        with self._fixture() as directory:
            root = Path(directory) / "fixture"
            manifest = tool._write_test_fixture(root, epochs=16)
            data = root / manifest["tensors"]["weights"]["file"]
            with data.open("r+b") as handle:
                handle.seek(0)
                handle.write(b"\xff\xff\xff\xff")
            report = tool._analyze_test_fixture(root)
            self.assertFalse(report["hashes_match_manifest"])

    def test_rejects_output_outside_internal_nvme(self) -> None:
        with self.assertRaises(ValueError):
            tool._write_test_fixture(Path("/tmp/forbidden-laguna-fixture"), epochs=16)

    def test_production_dimensions_are_not_cli_overrides(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn('add_argument("--epochs"', source)
        self.assertNotIn('add_argument("--hidden"', source)
        self.assertEqual(tool.EPOCHS, 288)
        self.assertEqual((tool.TOKENS, tool.TOPK, tool.HIDDEN), (8, 10, 3072))
        self.assertNotIn("torch", source.lower())
        self.assertNotIn("requests", source.lower())
        self.assertNotIn("socket", source.lower())

    def test_production_mask_schedule_contains_every_independent_slot_and_mask(self) -> None:
        masks = [value for row in tool._masks(tool.EPOCHS) for value in row]
        self.assertTrue(set(range(1024)).issubset(masks))
        self.assertTrue(all((1 << slot) in masks for slot in range(tool.TOPK)))

    def test_manifest_is_canonical_json(self) -> None:
        with self._fixture() as directory:
            root = Path(directory) / "fixture"
            tool._write_test_fixture(root, epochs=16)
            raw = (root / "manifest.json").read_text(encoding="utf-8")
            self.assertEqual(raw, json.dumps(json.loads(raw), sort_keys=True, separators=(",", ":")) + "\n")

    def test_analyzer_rejects_all_remote_and_single_slot_binary_mutations(self) -> None:
        with self._fixture() as directory:
            root = Path(directory) / "fixture"
            manifest = tool._write_test_fixture(root, epochs=16)
            rows = root / manifest["tensors"]["route_rows"]["file"]
            with rows.open("r+b") as handle:
                handle.seek(80 * tool.HIDDEN * 2)  # epoch 1, slot 0: must be remote zero
                handle.write(b"\x01\x00")
            self.assertFalse(tool._analyze_test_fixture(root)["coverage"]["zero_rows_literal_uint16_zero"])

        with self._fixture() as directory:
            root = Path(directory) / "fixture"
            manifest = tool._write_test_fixture(root, epochs=16)
            weights = root / manifest["tensors"]["weights"]["file"]
            with weights.open("r+b") as handle:
                handle.seek(2 * 80 * 4)  # epoch 2 token 0 slot 0 must be +1
                handle.write(b"\0\0\0\0")
            self.assertFalse(tool._analyze_test_fixture(root)["coverage"]["all_slots_independently_active"])

    def test_analyzer_rejects_manifest_schedule_and_spec_mutation(self) -> None:
        with self._fixture() as directory:
            root = Path(directory) / "fixture"
            tool._write_test_fixture(root, epochs=16)
            path = root / "manifest.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["local_masks_uint16"][1][0] = 1
            path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "mask schedule"):
                tool._analyze_test_fixture(root)

        with self._fixture() as directory:
            root = Path(directory) / "fixture"
            tool._write_test_fixture(root, epochs=16)
            path = root / "manifest.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["tensors"]["weights"]["file"] = "forged.bin"
            path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "tensor specification"):
                tool._analyze_test_fixture(root)

    def test_analyzer_rejects_fixture_phase_and_witness_mutation(self) -> None:
        with self._fixture() as directory:
            root = Path(directory) / "fixture"
            tool._write_test_fixture(root, epochs=16)
            path = root / "manifest.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["fixtures"][0]["phase"] = "post_timing"
            path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "phase"):
                tool._analyze_test_fixture(root)

        with self._fixture() as directory:
            root = Path(directory) / "fixture"
            manifest = tool._write_test_fixture(root, epochs=16)
            rows = root / manifest["tensors"]["route_rows"]["file"]
            with rows.open("r+b") as handle:
                handle.write(b"\0\0")
            self.assertFalse(tool._analyze_test_fixture(root)["coverage"]["ordered_cancellation_witness"])

    def test_paired_digest_mutation_cannot_forge_any_tensor(self) -> None:
        with self._fixture() as directory:
            root = Path(directory) / "fixture"
            manifest = tool._write_test_fixture(root, epochs=16)
            for name, spec in tool._tensor_specs(16).items():
                data = root / spec[0]
                with data.open("r+b") as handle:
                    handle.seek(0)
                    handle.write(b"\xfe")
                whole, per_epoch = tool._checked_record(root, spec)
                manifest["tensors"][name]["sha256"] = whole
                manifest["tensors"][name]["epoch_sha256"] = per_epoch
                for epoch, fixture in enumerate(manifest["fixtures"]):
                    fixture["tensor_sha256"][name] = per_epoch[epoch]
            self._save_manifest(root, manifest)
            report = tool._analyze_test_fixture(root)
            self.assertTrue(report["hashes_match_manifest"])
            self.assertFalse(report["deterministic_bytes_match"])

    def test_edge_midpoint_map_and_size_mutations(self) -> None:
        with self._fixture() as directory:
            root = Path(directory) / "fixture"
            manifest = tool._write_test_fixture(root, epochs=16)
            weights = root / manifest["tensors"]["weights"]["file"]
            with weights.open("r+b") as handle:
                handle.seek(12 * 80 * 4 + 12 * 4)  # unique positive payload-NaN edge
                handle.write(b"\x02\0\0\0")
            report = tool._analyze_test_fixture(root)
            self.assertFalse(report["coverage"]["all_fp32_edge_classes"])

        with self._fixture() as directory:
            root = Path(directory) / "fixture"
            manifest = tool._write_test_fixture(root, epochs=16)
            weights = root / manifest["tensors"]["weights"]["file"]
            with weights.open("r+b") as handle:
                handle.seek(11 * 4)  # token 1 slot 1 midpoint weight
                handle.write(b"\0\0\0\0")
            self.assertFalse(tool._analyze_test_fixture(root)["coverage"]["bf16_midpoint_witness"])
            route_map = root / manifest["canonical_route_map"]["file"]
            with route_map.open("r+b") as handle:
                handle.write(b"\xff\xff\xff\xff")
            self.assertFalse(tool._analyze_test_fixture(root)["coverage"]["canonical_route_map"])

        with self._fixture() as directory:
            root = Path(directory) / "fixture"
            manifest = tool._write_test_fixture(root, epochs=16)
            path = root / manifest["tensors"]["norm_weight"]["file"]
            path.write_bytes(path.read_bytes()[:-1])
            with self.assertRaisesRegex(ValueError, "wrong binary size"):
                tool._analyze_test_fixture(root)

    def test_format_classes_and_production_type_are_strict(self) -> None:
        for key, value in (("format", "forged"), ("classes", {}), ("production", "false")):
            with self._fixture() as directory:
                root = Path(directory) / "fixture"
                tool._write_test_fixture(root, epochs=16)
                path = root / "manifest.json"
                manifest = json.loads(path.read_text(encoding="utf-8"))
                manifest[key] = value
                self._save_manifest(root, manifest)
                with self.assertRaises(ValueError):
                    tool._analyze_test_fixture(root)

    def test_epoch_nested_schema_and_exact_integer_types_are_strict(self) -> None:
        mutations = (
            ("epochs", "16"),
            ("geometry", {"tokens": True, "topk": 10, "hidden": 3072, "ranks": 4}),
        )
        for key, value in mutations:
            with self._fixture() as directory:
                root = Path(directory) / "fixture"
                tool._write_test_fixture(root, epochs=16)
                path = root / "manifest.json"
                manifest = json.loads(path.read_text(encoding="utf-8"))
                manifest[key] = value
                self._save_manifest(root, manifest)
                with self.assertRaises(ValueError):
                    tool._analyze_test_fixture(root)

        with self._fixture() as directory:
            root = Path(directory) / "fixture"
            tool._write_test_fixture(root, epochs=16)
            path = root / "manifest.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["canonical_route_map"]["extra"] = True
            self._save_manifest(root, manifest)
            with self.assertRaisesRegex(ValueError, "canonical map"):
                tool._analyze_test_fixture(root)

        with self._fixture() as directory:
            root = Path(directory) / "fixture"
            tool._write_test_fixture(root, epochs=16)
            path = root / "manifest.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["fixtures"][0]["extra"] = True
            self._save_manifest(root, manifest)
            with self.assertRaisesRegex(ValueError, "fixture class"):
                tool._analyze_test_fixture(root)

    def test_manifest_map_and_tensor_symlinks_and_manifest_bound_fail_closed(self) -> None:
        with self._fixture() as directory:
            root = Path(directory) / "fixture"
            tool._write_test_fixture(root, epochs=16)
            manifest_path = root / "manifest.json"
            target = root / "manifest.real"
            manifest_path.rename(target)
            manifest_path.symlink_to(target)
            with self.assertRaisesRegex(ValueError, "regular fixture"):
                tool._analyze_test_fixture(root)

        with self._fixture() as directory:
            root = Path(directory) / "fixture"
            manifest = tool._write_test_fixture(root, epochs=16)
            map_path = root / manifest["canonical_route_map"]["file"]
            target = root / "map.real"
            map_path.rename(target)
            map_path.symlink_to(target)
            with self.assertRaisesRegex(ValueError, "regular fixture"):
                tool._analyze_test_fixture(root)

        with self._fixture() as directory:
            root = Path(directory) / "fixture"
            manifest = tool._write_test_fixture(root, epochs=16)
            tensor_path = root / manifest["tensors"]["norm_weight"]["file"]
            target = root / "tensor.real"
            tensor_path.rename(target)
            tensor_path.symlink_to(target)
            with self.assertRaisesRegex(ValueError, "regular fixture"):
                tool._analyze_test_fixture(root)

        with self._fixture() as directory:
            root = Path(directory) / "fixture"
            tool._write_test_fixture(root, epochs=16)
            (root / "manifest.json").write_bytes(b" " * (tool.MAX_MANIFEST_BYTES + 1))
            with self.assertRaisesRegex(ValueError, "size bound"):
                tool._analyze_test_fixture(root)

    def test_public_analyzer_rejects_any_false_proof(self) -> None:
        proof = {
            "hashes_match_manifest": True,
            "deterministic_bytes_match": True,
            "coverage": {
                "uint16_patterns_present": 65536,
                "all_65536": True,
                "all_fp32_edge_classes": True,
                "all_1024_local_zero_masks": True,
                "all_slots_independently_active": True,
                "all_local": True,
                "all_remote_zero": True,
                "zero_rows_literal_uint16_zero": True,
                "local_rows_match_formula": True,
                "canonical_route_map": True,
                "ordered_cancellation_witness": True,
                "bf16_midpoint_witness": True,
            },
        }
        with mock.patch.object(tool, "_analyze", return_value=proof):
            self.assertEqual(tool.analyze_existing(Path("/mnt/fast-ai"))["status"], "passed")
            broken = json.loads(json.dumps(proof))
            broken["coverage"]["local_rows_match_formula"] = False
        with mock.patch.object(tool, "_analyze", return_value=broken):
            with self.assertRaisesRegex(ValueError, "failed closed"):
                tool.analyze_existing(Path("/mnt/fast-ai"))

    def test_public_analyzer_rejects_test_and_oversized_corpora(self) -> None:
        with self._fixture() as directory:
            root = Path(directory) / "fixture"
            manifest = tool._write_test_fixture(root, epochs=16)
            with self.assertRaisesRegex(ValueError, "production manifests"):
                tool.analyze_existing(root)
            path = root / manifest["tensors"]["norm_weight"]["file"]
            with path.open("ab") as handle:
                handle.write(b"\0")
            with self.assertRaisesRegex(ValueError, "wrong binary size"):
                tool._analyze_test_fixture(root)


if __name__ == "__main__":
    unittest.main()
