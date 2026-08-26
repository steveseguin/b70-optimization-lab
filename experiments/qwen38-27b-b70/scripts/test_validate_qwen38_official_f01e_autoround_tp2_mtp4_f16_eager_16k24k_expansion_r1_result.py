#!/usr/bin/env python3
"""Mutation and static tests for TP2/MTP4 exact 16K+24K evidence."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[3]
VALIDATOR = REPO / "experiments/qwen38-27b-b70/scripts/validate-20260826-qwen38-official-f01e-autoround-tp2-mtp4-f16-eager-16k24k-expansion-r1-result.py"
RESULT = REPO / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp2-mtp4-f16-eager-16k24k-expansion-r1-result.json"


class ResultValidatorMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        spec = importlib.util.spec_from_file_location("tp2_mtp4_16k24k_result_validator", VALIDATOR)
        assert spec and spec.loader
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def copy_root(self, directory: str) -> Path:
        root = Path(directory) / "raw"
        shutil.copytree(self.module.ROOT, root)
        return root

    def write_result(self, directory: str, mutate) -> Path:
        path = Path(directory) / "result.json"
        payload = json.loads(RESULT.read_text())
        mutate(payload)
        path.write_text(json.dumps(payload))
        return path

    def test_sealed_raw_result_passes(self) -> None:
        self.assertEqual(
            self.module.validate(),
            {"status": "pass", "evidence_depths": [16384, 24576], "site_cells": 0, "tp": 2, "mtp": 4, "accepted": [89, 93], "drafted": [160, 144]},
        )

    def test_mutated_exact_output_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_root(directory)
            path = root / "exact-depth/depth-16384.json"
            payload = json.loads(path.read_text())
            payload["response"]["output_token_ids_sha256"] = "0" * 64
            path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(RuntimeError, "stdout differs"):
                self.module.validate(root, RESULT)

    def test_mutated_acceptance_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_root(directory)
            path = root / "verification/depth-24576.json"
            payload = json.loads(path.read_text())
            payload["acceptance"]["accepted_tokens"] = 92
            path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(RuntimeError, "raw hash changed"):
                self.module.validate(root, RESULT)

    def test_mutated_target_parity_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_root(directory)
            path = root / "verification/depth-16384.json"
            payload = json.loads(path.read_text())
            payload["same_topology_target_verification"]["passed"] = False
            path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(RuntimeError, "raw hash changed"):
                self.module.validate(root, RESULT)

    def test_mutated_decode_speed_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self.write_result(directory, lambda payload: payload["points"][0].__setitem__("decode_tok_s", 99.0))
            with self.assertRaisesRegex(RuntimeError, "decode changed"):
                self.module.validate(self.module.ROOT, result)

    def test_added_depth_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            def mutate(payload: dict) -> None:
                extra = dict(payload["points"][1])
                extra["x"] = 32768
                payload["points"].append(extra)
            result = self.write_result(directory, mutate)
            with self.assertRaisesRegex(RuntimeError, "result depth scope changed"):
                self.module.validate(self.module.ROOT, result)

    def test_publication_authority_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self.write_result(directory, lambda payload: payload["authority"].update({"site_cells": 2, "publication_authorized": True}))
            with self.assertRaisesRegex(RuntimeError, "publication authority changed"):
                self.module.validate(self.module.ROOT, result)

    def test_static_scope_and_acceptance_contract(self) -> None:
        payload = json.loads(RESULT.read_text())
        self.assertEqual([point["x"] for point in payload["points"]], [16384, 24576])
        self.assertEqual([(point["accepted_tokens"], point["drafted_tokens"]) for point in payload["points"]], [(89, 160), (93, 144)])
        self.assertEqual(payload["authority"]["site_cells"], 0)
        self.assertFalse(payload["authority"]["publication_authorized"])
        self.assertTrue(payload["authority"]["existing_8k_quarantine_unchanged"])
        self.assertTrue(payload["authority"]["x0_2k_4k_8k_32k_not_selected_by_this_result"])


if __name__ == "__main__":
    unittest.main()
