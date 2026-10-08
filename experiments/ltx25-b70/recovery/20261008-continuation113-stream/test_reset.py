"""CPU tests (packet113): the client-requested chain reset, in the contract and in the authority."""
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import session  # noqa: E402
import stream_contract as c  # noqa: E402
from test_session import Harness  # noqa: E402

PARENT = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261008-continuation112-stream')


def parent_contract():
    import importlib.util
    spec = importlib.util.spec_from_file_location('stream_contract_112', PARENT / 'stream_contract.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ContractForm(unittest.TestCase):
    def test_unreset_graphs_are_byte_identical_to_112(self):
        old = parent_contract()
        for f in c.FRAME_CHOICES:
            for r in (0, 1):
                for p in c.PLACEMENTS:
                    for new, prev in zip(c.qualification_params(f, r, p), old.qualification_params(f, r, p)):
                        self.assertEqual(c.canonical(c.build_chunk_graph(new)),
                                         old.canonical(old.build_chunk_graph(prev)))
        for seq, pred, reuse in ((0, '', 0), (5, 'a' * 64, 0), (5, 'a' * 64, 1)):
            new = c.build_chunk_graph(c.stream_params(49, seq, 'boat', 3, pred, 's', reuse, 'two-way20-28'))
            prev = old.build_chunk_graph(old.stream_params(49, seq, 'boat', 3, pred, 's', reuse, 'two-way20-28'))
            self.assertEqual(c.canonical(new), old.canonical(prev))
            self.assertEqual(c.parse_chunk_graph(prev, 49, 'two-way20-28')['reset'], 0)

    def test_112_shaped_params_read_as_no_reset(self):
        old = parent_contract()
        params = old.stream_params(49, 4, 'boat', 3, 'a' * 64, 's', 0, 'two-way20-28')
        self.assertNotIn('reset', params)
        self.assertEqual(c.validate_params(params)['reset'], 0)
        self.assertEqual(c.canonical(c.build_chunk_graph(params)), old.canonical(old.build_chunk_graph(params)))

    def test_reset_graph_is_the_chunk0_form(self):
        reset = c.build_chunk_graph(c.stream_params(49, 7, 'boat', 3, 'a' * 64, 's', 0, reset=1))
        first = c.build_chunk_graph(c.stream_params(49, 0, 'boat', 3, '', 's', 0))
        self.assertEqual(set(reset), set(first))
        self.assertNotIn('stream_anchor', reset)
        self.assertEqual(reset['377']['inputs']['video_latent'], ['356', 0])
        self.assertEqual(reset['340']['inputs']['video_latent'], ['348', 0])
        self.assertEqual(reset['stream_output']['inputs']['reset'], 1)
        self.assertEqual(reset['364']['inputs']['clip_index'], c.STREAM_CLIP_BASE + 7)
        # Apart from identity fields, the reset chunk is exactly chunk 0's graph.
        strip = lambda g: {k: {kk: vv for kk, vv in v['inputs'].items()
                               if kk not in ('run_name', 'clip_index', 'stream_seq', 'chunk_index', 'reset',
                                             'predecessor_anchor_sha256')} for k, v in g.items()}
        self.assertEqual(strip(reset), strip(first))
        params = c.parse_chunk_graph(reset, 49)
        self.assertEqual((params['reset'], params['predecessor_anchor_sha256']), (1, 'a' * 64))
        self.assertEqual(c.parse_chunk_graph(c.build_chunk_graph(c.stream_params(49, 7, 'boat', 3, '', 's',
                                                                                 reset=1)), 49)['reset'], 1)

    def test_reset_refusals(self):
        bad = [dict(stream_seq=0, reset=1), dict(reuse_text=1, reset=1), dict(pred='zz', reset=1)]
        for row in bad:
            with self.assertRaises(ValueError):
                c.stream_params(49, row.get('stream_seq', 4), 'boat', 3, row.get('pred', ''), 's',
                                row.get('reuse_text', 0), reset=row['reset'])
        with self.assertRaises(ValueError):
            c.stream_params(49, 4, 'boat', 3, 'a' * 64, 's', reset=True)
        graph = c.build_chunk_graph(c.stream_params(49, 4, 'boat', 3, 'a' * 64, 's'))
        graph['stream_output']['inputs']['reset'] = 0          # explicit 0 is not the contract form
        with self.assertRaises(ValueError):
            c.parse_chunk_graph(graph, 49)
        params = c.qualification_params(49, 0)[0]
        with self.assertRaises(ValueError):
            c.validate_params(dict(params, reset=1))


class AuthorityReset(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.h.setup()
        self.h.qualify()

    def tearDown(self):
        self.h.close()

    def graph(self, seq, pred='', reset=0, reuse=0, prompt='boat'):
        return c.build_chunk_graph(c.stream_params(49, seq, prompt, 9, pred, 's', reuse, reset=reset))

    def refusal(self, graph):
        with self.assertRaises(session.Refusal) as ctx:
            self.h.a.precheck(graph, [], 0)
        return ctx.exception.code

    def test_reset_restarts_the_chain_and_takes_the_next_seq(self):
        h = self.h
        h.submit(self.graph(0))
        h.submit(self.graph(1, pred=h.anchor()))
        before = h.anchor()
        row = h.submit(self.graph(2, pred=before, reset=1))
        self.assertEqual(row['params']['reset'], 1)
        self.assertEqual(row['predecessor']['anchor_sha256'], before)     # recorded, not consumed
        after = h.anchor()
        self.assertNotEqual(after, before)
        # The chain continues from the reset chunk's anchor, in order.
        self.assertEqual(self.refusal(self.graph(3, pred=before)), 'stale-anchor')
        h.submit(self.graph(3, pred=after))
        self.assertEqual(h.a.status()['next_stream_seq'], 4)
        # Reset without naming a predecessor is admitted too.
        h.submit(self.graph(4, reset=1))
        self.assertEqual(h.a.status()['chain']['last_stream_seq'], 4)

    def test_reset_still_follows_order_and_rules(self):
        h = self.h
        h.submit(self.graph(0))
        self.assertEqual(self.refusal(self.graph(2, reset=1)), 'order')
        self.assertEqual(self.refusal(self.graph(1, pred='f' * 64, reset=1)), 'stale-anchor')
        h.submit(self.graph(1, reset=1))
        self.assertIsNone(h.a.failed)

    def test_reset_with_text_reuse_server(self):
        h = Harness(reuse=1)
        try:
            h.setup()
            h.qualify()
            h.submit(self.graph(0))
            # Same prompt, but a reset always encodes: reuse_text must be 0 (the contract refuses 1).
            h.submit(self.graph(1, pred=h.anchor(), reset=1))
            self.assertEqual(h.a.status()['next_stream_seq'], 2)
        finally:
            h.close()


if __name__ == '__main__':
    unittest.main()
