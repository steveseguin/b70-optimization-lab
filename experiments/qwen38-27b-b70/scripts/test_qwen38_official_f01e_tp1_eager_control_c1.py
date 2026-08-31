#!/usr/bin/env python3
"""Inert contract tests for the official-f01e TP1 strict control."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
RUNNER = Path(__file__).with_name(
    "run-20260831-qwen38-official-f01e-tp1-eager-control-c1.sh"
)
PREREG = ROOT / "experiments/qwen38-27b-b70/notes/2026-08-31-qwen38-official-f01e-tp1-eager-control-c1-prereg.md"


class Contract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = RUNNER.read_text()
        cls.prereg = PREREG.read_text()

    def test_exact_image_and_single_local_gpu(self):
        self.assertIn("f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f", self.runner)
        self.assertIn("ZE_AFFINITY_MASK=0", self.runner)
        self.assertIn("--tensor-parallel-size 1", self.runner)

    def test_eager_graph_off_and_no_prefix_cache(self):
        self.assertIn("VLLM_XPU_ENABLE_XPU_GRAPH=0", self.runner)
        self.assertIn("--enforce-eager", self.runner)
        self.assertIn("--no-enable-prefix-caching", self.runner)

    def test_complete_realistic_workload(self):
        for value in ("--max-tokens 512", "--metric-tokens 100", "--return-token-ids", "--require-natural-eos"):
            self.assertIn(value, self.runner)
        self.assertIn('g["cached_tokens_all_zero"]', self.runner)
        self.assertIn('len(p["rows"]) == 12', self.runner)

    def test_fresh_servers_and_caches(self):
        self.assertIn("run_arm official-A 18176", self.runner)
        self.assertIn("run_arm official-B 18177", self.runner)
        self.assertIn('local cache="$cache_root/$arm"', self.runner)

    def test_exact_cross_server_gate(self):
        self.assertIn('rows["official-A"][key] != rows["official-B"][key]', self.runner)
        self.assertIn("if mismatch: raise SystemExit(3)", self.runner)

    def test_no_automatic_promotion(self):
        self.assertIn('"promotion_authorized":False', self.runner)
        self.assertIn("cannot be promoted", self.prereg)


if __name__ == "__main__":
    unittest.main()
