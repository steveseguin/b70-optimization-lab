#!/usr/bin/env python3
"""CPU structural tests. Does not import Torch, ComfyUI, or the runtime nodes."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('build-continuation-graph.py')
spec = importlib.util.spec_from_file_location('continuation_graph', SCRIPT)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
ANCHOR = ['future_float_anchor', 0]
FIXTURE_HASH = hashlib.sha256(b'CPU contract fixture; no image payload').hexdigest()


def subsequent():
    return builder.build_chunk(1, 'continuation-cpu-test', anchor_edge=ANCHOR,
                               anchor_sha256=FIXTURE_HASH)


class GraphTests(unittest.TestCase):
    def test_first_chunk_preserves_graph_except_output_names(self):
        result = builder.build_chunk(0, 'continuation-first')
        expected = builder.load_base()
        expected['414']['inputs']['run_name'] = 'continuation-first'
        expected['75']['inputs']['filename_prefix'] = 'continuation-first/preview'
        self.assertEqual(result['graph'], expected)
        self.assertIsNone(result['external_image_input'])
        self.assertEqual(result['chunk']['new_video_frames'], 25)
        self.assertEqual(result['chunk']['delivery_frame_start'], 0)

    def test_both_stages_reanchor_after_mask_loss(self):
        result = subsequent()
        graph = result['graph']
        for key, latent in [('continuation_anchor_stage1', ['356', 0]),
                            ('continuation_anchor_stage2', ['348', 0])]:
            self.assertEqual(graph[key], {'class_type': 'LTXVImgToVideoInplace',
                'inputs': {'vae': ['420', 2], 'image': ANCHOR, 'latent': latent,
                           'strength': 1.0, 'bypass': False}})
        self.assertEqual(graph['377']['inputs']['video_latent'], ['continuation_anchor_stage1', 0])
        self.assertEqual(graph['340']['inputs']['video_latent'], ['continuation_anchor_stage2', 0])
        self.assertEqual(graph['344']['inputs']['latent_image'], ['377', 0])
        self.assertEqual(graph['368']['inputs']['latent_image'], ['340', 0])

    def test_subsequent_delta_is_exactly_two_anchor_nodes_and_two_edges(self):
        first = builder.build_chunk(0, 'continuation-cpu-test')['graph']
        graph = subsequent()['graph']
        del graph['continuation_anchor_stage1'], graph['continuation_anchor_stage2']
        graph['377']['inputs']['video_latent'] = ['356', 0]
        graph['340']['inputs']['video_latent'] = ['348', 0]
        self.assertEqual(graph, first)

    def test_workload_schedule_and_raw_audio_unchanged(self):
        graph = subsequent()['graph']
        base = builder.load_base()
        for key in ('356', '366', '404', '395', '352', '341', '338', '339',
                    '348', '358', '374', '370', '369', '420'):
            self.assertEqual(graph[key], base[key], key)
        self.assertEqual(graph['377']['inputs']['audio_latent'], ['366', 0])
        self.assertEqual(graph['340']['inputs']['audio_latent'], ['367', 1])
        self.assertEqual(graph['414']['inputs']['audio'], ['358', 0])
        self.assertEqual([len(graph[k]['inputs']['sigmas'].split(',')) - 1 for k in ('404', '395')], [8, 3])

    def test_explicit_pending_input_and_frame_accounting(self):
        result = subsequent()
        external = result['external_image_input']
        self.assertNotIn(ANCHOR[0], result['graph'])
        self.assertEqual(external['shape'], [1, 256, 256, 3])
        self.assertEqual(external['predecessor_chunk_index'], 0)
        self.assertEqual(external['predecessor_frame_index'], 24)
        self.assertFalse(external['provider_implemented'])
        self.assertFalse(external['payload_hash_verified'])
        self.assertFalse(result['ready_for_submission'])
        self.assertEqual(result['chunk']['new_video_frames'], 24)
        self.assertEqual(result['chunk']['delivery_frame_start'], 1)
        self.assertFalse(result['chunk']['output_slicing_implemented'])
        self.assertFalse(result['audio']['modified'])
        self.assertTrue(result['audio']['timeline_policy'].startswith('unresolved'))

    def test_deterministic_construction_and_seed_schedule(self):
        self.assertEqual(subsequent(), subsequent())
        result = builder.build_chunk(3, 'continuation-chunk3', 99, 'A second scene.', ANCHOR, FIXTURE_HASH)
        self.assertEqual(result['external_image_input']['predecessor_chunk_index'], 2)
        for key in ('338', '339'):
            self.assertEqual(result['graph'][key]['inputs']['noise_seed'], 99)
        self.assertEqual(result['graph']['364']['inputs']['text'], 'A second scene.')

    def test_invalid_chunk_contracts(self):
        cases = [(-1, 'continuation-x', 42, None, None, None),
                 (True, 'continuation-x', 42, None, None, None),
                 (0, '../unsafe', 42, None, None, None),
                 (0, 'continuation-x', -1, None, None, None),
                 (0, 'continuation-x', 2**64, None, None, None),
                 (0, 'continuation-x', 42, '', None, None),
                 (0, 'continuation-x', 42, None, ANCHOR, FIXTURE_HASH),
                 (0, 'continuation-x', 42, None, None, FIXTURE_HASH),
                 (1, 'continuation-x', 42, None, None, FIXTURE_HASH),
                 (1, 'continuation-x', 42, None, ANCHOR, 'not-a-hash'),
                 (1, 'continuation-x', 42, None, ['364', 0], FIXTURE_HASH),
                 (1, 'continuation-x', 42, None, ['external', -1], FIXTURE_HASH),
                 (1, 'continuation-x', 42, None, ['external', True], FIXTURE_HASH)]
        for args in cases:
            with self.subTest(args=args), self.assertRaises(ValueError):
                builder.build_chunk(*args)

    def test_complete_edge_validation_rejects_bad_sources_types_slots_and_cycles(self):
        cases = [('344', 'noise', ['absent', 0]), ('344', 'noise', ['339', 2]),
                 ('344', 'noise', ['364', 0]), ('344', 'noise', ['339', True]),
                 ('344', 'noise', ['339']), ('344', 'noise', 'not-an-edge'),
                 ('continuation_anchor_stage1', 'latent', ['377', 0]),
                 ('continuation_anchor_stage2', 'image', ['future_float_anchor', 1]),
                 ('continuation_anchor_stage2', 'image', ['374', 0]),
                 ('continuation_anchor_stage1', 'strength', float('nan'))]
        for key, field, value in cases:
            graph = subsequent()['graph']
            graph[key]['inputs'][field] = value
            with self.subTest(key=key, field=field, value=value), self.assertRaises(ValueError):
                builder.validate_edges(graph, ANCHOR)

    def test_schema_rejects_extra_missing_inputs_and_unknown_classes(self):
        for alteration in ('extra', 'missing', 'class'):
            graph = subsequent()['graph']
            if alteration == 'extra':
                graph['344']['inputs']['surprise'] = 1
            elif alteration == 'missing':
                del graph['344']['inputs']['noise']
            else:
                graph['344']['class_type'] = 'UnimplementedSampler'
            with self.subTest(alteration=alteration), self.assertRaises(ValueError):
                builder.validate_edges(graph, ANCHOR)

    def test_no_import_of_runtime_libraries(self):
        self.assertNotIn('torch', sys.modules)
        self.assertFalse(any(key.startswith('comfy') for key in sys.modules))

    def test_pinned_native_anchor_schema_from_ast_no_execution(self):
        root = Path('/home/steve/src/ComfyUI-ltx25-baseline')
        for relative, expected in builder.SOURCE_HASHES.items():
            raw = (root / relative).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), expected)
        tree = ast.parse((root / 'comfy_extras/nodes_lt.py').read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'LTXVImgToVideoInplace')
        schema = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'define_schema')
        inputs = {}
        for n in ast.walk(schema):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == 'Input':
                inputs[n.args[0].value] = n.func.value.attr
        self.assertEqual(inputs, {'vae': 'Vae', 'image': 'Image', 'latent': 'Latent',
                                  'strength': 'Float', 'bypass': 'Boolean'})
        execute = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'execute')
        self.assertEqual([a.arg for a in execute.args.args], ['cls', 'vae', 'image', 'latent', 'strength', 'bypass'])

    def test_all_declared_outputs_match_source_schemas_without_imports(self):
        root = Path('/home/steve/src/ComfyUI-ltx25-baseline')
        paths = [root / relative for relative in builder.SOURCE_HASHES]
        paths += [SCRIPT.with_name('resident_node.py'), SCRIPT.with_name('capture_node.py')]
        found = {}
        for path in paths:
            for cls in ast.parse(path.read_text()).body:
                if not isinstance(cls, ast.ClassDef) or cls.name not in builder.SPECS:
                    continue
                for item in cls.body:
                    if isinstance(item, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'RETURN_TYPES' for t in item.targets):
                        found[cls.name] = [value.value if isinstance(value, ast.Constant) else value.attr
                                           for value in item.value.elts]
                    if isinstance(item, ast.FunctionDef) and item.name == 'define_schema':
                        for field in ast.walk(item):
                            if isinstance(field, ast.keyword) and field.arg == 'outputs':
                                found[cls.name] = [call.func.value.attr.upper() for call in field.value.elts]
        self.assertEqual(set(found), set(builder.SPECS))
        for name, (_, expected) in builder.SPECS.items():
            self.assertEqual(found[name], expected, name)

    def test_cli_writes_envelope_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory(prefix='ltx-continuation-cpu-') as tmp:
            output = Path(tmp) / 'module.json'
            cmd = [sys.executable, str(SCRIPT), '--chunk-index', '0', '--run-name',
                   'continuation-cli', '--output', str(output)]
            first = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertFalse(json.loads(output.read_text())['ready_for_submission'])
            original = output.read_bytes()
            second = subprocess.run(cmd, capture_output=True, text=True)
            self.assertNotEqual(second.returncode, 0)
            self.assertEqual(output.read_bytes(), original)


if __name__ == '__main__':
    unittest.main(verbosity=2)
