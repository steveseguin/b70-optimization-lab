#!/usr/bin/env python3
"""Static fail-closed tests for the Q4 batched ladder's shared GPU locks."""

from pathlib import Path
import unittest


SCRIPT = Path(__file__).with_name("run-qwen38-q4km-tp1-batched-ladder.sh")


class BatchedLadderSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = SCRIPT.read_text(encoding="utf-8")

    def test_uses_canonical_host_and_benchmark_locks(self) -> None:
        self.assertIn("/run/lock/muse-glimmer-gpu-exclusive.lock", self.text)
        self.assertIn("/tmp/b70-benchmark.lock", self.text)
        self.assertIn('/tmp/b70-gpu${gpu_index}.lock', self.text)

    def test_locks_precede_process_scan_and_run_root_creation(self) -> None:
        first_flock = self.text.index("flock -n 7")
        process_scan = self.text.index("pgrep -af")
        run_root = self.text.index('mkdir -p "${out_parent}"')
        self.assertLess(first_flock, process_scan)
        self.assertLess(first_flock, run_root)

    def test_process_scan_includes_batched_bench(self) -> None:
        self.assertIn("llama-(server|bench|batched-bench)", self.text)


if __name__ == "__main__":
    unittest.main()
