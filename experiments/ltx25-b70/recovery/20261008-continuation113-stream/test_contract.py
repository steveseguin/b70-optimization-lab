"""CPU tests: packet112 request contract parsing and graph identity."""
import copy
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import stream_contract as c  # noqa: E402


def stream(seq=0, prompt='a red boat on calm water', pred='', reuse=0, frames=49, seed=7, scene='scene1'):
    return c.stream_params(frames, seq, prompt, seed, pred if seq else '', scene, reuse)


class Geometry(unittest.TestCase):
    def test_49_and_25(self):
        g49, g25 = c.geometry(49), c.geometry(25)
        self.assertEqual(g49['tensor_shapes'], {'images': [49, 256, 256, 3], 'video_latent': [1, 128, 7, 8, 8],
                                                'audio_latent': [1, 8, 51, 16], 'waveform': [1, 2, 96480]})
        self.assertEqual(g49['full_payload_bytes'], 39562496)
        self.assertEqual(g25['full_payload_bytes'], 20193024)
        self.assertEqual(g49['anchor_frame_index'], 48)
        self.assertEqual(g25['anchor_frame_index'], 24)
        self.assertEqual(g49['stage_shapes']['A'], [1, 128, 7, 4, 4])
        self.assertEqual(g25['noise_mask_shape'], [1, 1, 4, 1, 1])
        self.assertEqual(c.ANCHOR_BYTES, 786432)
        self.assertEqual((g49['new_frames_first_chunk'], g49['new_frames_continuation']), (49, 48))
        with self.assertRaises(ValueError):
            c.geometry(97)

    def test_qualification_ids_differ_by_length_and_placement(self):
        ids = {c.qualification_id(f, p) for f in c.FRAME_CHOICES for p in c.PLACEMENTS}
        self.assertEqual(len(ids), 4)
        self.assertEqual(c.launch_placement({}), 'two-way')
        with self.assertRaises(ValueError):
            c.launch_placement({'LTX_SAMPLER_PLACEMENT': 'shard3-c'})

    def test_placement_must_match_server(self):
        g = c.build_chunk_graph(c.stream_params(49, 0, 'x', 1, '', 's', placement='two-way20-28'))
        self.assertEqual(c.parse_chunk_graph(g, 49, 'two-way20-28')['placement'], 'two-way20-28')
        with self.assertRaises(ValueError):
            c.parse_chunk_graph(g, 49, 'two-way')

    def test_launch_frames(self):
        self.assertEqual(c.launch_frames({}), 49)
        self.assertEqual(c.launch_frames({'LTX_STREAM_FRAMES': '25'}), 25)
        with self.assertRaises(ValueError):
            c.launch_frames({'LTX_STREAM_FRAMES': '50'})


class Parse(unittest.TestCase):
    def test_roundtrip_every_fixed_and_stream_form(self):
        for frames in (49, 25):
            for mode in (0, 1):
                for params in c.qualification_params(frames, mode):
                    self.assertEqual(c.parse_chunk_graph(c.build_chunk_graph(params), frames), params)
            for params in (stream(0, frames=frames), stream(5, pred='a' * 64, frames=frames),
                           stream(5, pred='b' * 64, reuse=1, frames=frames)):
                self.assertEqual(c.parse_chunk_graph(c.build_chunk_graph(params), frames), params)

    def test_frames_must_match_server(self):
        with self.assertRaises(ValueError):
            c.parse_chunk_graph(c.build_chunk_graph(stream(frames=25)), 49)

    def test_any_tamper_is_refused(self):
        graph = c.build_chunk_graph(stream(3, pred='c' * 64))
        mutations = [
            lambda g: g.__setitem__('999', {'class_type': 'SaveImage', 'inputs': {}}),
            lambda g: g['344']['inputs'].__setitem__('sigmas', ['395', 0]),
            lambda g: g['356']['inputs'].__setitem__('length', 97),
            lambda g: g['stream_condition_a']['inputs'].__setitem__('strength', 0.5),
            lambda g: g['339']['inputs'].__setitem__('noise_seed', 8),
            lambda g: g['stream_output']['inputs'].__setitem__('stream_seq', 4),
            lambda g: g.pop('stream_condition_b'),
            lambda g: g['388']['inputs'].__setitem__('model', ['420', 1]),
        ]
        for mutate in mutations:
            g = copy.deepcopy(graph)
            mutate(g)
            with self.assertRaises((ValueError, KeyError)):
                c.parse_chunk_graph(g, 49)

    def test_not_a_contract_graph(self):
        for value in ({}, [], {'stream_output': {}}, None):
            with self.assertRaises(ValueError):
                c.parse_chunk_graph(value, 49)


class Rules(unittest.TestCase):
    def test_stream_chunk0_unanchored_and_later_anchored(self):
        self.assertNotIn('stream_anchor', c.build_chunk_graph(stream(0)))
        g = c.build_chunk_graph(stream(1, pred='d' * 64))
        self.assertEqual(g['stream_anchor']['inputs']['predecessor_anchor_sha256'], 'd' * 64)
        self.assertEqual(g['340']['inputs']['video_latent'], ['stream_condition_b', 0])
        self.assertEqual(g['377']['inputs']['video_latent'], ['stream_condition_a', 0])
        with self.assertRaises(ValueError):
            stream(1, pred='')
        with self.assertRaises(ValueError):
            c.validate_params(dict(stream(0), predecessor_anchor_sha256='e' * 64))
        with self.assertRaises(ValueError):
            c.validate_params(dict(stream(2, pred='f' * 64), chunk_index=1))

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
        rows = c.qualification_params(49, 1)
        self.assertEqual([r['kind'] for r in rows], ['qualify-eager'] * 3 + ['qualify-graph'] * 3 + ['qualify-repeat'] * 3)
        self.assertEqual([r['reuse_text'] for r in rows], [0, 0, 0, 0, 1, 0, 0, 1, 0])
        self.assertEqual([r['prompt'] for r in rows[:3]], list(c.QUALIFICATION_PROMPTS))
        self.assertNotEqual(rows[1]['prompt'], rows[2]['prompt'])
        with self.assertRaises(ValueError):
            c.validate_params(dict(rows[0], seed=1))
        with self.assertRaises(ValueError):
            c.validate_params(dict(rows[4], predecessor_anchor_sha256='a' * 64))

    def test_gates_and_captures_by_kind(self):
        rows = c.qualification_params(49, 0)
        eager, graph, repeat = (c.build_chunk_graph(rows[i]) for i in (0, 3, 6))
        self.assertEqual(eager['stream_gate']['inputs']['mode'], 'original')
        self.assertEqual(graph['stream_gate']['inputs']['mode'], 'graph')
        self.assertNotIn('stream_gate', repeat)
        self.assertNotIn('425', repeat)
        self.assertEqual(repeat['364']['inputs']['clip'], ['420', 1])
        for g in (eager, graph, repeat):
            self.assertIn('414', g)
        s = c.build_chunk_graph(stream(0))
        self.assertNotIn('414', s)
        self.assertNotIn('stream_gate', s)
        # repeat chain is the streaming form plus the capture node
        r = copy.deepcopy(repeat)
        r.pop('414')
        self.assertEqual(sorted(r), sorted(s))

    def test_prompt_and_scene_validation(self):
        for bad in ('', ' lead', 'x' * 4001, 'tab\there'):
            with self.assertRaises(ValueError):
                stream(prompt=bad)
        with self.assertRaises(ValueError):
            stream(scene='Has-Upper')
        with self.assertRaises(ValueError):
            stream(seed=2 ** 64)

    def test_run_names_and_clip_indices(self):
        self.assertEqual(c.run_name(stream(12, pred='a' * 64)), 'stream112-s00000012')
        self.assertEqual(c.run_name(c.qualification_params(49, 0)[5]), 'stream112-qgraph-c000002')
        self.assertEqual(c.clip_index(stream(3, pred='a' * 64)), c.STREAM_CLIP_BASE + 3)
        self.assertLess(c.STREAM_CLIP_BASE + c.MAX_STREAM_SEQ, c.CLIP_INDEX_MAX + 1)

    def test_executor_guard_single_run_name(self):
        for params in c.qualification_params(49, 1) + [stream(2, pred='a' * 64, reuse=1)]:
            g = c.build_chunk_graph(params)
            names = {n['inputs']['run_name'] for n in g.values() if 'run_name' in n['inputs']}
            self.assertEqual(names, {c.run_name(params)})


if __name__ == '__main__':
    unittest.main()
