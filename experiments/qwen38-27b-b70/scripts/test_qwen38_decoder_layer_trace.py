#!/usr/bin/env python3
from pathlib import Path
import unittest
H=Path(__file__).resolve().parent
class Contract(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.h=(H/'qwen38-decoder-layer-trace-sitecustomize.py').read_text(); cls.r=(H/'run-qwen38-decoder-layer-trace.sh').read_text(); cls.d=(H/'run-20260831-qwen38-decoder-layer31-trace-d10.sh').read_text()
 def test_only_selected_late_output_sync(self):
  self.assertIn('self.layer_idx == TARGET_LAYER and call_index == TARGET_CALL',self.h)
  self.assertIn('result = _original_forward',self.h)
 def test_complete_output_pair(self):
  self.assertIn('"hidden_states": _hash_tensor(hidden_states)',self.h); self.assertIn('"residual": _hash_tensor(residual)',self.h)
 def test_reproduces_branch(self):
  for s in ('--prompt-id sql-debugging','--seed 42','--api-mode completions','--no-enable-prefix-caching'): self.assertIn(s,self.r)
 def test_d10_boundary(self):
  self.assertIn('TARGET_LAYER=31',self.d); self.assertIn('for process in 1 2 3 4',self.r)
 def test_call_is_explicit_and_generalized(self):
  self.assertIn(': "${TARGET_CALL:=60}"',self.r); self.assertIn('VLLM_XPU_DECODER_LAYER_TRACE_CALL="$TARGET_CALL"',self.r)
 def test_trace_hook_is_explicit_and_generalized(self):
  self.assertIn(': "${TRACE_HOOK_NAME:=qwen38-decoder-layer-trace-sitecustomize.py}"',self.r)
  self.assertIn('hook="$script_dir/$TRACE_HOOK_NAME"',self.r)
if __name__=='__main__': unittest.main()
