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
    ) -> tuple[int, dict]:
        control_capture = root / "control-capture.json"
        candidate_capture = root / "candidate-capture.json"
        control_metrics = root / "control-metrics.json"
        candidate_metrics = root / "candidate-metrics.json"
        write_json(control_capture, capture_gate("control", 20.0))
        write_json(candidate_capture, capture_gate("mtp3", candidate_rate))
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


if __name__ == "__main__":
    unittest.main()
