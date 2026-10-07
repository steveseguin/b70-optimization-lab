"""CPU-only evidence boundary tests; no inference/runtime dependencies."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import export_trials as exporter


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def dump(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def trial(self, name='trial__one', correct=1, void=False, finished=True, exception=None):
        task = self.root / 'task'
        (task / 'tests').mkdir(parents=True, exist_ok=True)
        (task / 'environment').mkdir(exist_ok=True)
        (task / 'task.toml').write_text('[metadata]\nseed=0\nkind="sparse"\nmode="memory"\n'
                                      'target_tokens=480000\nstream_tokens=479512\ndensity=3\nn_surprise=0\n')
        self.dump(task / 'tests/expected.json', {'a': 1, 'b': 2})
        (task / 'environment/stream.jsonl').write_text('{"text":"a=1,b=2"}\n')
        p = self.root / 'runs/jobs/B32iq__task' / name
        self.dump(p / 'config.json', {'task': {'path': str(task)}, 'trial_name': name,
                                     'agent': {'name': 'test', 'model_name': 'model',
                                               'kwargs': {'context_budget_tokens': 32768, 'api_key': 'do-not-export'}}})
        self.dump(p / 'result.json', {'started_at': '2026-10-06T00:00:00Z',
                                     'finished_at': '2026-10-06T00:01:00Z' if finished else None,
                                     'exception_info': {'exception_type': exception} if exception else None,
                                     'agent_info': {'version': '0.1'}})
        self.dump(p / 'agent/usage.json', {'completion_tokens': 30, 'n_lm_calls': 4,
                                         'code_fingerprint': {'harness': '123abc'}})
        if finished and not exception:
            self.dump(p / 'verifier/details.json', {'correct': correct, 'n': 2, 'void': void,
                                                   'counts': {'correct': correct, 'wrong': 2-correct},
                                                   'score_raw': correct / 2, 'score': 0 if void else correct / 2})
        return p

    def test_exact_counts_void_and_multiple_attempts_preserved(self):
        self.trial('trial__one', correct=1)
        self.trial('trial__two', correct=2, void=True)
        out = self.root / 'out'
        result = exporter.export([], [self.root / 'runs'], out)
        self.assertEqual(len(result['rows']), 2)
        self.assertEqual([(r['correct'], r['asked'], r['void'], r['status']) for r in result['rows']],
                         [(1, 2, False, 'completed'), (2, 2, True, 'completed')])
        self.assertNotIn('do-not-export', (out / 'manifest.json').read_text())
        self.assertEqual(result['rows'][0]['versions']['checker']['status'], 'unknown')

    def test_interrupted_and_unfinished_are_not_scores(self):
        self.trial('trial__cancelled', exception='CancelledError')
        self.trial('trial__running', finished=False)
        rows = exporter.export([], [self.root / 'runs'], self.root / 'out')['rows']
        self.assertEqual([r['status'] for r in rows], ['interrupted', 'incomplete'])
        self.assertTrue(all(r['correct'] is None and r['asked'] is None for r in rows))

    def test_missing_grade_is_not_inferred_from_reward(self):
        p = self.trial()
        (p / 'verifier/details.json').unlink()
        self.dump(p / 'result.json', {'finished_at': '2026-10-06T00:01:00Z', 'verifier_result': {'rewards': {'reward': 1}}})
        row = exporter.raw_trial(p)[0]
        self.assertEqual(row['status'], 'incomplete')
        self.assertIsNone(row['correct'])

    def test_malformed_and_missing_inputs_fail_before_output(self):
        p = self.trial()
        (p / 'verifier/details.json').write_text('{')
        with self.assertRaises(ValueError):
            exporter.export([], [p], self.root / 'out')
        self.assertFalse((self.root / 'out').exists())
        (p / 'config.json').unlink()
        with self.assertRaises(exporter.EvidenceError):
            exporter.raw_trial(p)

    def test_denominator_and_boolean_integer_rejected(self):
        p = self.trial()
        for grade in [{'correct': 1, 'n': 24, 'void': False}, {'correct': True, 'n': 2, 'void': False}]:
            self.dump(p / 'verifier/details.json', grade)
            with self.assertRaises(exporter.EvidenceError):
                exporter.raw_trial(p)

    def test_multi_attempt_summary_cannot_be_borrowed(self):
        p = self.trial('trial__one')
        self.trial('trial__two')
        summary = self.root / 'runs/B32iq__task.summary.txt'
        summary.write_text('arm\twall_s\tcompletion_tokens\nB32iq\t999\t9999\n')
        row = exporter.raw_trial(p)[0]
        self.assertEqual(row['elapsed_seconds'], 60)
        self.assertEqual(row['completion_tokens'], 30)
        self.assertNotIn('summary', row['sources'])

    def test_deterministic_export_and_bound_projection(self):
        p = self.trial()
        a, b = self.root / 'out-a', self.root / 'out-b'
        exporter.export([], [p], a)
        exporter.export([], [p], b)
        for file in ['manifest.json', 'site_projection.json', 'results.md']:
            self.assertEqual((a / file).read_bytes(), (b / file).read_bytes())
        manifest = json.loads((a / 'manifest.json').read_text())
        projection = json.loads((a / 'site_projection.json').read_text())
        self.assertEqual(projection['rows'], manifest['rows'])
        self.assertEqual(projection['manifest_sha256'], hashlib.sha256((a / 'manifest.json').read_bytes()).hexdigest())

    def test_review_copy_hash_is_enforced(self):
        p = self.trial()
        row, _ = exporter.raw_trial(p)
        index = self.root / 'review.json'
        self.dump(index, {'schema': 'context-review-evidence.v1', 'rows': [
            {'id': 'trial__one', 'sources': {'verifier': {'path': str(p / 'verifier/details.json'),
            'sha256': '0' * 64, 'bytes': 1}}, 'copies': {'verifier.json': 'wrong.json'}}]})
        self.dump(self.root / 'wrong.json', {'n': 24})
        with self.assertRaisesRegex(exporter.EvidenceError, 'SHA256'):
            exporter.import_review(index)

    def test_empty_selection_fails(self):
        with self.assertRaisesRegex(exporter.EvidenceError, 'no trial records'):
            exporter.export([], [self.root], self.root / 'out')


if __name__ == '__main__':
    unittest.main()
