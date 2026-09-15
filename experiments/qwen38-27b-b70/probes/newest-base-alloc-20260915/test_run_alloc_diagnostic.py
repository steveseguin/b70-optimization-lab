"""CPU-only tests for the allocation diagnostic; no Docker, GPU or sudo."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('alloc_diag', Path(__file__).with_name('run-alloc-diagnostic.py'))
diag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diag)
GIB = diag.GIB


def sample(unaccounted_gib, available_gib=12):
    return {'unaccounted': int(unaccounted_gib * GIB), 'available': int(available_gib * GIB)}


def result(label, growth, **kw):
    base = dict(label=label, env={}, samples=[sample(0.3), sample(0.3 + growth)], baseline=int(0.3 * GIB),
                exit_code=0, fault_lines=[], guard_fired=False, log_text='ALLOC-DONE {}', timed_out=False)
    base.update(kw)
    return diag.run_result(**base)


class DiagnosticTests(unittest.TestCase):
    def test_runs_are_safest_first_and_only_last_omits_allocator(self):
        labels = [label for label, _ in diag.RUNS]
        self.assertEqual(labels, ['one-gpu-default', 'two-gpu-expandable', 'two-gpu-default'])
        self.assertEqual(diag.RUNS[1][1]['PYTORCH_ALLOC_CONF'], 'expandable_segments:True')
        self.assertNotIn('PYTORCH_ALLOC_CONF', diag.RUNS[2][1])

    def test_argv_is_unprivileged_and_bounded(self):
        argv = diag.docker_argv('n', diag.RUNS[1][1])
        self.assertNotIn('--privileged', argv)
        self.assertEqual(argv[argv.index('--network') + 1], 'none')
        self.assertIn('--env', argv)
        self.assertIn('PYTORCH_ALLOC_CONF=expandable_segments:True', argv)
        self.assertIn('PrintIoctlEntries=1', argv)
        self.assertEqual(argv[argv.index(diag.IMAGE) + 1:argv.index(diag.IMAGE) + 2], ['-c'])

    def test_verdict_admits_model_launch_only_when_expandable_is_clean(self):
        good = [result('one-gpu-default', 0.1), result('two-gpu-expandable', 0.1),
                result('two-gpu-default', 2.0, log_text='ALLOC-DONE PRIME_HANDLE_TO_FD')]
        v = diag.verdict(good)
        self.assertTrue(v['model_launch_admissible'])
        self.assertTrue(v['default_two_gpu_reproduces'])
        grown = [result('two-gpu-expandable', 1.2)]
        self.assertFalse(diag.verdict(grown)['model_launch_admissible'])
        faulted = [result('two-gpu-expandable', 0.1), result('two-gpu-default', 0.1, fault_lines=['xe CAT error'])]
        self.assertFalse(diag.verdict(faulted)['model_launch_admissible'])
        unfinished = [result('two-gpu-expandable', 0.1, log_text='')]
        self.assertFalse(diag.verdict(unfinished)['model_launch_admissible'])

    def test_missing_samples_are_not_clean(self):
        r = diag.run_result('two-gpu-expandable', {}, [], 0, 0, [], False, 'ALLOC-DONE', False)
        self.assertIsNone(r['driver_growth_gib'])
        self.assertFalse(diag.clean(r))


if __name__ == '__main__':
    unittest.main()
