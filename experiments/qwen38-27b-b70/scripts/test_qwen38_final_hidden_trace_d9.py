#!/usr/bin/env python3
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent

class Contract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hook=(HERE/"qwen38-final-hidden-trace-sitecustomize.py").read_text()
        cls.runner=(HERE/"run-20260831-qwen38-final-hidden-trace-d9.sh").read_text()

    def test_single_late_sync(self):
        self.assertIn('TARGET_CALL = int(',self.hook)
        self.assertIn('if call_index == TARGET_CALL:',self.hook)
        self.assertNotIn('for layer',self.hook)

    def test_inputs_and_final_hidden_are_complete_hashes(self):
        for name in ('"input_ids"','"positions"','"hidden_states"'):
            self.assertIn(name,self.hook)
        self.assertIn('reshape(-1).view(torch.uint8)',self.hook)

    def test_exact_failing_prompt_contract(self):
        self.assertIn('--api-mode completions',self.runner)
        self.assertIn('--prompt-id sql-debugging',self.runner)
        self.assertIn('--seed 42',self.runner)
        self.assertIn('VLLM_XPU_FINAL_HIDDEN_TRACE_CALL=60',self.runner)

    def test_four_fresh_processes_and_no_prefix_cache(self):
        self.assertIn('for process in 1 2 3 4',self.runner)
        self.assertIn('--no-enable-prefix-caching',self.runner)
        self.assertIn('verify-model-direct.py',self.runner)

if __name__ == '__main__': unittest.main()
