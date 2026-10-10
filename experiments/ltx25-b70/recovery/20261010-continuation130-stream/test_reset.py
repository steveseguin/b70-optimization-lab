"""CPU tests (packet117): graph form against 113 and 114, the mixed and guide graph forms, and the chain reset
in the contract and the authority."""
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import session  # noqa: E402
import stream_contract as c  # noqa: E402
from test_session import Harness  # noqa: E402

PARENT = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261008-continuation113-stream')
PARENT114 = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261008-continuation114-stream')
MODEL_NODES = ('338', '339', '340', '341', '344', '348', '352', '356', '365', '366', '367', '368', '369', '377',
               '388', '391', '395', '404', '420', 'stream_gate', '425')


def parent_contract(parent=PARENT, name='stream_contract_113'):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, parent / 'stream_contract.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def model_graph(graph):
    """The model-side nodes with their packet-specific labels removed (run names, ids, clip index)."""
    out = {}
    for key in MODEL_NODES + ('364', 'stream_condition_a', 'stream_condition_b', 'stream_anchor',
                              'stream_crop_a', 'stream_crop_b'):
        if key not in graph:
            continue
        inputs = {k: v for k, v in graph[key]['inputs'].items()
                  if k not in ('run_name', 'clip_index', 'qualification_id', 'comparison_mode')}
        out[key] = {'class_type': graph[key]['class_type'].replace('112', 'NN').replace('114', 'NN')
                                                         .replace('116', 'NN'),
                    'inputs': inputs}
    return out


class ContractForm(unittest.TestCase):
    def test_frame_anchor_model_graph_is_113s(self):
        """LTX_ANCHOR=frame keeps packet113's model graph; only the decoders left the graph."""
        old = parent_contract()
        for r in (0, 1):
            for p in c.PLACEMENTS:
                for new, prev in zip(c.qualification_params(49, r, p, 'frame'), old.qualification_params(49, r, p)):
                    a, b = c.build_chunk_graph(new), old.build_chunk_graph(prev)
                    self.assertEqual(model_graph(a), model_graph(b))
                    self.assertTrue({'374', '358', '414'} <= set(b) and not {'374', '358', '414'} & set(a))
        for seq, pred, reuse in ((0, '', 0), (5, 'a' * 64, 0), (5, 'a' * 64, 1)):
            a = c.build_chunk_graph(c.stream_params(49, seq, 'boat', 3, pred, 's', reuse, 'two-way20-28', anchor='frame'))
            b = old.build_chunk_graph(old.stream_params(49, seq, 'boat', 3, pred, 's', reuse, 'two-way20-28'))
            self.assertEqual(model_graph(a), model_graph(b))

    def test_latent_anchor_changes_only_the_anchor_and_condition_nodes(self):
        old = parent_contract()
        a = c.build_chunk_graph(c.stream_params(49, 5, 'boat', 3, 'a' * 64, 's', 0, anchor='latent'))
        b = old.build_chunk_graph(old.stream_params(49, 5, 'boat', 3, 'a' * 64, 's', 0))
        ma, mb = model_graph(a), model_graph(b)
        changed = {k for k in set(ma) | set(mb) if ma.get(k) != mb.get(k)}
        self.assertEqual(changed, {'stream_anchor', 'stream_condition_a', 'stream_condition_b'})
        self.assertEqual(a['stream_condition_a']['inputs'], {'latent': ['356', 0], 'anchor': ['stream_anchor', 0],
                                                             'strength': 1.0, 'run_name': 'stream130-s00000005',
                                                             'stage': 'A'})
        self.assertEqual(a['stream_condition_b']['inputs']['latent'], ['348', 0])
        self.assertEqual(a['stream_condition_b']['inputs']['anchor'], ['stream_anchor', 1])
        self.assertNotIn('vae', a['stream_condition_a']['inputs'])
        # Unanchored chunks are the same graph in both anchor modes, apart from the anchor label and qid.
        u = {m: c.build_chunk_graph(c.stream_params(49, 0, 'boat', 3, '', 's', anchor=m)) for m in c.ANCHORS}
        for m in c.ANCHORS:
            self.assertEqual(model_graph(u['latent']), model_graph(u[m]))

    def test_latent_anchor_model_graph_is_114s(self):
        old = parent_contract(PARENT114, 'stream_contract_114')
        for f in old.FRAME_CHOICES:                     # 49 and 97 (121 is new in 117; see below)
            for r in (0, 1):
                for new, prev in zip(c.qualification_params(f, r, 'two-way20-28', 'latent'),
                                     old.qualification_params(f, r, 'two-way20-28', 'latent')):
                    self.assertEqual(model_graph(c.build_chunk_graph(new)), model_graph(old.build_chunk_graph(prev)))

    def test_levers_change_no_model_node(self):
        """Packet117: the levers only label stream_output (and the qualification id); the model graph is the same."""
        for f in c.FRAME_CHOICES:
            for seq, pred, reuse in ((0, '', 0), (5, 'a' * 64, 0), (5, 'a' * 64, 1)):
                graphs = [c.build_chunk_graph(c.stream_params(f, seq, 'boat', 3, pred, 's', reuse, 'two-way20-28',
                                                              anchor_decode=ad, bencode_overlap=bo, prep_ahead=pa))
                          for ad in c.ANCHOR_DECODE_CHOICES for bo in (0, 1) for pa in (0, 1)]
                for g in graphs[1:]:
                    self.assertEqual(model_graph(g), model_graph(graphs[0]))
                    self.assertEqual(set(g), set(graphs[0]))
                    diff = {k for k in g if g[k] != graphs[0][k]}
                    self.assertLessEqual(diff, {'stream_output', '364'})

    def test_121_graph_differs_from_97_only_in_length(self):
        a = model_graph(c.build_chunk_graph(c.stream_params(121, 5, 'boat', 3, 'a' * 64, 's', 0, 'two-way20-28')))
        b = model_graph(c.build_chunk_graph(c.stream_params(97, 5, 'boat', 3, 'a' * 64, 's', 0, 'two-way20-28')))
        self.assertEqual({k for k in a if a[k] != b[k]}, {'356', '366'})
        self.assertEqual((a['356']['inputs']['length'], a['366']['inputs']['frames_number']), (121, 121))

    def test_mixed_is_114_stage_a_and_113_stage_b(self):
        g = c.build_chunk_graph(c.stream_params(49, 5, 'boat', 3, 'a' * 64, 's', 0, anchor='mixed'))
        latent = c.build_chunk_graph(c.stream_params(49, 5, 'boat', 3, 'a' * 64, 's', 0, anchor='latent'))
        frame = c.build_chunk_graph(c.stream_params(49, 5, 'boat', 3, 'a' * 64, 's', 0, anchor='frame'))
        mg, ml, mf = model_graph(g), model_graph(latent), model_graph(frame)
        self.assertEqual({k for k in set(mg) | set(ml) if mg.get(k) != ml.get(k)}, {'stream_condition_b'})
        self.assertEqual(mg['stream_anchor'], ml['stream_anchor'])
        self.assertEqual(mg['stream_condition_a'], ml['stream_condition_a'])
        b = g['stream_condition_b']
        self.assertEqual(b['class_type'], 'LTXStreamFrameConditionB116')
        # Stage B: 113's native image-conditioning inputs on the upsampler output, without an image edge
        # (the frame comes from the predecessor's decode record, after the bounded wait).
        self.assertEqual(b['inputs'], {'vae': ['420', 2], 'latent': ['348', 0], 'strength': 1.0, 'bypass': False,
                                       'run_name': 'stream130-s00000005'})
        self.assertEqual({k: v for k, v in frame['stream_condition_b']['inputs'].items() if k not in ('image', 'stage')},
                         b['inputs'])
        self.assertEqual(g['340']['inputs']['video_latent'], ['stream_condition_b', 0])
        self.assertEqual(mf['340'], mg['340'])

    def test_guide_graph(self):
        g = c.build_chunk_graph(c.stream_params(97, 5, 'boat', 3, 'a' * 64, 's', 1, anchor='guide'))
        ml = model_graph(c.build_chunk_graph(c.stream_params(97, 5, 'boat', 3, 'a' * 64, 's', 1, anchor='latent')))
        mg = model_graph(g)
        changed = {k for k in set(mg) | set(ml) if mg.get(k) != ml.get(k)}
        self.assertEqual(changed, {'stream_anchor', 'stream_condition_a', 'stream_condition_b', 'stream_crop_a',
                                   'stream_crop_b', '377', '340', '348', '388', '391'})
        self.assertEqual(g['stream_anchor']['class_type'], 'LTXStreamGuideAnchor116')
        for stage, guider, edge, sampled in (('a', '388', ['356', 0], ['367', 0]), ('b', '391', ['348', 0], ['369', 0])):
            node = g['stream_condition_' + stage]
            self.assertEqual(node['class_type'], 'LTXStreamGuide116')
            self.assertEqual(node['inputs']['latent'], edge)
            self.assertEqual(node['inputs']['guide'], ['stream_anchor', 0 if stage == 'a' else 1])
            self.assertEqual((node['inputs']['positive'], node['inputs']['negative']), (['365', 0], ['365', 1]))
            self.assertEqual(g[guider]['inputs']['positive'], ['stream_condition_' + stage, 0])
            self.assertEqual(g[guider]['inputs']['negative'], ['stream_condition_' + stage, 1])
            crop = g['stream_crop_' + stage]
            self.assertEqual(crop['class_type'], 'LTXStreamCropGuides116')
            self.assertEqual(crop['inputs']['latent'], sampled)
            self.assertEqual(crop['inputs']['positive'], ['stream_condition_' + stage, 0])
        # The guides never reach the upsampler or the output node: both read the cropped latents.
        self.assertEqual(g['348']['inputs']['samples'], ['stream_crop_a', 2])
        self.assertEqual(g['377']['inputs']['video_latent'], ['stream_condition_a', 2])
        self.assertEqual(g['340']['inputs']['video_latent'], ['stream_condition_b', 2])
        self.assertEqual(g['340']['inputs']['audio_latent'], ['367', 1])
        self.assertEqual(g['stream_output']['inputs']['video_latent'], ['stream_crop_b', 2])
        self.assertEqual(g['stream_output']['inputs']['stage_a_latent'], ['stream_crop_a', 2])
        self.assertEqual(g['stream_output']['inputs']['audio_latent'], ['369', 1])
        geo = c.geometry(97)
        self.assertEqual(geo['guided_stage_tokens'], {'A': 240, 'B': 960})
        self.assertEqual(c.geometry(49)['guided_stage_tokens'], {'A': 144, 'B': 576})

    def test_params_without_reset_read_as_no_reset(self):
        params = c.stream_params(49, 4, 'boat', 3, 'a' * 64, 's', 0, 'two-way20-28')
        params.pop('reset')
        self.assertEqual(c.validate_params(params)['reset'], 0)
        with self.assertRaises(ValueError):
            c.validate_params({k: v for k, v in params.items() if k != 'anchor'})

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
