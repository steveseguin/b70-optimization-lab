#!/usr/bin/env python3
"""Regression tests for the speed/quality promotion binding."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.promotion_evidence import sha256_file, validate_promotion_attestation


class PromotionEvidenceTest(unittest.TestCase):
    def write_bundle(self, root: Path, **gate_overrides: bool) -> tuple[Path, Path]:
        performance = root / "performance.json"
        quality = root / "quality.json"
        performance.write_text('{"speed": 1}\n', encoding="utf-8")
        quality.write_text('{"quality": "passed"}\n', encoding="utf-8")
        gates = {
            "varied_task_quality_passed": True,
            "exact_or_target_oracle_passed": True,
            "deterministic_repeats_passed": True,
            "fresh_server_repeat_passed": True,
            "target_model_unchanged": True,
            "no_quality_loss": True,
        }
        gates.update(gate_overrides)
        bundle = {
            "schema": "neural.download.promotion-attestation.v1",
            "performance_evidence": {
                "path": "performance.json",
                "sha256": sha256_file(performance),
            },
            "identity": {
                "model_revision": "model-rev",
                "runtime_revision": "runtime-rev",
                "optimization_identity": "exact-env-and-flags-digest",
            },
            "gates": gates,
            "quality_evidence": [
                {
                    "path": "quality.json",
                    "sha256": sha256_file(quality),
                    "supports": [
                        "varied_task_quality_passed",
                        "exact_or_target_oracle_passed",
                        "deterministic_repeats_passed",
                        "fresh_server_repeat_passed",
                        "target_model_unchanged",
                        "no_quality_loss",
                    ],
                }
            ],
        }
        attestation = root / "attestation.json"
        attestation.write_text(json.dumps(bundle), encoding="utf-8")
        return attestation, performance

    def test_complete_hash_bound_attestation_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            attestation, performance = self.write_bundle(Path(temp))
            validate_promotion_attestation(
                attestation,
                performance,
                expected_model_revision="model-rev",
                expected_runtime_revision="runtime-rev",
            )

    def test_quality_failure_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            attestation, performance = self.write_bundle(
                Path(temp), no_quality_loss=False
            )
            with self.assertRaisesRegex(ValueError, "no_quality_loss"):
                validate_promotion_attestation(attestation, performance)

    def test_performance_file_substitution_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            attestation, performance = self.write_bundle(Path(temp))
            performance.write_text('{"speed": 999}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "performance_evidence_hash"):
                validate_promotion_attestation(attestation, performance)

    def test_performance_path_substitution_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            attestation, performance = self.write_bundle(root)
            alias = root / "same-bytes-different-path.json"
            alias.write_bytes(performance.read_bytes())
            with self.assertRaisesRegex(ValueError, "performance_evidence_path"):
                validate_promotion_attestation(attestation, alias)

    def test_every_gate_requires_bound_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            attestation, performance = self.write_bundle(root)
            data = json.loads(attestation.read_text(encoding="utf-8"))
            data["quality_evidence"][0]["supports"].remove("no_quality_loss")
            attestation.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "has_no_bound_evidence"):
                validate_promotion_attestation(attestation, performance)

    def test_runtime_identity_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            attestation, performance = self.write_bundle(Path(temp))
            with self.assertRaisesRegex(ValueError, "runtime_revision_mismatch"):
                validate_promotion_attestation(
                    attestation,
                    performance,
                    expected_runtime_revision="another-runtime",
                )


if __name__ == "__main__":
    unittest.main()
