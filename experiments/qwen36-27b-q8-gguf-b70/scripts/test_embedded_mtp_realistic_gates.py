#!/usr/bin/env python3
"""Focused offline tests for realistic once-only evidence joins."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
SPEC = importlib.util.spec_from_file_location(
    "embedded_mtp_realistic_gates", HERE / "embedded_mtp_realistic_gates.py"
)
assert SPEC is not None and SPEC.loader is not None
GATES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATES)


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n")


def capture_gate(mode: str, rate: float) -> dict:
    metric = {
        "count": 12,
        "p10": rate,
        "median": rate,
        "mean": rate,
        "min": rate,
        "max": rate,
        "stdev": 0.0,
    }
    value = {
        "passed": True,
        "mode": mode,
        "input_sha256": f"{mode}-raw",
        "forensic_input_sha256": f"{mode}-forensic",
        "suite_sha256": GATES.SUITE_SHA256,
        "prefix_oracle_sha256": GATES.PREFIX_ORACLE_SHA256,
        "legacy_oracle_identity": GATES.LEGACY_PREFIX_ORACLE_IDENTITY,
        "current_gate_identity": GATES.CURRENT_REALISTIC_IDENTITY,
        "legacy_oracle_identity_compatible": False,
        "quality_reference": GATES.QUALITY_REFERENCE,
        "model_sha256": GATES.MODEL_SHA256,
        "runtime_sha256": GATES.RUNTIME_SHA256,
        "policy": {
            "headline_requests_per_prompt": 1,
            "headline_replay_requests": 0,
            "separate_fresh_forensic_requests_per_prompt": 1,
        },
        "summary": {
            "d99_interval_tok_s": metric,
            "d127_interval_tok_s": metric,
            "full_interval_tok_s": metric,
            "native_predicted_tok_s": metric,
            "client_full_after_ttft_tok_s": metric,
            "ttft_s": {**metric, "median": 1.0},
            "all_rows_full_512": True,
        },
        "per_prompt": {
            prompt_id: {"d99_interval_tok_s": rate} for prompt_id in GATES.PROMPT_IDS
        },
        "control_checks": {},
    }
    if mode == "mtp3":
        value["control_checks"] = {
            "full_candidate_control_token_ids_exact": True,
            "full_candidate_control_content_exact": True,
            "full_candidate_control_exact": True,
            "observed_control_scored_sha256": "control-raw",
            "observed_control_forensic_sha256": "control-forensic",
        }
    return value


def metrics_gate(mode: str) -> dict:
    counters = (
        {"accepted_tokens": 0, "draft_tokens": 0, "drafts": 0}
        if mode == "control"
        else {"accepted_tokens": 150, "draft_tokens": 300, "drafts": 100}
    )
    return {
        "passed": True,
        "mode": mode,
        "capture_sha256": f"{mode}-raw",
        "speculative": {
            "counters": counters,
            "acceptance_ratio": 0 if mode == "control" else 0.5,
            "accepted_per_verification": 0 if mode == "control" else 1.5,
            "effective_tokens_per_target_verification": 1 if mode == "control" else 2.5,
            "accepted_per_position": {},
        },
    }


class CompareEvidenceTests(unittest.TestCase):
    def run_compare(
        self,
        root: Path,
        candidate_rate: float = 20.5,
        candidate_metrics_capture_sha: str = "mtp3-raw",
        capture_mutator=None,
    ) -> tuple[int, dict]:
        control_capture = root / "control-capture.json"
        candidate_capture = root / "candidate-capture.json"
        control_metrics = root / "control-metrics.json"
        candidate_metrics = root / "candidate-metrics.json"
        control_capture_value = capture_gate("control", 20.0)
        candidate_capture_value = capture_gate("mtp3", candidate_rate)
        if capture_mutator is not None:
            capture_mutator(control_capture_value, candidate_capture_value)
        write_json(control_capture, control_capture_value)
        write_json(candidate_capture, candidate_capture_value)
        write_json(control_metrics, metrics_gate("control"))
        candidate_metrics_value = metrics_gate("mtp3")
        candidate_metrics_value["capture_sha256"] = candidate_metrics_capture_sha
        write_json(candidate_metrics, candidate_metrics_value)
        cleanups = []
        for name in ("control", "candidate", "control-forensic", "candidate-forensic"):
            path = root / f"{name}.env"
            path.write_text(
                "forced_kill=0\ncleanup_survivor=0\nport_closed=1\nvram_returned=1\n"
            )
            cleanups.append(path)
        output = root / "compare.json"
        status = GATES.compare_arms(
            argparse.Namespace(
                control_capture_gate=control_capture,
                candidate_capture_gate=candidate_capture,
                control_metrics_gate=control_metrics,
                candidate_metrics_gate=candidate_metrics,
                control_cleanup=cleanups[0],
                candidate_cleanup=cleanups[1],
                control_forensic_cleanup=cleanups[2],
                candidate_forensic_cleanup=cleanups[3],
                output=output,
            )
        )
        return status, json.loads(output.read_text())

    def test_valid_once_only_evidence_survives_no_speed_win(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            status, result = self.run_compare(Path(raw))
        self.assertEqual(status, 0)
        self.assertTrue(result["evidence_passed"])
        self.assertTrue(result["realistic_policy_passed"])
        self.assertFalse(result["performance_passed"])
        self.assertEqual(result["classification"], "VALID_REALISTIC_NO_MTP_WIN")

    def test_mixed_metrics_capture_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            status, result = self.run_compare(
                root, candidate_metrics_capture_sha="different-capture"
            )
        self.assertEqual(status, 1)
        self.assertFalse(result["evidence_passed"])
        self.assertFalse(result["evidence_checks"]["candidate_metrics_capture_join"])

    def test_quality_reference_and_legacy_compatibility_are_fail_closed(self) -> None:
        cases = (
            (
                "missing-control-quality-reference",
                "control",
                "quality_reference",
                None,
                "control_quality_reference",
            ),
            (
                "wrong-control-quality-reference",
                "control",
                "quality_reference",
                "legacy_prefix_v0",
                "control_quality_reference",
            ),
            (
                "missing-candidate-quality-reference",
                "candidate",
                "quality_reference",
                None,
                "candidate_quality_reference",
            ),
            (
                "wrong-candidate-quality-reference",
                "candidate",
                "quality_reference",
                "legacy_prefix_v0",
                "candidate_quality_reference",
            ),
            (
                "missing-control-compatibility",
                "control",
                "legacy_oracle_identity_compatible",
                None,
                "control_legacy_oracle_identity_incompatible",
            ),
            (
                "wrong-control-compatibility",
                "control",
                "legacy_oracle_identity_compatible",
                True,
                "control_legacy_oracle_identity_incompatible",
            ),
            (
                "missing-candidate-compatibility",
                "candidate",
                "legacy_oracle_identity_compatible",
                None,
                "candidate_legacy_oracle_identity_incompatible",
            ),
            (
                "wrong-candidate-compatibility",
                "candidate",
                "legacy_oracle_identity_compatible",
                True,
                "candidate_legacy_oracle_identity_incompatible",
            ),
        )
        for name, arm, key, replacement, expected_check in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as raw:
                def mutate(control: dict, candidate: dict) -> None:
                    target = control if arm == "control" else candidate
                    if replacement is None:
                        target.pop(key)
                    else:
                        target[key] = replacement

                status, result = self.run_compare(
                    Path(raw), capture_mutator=mutate
                )
            self.assertEqual(status, 1)
            self.assertFalse(result["evidence_passed"])
            self.assertFalse(result["evidence_checks"][expected_check])

    def test_fresh_control_token_content_and_hash_proof_is_fail_closed(self) -> None:
        cases = (
            ("full_candidate_control_token_ids_exact", False),
            ("full_candidate_control_content_exact", False),
            ("observed_control_forensic_sha256", "different-control"),
        )
        for key, replacement in cases:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as raw:
                def mutate(_control: dict, candidate: dict) -> None:
                    candidate["control_checks"][key] = replacement

                status, result = self.run_compare(
                    Path(raw), capture_mutator=mutate
                )
            self.assertEqual(status, 1)
            self.assertFalse(result["evidence_passed"])
            self.assertFalse(
                result["evidence_checks"]["candidate_bound_to_fresh_control"]
            )


class HardRowPolicyTests(unittest.TestCase):
    def test_only_legacy_prefix_match_is_diagnostic(self) -> None:
        checks = {
            "prompt_identity": True,
            "fresh_control_token_content_exact": True,
            GATES.LEGACY_PREFIX_DIAGNOSTIC_CHECK: False,
        }
        self.assertTrue(GATES.hard_row_checks_pass(checks))

        for name in ("prompt_identity", "fresh_control_token_content_exact"):
            with self.subTest(name=name):
                adversarial = dict(checks)
                adversarial[name] = False
                self.assertFalse(GATES.hard_row_checks_pass(adversarial))

        missing_diagnostic = dict(checks)
        missing_diagnostic.pop(GATES.LEGACY_PREFIX_DIAGNOSTIC_CHECK)
        self.assertFalse(GATES.hard_row_checks_pass(missing_diagnostic))


if __name__ == "__main__":
    unittest.main()
