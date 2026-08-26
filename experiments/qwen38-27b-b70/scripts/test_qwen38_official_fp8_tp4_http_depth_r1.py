#!/usr/bin/env python3
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-fp8-tp4-http-depth-r1.sh"
PREREG = ROOT / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-fp8-tp4-http-depth-r1-prereg.json"


class ContractTest(unittest.TestCase):
    def test_frozen_contract(self):
        text = SCRIPT.read_text()
        manifest = json.loads(PREREG.read_text())
        self.assertEqual(manifest["measured_depths"], [2048, 4096, 8192, 16384, 24576, 32768])
        self.assertEqual(manifest["tuple"]["cards"], 4)
        self.assertEqual(manifest["tuple"]["generation"], "target-only / MTP0 / no draft / no speculation")
        self.assertIn("--tensor-parallel-size 4", text)
        self.assertIn("ZE_AFFINITY_MASK=0,1,2,3", text)
        self.assertIn("--max-model-len 33024", text)
        self.assertIn("--max-num-seqs 1", text)
        self.assertIn("--max-num-batched-tokens 4096", text)
        self.assertIn("--no-enable-prefix-caching", text)
        self.assertIn("--response-adapter vllm", text)
        self.assertIn("effective_prompt_throughput_proxy_tok_s", text)
        self.assertNotIn("interpolat", text.lower().replace("interpolation", ""))

    def test_create_only_and_cleanup(self):
        text = SCRIPT.read_text()
        self.assertIn('[[ ! -e "${run_dir}" ]]', text)
        self.assertIn("docker stop -t 20", text)
        self.assertIn("cleanup-status.txt", text)
        self.assertIn("repository must be clean", text)
        self.assertIn("--execute --ack", text)


if __name__ == "__main__":
    unittest.main()
