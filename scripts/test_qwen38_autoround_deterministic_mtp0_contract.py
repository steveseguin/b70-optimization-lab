#!/usr/bin/env python3
"""Static fail-closed contract tests for the Qwen3.8 INT4 MTP0 campaign."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "repro/qwen38-27b-autoround-int4-b70/scripts/run-current-deterministic-mtp0-server.sh"
ATTEMPT = ROOT / "experiments/qwen38-27b-b70/scripts/run-20260828-qwen38-autoround-deterministic-mtp0-strict-attempt.sh"


class DeterministicMtp0ContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = SERVER.read_text()
        cls.attempt = ATTEMPT.read_text()

    def test_server_pins_correctness_treatment(self) -> None:
        for required in (
            "--tensor-parallel-size 2",
            "--dtype float16 --kv-cache-dtype auto",
            "--env VLLM_XPU_ENABLE_XPU_GRAPH=0",
            "--env VLLM_XPU_GRAPH=0",
            "--env TORCHINDUCTOR_DETERMINISTIC=1",
            "--env VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=1",
            "VLLM_XPU_ONEDNN_INT4_DETERMINISM_PAD",
            "--compilation-config '{\"cudagraph_mode\":\"NONE\"}'",
            "--no-enable-prefix-caching",
        ):
            self.assertIn(required, self.server)
        self.assertNotIn("--speculative-config", self.server)

    def test_server_fails_closed_on_identity_and_shared_state(self) -> None:
        for required in (
            "EXPECTED_IMAGE_ID:?",
            "MODEL_DIR must be a real directory",
            "MODEL_DIR must be on ext4",
            "cache path must be new",
            "patched image file identities mismatch",
            "INT4 determinism patch identity mismatch",
            "/tmp/b70-benchmark.lock",
            "/tmp/b70-gpu2.lock",
            "/tmp/b70-gpu3.lock",
        ):
            self.assertIn(required, self.server)

    def test_attempt_enforces_full_strict_workload(self) -> None:
        for required in (
            "--max-tokens 512",
            "--metric-tokens 100",
            "--return-token-ids",
            "--require-natural-eos",
            'len(p["rows"]) == 12',
            'g["cached_tokens_all_zero"]',
            'p["fresh_response_validity"]["performance_gate_eligible"]',
            'c["pass_all"]',
        ):
            self.assertIn(required, self.attempt)

    def test_attempt_rejects_graphs_and_leaks(self) -> None:
        for required in (
            "unexpected XPU Graph capture",
            "container remained after bounded shutdown",
            "port remained occupied after bounded shutdown",
            "vLLM process remained after bounded shutdown",
            "new GPU2/3 kernel fault event detected",
        ):
            self.assertIn(required, self.attempt)


if __name__ == "__main__":
    unittest.main()
