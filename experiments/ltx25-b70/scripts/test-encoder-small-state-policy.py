#!/usr/bin/env python3
"""Additive clone-policy regression tests; original candidate artifact stays frozen."""
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

LANE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('base', LANE / 'scripts/test-encoder-small-state.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
OriginalCandidate = base.Candidate
patch = LANE / 'patches/encoder-small-state-policy-guard.patch'
name = 'comfy/model_patcher.py'
source = base.helpers.apply_patch_in_memory({name: base.candidate}, patch.read_text())[name]
class GuardedCandidate(OriginalCandidate):
    pass
for method in ('_ltx_small_state', '_ltx_guard_small_state_policy', 'load', 'partially_load', 'partially_unload', 'unpatch_model'):
    setattr(GuardedCandidate, method, base.helpers.extract(source, 'ModelPatcher', dict(vars(base.mp)), method))
# The original make() default argument captured OriginalCandidate. Override only
# this imported test module's factory, leaving its on-disk source unchanged.
def make(enabled=True, cls=GuardedCandidate):
    p = cls(base.TinyGemma(), base.CPU, base.CPU)
    p.model_options['ltx_small_state_residency'] = enabled
    return p
base.make = make

class Tests(base.Tests):
    def test_only_stock_clip_compute_dtype_object_patch_is_supported(self):
        p = make()
        p.is_clip = True
        p.set_model_compute_dtype(base.torch.float32)
        p.load(base.CPU, full_load=True)
        self.assertEqual(p.loaded_size(), p.model_size())
        p.detach()
        p.object_patches['manual_cast_dtype'] = base.torch.float16
        with self.assertRaisesRegex(RuntimeError, 'patches/hooks'):
            p.load(base.CPU, full_load=True)

    def test_original_full_resident_clone_bypasses_policy_guard(self):
        p = make(True, OriginalCandidate)
        p.load(base.CPU, full_load=True)
        clone = p.clone()
        clone.model_options['ltx_small_state_residency'] = False
        self.assertEqual(clone.partially_load(base.CPU, extra_memory=0), 0)
        self.assertTrue(clone.model._ltx_small_buffers_loaded)
    def test_full_resident_clone_rejects_both_policy_toggles_before_return(self):
        for enabled in (False, True):
            p = make(enabled)
            p.load(base.CPU, full_load=True)
            before, size = base.hashes(p), p.loaded_size()
            clone = p.clone()
            clone.model_options['ltx_small_state_residency'] = not enabled
            for operation in (lambda: clone.partially_load(base.CPU, extra_memory=0),
                              lambda: clone.load(base.CPU, full_load=True),
                              lambda: clone.partially_unload(base.CPU, memory_to_free=1)):
                with self.assertRaisesRegex(RuntimeError, 'Detach before changing'):
                    operation()
            self.assertEqual(p.loaded_size(), size)
            self.assertEqual(base.hashes(p), before)
    def test_complete_detach_allows_deliberate_policy_change(self):
        for enabled in (False, True):
            p = make(enabled)
            p.load(base.CPU, full_load=True)
            before = base.hashes(p)
            clone = p.clone()
            clone.detach()
            clone.model_options['ltx_small_state_residency'] = not enabled
            clone.partially_load(base.CPU, extra_memory=1e9)
            self.assertEqual(clone.loaded_size(), clone.model_size())
            self.assertEqual(base.hashes(clone), before)
            self.assertEqual(bool(getattr(clone.model, '_ltx_small_state_policy', False)), not enabled)
    def test_same_policy_clone_keeps_full_resident_fast_return(self):
        for enabled in (False, True):
            p = make(enabled)
            p.load(base.CPU, full_load=True)
            clone = p.clone()
            self.assertEqual(clone.partially_load(base.CPU, extra_memory=0), 0)
            self.assertEqual(clone.loaded_size(), clone.model_size())

if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    print(json.dumps({'passed': result.wasSuccessful(), 'tests_run': result.testsRun,
                      'source_commit': base.PIN,
                      'patch_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (base.patch, patch)},
                      'scope': 'CPU-only original bypass reproduction plus real tiny Gemma4 lifecycle; no GPU validation'}, indent=2))
    raise SystemExit(0 if result.wasSuccessful() else 1)
