#!/usr/bin/env python3
"""Regression tests for the verifier-trace alignment helper."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
ANALYZER = HERE / "analyze-verifier-trace.py"
PROMPT_ID = "holdout--arithmetic-reasoning"


class VerifierTraceAnalyzerTest(unittest.TestCase):
    def test_tp_duplicates_seed_token_and_later_row_divergence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / "candidate.json"
            reference = root / "reference.json"
            trace = root / "trace.jsonl"
            output = root / "analysis.json"
            candidate.write_text(json.dumps({"rows": [{
                "prompt_id": PROMPT_ID,
                "token_ids": [10, 20, 30, 99],
            }]}))
            reference.write_text(json.dumps({"rows": [{
                "prompt_id": PROMPT_ID,
                "token_ids": [10, 20, 30, 40],
            }]}))
            warmup = {
                "stage": "dense",
                "records": [{
                    "draft_token_ids": [0, 0, 0],
                    "target_argmax_token_ids": [1, 2, 3],
                    "output_token_ids": [1],
                }],
            }
            request = {
                "stage": "dense",
                "records": [{
                    "draft_token_ids": [20, 30, 99],
                    "target_argmax_token_ids": [20, 30, 99],
                    "output_token_ids": [20, 30, 99],
                }],
            }
            trace.write_text("\n".join(json.dumps(row) for row in (
                warmup, warmup, request, request,
            )) + "\n")

            subprocess.run([
                sys.executable,
                str(ANALYZER),
                "--trace", str(trace),
                "--candidate", str(candidate),
                "--reference", str(reference),
                "--prompt-id", PROMPT_ID,
                "--out", str(output),
            ], check=True, stdout=subprocess.DEVNULL)

            result = json.loads(output.read_text())
            self.assertEqual(result["trace_record_count"], 2)
            self.assertEqual(result["candidate_tokens_before_trace"], 1)
            self.assertEqual(
                result["classification"],
                "target_verifier_row_diverged_before_or_at_output",
            )
            self.assertEqual(
                result["first_target_verifier_disagreement"]["row_index"], 2
            )
            self.assertEqual(
                result["first_target_verifier_disagreement"]["output_position"], 3
            )


if __name__ == "__main__":
    unittest.main()
