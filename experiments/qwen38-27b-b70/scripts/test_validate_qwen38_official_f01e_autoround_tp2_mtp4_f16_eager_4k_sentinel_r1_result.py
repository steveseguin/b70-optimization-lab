#!/usr/bin/env python3
"""Mutation tests for the sealed current-f01e TP2/MTP4 exact-4K result."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[3]
VALIDATOR = REPO / "experiments/qwen38-27b-b70/scripts/validate-20260826-qwen38-official-f01e-autoround-tp2-mtp4-f16-eager-4k-sentinel-r1-result.py"
RESULT = REPO / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp2-mtp4-f16-eager-4k-sentinel-r1-result.json"


class ResultValidatorMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        spec = importlib.util.spec_from_file_location("tp2_mtp4_4k_result_validator", VALIDATOR)
        assert spec and spec.loader
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def copy_root(self, directory: str) -> Path:
        root = Path(directory) / "raw"
        shutil.copytree(self.module.ROOT, root)
        return root

    def test_sealed_raw_result_passes(self) -> None:
        self.assertEqual(
            self.module.validate(),
            {"status": "pass", "cells_published": 1, "tp": 2, "mtp": 4, "depth": 4096, "accepted": 90, "drafted": 148, "grade": "C"},
        )

    def test_mutated_exact_output_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_root(directory)
            path = root / "exact-depth/depth-4096.json"
            payload = json.loads(path.read_text())
            payload["response"]["output_token_ids_sha256"] = "0" * 64
            path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(RuntimeError, "stdout receipt differs"):
                self.module.validate(root, RESULT)

    def test_mutated_acceptance_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_root(directory)
            path = root / "verification-gates.json"
            payload = json.loads(path.read_text())
            payload["acceptance"]["accepted_tokens"] = 89
            path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(RuntimeError, "verification gates changed"):
                self.module.validate(root, RESULT)

    def test_mutated_mtp_identity_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_root(directory)
            path = root / "container-inspect.json"
            payload = json.loads(path.read_text())
            args = payload[0]["Config"]["Cmd"]
            args[args.index("--speculative-config") + 1] = '{"method":"qwen3_next_mtp","num_speculative_tokens":3}'
            path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(RuntimeError, "identity changed: container-inspect.json"):
                self.module.validate(root, RESULT)

    def test_mutated_site_scope_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result_path = Path(directory) / "result.json"
            payload = json.loads(RESULT.read_text())
            payload["authority"]["x0_2k_16k_24k_32k_remain_missing"] = False
            result_path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(RuntimeError, "cell scope widened"):
                self.module.validate(self.module.ROOT, result_path)

    def test_prior_8k_quarantine_remains_bound(self) -> None:
        payload = json.loads(RESULT.read_text())
        self.assertTrue(payload["adjudication"]["quarantined_8k_retained"])
        self.assertEqual(payload["tracked_inputs"]["prior_8k_quarantine"]["sha256"], "ae0828434248862bc9eaa8bcb82fe6a74d20b8007dc186b3f72477e68a38a3d3")


if __name__ == "__main__":
    unittest.main()
