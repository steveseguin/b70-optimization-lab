"""CPU-only campaign identity/gate and extraction-calibration regressions."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import campaign
import extraction
from pilot import StubClient, ARMS
from tasks import make_task, encoded


class FixtureClient(StubClient):
    kind = 'model'  # Test double only: no network/model invocation.
    model = 'fixture-model'
    endpoint = 'http://127.0.0.1:9999/v1'

    def __init__(self, task, mode='correct'):
        super().__init__(task); self.mode = mode

    def __call__(self, messages, phase, batch_id):
        events = copy.deepcopy(self.task['oracle']['events'][batch_id-1])
        if self.mode == 'reverse': events.reverse()
        if self.mode == 'float':
            for event in events: event['amount'] = float(event['amount'])
        if self.mode == 'malformed': events = [None]
        if self.mode == 'fail': raise RuntimeError('injected client failure')
        return json.dumps({'events': events}), {}


class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='campaign-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.suite_path = self.root / 'suite.json'
        self.tasks = [make_task(seed=7, batches=4, filler_words=0, style=style)
                      for style in ('report', 'dispatch')]
        rows = []
        for task in self.tasks:
            path = self.root / (task['style'] + '.json')
            path.write_text(json.dumps(task))
            rows.append({'path': path.name, 'task_sha256': task['task_sha256'],
                         'file_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        self.suite_path.write_text(json.dumps({'cases': rows, 'arms': list(ARMS)}))
        self.frozen = campaign.plan(self.suite_path)
        lock = patch.object(campaign, 'endpoint_lock_path', return_value=self.root / 'endpoint.lock')
        lock.start(); self.addCleanup(lock.stop)

    def result(self, item, *, kind='model', identity=None):
        return {'status': 'completed', 'task_sha256': item['task_sha256'], 'arm': item['arm'],
                'score': {'asked': 24, 'correct': 24, 'valid': True}, 'measurement_kind': kind,
                'timing_complete': True, 'resumed': False,
                'wall_seconds_this_session': 8 if item['arm'] == 'quoted' else 10,
                'source_sha256': self.frozen['source_sha256'], 'server_identity': identity,
                'context_limit_utf8_bytes': self.frozen['context_limit_utf8_bytes']}

    def fake_run(self, task, arm, out, client, limit, identity=None):
        return self.result({'task_sha256': task['task_sha256'], 'arm': arm},
                           kind=client.kind, identity=identity)

    def test_complete_matrix_qualifies_only_for_clean_model_timing(self):
        results = [self.result(item) for item in self.frozen['runs']]
        summary = campaign.summarize(results, self.frozen['runs'])
        self.assertTrue(summary['quality_gate_passed'])
        self.assertTrue(summary['speed_gate_passed'])
        self.assertEqual(summary['median_quoted_over_archive_elapsed_ratio'], .8)
        self.assertFalse(campaign.summarize(results, self.frozen['runs'], campaign_clean=False)['speed_gate_passed'])
        results[0]['timing_complete'] = False
        self.assertFalse(campaign.summarize(results, self.frozen['runs'])['speed_gate_passed'])

    def test_partial_unpaired_or_duplicate_matrix_cannot_qualify(self):
        results = [self.result(item) for item in self.frozen['runs']]
        for bad in (results[:-1], results + results[:1], copy.deepcopy(results)):
            if len(bad) == len(results): bad[-1]['task_sha256'] = 'different-task'
            summary = campaign.summarize(bad, self.frozen['runs'])
            self.assertFalse(summary['complete_planned_matrix'])
            self.assertFalse(summary['quality_gate_passed'])
            self.assertFalse(summary['speed_gate_passed'])
            self.assertIsNone(summary['median_quoted_over_archive_elapsed_ratio'])

    def test_stub_or_wrong_answer_or_nonfinite_time_cannot_pass(self):
        for mutate in (lambda r: r.update(measurement_kind='stub'),
                       lambda r: r['score'].update(correct=23),
                       lambda r: r.update(wall_seconds_this_session=float('nan'))):
            results = [self.result(item) for item in self.frozen['runs']]
            mutate(results[0])
            self.assertFalse(campaign.summarize(results, self.frozen['runs'])['speed_gate_passed'])

    def test_self_consistent_task_edit_is_not_a_frozen_task(self):
        path = self.root / self.frozen['runs'][0]['task']
        task = json.loads(path.read_text()); task['batches'][0]['text'] += ' Edited.'
        del task['task_sha256']; task['task_sha256'] = hashlib.sha256(encoded(task)).hexdigest()
        path.write_text(json.dumps(task))
        with self.assertRaisesRegex(ValueError, 'task bytes changed'):
            campaign.verify_frozen(self.frozen, self.suite_path, self.frozen['runs'][0])

    def test_source_drift_and_result_identity_drift_are_rejected(self):
        with patch.object(campaign, 'source_hashes', return_value={'changed.py': 'new'}):
            with self.assertRaisesRegex(ValueError, 'source files changed'):
                campaign.verify_frozen(self.frozen, self.suite_path, self.frozen['runs'][0])
        result = self.result(self.frozen['runs'][0]); result['source_sha256'] = {}
        with self.assertRaisesRegex(ValueError, 'source_sha256'):
            campaign.verify_result(result, self.frozen, self.frozen['runs'][0], 'model', None)

    def test_failed_attempt_is_retained_and_resume_cannot_qualify(self):
        out = self.root / 'campaign'
        with patch.object(campaign, 'run', side_effect=RuntimeError('injected failure')):
            with self.assertRaises(RuntimeError):
                campaign.execute(self.frozen, self.suite_path, out, stub=True)
        with patch.object(campaign, 'run', side_effect=self.fake_run):
            result = campaign.execute(self.frozen, self.suite_path, out, stub=True)
        history = [json.loads(line) for line in (out / 'campaign-attempts.jsonl').read_text().splitlines()]
        self.assertEqual([row['status'] for row in history], ['started', 'failed', 'started', 'completed'])
        self.assertFalse(result['campaign_clean'])
        self.assertFalse(result['speed_gate_passed'])

    def test_execution_identity_is_bound_before_resuming(self):
        out = self.root / 'identity-bound'
        with patch.object(campaign, 'run', side_effect=RuntimeError('stop')):
            with self.assertRaises(RuntimeError):
                campaign.execute(self.frozen, self.suite_path, out, stub=True)
        identity_path = out / 'execution-identity.json'
        saved = json.loads(identity_path.read_text()); saved['measurement_kind'] = 'model'
        identity_path.write_text(json.dumps(saved))
        with patch.object(campaign, 'run') as call:
            with self.assertRaisesRegex(ValueError, 'execution identity changed'):
                campaign.execute(self.frozen, self.suite_path, out, stub=True)
            call.assert_not_called()

    def calibration_files(self):
        identity = {'endpoint': FixtureClient.endpoint, 'model': FixtureClient.model, 'launch_sha256': 'fixture'}
        paths = []
        for style in ('report', 'dispatch'):
            task = make_task(seed=7, batches=48, filler_words=320, style=style)
            path = self.root / ('calibration-' + task['style'])
            extraction.diagnose(task, FixtureClient(task), path, extraction.DEVELOPMENT_INDICES, identity=identity)
            paths.append(path / 'result.json')
        return paths, identity

    def test_live_calibration_requires_both_styles_and_same_runtime(self):
        paths, identity = self.calibration_files()
        records = campaign.validate_calibration(paths, self.frozen, identity)
        self.assertEqual(len(records), 2)
        for bad_paths in (None, paths[:1], [paths[0], paths[0]]):
            with self.assertRaises(ValueError):
                campaign.validate_calibration(bad_paths, self.frozen, identity)
        changed = dict(identity, model='different')
        with self.assertRaises(ValueError):
            campaign.validate_calibration(paths, self.frozen, changed)
        data = json.loads(paths[1].read_text()); data['seed'] = 19; paths[1].write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            campaign.validate_calibration(paths, self.frozen, identity)

    def test_calibration_subset_wrong_task_budget_or_99_percent_is_rejected(self):
        paths, identity = self.calibration_files()
        original = json.loads(paths[0].read_text())
        alternatives = []
        subset = copy.deepcopy(original)
        subset['indices'] = [1, 2, 3, 4]; subset['rows'] = subset['rows'][:4]
        alternatives.append(subset)
        wrong_task = copy.deepcopy(original)
        wrong_task['task_sha256'] = make_task(seed=7, batches=48, filler_words=0)['task_sha256']
        alternatives.append(wrong_task)
        wrong_budget = copy.deepcopy(original); wrong_budget['context_limit_utf8_bytes'] = 12000
        alternatives.append(wrong_budget)
        near_exact = copy.deepcopy(original); near_exact['event_recall'] = .99
        alternatives.append(near_exact)
        for invalid in alternatives:
            with self.subTest(indices=invalid['indices'], recall=invalid['event_recall']):
                paths[0].write_text(json.dumps(invalid))
                with self.assertRaises(ValueError):
                    campaign.validate_calibration(paths, self.frozen, identity)
        paths[0].write_text(json.dumps(original))
        self.assertEqual(len(campaign.validate_calibration(paths, self.frozen, identity)), 2)
        self.assertIn('100% exact', original['gate_policy'])

    def test_no_live_requests_before_calibration(self):
        launch = self.root / 'launch.json'; launch.write_text('{}')
        with patch.object(campaign, 'HTTPClient') as client:
            with self.assertRaisesRegex(ValueError, 'requires --calibration'):
                campaign.execute(self.frozen, self.suite_path, self.root / 'blocked',
                                 endpoint=FixtureClient.endpoint, server_identity=launch)
            client.assert_not_called()

    def test_extraction_rejects_reversed_float_and_malformed_events_without_crash(self):
        task = self.tasks[0]
        for mode in ('reverse', 'float', 'malformed'):
            with self.subTest(mode=mode):
                result = extraction.diagnose(task, FixtureClient(task, mode), self.root / mode, [1])
                self.assertFalse(result['gate_passed'])
                self.assertEqual(result['status'], 'completed')
        self.assertFalse(json.loads((self.root / 'reverse' / 'result.json').read_text())['rows'][0]['exact_order'])

    def test_extraction_indices_budget_and_holdout_restrictions(self):
        for indices in ([], [1, 1], [0], [5], [True], ['1']):
            with self.assertRaises(ValueError):
                extraction.diagnose(self.tasks[0], FixtureClient(self.tasks[0]), self.root / 'invalid', indices)
        with self.assertRaises(ValueError):
            extraction.diagnose(self.tasks[0], FixtureClient(self.tasks[0]), self.root / 'oversize', [1], limit=99999)
        heldout = make_task(seed=19, batches=4, filler_words=0)
        with self.assertRaisesRegex(ValueError, 'development seed 7'):
            extraction.diagnose(heldout, FixtureClient(heldout), self.root / 'holdout', [1])

    def test_extraction_failure_keeps_failed_status_and_calls(self):
        out = self.root / 'failed-extraction'
        with self.assertRaisesRegex(RuntimeError, 'injected client failure'):
            extraction.diagnose(self.tasks[0], FixtureClient(self.tasks[0], 'fail'), out, [1])
        self.assertEqual(json.loads((out / 'status.json').read_text())['status'], 'failed')
        self.assertTrue((out / 'calls.jsonl').exists())
        self.assertTrue((out / 'failures.jsonl').exists())
        self.assertFalse((out / 'result.json').exists())
        with self.assertRaises(FileExistsError):
            extraction.diagnose(self.tasks[0], FixtureClient(self.tasks[0]), out, [1])

    def test_real_stub_campaign_completes_without_passing_model_gates(self):
        result = campaign.execute(self.frozen, self.suite_path, self.root / 'stub', stub=True)
        self.assertTrue(result['complete_planned_matrix'])
        self.assertFalse(result['quality_gate_passed'])
        self.assertFalse(result['speed_gate_passed'])


if __name__ == '__main__':
    unittest.main()
