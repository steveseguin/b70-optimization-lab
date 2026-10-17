"""CPU check of b70-step-breadcrumbs 0.3.0 against a stand-in runner: steps kept with the worker's own view, one block
per stall and per failure, events still forward record(), outputs returned unchanged, collectives counted per step
with a signature that differs when the calls differ; device marks (0.3.0) name the first collective whose mark has not
landed, skip host tensors and async calls, survive the counter wrap and turn off on an error. No vLLM, no GPU."""
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


    def test_collectives_counted_per_step(self):
        calls = []

        class Tensor:
            def __init__(self, n):
                self.n = n

            def numel(self):
                return self.n

        fake = SimpleNamespace(all_gather_into_tensor=lambda out, x, group=None: calls.append(('ag', x.n)) or 'w',
                               broadcast=lambda x, src=0, group=None: calls.append(('bc', x.n)))
        self.assertTrue(crumbs.count_collectives(fake))
        self.assertFalse(crumbs.count_collectives(fake))
        lines = []
        r = self.make(lines)
        sigs = []
        for extra in (False, False, True):
            r.execute_model(step('req-00000004', 6, 5, 4600))
            for _ in range(3):
                self.assertEqual(fake.all_gather_into_tensor(Tensor(12), Tensor(6), group='g'), 'w')
            fake.broadcast(Tensor(1), src=0)
            if extra:
                fake.all_gather_into_tensor(Tensor(12), Tensor(6))
            s = r._b70_crumbs.steps[-1]
            sigs.append((s['coll'], s['elems'], s['sig']))
        self.assertEqual(len(calls), 13)                                    # every call reached the original
        self.assertEqual(sigs[0], sigs[1])                                  # same calls, same signature
        self.assertEqual(sigs[0][:2], (4, 3 * 18 + 1))
        self.assertEqual(sigs[2][0], 5)
        self.assertNotEqual(sigs[2][2], sigs[0][2])
        r._b70_crumbs.dump('test')
        self.assertIn('coll 4 elems 55 sig %08x' % sigs[0][2], lines[-1])


class Tensor:
    def __init__(self, n, device=None):
        self.n = n
        if device is not None:
            self.device = device

    def numel(self):
        return self.n


XPU = SimpleNamespace(type='xpu', index=0)
CPU = SimpleNamespace(type='cpu', index=None)


class Card:
    """Stand-in for the device table and the pinned host buffer: a copy lands only when land() says so."""
    def __init__(self):
        self.queue, self.value = [], -1

    def make(self, device):
        card = self

        class Table:
            def __getitem__(self, sl):
                return sl.start

        class Host:
            def copy_(self, src, non_blocking=False):
                assert non_blocking
                card.queue.append(src)

            def __getitem__(self, i):
                return card.value
        return Table(), Host()

    def land(self, k):
        for _ in range(k):
            self.value = self.queue.pop(0)


class DeviceMarksTest(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.fake = SimpleNamespace(
            all_gather_into_tensor=lambda out, x, group=None, async_op=False: self.calls.append(x.n) or 'w')
        crumbs.count_collectives(self.fake)

    def runner(self, lines, marks=True, make=None):
        cls = type('GPUModelRunner', (Runner,), {})
        crumbs.install(cls, lines.append, keep=4, stall_s=5.0, watch=False, marks=marks)
        r = cls()
        r.execute_model(step('req-00000004', 443, 0, 4160, new=True))
        if marks and make is not None:
            r._b70_crumbs.marks = crumbs.DeviceMarks(lines.append, make=make)
        return r

    def test_first_unfinished_collective_named(self):
        lines, card = [], Card()
        r = self.runner(lines, make=card.make)
        for _ in range(5):
            self.assertEqual(self.fake.all_gather_into_tensor(Tensor(12, XPU), Tensor(6, XPU)), 'w')
        card.land(3)
        r._b70_crumbs.dump('STALL: test')
        head = lines[-1].split('\n')[0]
        self.assertIn('5 collectives issued', head)
        self.assertIn('3 completed on this card', head)
        self.assertIn('first not completed #4 all_gather_into_tensor 18 elems (step #0); 1 issued after it', head)
        card.land(2)
        self.assertEqual(r._b70_crumbs.marks.completed(), 5)
        self.assertNotIn('first not completed', r._b70_crumbs.marks.report())
        self.assertEqual(len(self.calls), 5)

    def test_host_tensors_and_async_calls_not_marked(self):
        lines, card = [], Card()
        r = self.runner(lines, make=card.make)
        self.fake.all_gather_into_tensor(Tensor(12, CPU), Tensor(6, CPU))
        self.fake.all_gather_into_tensor(Tensor(12, XPU), Tensor(6, XPU), async_op=True)
        self.assertEqual(r._b70_crumbs.marks.issued, 0)
        self.assertEqual(card.queue, [])
        self.assertIn('no collective on a device yet', r._b70_crumbs.marks.report())
        self.assertEqual(r._b70_crumbs.steps[-1]['coll'], 2)          # still counted on the host

    def test_counter_wrap(self):
        card = Card()
        m = crumbs.DeviceMarks(print, make=card.make)
        m.R = 8
        for _ in range(21):
            m.after(1, (Tensor(12, XPU),), 12, 0)
        card.land(15)                                   # exact while fewer than R are pending (6 < 8 here)
        self.assertEqual(m.completed(), 15)
        card.land(6)
        self.assertEqual(m.completed(), 21)

    def test_error_turns_marks_off_and_call_still_returns(self):
        lines = []

        def broken(device):
            raise RuntimeError('pin_memory unsupported')
        r = self.runner(lines, make=broken)
        self.assertEqual(self.fake.all_gather_into_tensor(Tensor(12, XPU), Tensor(6, XPU)), 'w')
        self.assertTrue(r._b70_crumbs.marks.off)
        self.assertIn('device marks off', lines[-1])
        self.assertIn('off after an error', r._b70_crumbs.marks.report())

    def test_off_by_default(self):
        lines = []
        r = self.runner(lines, marks=False)
        self.fake.all_gather_into_tensor(Tensor(12, XPU), Tensor(6, XPU))
        self.assertIsNone(r._b70_crumbs.marks)
        r._b70_crumbs.dump('STALL: test')
        self.assertNotIn('device marks', lines[-1])


if __name__ == '__main__':
    unittest.main()
