#!/usr/bin/env python3
from pathlib import Path
import json
import unittest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = Path(__file__).with_name("run-qwen38-q4km-tp1-http-smallctx.sh")
SUITE = ROOT / "experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp1-http-smallctx-suite.json"


class SmallContextHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = SCRIPT.read_text(encoding="utf-8")

    def test_exact_frozen_profile(self) -> None:
        for fragment in (
            'parallel_slots="${PARALLEL_SLOTS:-64}"',
            'ctx_size="${CTX_SIZE:-32768}"',
            'concurrency_points="${CONCURRENCY_POINTS:-1,2,4,8,16,32,64}"',
            '--ctx-size "${ctx_size}"',
            '--parallel "${parallel_slots}"',
            '--max-tokens 128',
            '--concurrency "${concurrency_points}"',
            "a concurrency point exceeds PARALLEL_SLOTS",
        ):
            self.assertIn(fragment, self.text)

    def test_quality_requirements(self) -> None:
        for fragment in ("completion_tokens_128_all", "cached_tokens_all_zero", "oracle_hashes_exact_all"):
            self.assertIn(fragment, self.text)

    def test_profiles_have_separate_model_identities(self) -> None:
        for fragment in (
            "PROFILE must be tp1, tp2, or q8_tp1",
            "model_filename=Qwen3.8-27B-Q4_K_M.gguf",
            "model_filename=Qwen3.8-27B-Q8_0.gguf",
            "expected_model_sha=f5c702d8820d36fb55985bb238fc83ee3a313e920f4b752a437c3a6a9e14e4c8",
            "model_label=qwen38-q8-tp1-http-smallctx",
        ):
            self.assertIn(fragment, self.text)

    def test_locks_precede_process_scan(self) -> None:
        self.assertLess(self.text.index("flock -n 7"), self.text.index("pgrep -af"))

    def test_suite_is_short_and_distinct(self) -> None:
        value = json.loads(SUITE.read_text(encoding="utf-8"))
        prompts = value["prompts"]
        self.assertEqual(len(prompts), 8)
        self.assertEqual(len({p["id"] for p in prompts}), 8)
        self.assertTrue(all(len(p["prompt"].split()) <= 18 for p in prompts))


if __name__ == "__main__":
    unittest.main()
