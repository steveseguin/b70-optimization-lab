#!/usr/bin/env python3
"""Focused host-only tests for the DeepSeek exact-canary scorer."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("score-exact-canaries.py")
SPEC = importlib.util.spec_from_file_location("score_exact_canaries", SCRIPT)
assert SPEC and SPEC.loader
SCORER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCORER)


class ExactCanaryScorerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.suite = {
            "suite_id": "test-exact-canaries-v1",
            "version": 1,
            "policy": "ordered",
            "prompts": [
                {"id": "a", "prompt": "Return A.", "expected": "A"},
                {"id": "b", "prompt": "Return B.", "expected": "B"},
                {"id": "a-replay", "prompt": "Return A.", "expected": "A"},
            ],
        }
        self.suite_raw = json.dumps(
            self.suite, sort_keys=True, separators=(",", ":")
        ).encode()
        self.suite_sha = hashlib.sha256(self.suite_raw).hexdigest()
        suite_meta = {
            key: value for key, value in self.suite.items() if key != "prompts"
        }
        self.capture = {
            "model": "deepseek-test",
            "model_revision": "d" * 40,
            "suite": suite_meta,
            "suite_sha256": self.suite_sha,
            "seed": 1,
            "max_tokens": 32,
            "top_logprobs": 0,
            "cached_tokens_all_zero": True,
            "rows": [
                {
                    "id": prompt["id"],
                    "prompt_sha256": hashlib.sha256(
                        prompt["prompt"].encode()
                    ).hexdigest(),
                    "content": prompt["expected"],
                    "cached_tokens": 0,
                }
                for prompt in self.suite["prompts"]
            ],
        }
        self.contract = {
            "schema": SCORER.STRICT_CONTRACT_SCHEMA,
            "suite_sha256": self.suite_sha,
            "suite_id": self.suite["suite_id"],
            "model": self.capture["model"],
            "model_revision": self.capture["model_revision"],
            "decoding": {"seed": 1, "max_tokens": 32, "top_logprobs": 0},
        }

    def score(
        self,
        capture: dict,
        *,
        strict: bool = True,
        contract: dict | None = None,
        suite: dict | None = None,
    ) -> dict:
        return SCORER.score(
            capture,
            self.suite if suite is None else suite,
            capture_path="capture.json",
            suite_path="suite.json",
            suite_sha256=self.suite_sha,
            strict=strict,
            contract=self.contract if contract is None and strict else contract,
        )

    def test_strict_valid_capture_passes(self) -> None:
        result = self.score(self.capture)
        self.assertTrue(result["passed"])
        self.assertTrue(result["capture_integrity_passed"])
        self.assertEqual(
            result["strict_contract_canonical_sha256"],
            SCORER.canonical_sha256(self.contract),
        )

    def test_legacy_mode_preserves_permissive_historical_scoring(self) -> None:
        capture = copy.deepcopy(self.capture)
        capture["rows"].reverse()
        capture["rows"].append(
            {"id": "extra", "content": "ignored", "cached_tokens": 7}
        )
        capture.pop("suite_sha256")
        capture.pop("model_revision")
        result = self.score(capture, strict=False)
        self.assertTrue(result["passed"])
        self.assertFalse(result["strict"])

    def test_strict_rejects_duplicate_missing_extra_and_out_of_order(self) -> None:
        mutations = {}

        duplicate = copy.deepcopy(self.capture)
        duplicate["rows"][1] = copy.deepcopy(duplicate["rows"][0])
        mutations["duplicate"] = duplicate

        missing = copy.deepcopy(self.capture)
        missing["rows"].pop()
        mutations["missing"] = missing

        extra = copy.deepcopy(self.capture)
        extra["rows"].append(
            {
                "id": "extra",
                "prompt_sha256": "0" * 64,
                "content": "x",
                "cached_tokens": 0,
            }
        )
        mutations["extra"] = extra

        reordered = copy.deepcopy(self.capture)
        reordered["rows"][0], reordered["rows"][1] = (
            reordered["rows"][1],
            reordered["rows"][0],
        )
        mutations["out-of-order"] = reordered

        for label, capture in mutations.items():
            with self.subTest(label=label):
                result = self.score(capture)
                self.assertFalse(result["passed"])
                self.assertTrue(result["capture_integrity_errors"])

    def test_strict_rejects_suite_prompt_and_row_cache_tampering(self) -> None:
        mutations = {}

        wrong_suite_hash = copy.deepcopy(self.capture)
        wrong_suite_hash["suite_sha256"] = "0" * 64
        mutations["suite-hash"] = wrong_suite_hash

        wrong_prompt_hash = copy.deepcopy(self.capture)
        wrong_prompt_hash["rows"][0]["prompt_sha256"] = "0" * 64
        mutations["prompt-hash"] = wrong_prompt_hash

        hidden_cache = copy.deepcopy(self.capture)
        hidden_cache["rows"][0]["cached_tokens"] = 1
        mutations["per-row-cache"] = hidden_cache

        wrong_metadata = copy.deepcopy(self.capture)
        wrong_metadata["suite"]["version"] = 2
        mutations["suite-metadata"] = wrong_metadata

        for label, capture in mutations.items():
            with self.subTest(label=label):
                self.assertFalse(self.score(capture)["passed"])

    def test_contract_binds_model_revision_and_decoding_identity(self) -> None:
        mutations = {}
        for field in ("model", "model_revision"):
            capture = copy.deepcopy(self.capture)
            capture[field] = "wrong"
            mutations[field] = capture
        for field in SCORER.DECODING_FIELDS:
            capture = copy.deepcopy(self.capture)
            capture[field] = capture[field] + 1
            mutations[f"decoding-{field}"] = capture

        for label, capture in mutations.items():
            with self.subTest(label=label):
                result = self.score(capture)
                self.assertFalse(result["passed"])
                self.assertTrue(
                    any(
                        "strict contract" in error
                        for error in result["capture_integrity_errors"]
                    )
                )

    def test_contract_rejects_wrong_suite_hash(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["suite_sha256"] = "0" * 64
        result = self.score(self.capture, contract=contract)
        self.assertFalse(result["passed"])
        self.assertIn(
            "strict contract suite_sha256 does not match suite bytes",
            result["capture_integrity_errors"],
        )

    def test_strict_contract_loader_rejects_unknown_or_invalid_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "contract.json"
            path.write_text(json.dumps(self.contract), encoding="utf-8")
            self.assertEqual(SCORER.load_strict_contract(path), self.contract)

            invalid = copy.deepcopy(self.contract)
            invalid["unknown"] = True
            path.write_text(json.dumps(invalid), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unknown strict contract fields"):
                SCORER.load_strict_contract(path)

            invalid = copy.deepcopy(self.contract)
            invalid["decoding"]["max_tokens"] = 0
            path.write_text(json.dumps(invalid), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "max_tokens must be positive"):
                SCORER.load_strict_contract(path)

    def test_repository_0731_contract_binds_frozen_suite(self) -> None:
        quality = SCRIPT.parent.parent / "quality"
        suite = quality / "exact-canaries-v1.json"
        contract = SCORER.load_strict_contract(
            quality / "exact-canaries-0731-target-contract-v1.json"
        )
        self.assertEqual(
            contract["suite_sha256"], SCORER.sha256_bytes(suite.read_bytes())
        )
        self.assertEqual(
            contract["model_revision"],
            "ddc04540efda3d2a0788b129f1fad828ddc19b60",
        )

    def test_strict_rejects_duplicate_suite_ids(self) -> None:
        suite = copy.deepcopy(self.suite)
        suite["prompts"][1]["id"] = suite["prompts"][0]["id"]
        result = self.score(self.capture, suite=suite)
        self.assertFalse(result["passed"])
        self.assertTrue(
            any(
                "duplicate suite IDs" in error
                for error in result["capture_integrity_errors"]
            )
        )

    def test_strict_rejects_empty_or_malformed_ids_without_crashing(self) -> None:
        empty_suite = copy.deepcopy(self.suite)
        empty_suite["prompts"] = []
        empty_capture = copy.deepcopy(self.capture)
        empty_capture["rows"] = []
        self.assertFalse(self.score(empty_capture, suite=empty_suite)["passed"])

        malformed_suite = copy.deepcopy(self.suite)
        malformed_suite["prompts"][0]["id"] = {"not": "hashable"}
        result = self.score(self.capture, suite=malformed_suite)
        self.assertFalse(result["passed"])
        self.assertIn(
            "suite prompt IDs must be non-empty strings",
            result["capture_integrity_errors"],
        )


if __name__ == "__main__":
    unittest.main()
