"""Negative controls for actual pinned graph authority and pipeline phase barriers."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import types
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('resolution_session_tested', HERE / 'session.py')
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)
PLAN = HERE.parent / '20261007-resolution-full-103/candidate-plan.json'


def empty_state():
    return {'queue_pending': 0, 'queue_running': 0, 'pipeline': {'running': 0, 'stages': {}},
            'fault': False, 'sampler_routes': 0, 'lean_state': 0, 'decode_replicas': 0}


class SessionControls(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.state = empty_state()
        self.verified = []
        def verifier(path, sha):
            self.verified.append((path, sha))
            return {'plan_sha256': S.PLAN_SHA256, 'runtime_manifest_sha256': 'a'*64,
                    'server_identity_sha256': 'b'*64}
        self.a = S.Authority(PLAN, 'a'*64, 'b'*64, self.root,
                             lambda: copy.deepcopy(self.state), {'reference_verified': verifier})
        self.rows = self.a.plan['requests']

    def tearDown(self):
        self.tmp.cleanup()

    def run_row(self, row):
        self.a.begin(row['name'], row['graph'], 'pid-' + row['name'])
        result = self.a.require_phase('text', self.a.plan['qualification_id'], row['name'])
        self.a.finish([('execution_cached', {'nodes': []}),
                       ('execution_success', {'prompt_id': 'pid-' + row['name']})])
        return result

    def test_actual_twenty_native_graphs_require_independent_ordered_executions(self):
        for row in (r for r in self.rows if r['phase'] in ('native-reference','native-repeat')):
            receipt = self.run_row(row)
            self.assertEqual(receipt['phase'], 'native_reference')
            self.assertIsNone(receipt['reference_receipt_sha256'])
        self.assertEqual(len(self.a.completed), 20)
        self.assertEqual(len(self.a.prompt_ids), 20)
        self.assertEqual(self.a.capture_count, 20)

    def test_capture_cap80_separate_from87_request_plan(self):
        self.assertEqual(len(self.rows),78)
        self.a.capture_count=79
        self.run_row(self.rows[0])
        self.assertEqual(self.a.capture_count,80)
        with self.assertRaisesRegex(RuntimeError,'capture allowance exhausted'):
            self.run_row(self.rows[1])
        self.assertEqual(self.a.capture_count,80)
        self.assertIsNotNone(self.a.failed)

    def test_noncapturing_setup_does_not_consume_capture_allowance(self):
        spec=importlib.util.spec_from_file_location('w2_test_schedule',HERE/'schedule.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        setup=module.build_schedule()['schedule']['rows']
        self.assertEqual(len(setup),9)
        self.assertEqual(sum(any(n['class_type'] in ('LTXBaselineCapture','LTXPipelineSave')
                                 for n in r['graph'].values()) for r in [*self.rows,*setup]),80)
        self.a=S.Authority(PLAN,'a'*64,'b'*64,self.root,lambda:copy.deepcopy(self.state),{},setup)
        self.a.capture_count=80
        row=setup[0]
        self.a.begin(row['name'],row['graph'],'setup-pid')
        self.a.finish([('execution_success',{'prompt_id':'setup-pid'})])
        self.assertEqual(self.a.capture_count,80)

    def test_forged_graph_fails_before_authorization_and_latches(self):
        row = self.rows[0]
        graph = copy.deepcopy(row['graph'])
        graph['338']['inputs']['noise_seed'] += 1
        with self.assertRaisesRegex(RuntimeError, 'Submitted graph differs'):
            self.a.begin(row['name'], graph, 'p1')
        with self.assertRaisesRegex(RuntimeError, 'Session halted'):
            self.a.begin(row['name'], row['graph'], 'p2')
        self.assertTrue((self.root / 'resolution-halt.json').exists())

    def test_no_cached_or_failed_execution_may_count(self):
        row = self.rows[0]
        self.a.begin(row['name'], row['graph'], 'p1')
        with self.assertRaisesRegex(RuntimeError, 'Failed or cached'):
            self.a.finish([('execution_cached', {'nodes': ['344']}),
                           ('execution_success', {'prompt_id': 'p1'})])
        self.assertEqual(self.a.completed, [])

    def test_optimized_candidate_cannot_run_before_native_receipt(self):
        row = next(r for r in self.rows if r['phase']=='candidate-check')
        with self.assertRaisesRegex(RuntimeError, 'wrong phase'):
            self.a.begin(row['name'], row['graph'], 'p1')

    def test_repeat_cannot_run_before_first_pass(self):
        row = next(r for r in self.rows if r['phase']=='native-repeat')
        with self.assertRaisesRegex(RuntimeError, 'first pass incomplete'):
            self.a.begin(row['name'], row['graph'], 'p1')

    def test_role_and_active_request_binding(self):
        row = self.rows[0]
        self.a.begin(row['name'], row['graph'], 'p1')
        with self.assertRaisesRegex(RuntimeError, 'Role disallowed'):
            self.a.require_phase('sampler', self.a.plan['qualification_id'], row['name'])
        with self.assertRaisesRegex(RuntimeError, 'Session halted'):
            self.a.require_phase('text', self.a.plan['qualification_id'], row['name'])

    def test_role_cannot_authorize_other_request(self):
        row = self.rows[0]
        self.a.begin(row['name'], row['graph'], 'p1')
        with self.assertRaisesRegex(RuntimeError, 'No admitted'):
            self.a.require_phase('text', self.a.plan['qualification_id'], self.rows[1]['name'])

    def test_native_refuses_optimized_state_and_queued_work(self):
        self.state['sampler_routes'] = 1
        with self.assertRaisesRegex(RuntimeError, 'optimized state'):
            self.run_row(self.rows[0])

    def test_reference_transition_requires_actual_verifier_and_identity(self):
        for row in (r for r in self.rows if r['phase'] in ('native-reference','native-repeat')):
            self.run_row(row)
        receipt = self.root / 'references.json'
        receipt.write_text('{"test":"verifier called separately"}')
        sha = S.digest(receipt.read_bytes())
        self.a.advance('reference_verified', receipt, sha)
        self.assertEqual(self.verified, [(receipt, sha)])
        self.assertEqual(self.a.references_sha, sha)
        self.a.advance('optimized_preparation')
        row = next(r for r in self.rows if r['phase']=='candidate-check')
        self.a.begin(row['name'], row['graph'], 'candidate-p1')
        auth = self.a.require_phase('sampler', self.a.plan['qualification_id'], row['name'])
        self.assertEqual(auth['reference_receipt_sha256'], sha)

    def test_transition_cannot_skip_evidence(self):
        with self.assertRaisesRegex(RuntimeError, 'next barrier'):
            self.a.advance('optimized_preparation')

    def test_unfinished_or_failed_tails_are_not_quiescent(self):
        base = empty_state()
        base['pipeline']['stages']['sample'] = {'queued_indices': [],
            'jobs': [{'index': 4, 'done': True, 'error': None}]}
        S.require_quiescent(base)
        with self.assertRaisesRegex(RuntimeError, 'tail remains'):
            S.require_quiescent(base, no_tails=True)
        base['pipeline']['stages']['sample']['jobs'][0]['done'] = False
        with self.assertRaisesRegex(RuntimeError, 'unfinished'):
            S.require_quiescent(base)
        base['pipeline']['running'] = 1
        with self.assertRaisesRegex(RuntimeError, 'executing'):
            S.require_quiescent(base)

    def test_tail_retirement_records_then_releases_only_finished_jobs(self):
        done = threading.Event()
        done.set()
        job = types.SimpleNamespace(index=99, done=done, error=None, tag='tag', target=None,
                                    started=1., finished=2., value=object())
        p = types.SimpleNamespace(_LOCK=threading.Lock(), _RUNNING=[0],
                                  _STAGES={'sample': {'queue': [], 'jobs': {99: job}}})
        snap = S.retire_completed_tails(p, self.root / 'tails.json', lambda: True)
        self.assertEqual(snap['stages']['sample']['jobs'][0]['index'], 99)
        self.assertEqual(p._STAGES['sample']['jobs'], {})
        self.assertTrue((self.root / 'tails.json').is_file())
        p._STAGES['sample']['jobs'][100] = job
        done.clear()
        with self.assertRaisesRegex(RuntimeError, 'unfinished'):
            S.retire_completed_tails(p, self.root / 'not-created.json', lambda: True)
        self.assertFalse((self.root / 'not-created.json').exists())
        self.assertIn(100, p._STAGES['sample']['jobs'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
