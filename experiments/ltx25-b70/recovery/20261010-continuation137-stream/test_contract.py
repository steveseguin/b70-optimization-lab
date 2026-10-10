"""CPU tests: packet117 request contract parsing, graph identity, geometry and names."""
import copy
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import stream_contract as c  # noqa: E402


def stream(seq=0, prompt='a red boat on calm water', pred='', reuse=0, frames=49, seed=7, scene='scene1',
           anchor=c.DEFAULT_ANCHOR):
    return c.stream_params(frames, seq, prompt, seed, pred if seq else '', scene, reuse, anchor=anchor)


class Geometry(unittest.TestCase):
    def test_49_and_97(self):
        g49, g97 = c.geometry(49), c.geometry(97)
        self.assertEqual(g49['tensor_shapes'], {'images': [49, 256, 256, 3], 'video_latent': [1, 128, 7, 8, 8],
                                                'audio_latent': [1, 8, 51, 16], 'waveform': [1, 2, 96480]})
        self.assertEqual(g97['tensor_shapes'], {'images': [97, 256, 256, 3], 'video_latent': [1, 128, 13, 8, 8],
                                                'audio_latent': [1, 8, 101, 16], 'waveform': [1, 2, 192480]})
        self.assertEqual(g49['full_payload_bytes'], 39562496)
        self.assertEqual(g97['full_payload_bytes'], 97 * 256 * 256 * 12 + 128 * 13 * 64 * 4 + 8 * 101 * 16 * 4 +
                         2 * 192480 * 4)
        self.assertEqual((g49['anchor_frame_index'], g97['anchor_frame_index']), (48, 96))
        self.assertEqual((g49['latent_anchor_slot'], g97['latent_anchor_slot']), (6, 12))
        self.assertEqual(g97['stage_tokens'], {'A': 208, 'B': 832})
        self.assertEqual(g49['stage_tokens'], {'A': 112, 'B': 448})
        self.assertEqual(g97['latent_shapes']['stage_a_latent'], [1, 128, 13, 4, 4])
        self.assertEqual(g97['noise_mask_shape'], [1, 1, 13, 1, 1])
        self.assertEqual((g97['new_frames_first_chunk'], g97['new_frames_continuation']), (97, 96))
        with self.assertRaises(ValueError):
            c.geometry(25)

    def test_97_audio_shapes_follow_the_sealed_formulas(self):
        # audio_vae.num_of_latents_from_frames: round(frames / fps * 16000 / 160 / 4); samples ((L-1)*4+1)*160*3.
        for frames, measured in ((49, (51, 96480)), (25, (26, 48480))):
            latents = round(frames / 24 * 25)
            self.assertEqual((latents, ((latents - 1) * 4 + 1) * 480), measured)
        latents = round(97 / 24 * 25)
        self.assertEqual((latents, ((latents - 1) * 4 + 1) * 480), (101, 192480))
        self.assertEqual(c.geometry(97)['audio_latents'], 101)
        self.assertIn('measured', c.geometry(97)['provenance'])
        # Packet117: 121 frames by the same formulas, checked on the first eager chunk.
        latents = round(121 / 24 * 25)
        self.assertEqual((latents, ((latents - 1) * 4 + 1) * 480), (126, 240480))
        g = c.geometry(121)
        self.assertEqual((g['temporal_latents'], g['audio_latents'], g['audio_samples']), (16, 126, 240480))
        self.assertEqual(g['tensor_shapes'], {'images': [121, 256, 256, 3], 'video_latent': [1, 128, 16, 8, 8],
                                              'audio_latent': [1, 8, 126, 16], 'waveform': [1, 2, 240480]})
        self.assertEqual(g['stage_tokens'], {'A': 256, 'B': 1024})
        self.assertEqual((g['anchor_frame_index'], g['latent_anchor_slot']), (120, 15))
        self.assertEqual(g['noise_mask_shape'], [1, 1, 16, 1, 1])
        self.assertEqual(g['sharpness_frames'], [0, 1, 2, 5, 10, 24, 60, 120])
        self.assertIn('measured (packet 117 at 121 frames', g['provenance'])   # packet123: measured by 117

    def test_latent_anchor_layout(self):
        self.assertEqual(c.LATENT_ANCHOR_PARTS, (('A', [1, 128, 1, 4, 4]), ('B', [1, 128, 1, 8, 8])))
        self.assertEqual(c.LATENT_ANCHOR_PART_BYTES, {'A': 8192, 'B': 32768})
        self.assertEqual(c.LATENT_ANCHOR_BYTES, 40960)
        self.assertEqual(c.ANCHOR_BYTES, 786432)
        self.assertEqual(c.GUIDE_ANCHOR_PARTS, (('A', [1, 128, 2, 4, 4]), ('B', [1, 128, 2, 8, 8])))
        self.assertEqual(c.GUIDE_ANCHOR_PART_BYTES, {'A': 16384, 'B': 65536})
        self.assertEqual((c.GUIDE_ANCHOR_BYTES, c.GUIDE_LATENT_IDX, c.GUIDE_FRAMES), (81920, -2, 2))

    def test_sharpness_frames(self):
        self.assertEqual(c.geometry(49)['sharpness_frames'], [0, 1, 2, 5, 10, 24, 48])
        self.assertEqual(c.geometry(97)['sharpness_frames'], [0, 1, 2, 5, 10, 24, 48, 96])
        self.assertEqual(c.SHARPNESS_FRAMES, (0, 1, 2, 5, 10, 24))

    def test_anchor_modes(self):
        self.assertEqual(c.ANCHORS, ('mixed', 'latent', 'frame', 'guide'))
        self.assertEqual(c.DEFAULT_ANCHOR, 'frame')                      # packet116: sharp seams by default
        self.assertEqual(c.OFF_CHAIN_DECODE, ('mixed', 'latent', 'guide'))
        self.assertEqual(c.SLOT0_ANCHORS, ('mixed', 'latent', 'frame'))
        mixed = c.numerical_contract(49, 'two-way20-28', 'mixed')['conditioning']
        self.assertEqual(mixed['stage_B']['native'], 'LTXVImgToVideoInplace.execute')
        self.assertIn('367', mixed['stage_A']['anchor'])
        guide = c.numerical_contract(97, 'two-way20-28', 'guide')['conditioning']
        self.assertEqual((guide['latent_idx'], guide['strength'], guide['tokens']), (-2, 1.0, {'A': 240, 'B': 960}))
        self.assertIn('[:, :, 11:13]', guide['guide']['A'])

    def test_qualification_ids_differ_by_length_placement_anchor_and_decoder_graph(self):
        ids = {c.qualification_id(f, p, a, d) for f in c.FRAME_CHOICES for p in c.PLACEMENTS for a in c.ANCHORS
               for d in c.DECODER_GRAPH_CHOICES}
        self.assertEqual(len(ids), 80)
        keys = c.variant_keys()
        self.assertEqual(len(keys), 220)
        self.assertEqual(len({c.variant(*k) for k in keys}), 220)
        self.assertEqual(len({c.qualification_id(*k) for k in keys}), 220)
        self.assertEqual(c.qualification_id(49, 'two-way', 'frame'), c.qualification_id(49, 'two-way', 'frame', 1))
        self.assertEqual(c.launch_placement({}), 'two-way')
        self.assertEqual(c.launch_anchor({}), 'frame')
        self.assertEqual(c.launch_anchor({'LTX_ANCHOR': 'guide'}), 'guide')
        self.assertEqual(c.launch_anchor({'LTX_ANCHOR': 'frame'}), 'frame')
        for bad in ({'LTX_SAMPLER_PLACEMENT': 'shard3-c'},):
            with self.assertRaises(ValueError):
                c.launch_placement(bad)
        with self.assertRaises(ValueError):
            c.launch_anchor({'LTX_ANCHOR': 'pixel'})

    def test_decoder_graph_launch_parameter(self):
        self.assertEqual((c.DECODER_GRAPH_CHOICES, c.DEFAULT_DECODER_GRAPH), ((0, 1), 1))
        self.assertEqual(c.launch_decoder_graph({}), 1)
        self.assertEqual(c.launch_decoder_graph({'LTX_DECODER_GRAPH': '0'}), 0)
        for bad in ('yes', '2', ''):
            with self.assertRaises(ValueError):
                c.launch_decoder_graph({'LTX_DECODER_GRAPH': bad})
        on = c.numerical_contract(49, 'two-way20-28', 'frame', 1)
        off = c.numerical_contract(49, 'two-way20-28', 'frame', 0)
        self.assertTrue(on['decoder_graph']['enabled'] and not off['decoder_graph']['enabled'])
        self.assertEqual(on['decoder_graph']['captured'], ['NADiffusionDecoder.forward_pre_diffusion',
                                                           'NADiffusionDecoder.forward_diff_step'])
        self.assertIn('anchor frame', on['scheduling'])
        self.assertEqual(c.numerical_contract(49, 'two-way20-28', 'latent', 1)['scheduling'], 'as packet115')
        g = c.build_chunk_graph(stream(0))
        self.assertEqual(g['stream_output']['inputs']['decoder_graph'], 1)
        self.assertEqual(g['364']['inputs']['qualification_id'], c.qualification_id(49, 'two-way', 'frame', 1))
        off_graph = c.build_chunk_graph(c.stream_params(49, 0, 'a red boat on calm water', 7, '', 'scene1',
                                                        decoder_graph=0))
        self.assertEqual(c.parse_chunk_graph(off_graph, 49, decoder_graph=0)['decoder_graph'], 0)
        with self.assertRaises(ValueError):
            c.parse_chunk_graph(off_graph, 49)                    # the server runs decoder_graph 1
        with self.assertRaises(ValueError):
            c.parse_chunk_graph(g, 49, decoder_graph=0)
        with self.assertRaises(ValueError):
            c.validate_params(dict(stream(0), decoder_graph=2))
        with self.assertRaises(ValueError):
            c.validate_params(dict(stream(0), decoder_graph=True))
        self.assertEqual(c.variant(49, 'two-way20-28', 'frame', 1), '49/two-way20-28/frame/dg1/ad-cone/bo1/pa1')
        self.assertEqual(c.variant(49, 'two-way20-28', 'latent', 1), '49/two-way20-28/latent/dg1/ad-full/bo0/pa0')

    def test_launch_frames_and_text_reuse_default_on(self):
        self.assertEqual(c.launch_frames({}), 49)
        self.assertEqual(c.launch_frames({'LTX_STREAM_FRAMES': '97'}), 97)
        self.assertEqual(c.launch_frames({'LTX_STREAM_FRAMES': '121'}), 121)
        for bad in ('25', '120', '50'):
            with self.assertRaises(ValueError):
                c.launch_frames({'LTX_STREAM_FRAMES': bad})
        self.assertEqual(c.launch_text_reuse({}), 1)
        self.assertEqual(c.launch_text_reuse({'LTX_STREAM_TEXT_REUSE': '0'}), 0)
        with self.assertRaises(ValueError):
            c.launch_text_reuse({'LTX_STREAM_TEXT_REUSE': 'yes'})

    def test_placement_and_anchor_must_match_server(self):
        g = c.build_chunk_graph(c.stream_params(49, 0, 'x', 1, '', 's', placement='two-way20-28'))
        self.assertEqual(c.parse_chunk_graph(g, 49, 'two-way20-28')['placement'], 'two-way20-28')
        with self.assertRaises(ValueError):
            c.parse_chunk_graph(g, 49, 'two-way')
        for other in ('latent', 'guide', 'mixed'):
            with self.assertRaises(ValueError):
                c.parse_chunk_graph(g, 49, 'two-way20-28', other)


class Parse(unittest.TestCase):
    def test_roundtrip_every_fixed_and_stream_form(self):
        for frames in c.FRAME_CHOICES:
            for anchor in c.ANCHORS:
                for mode in (0, 1):
                    for params in c.qualification_params(frames, mode, anchor=anchor):
                        self.assertEqual(c.parse_chunk_graph(c.build_chunk_graph(params), frames, anchor=anchor),
                                         params)
                for params in (stream(0, frames=frames, anchor=anchor), stream(5, pred='a' * 64, frames=frames,
                                                                               anchor=anchor),
                               stream(5, pred='b' * 64, reuse=1, frames=frames, anchor=anchor)):
                    self.assertEqual(c.parse_chunk_graph(c.build_chunk_graph(params), frames, anchor=anchor), params)

    def test_frames_must_match_server(self):
        with self.assertRaises(ValueError):
            c.parse_chunk_graph(c.build_chunk_graph(stream(frames=97)), 49)

    def test_any_tamper_is_refused(self):
        for anchor in c.ANCHORS:
            graph = c.build_chunk_graph(stream(3, pred='c' * 64, anchor=anchor))
            mutations = [
                lambda g: g.__setitem__('999', {'class_type': 'SaveImage', 'inputs': {}}),
                lambda g: g.__setitem__('374', {'class_type': 'VAEDecode',
                                                'inputs': {'samples': ['369', 0], 'vae': ['420', 2]}}),
                lambda g: g['344']['inputs'].__setitem__('sigmas', ['395', 0]),
                lambda g: g['356']['inputs'].__setitem__('length', 49 + 48),
                lambda g: g['stream_condition_a']['inputs'].__setitem__('strength', 0.5),
                lambda g: g['339']['inputs'].__setitem__('noise_seed', 8),
                lambda g: g['stream_output']['inputs'].__setitem__('stream_seq', 4),
                lambda g: g['stream_output']['inputs'].__setitem__('stage_a_latent', ['348', 0]),
                lambda g: g['stream_output']['inputs'].__setitem__('vae', ['420', 3]),
                lambda g: g.pop('stream_condition_b'),
                lambda g: g['388']['inputs'].__setitem__('model', ['420', 1]),
                lambda g: g['388']['inputs'].__setitem__('positive', ['365', 1]),
                lambda g: g['340']['inputs'].__setitem__('video_latent', ['348', 0]),
                lambda g: g['stream_output']['inputs'].__setitem__('video_latent', ['368', 0]),
            ]
            for mutate in mutations:
                g = copy.deepcopy(graph)
                mutate(g)
                with self.assertRaises((ValueError, KeyError)):
                    c.parse_chunk_graph(g, 49, anchor=anchor)

    def test_latent_condition_edges_cannot_be_crossed(self):
        for anchor in ('latent', 'mixed'):
            g = c.build_chunk_graph(stream(3, pred='c' * 64, anchor=anchor))
            g['stream_condition_a']['inputs']['anchor'] = ['stream_anchor', 1]
            with self.assertRaises(ValueError):
                c.parse_chunk_graph(g, 49, anchor=anchor)
        g = c.build_chunk_graph(stream(3, pred='c' * 64, anchor='guide'))
        g['stream_condition_b']['inputs']['guide'] = ['stream_anchor', 0]
        with self.assertRaises(ValueError):
            c.parse_chunk_graph(g, 49, anchor='guide')
        g = c.build_chunk_graph(stream(3, pred='c' * 64, anchor='guide'))
        g['348']['inputs']['samples'] = ['367', 0]          # the upsampler must never see the guide frames
        with self.assertRaises(ValueError):
            c.parse_chunk_graph(g, 49, anchor='guide')

    def test_not_a_contract_graph(self):
        for value in ({}, [], {'stream_output': {}}, None):
            with self.assertRaises(ValueError):
                c.parse_chunk_graph(value, 49)
        old = c.build_chunk_graph(stream(0))
        old['stream_output']['class_type'] = 'LTXStreamChunk112'
        with self.assertRaises(ValueError):
            c.parse_chunk_graph(old, 49)


class Rules(unittest.TestCase):
    def test_stream_chunk0_unanchored_and_later_anchored(self):
        for anchor, provider, condition in (('latent', 'LTXStreamLatentAnchor116', 'LTXStreamLatentCondition116'),
                                            ('frame', 'LTXStreamAnchor116', 'LTXStreamCondition116')):
            self.assertNotIn('stream_anchor', c.build_chunk_graph(stream(0, anchor=anchor)))
            g = c.build_chunk_graph(stream(1, pred='d' * 64, anchor=anchor))
            self.assertEqual(g['stream_anchor']['class_type'], provider)
            self.assertEqual(g['stream_condition_a']['class_type'], condition)
            self.assertEqual(g['stream_anchor']['inputs']['predecessor_anchor_sha256'], 'd' * 64)
            self.assertEqual(g['340']['inputs']['video_latent'], ['stream_condition_b', 0])
            self.assertEqual(g['377']['inputs']['video_latent'], ['stream_condition_a', 0])
        with self.assertRaises(ValueError):
            stream(1, pred='')
        with self.assertRaises(ValueError):
            c.validate_params(dict(stream(0), predecessor_anchor_sha256='e' * 64))
        with self.assertRaises(ValueError):
            c.validate_params(dict(stream(2, pred='f' * 64), chunk_index=1))

    def test_no_decoder_nodes_and_output_takes_latents_and_vaes(self):
        for params in c.qualification_params(97, 1) + [stream(0), stream(4, pred='a' * 64)]:
            g = c.build_chunk_graph(params)
            self.assertFalse({'374', '358', '414'} & set(g))
            self.assertNotIn('VAEDecode', {n['class_type'] for n in g.values()})
            out = g['stream_output']['inputs']
            self.assertEqual((out['video_latent'], out['audio_latent'], out['stage_a_latent'], out['vae'],
                              out['audio_vae']), (['369', 0], ['369', 1], ['367', 0], ['420', 2], ['420', 3]))
            self.assertEqual(out['anchor'], params['anchor'])

    def test_reuse_only_on_anchored_non_eager_chunks(self):
        with self.assertRaises(ValueError):
            c.validate_params(dict(stream(0), reuse_text=1))
        params = stream(4, pred='a' * 64, reuse=1)
        g = c.build_chunk_graph(params)
        self.assertNotIn('364', g)
        self.assertNotIn('conditioning', g['stream_text']['inputs'])
        eager = c.qualification_params(49, 1)[1]
        with self.assertRaises(ValueError):
            c.validate_params(dict(eager, reuse_text=1))

    def test_qualification_fixed_and_includes_a_cut(self):
        rows = c.qualification_params(97, 1)
        self.assertEqual([r['kind'] for r in rows], ['qualify-eager'] * 3 + ['qualify-graph'] * 3 + ['qualify-repeat'] * 3)
        self.assertEqual([r['reuse_text'] for r in rows], [0, 0, 0, 0, 1, 0, 0, 1, 0])
        self.assertEqual([r['prompt'] for r in rows[:3]], list(c.QUALIFICATION_PROMPTS))
        self.assertNotEqual(rows[1]['prompt'], rows[2]['prompt'])
        self.assertEqual({r['anchor'] for r in rows}, {'frame'})
        self.assertEqual({r['decoder_graph'] for r in rows}, {1})
        self.assertEqual({r['decoder_graph'] for r in c.qualification_params(97, 1, decoder_graph=0)}, {0})
        with self.assertRaises(ValueError):
            c.validate_params(dict(rows[0], seed=1))
        with self.assertRaises(ValueError):
            c.validate_params(dict(rows[4], predecessor_anchor_sha256='a' * 64))

    def test_gates_by_kind_and_repeat_is_the_streaming_form(self):
        rows = c.qualification_params(49, 0)
        eager, graph, repeat = (c.build_chunk_graph(rows[i]) for i in (0, 3, 6))
        self.assertEqual(eager['stream_gate']['inputs']['mode'], 'original')
        self.assertEqual(graph['stream_gate']['inputs']['mode'], 'graph')
        self.assertNotIn('stream_gate', repeat)
        self.assertNotIn('425', repeat)
        self.assertEqual(repeat['364']['inputs']['clip'], ['420', 1])
        s = c.build_chunk_graph(stream(0))
        self.assertNotIn('stream_gate', s)
        self.assertEqual(sorted(repeat), sorted(s))
        self.assertEqual(c.GATED_KINDS, ('qualify-eager', 'qualify-graph'))

    def test_prompt_and_scene_validation(self):
        for bad in ('', ' lead', 'x' * 4001, 'tab\there'):
            with self.assertRaises(ValueError):
                stream(prompt=bad)
        with self.assertRaises(ValueError):
            stream(scene='Has-Upper')
        with self.assertRaises(ValueError):
            stream(seed=2 ** 64)

    def test_run_names_carry_the_117_prefix(self):
        self.assertEqual(c.run_name(stream(12, pred='a' * 64)), 'stream137-s00000012')
        self.assertEqual(c.run_name(c.qualification_params(49, 0)[5]), 'stream137-qgraph-c000002')
        self.assertEqual(c.RUN_PREFIX, 'stream137')
        self.assertEqual((c.PACKET, c.COMPARISON_MODE), (137, 'stream-candidate-137-v1'))
        self.assertEqual((c.QUALIFICATION_CLIP_BASE, c.STREAM_CLIP_BASE), (13700000, 13701000))
        names = c.fixed_names()
        self.assertEqual(len(names), 11)
        self.assertTrue(all(n.startswith('stream137-') for n in names))
        self.assertIn('stream137-window-probe', names)
        self.assertIsNone(c.RUN_NAME_RE.fullmatch('stream116b-s00000001'))
        self.assertTrue(all(c.RUN_NAME_RE.fullmatch(n) for n in names[2:]))
        self.assertIsNone(c.RUN_NAME_RE.fullmatch('stream112-s00000001'))
        self.assertEqual(c.clip_index(stream(3, pred='a' * 64)), c.STREAM_CLIP_BASE + 3)
        self.assertLess(c.STREAM_CLIP_BASE + c.MAX_STREAM_SEQ, c.CLIP_INDEX_MAX + 1)

    def test_no_previous_packet_name_in_any_graph(self):
        import json
        for frames in c.FRAME_CHOICES:
            for anchor in c.ANCHORS:
                rows = c.qualification_params(frames, 1, anchor=anchor) + [stream(0, anchor=anchor),
                                                                           stream(3, pred='a' * 64, anchor=anchor)]
                for params in rows:
                    text = json.dumps(c.build_chunk_graph(params))
                    self.assertNotIn('stream112', text)
                    self.assertNotIn('stream113', text)
                    self.assertNotIn('stream114', text)
                    self.assertNotIn('stream115', text)
                    self.assertNotIn('stream116-', text)
                    self.assertNotIn('stream116b-', text)
                    classes = ' '.join(n['class_type'] for n in c.build_chunk_graph(params).values())
                    self.assertNotIn('114', classes)
                    self.assertNotIn('115', classes)
        self.assertNotIn('stream112', json.dumps(c.setup_graphs()))
        self.assertNotIn('stream114', json.dumps(c.setup_graphs()))
        self.assertNotIn('115', json.dumps(c.setup_graphs()))

    def test_executor_guard_single_run_name(self):
        for params in c.qualification_params(49, 1) + [stream(2, pred='a' * 64, reuse=1),
                                                       stream(2, pred='a' * 64, anchor='frame'),
                                                       stream(2, pred='a' * 64, anchor='guide'),
                                                       stream(2, pred='a' * 64, anchor='latent')]:
            g = c.build_chunk_graph(params)
            names = {n['inputs']['run_name'] for n in g.values() if 'run_name' in n['inputs']}
            self.assertEqual(names, {c.run_name(params)})


class Levers(unittest.TestCase):
    """Packet117: anchor_decode / bencode_overlap / prep_ahead."""
    def test_defaults_and_launch(self):
        self.assertEqual(c.DEFAULT_LEVERS, ('cone', 1, 1))
        self.assertEqual(c.default_levers('frame'), ('cone', 1, 1))
        for a in ('mixed', 'latent', 'guide'):
            self.assertEqual(c.default_levers(a), ('full', 0, 0))
        self.assertEqual(c.launch_levers({}), ('cone', 1, 1))
        self.assertEqual(c.launch_levers({'LTX_ANCHOR': 'latent'}), ('full', 0, 0))
        self.assertEqual(c.launch_levers({'LTX_ANCHOR_DECODE': 'full', 'LTX_BENCODE_OVERLAP': '0',
                                          'LTX_PREP_AHEAD': '1'}), ('full', 0, 1))
        for bad in ({'LTX_ANCHOR_DECODE': 'tail'}, {'LTX_BENCODE_OVERLAP': '2'}, {'LTX_PREP_AHEAD': 'yes'},
                    {'LTX_ANCHOR': 'mixed', 'LTX_ANCHOR_DECODE': 'cone'},
                    {'LTX_ANCHOR': 'guide', 'LTX_BENCODE_OVERLAP': '1'},
                    {'LTX_ANCHOR': 'latent', 'LTX_PREP_AHEAD': '1'}):
            with self.assertRaises(ValueError):
                c.launch_levers(bad)

    def test_validation_refuses_levers_without_the_frame_anchor(self):
        for anchor in ('mixed', 'latent', 'guide'):
            for levers in (('cone', 0, 0), ('full', 1, 0), ('full', 0, 1)):
                with self.assertRaises(ValueError):
                    c.stream_params(49, 0, 'x', 1, '', 's', anchor=anchor, anchor_decode=levers[0],
                                    bencode_overlap=levers[1], prep_ahead=levers[2])
        p = stream(0)
        for key, bad in (('anchor_decode', 'tail'), ('anchor_decode', 1), ('bencode_overlap', 2),
                         ('bencode_overlap', True), ('prep_ahead', '1')):
            with self.assertRaises(ValueError):
                c.validate_params(dict(p, **{key: bad}))
        with self.assertRaises(ValueError):
            c.validate_params({k: v for k, v in p.items() if k != 'prep_ahead'})

    def test_graph_carries_the_levers_and_parse_refuses_a_different_server(self):
        p = c.stream_params(121, 0, 'x', 1, '', 's', placement='two-way20-28', anchor_decode='full',
                            bencode_overlap=1, prep_ahead=0)
        g = c.build_chunk_graph(p)
        out = g['stream_output']['inputs']
        self.assertEqual((out['anchor_decode'], out['bencode_overlap'], out['prep_ahead'], out['frames']),
                         ('full', 1, 0, 121))
        self.assertEqual(g['364']['inputs']['qualification_id'],
                         c.qualification_id(121, 'two-way20-28', 'frame', 1, 'full', 1, 0))
        self.assertEqual(c.parse_chunk_graph(g, 121, 'two-way20-28', 'frame', 1, ('full', 1, 0)), p)
        for levers in (None, ('cone', 1, 0), ('full', 0, 0), ('full', 1, 1)):
            with self.assertRaises(ValueError):
                c.parse_chunk_graph(g, 121, 'two-way20-28', 'frame', 1, levers)
        with self.assertRaises(ValueError):
            c.parse_chunk_graph(g, 97, 'two-way20-28', 'frame', 1, ('full', 1, 0))
        tampered = copy.deepcopy(g)
        tampered['stream_output']['inputs']['prep_ahead'] = 1
        with self.assertRaises(ValueError):
            c.parse_chunk_graph(tampered, 121, 'two-way20-28', 'frame', 1, ('full', 1, 1))  # qid no longer matches

    def test_numerical_contract_names_each_lever(self):
        on = c.numerical_contract(97, 'two-way20-28', 'frame', 1)['levers']
        off = c.numerical_contract(97, 'two-way20-28', 'frame', 1, 'full', 0, 0)['levers']
        self.assertEqual(on['anchor_decode']['mode'], 'cone')
        self.assertEqual(off['anchor_decode']['mode'], 'full')
        self.assertTrue(on['bencode_overlap']['enabled'] and on['prep_ahead']['enabled'])
        self.assertFalse(off['bencode_overlap']['enabled'] or off['prep_ahead']['enabled'])
        self.assertIn('images[96]', on['anchor_decode']['anchor'])
        self.assertEqual(c.numerical_contract(97, 'two-way20-28', 'latent', 1)['levers']['anchor_decode']['mode'],
                         'full')

    def test_qualification_rows_carry_the_launch_levers(self):
        rows = c.qualification_params(121, 1, 'two-way20-28', 'frame', 0, 'cone', 0, 1)
        self.assertEqual(len(rows), 9)
        self.assertTrue(all((r['anchor_decode'], r['bencode_overlap'], r['prep_ahead']) == ('cone', 0, 1)
                            for r in rows))
        self.assertTrue(all(c.validate_params(r) for r in rows))


if __name__ == '__main__':
    unittest.main()
