"""CPU check of b70-step-breadcrumbs 0.1.0 against a stand-in runner: steps kept with the worker's own view, one block
per stall and per failure, events still forward record(), outputs returned unchanged. No vLLM, no GPU."""
import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('crumbs', HERE / 'overlays/b70-step-breadcrumbs/b70_step_breadcrumbs.py')
crumbs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(crumbs)


class Event:
    def __init__(self):
        self.records, self.fail = 0, False

    def record(self, *a):
        self.records += 1

    def synchronize(self):
        if self.fail:
            raise RuntimeError('UR_RESULT_ERROR_DEVICE_LOST')


class Runner:
    def __init__(self):
        self.prepare_inputs_event = Event()
        self.valid_sampled_token_count_event = None
        self.draft_token_ids_event = Event()
        self.num_accepted_tokens_event = Event()
        self.input_batch = SimpleNamespace(req_ids=[], num_computed_tokens_cpu=np.zeros(4, np.int32),
                                           num_tokens_no_spec=np.zeros(4, np.int32))
        self.num_accepted_tokens = SimpleNamespace(np=np.zeros(4, np.int32))

    def execute_model(self, out, intermediate=None):
        self.num_accepted_tokens_event.synchronize()
        b = self.input_batch
        b.req_ids = list(out.num_scheduled_tokens)
        computed = dict(zip(out.scheduled_cached_reqs.req_ids, out.scheduled_cached_reqs.num_computed_tokens))
        computed.update({q.req_id: q.num_computed_tokens for q in out.scheduled_new_reqs})
        for i, rid in enumerate(b.req_ids):
            b.num_computed_tokens_cpu[i] = computed[rid]
            b.num_tokens_no_spec[i] = computed[rid] + 1
            self.num_accepted_tokens.np[i] = 5
        self.prepare_inputs_event.record()
        return 'out'

    def sample_tokens(self, g):
        return self.propose_draft_token_ids(g)

    def propose_draft_token_ids(self, x):
        self.num_accepted_tokens_event.record()
        return ('drafts', x)


def step(rid, sched, drafts, computed, new=False):
    req = SimpleNamespace(req_id=rid, num_computed_tokens=computed)
    cached = SimpleNamespace(req_ids=[] if new else [rid], num_computed_tokens=[] if new else [computed])
    return SimpleNamespace(num_scheduled_tokens={rid: sched}, scheduled_spec_decode_tokens={rid: [0] * drafts},
                           scheduled_new_reqs=[req] if new else [], scheduled_cached_reqs=cached,
                           total_num_scheduled_tokens=sched, finished_req_ids=set(), preempted_req_ids=None)


class CrumbsTest(unittest.TestCase):
    def make(self, lines, **kw):
        cls = type('GPUModelRunner', (Runner,), {})
        self.assertTrue(crumbs.install(cls, lines.append, keep=4, stall_s=5.0, one_launch=True, watch=False, **kw))
        self.assertFalse(crumbs.install(cls, lines.append))
        return cls()

    def test_steps_kept_with_worker_view(self):
        lines = []
        r = self.make(lines)
        self.assertIsInstance(r.num_accepted_tokens_event, crumbs.CrumbEvent)
        self.assertIsNone(r.valid_sampled_token_count_event)
        self.assertEqual(r.execute_model(step('chatcmpl-abc-0123456789', 443, 0, 4160, new=True)), 'out')
        for _ in range(5):
            self.assertEqual(r.execute_model(step('chatcmpl-abc-0123456789', 6, 5, 4600)), 'out')
            self.assertEqual(r.sample_tokens(7), ('drafts', 7))
        c = r._b70_crumbs
        self.assertEqual([s['i'] for s in c.steps], [2, 3, 4, 5])          # keep=4, oldest dropped
        last = c.steps[-1]
        self.assertTrue(last['one_launch'])
        self.assertEqual(last['reqs'][0]['id'], '23456789')
        self.assertEqual((last['reqs'][0]['w_computed'], last['reqs'][0]['w_tokens'], last['reqs'][0]['w_accepted']),
                         (4600, 4601, 5))
        self.assertEqual([e[:2] for e in last['events']], [('accepted', 'waited'), ('prep', 'rec'), ('accepted', 'rec')])
        self.assertEqual(r.prepare_inputs_event._event.records, 6)
        self.assertEqual(lines, [])                                         # nothing written without an incident

    def test_one_stall_block_then_cleared(self):
        lines = []
        r = self.make(lines)
        c = r._b70_crumbs
        r.execute_model(step('req-00000001', 6, 5, 1000))
        self.assertFalse(c.steps[-1]['one_launch'])                         # 1,006 keys: not the one-launch path
        outer = c.enter('execute_model')
        inner = c.enter('wait on num_accepted_tokens_event')
        t0 = c.clock()
        c.check(t0 + 1.0)
        self.assertEqual(lines, [])
        c.check(t0 + 6.0)
        c.check(t0 + 7.0)
        self.assertEqual(len(lines), 1)
        self.assertIn('rank unknown STALL: execute_model since', lines[0])   # no vLLM here: rank unresolved
        self.assertIn('wait on num_accepted_tokens_event since', lines[0])
        self.assertIn('#0 ', lines[0])
        c.leave(inner)
        c.leave(outer)
        self.assertEqual(len(lines), 2)
        self.assertIn('stall cleared', lines[1])

    def test_failure_written_once_and_raised(self):
        lines = []
        r = self.make(lines)
        r.execute_model(step('req-00000002', 6, 5, 4600))
        r.num_accepted_tokens_event._event.fail = True
        with self.assertRaises(RuntimeError):
            r.execute_model(step('req-00000003', 443, 0, 4160, new=True))
        failed = [x for x in lines if 'FAILED' in x]
        self.assertEqual(len(failed), 1)
        self.assertIn('FAILED: wait on num_accepted_tokens_event raised', failed[0])
        self.assertIn('DEVICE_LOST', failed[0])
        self.assertIn('ONE-LAUNCH', failed[0])                              # the step before, 4,606 keys, 6 rows
        self.assertEqual(r._b70_crumbs.busy, {})


if __name__ == '__main__':
    unittest.main()
