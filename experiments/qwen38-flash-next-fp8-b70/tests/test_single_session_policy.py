"""Preparation checks only: deliberately never enter the device execution path."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1] / "stability"
SCRIPT = ROOT / "serve-single-session.sh"


class PolicyTests(unittest.TestCase):
    def test_no_arguments_cannot_launch(self):
        result = subprocess.run(["bash", str(SCRIPT)], capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 2)

    def test_explicit_execute_still_refuses_until_review_complete(self):
        result = subprocess.run([
            "bash", str(SCRIPT), "--execute", "--ack",
            "RUN qwen38-flash-next-stability-mtp1-33280-single-session-v1"
        ], capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"candidate disabled", result.stderr)

    def test_hash_and_syntax(self):
        manifest = json.loads((ROOT / "provenance.json").read_text())
        self.assertEqual(hashlib.sha256(SCRIPT.read_bytes()).hexdigest(), manifest["candidate_sha256"])
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True, timeout=5)

    def test_single_launch_and_no_host_mutation_commands(self):
        source = SCRIPT.read_text()
        self.assertEqual(source.count('setsid "${vllm_bin}" serve'), 1)
        self.assertNotRegex(source, r"\b(sudo|swapoff|swapon|sysctl|reboot|modprobe)\b")
        self.assertNotIn("drop_caches", source)
        self.assertNotIn("kill -KILL", source)
        self.assertNotRegex(source, r">\s*[\"']?/(sys|proc)/")
        self.assertNotIn("-delete", source)
        for selector in (
            "VLLM_XPU_GDN_SERIAL_SPEC_DECODE=0",
            "VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=1",
            "VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=1",
            "VLLM_XPU_GDN_NATIVE_SPEC_COMPLETION_BARRIER=1",
        ):
            self.assertIn("export " + selector, source)
        self.assertIn("/tmp/b70-benchmark.lock", source)
        self.assertIn("/tmp/b70-gpu${gpu}.lock", source)


if __name__ == "__main__":
    unittest.main()
