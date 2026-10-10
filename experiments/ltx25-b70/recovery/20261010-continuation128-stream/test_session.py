"""CPU tests (packet117): streaming authority ordering, refusal, anchor chain, latching, variants."""
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import plan as plan_module  # noqa: E402
import session  # noqa: E402
import stream_contract as c  # noqa: E402

SHA = 'a' * 64
_PLAN = []


def built_plan():
    if not _PLAN:
        _PLAN.append(plan_module.build_plan())
    return _PLAN[0]


class FakeState:
    def __init__(self):
        self.routes, self.frozen, self.fault = 0, False, False

    def __call__(self):
        return {'fault': self.fault, 'preview_pending': 0, 'preview_failures': 0, 'captures_frozen': self.frozen,
                'loads_frozen': False, 'sampler_routes': self.routes, 'lean_state': 0, 'decode_replicas': 0,
                'queue_running': 1, 'queue_pending': 0, 'queue_running_ids': [],
                'pipeline': {'running': 0, 'stages': {}}}


def success(pid):
    return [('execution_start', {'prompt_id': pid}), ('execution_success', {'prompt_id': pid})]


class Harness:
    def __init__(self, frames=49, reuse=0, anchor=c.DEFAULT_ANCHOR, placement='two-way',
                 decoder_graph=c.DEFAULT_DECODER_GRAPH, levers=None):
        self.tmp = tempfile.TemporaryDirectory()
        self.run = Path(self.tmp.name) / 'run'
        (self.run / 'receipts').mkdir(parents=True)
        (self.run / 'anchors').mkdir()
        envelope = built_plan()
        path = Path(self.tmp.name) / 'plan.json'
        path.write_text(json.dumps(envelope))
        self.saved = session.PLAN_SHA256
        session.PLAN_SHA256 = envelope['plan_sha256']
        self.state = FakeState()
        self.frames, self.reuse, self.anchor_kind, self.placement = frames, reuse, anchor, placement
        self.decoder_graph = decoder_graph
        self.levers = c._levers(anchor, *(levers or (None, None, None)))
        self.a = session.StreamAuthority(path, SHA, 'b' * 64, self.run, self.state, reuse, frames, placement, anchor,
                                         decoder_graph, levers)
        self.n = 0

    def close(self):
        session.PLAN_SHA256 = self.saved
        self.tmp.cleanup()

    def submit(self, graph, receipt_extra=None, routes_after=None):
        self.n += 1
        pid = '00000000-0000-4000-8000-%012d' % self.n
        descriptor = self.a.precheck(graph, [], 0)
        row = self.a.begin(descriptor['name'], graph, pid)
        if routes_after is not None:
            self.state.routes = routes_after
        if row['params'] is not None:
            suffix = {'latent': '.latent.f32', 'mixed': '.latent.f32', 'guide': '.guide.f32'}.get(self.anchor_kind, '.f32')
            anchor_path = self.run / 'anchors' / (row['name'] + suffix)
            anchor_path.write_bytes(b'\0' * 8)
            receipt = {'run_name': row['name'], 'prompt_id': pid,
                       'anchor_out': {'sha256': ('%064x' % self.n), 'path': str(anchor_path),
                                      'kind': self.anchor_kind}}
            receipt.update(receipt_extra or {})
            self.a.stage_receipt(row['name'], receipt)
        self.a.finish(success(pid))
        return row

    def setup(self):
        for r in c.setup_graphs():
            self.submit(r['graph'])

    def qualify(self):
        for i, params in enumerate(c.qualification_params(self.frames, self.reuse, self.placement, self.anchor_kind,
                                                          self.decoder_graph, *self.levers)):
            self.submit(c.build_chunk_graph(params), routes_after=48 if i == 3 else None)
        self.a.accept_verdict({'passed': True, 'plan_sha256': session.PLAN_SHA256}, 'c' * 64)
        self.state.frozen = True

    def anchor(self):
        return self.a.chains['stream']['anchor_sha256']


class Ordering(unittest.TestCase):
    def setUp(self):
        self.h = Harness()

    def tearDown(self):
        self.h.close()

    def test_setup_then_qualification_then_verdict_then_stream(self):
        h = self.h
        self.assertEqual(h.a.phase, 'stream_setup')
        with self.assertRaises(session.Refusal) as ctx:
            h.a.precheck(c.build_chunk_graph(c.stream_params(49, 0, 'x', 1, '', 's')), [], 0)
        self.assertEqual(ctx.exception.code, 'order')
        h.setup()
        self.assertEqual(h.a.phase, 'stream_qualification')
        with self.assertRaises(session.Refusal) as ctx:
            h.a.precheck(c.build_chunk_graph(c.qualification_params(49, 0)[1]), [], 0)
        self.assertEqual(ctx.exception.code, 'order')
        for i, params in enumerate(c.qualification_params(49, 0)):
            h.submit(c.build_chunk_graph(params), routes_after=48 if i == 3 else None)
        with self.assertRaises(session.Refusal) as ctx:
            h.a.precheck(c.build_chunk_graph(c.stream_params(49, 0, 'x', 1, '', 's')), [], 0)
        self.assertEqual(ctx.exception.code, 'not-streaming')
        h.a.accept_verdict({'passed': True, 'plan_sha256': session.PLAN_SHA256}, 'c' * 64)
        h.state.frozen = True
        self.assertEqual(h.a.phase, 'stream')
        h.submit(c.build_chunk_graph(c.stream_params(49, 0, 'boat', 1, '', 's')))
        self.assertEqual(h.a.status()['next_stream_seq'], 1)

    def test_failed_verdict_cannot_open_stream(self):
        h = self.h
        h.setup()
        for i, params in enumerate(c.qualification_params(49, 0)):
            h.submit(c.build_chunk_graph(params), routes_after=48 if i == 3 else None)
        with self.assertRaises(RuntimeError):
            h.a.accept_verdict({'passed': False, 'plan_sha256': session.PLAN_SHA256}, 'c' * 64)
        self.assertIsNotNone(h.a.failed)
        self.assertTrue((h.run / 'stream-halt.json').exists())
        with self.assertRaises(session.Refusal) as ctx:
            h.a.precheck(c.build_chunk_graph(c.stream_params(49, 0, 'x', 1, '', 's')), [], 0)
        self.assertEqual(ctx.exception.code, 'halted')


class StreamChain(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.h.setup()
        self.h.qualify()

    def tearDown(self):
        self.h.close()

    def graph(self, seq, prompt='boat', pred=None, reuse=0, scene='s'):
        return c.build_chunk_graph(c.stream_params(49, seq, prompt, 9, pred or '', scene, reuse))

    def refusal(self, graph):
        with self.assertRaises(session.Refusal) as ctx:
            self.h.a.precheck(graph, [], 0)
        return ctx.exception.code

    def test_anchor_chain_and_prompt_cut(self):
        h = self.h
        h.submit(self.graph(0))
        first = h.anchor()
        self.assertEqual(self.refusal(self.graph(1, pred='f' * 64)), 'stale-anchor')
        row = h.submit(self.graph(1, pred=first))
        self.assertEqual(row['predecessor']['anchor_sha256'], first)
        # A cut: new prompt and new scene label, same anchor chain.
        row = h.submit(self.graph(2, prompt='a lighthouse at dusk', pred=h.anchor(), scene='cut2'))
        self.assertEqual(row['predecessor']['run_name'], 'stream128-s00000001')
        self.assertEqual(h.a.status()['chain']['last_stream_seq'], 2)

    def test_gaps_reuse_and_restart_refused(self):
        h = self.h
        h.submit(self.graph(0))
        self.assertEqual(self.refusal(self.graph(2, pred=h.anchor())), 'order')
        self.assertEqual(self.refusal(self.graph(0)), 'order')
        h.submit(self.graph(1, pred=h.anchor()))
        old = h.a.chains['stream']['anchor_sha256']
        h.submit(self.graph(2, pred=old))
        self.assertEqual(self.refusal(self.graph(3, pred=old)), 'stale-anchor')

    def test_busy_and_queue_refusals(self):
        h = self.h
        with self.assertRaises(session.Refusal) as ctx:
            h.a.precheck(self.graph(0), [], 1)
        self.assertEqual(ctx.exception.code, 'busy')
        with self.assertRaises(session.Refusal) as ctx:
            h.a.precheck(self.graph(0), ['unknown-running-prompt'], 0)
        self.assertEqual(ctx.exception.code, 'busy')

    def test_reuse_rule_when_server_reuse_off(self):
        h = self.h
        h.submit(self.graph(0))
        self.assertEqual(self.refusal(self.graph(1, pred=h.anchor(), reuse=1)), 'text-reuse-rule')

    def test_anchor_pruning_keeps_two_newest(self):
        h = self.h
        h.submit(self.graph(0))
        for seq in (1, 2, 3):
            h.submit(self.graph(seq, pred=h.anchor()))
        names = sorted(p.name for p in (h.run / 'anchors').iterdir() if p.name.startswith('stream128-s'))
        self.assertEqual(names, ['stream128-s00000002.f32', 'stream128-s00000003.f32'])   # frame anchor default
        self.assertEqual(len(list((h.run / 'receipts').glob('receipt-stream128-s*.json'))), 4)

    def test_execution_mismatch_latches(self):
        h = self.h
        graph = self.graph(0)
        h.a.precheck(graph, [], 0)
        with self.assertRaises(RuntimeError):
            h.a.begin('stream128-s00000099', graph, '00000000-0000-4000-8000-999999999999')
        self.assertIsNotNone(h.a.failed)
        self.assertEqual(self.refusal(graph), 'halted')

    def test_finish_requires_staged_receipt_and_success(self):
        h = self.h
        graph = self.graph(0)
        pid = '00000000-0000-4000-8000-888888888888'
        h.a.begin('stream128-s00000000', graph, pid)
        with self.assertRaises(RuntimeError):
            h.a.finish(success(pid))
        self.assertIsNotNone(h.a.failed)

    def test_route_state_must_match_phase(self):
        h = self.h
        h.state.frozen = False
        with self.assertRaises(RuntimeError):
            h.a.begin('stream128-s00000000', self.graph(0), '00000000-0000-4000-8000-777777777777')

    def test_prompt_thread_bound(self):
        h = self.h
        errors = []

        def other():
            try:
                h.a.begin('stream128-s00000000', self.graph(0), '00000000-0000-4000-8000-666666666666')
            except RuntimeError as error:
                errors.append(str(error))
        t = threading.Thread(target=other)
        t.start()
        t.join()
        self.assertTrue(errors and 'thread' in errors[0])


class ReuseServer(unittest.TestCase):
    def setUp(self):
        self.h = Harness(frames=97, reuse=1)
        self.h.setup()
        self.h.qualify()

    def tearDown(self):
        self.h.close()

    def test_reuse_required_iff_prompt_unchanged(self):
        h = self.h
        g = lambda seq, prompt, reuse: c.build_chunk_graph(c.stream_params(97, seq, prompt, 1, h.anchor() if seq else '', 's', reuse))
        h.submit(g(0, 'boat', 0))
        with self.assertRaises(session.Refusal) as ctx:
            h.a.precheck(g(1, 'boat', 0), [], 0)
        self.assertEqual(ctx.exception.code, 'text-reuse-rule')
        h.submit(g(1, 'boat', 1))
        with self.assertRaises(session.Refusal) as ctx:
            h.a.precheck(g(2, 'harbour at night', 1), [], 0)
        self.assertEqual(ctx.exception.code, 'text-reuse-rule')
        h.submit(g(2, 'harbour at night', 0))


class Variants(unittest.TestCase):
    def test_anchor_frames_placement_and_decoder_graph_select_the_pinned_graphs(self):
        for frames in c.FRAME_CHOICES:
            for anchor in c.ANCHORS:
                for dg in c.DECODER_GRAPH_CHOICES:
                    h = Harness(frames=frames, reuse=1, anchor=anchor, placement='two-way20-28', decoder_graph=dg)
                    try:
                        self.assertEqual(h.a.variant, '%d/two-way20-28/%s/dg%d/ad-%s/bo%d/pa%d'
                                         % ((frames, anchor, dg) + c.default_levers(anchor)))
                        self.assertEqual(h.a.qid, c.qualification_id(frames, 'two-way20-28', anchor, dg))
                        h.setup()
                        h.qualify()
                        g = c.build_chunk_graph(c.stream_params(frames, 0, 'boat', 1, '', 's', 0, 'two-way20-28',
                                                                anchor=anchor, decoder_graph=dg))
                        h.submit(g)
                        other = 'frame' if anchor == 'latent' else 'latent'
                        for wrong in (c.build_chunk_graph(c.stream_params(frames, 1, 'boat', 1, h.anchor(), 's', 1,
                                                                          'two-way20-28', anchor=other,
                                                                          decoder_graph=dg)),
                                      c.build_chunk_graph(c.stream_params(frames, 1, 'boat', 1, h.anchor(), 's', 1,
                                                                          'two-way20-28', anchor=anchor,
                                                                          decoder_graph=1 - dg))):
                            with self.assertRaises(session.Refusal) as ctx:
                                h.a.precheck(wrong, [], 0)
                            self.assertEqual(ctx.exception.code, 'contract')
                        status = h.a.status()
                        self.assertEqual((status['anchor'], status['decoder_graph']), (anchor, dg))
                        self.assertEqual((status['anchor_decode'], status['bencode_overlap'], status['prep_ahead']),
                                         c.default_levers(anchor))
                        self.assertEqual(h.a.chains['stream']['anchor_kind'], anchor)
                    finally:
                        h.close()

    def test_qualification_graph_of_another_length_is_refused(self):
        h = Harness(frames=97)
        try:
            h.setup()
            with self.assertRaises(session.Refusal) as ctx:
                h.a.precheck(c.build_chunk_graph(c.qualification_params(49, 0)[0]), [], 0)
            self.assertEqual(ctx.exception.code, 'contract')
        finally:
            h.close()


class Levers(unittest.TestCase):
    """Packet117: the levers select the pinned graphs; a request with other levers is refused."""
    def test_levers_select_the_variant_and_refuse_others(self):
        for levers in (('full', 0, 0), ('cone', 0, 1), ('full', 1, 0)):
            h = Harness(frames=121, reuse=1, anchor='frame', placement='two-way20-28', decoder_graph=1, levers=levers)
            try:
                self.assertEqual(h.a.levers, levers)
                self.assertEqual(h.a.variant, '121/two-way20-28/frame/dg1/ad-%s/bo%d/pa%d' % levers)
                self.assertEqual(h.a.qid, c.qualification_id(121, 'two-way20-28', 'frame', 1, *levers))
                h.setup()
                h.qualify()
                h.submit(c.build_chunk_graph(c.stream_params(121, 0, 'boat', 1, '', 's', 0, 'two-way20-28',
                                                             anchor_decode=levers[0], bencode_overlap=levers[1],
                                                             prep_ahead=levers[2])))
                wrong = c.build_chunk_graph(c.stream_params(121, 1, 'boat', 1, h.anchor(), 's', 1, 'two-way20-28'))
                with self.assertRaises(session.Refusal) as ctx:
                    h.a.precheck(wrong, [], 0)                         # default cone/1/1 levers
                self.assertEqual(ctx.exception.code, 'contract')
            finally:
                h.close()

    def test_non_frame_anchor_refuses_levers(self):
        with self.assertRaises(ValueError):
            Harness(anchor='latent', levers=('cone', 0, 0))

    def test_wait_committed(self):
        h = Harness()
        try:
            h.setup()
            for i, params in enumerate(c.qualification_params(49, 0)[:3]):
                name = c.run_name(params)
                self.assertFalse(h.a.wait_committed(name, 0.05))      # bounded: not yet committed
                result = []
                waiter = threading.Thread(target=lambda: result.append(h.a.wait_committed(name, 10)))
                waiter.start()
                h.submit(c.build_chunk_graph(params), routes_after=None)
                waiter.join(10)
                self.assertEqual(result, [True])
                self.assertTrue(h.a.wait_committed(name, 0))
            self.assertIn(c.run_name(c.qualification_params(49, 0)[0]), h.a.committed_names)
            h.a.halt(RuntimeError('test halt'))
            self.assertFalse(h.a.wait_committed('stream128-s00000099', 5))   # a halt ends the wait at once
        finally:
            h.close()


if __name__ == '__main__':
    unittest.main()
