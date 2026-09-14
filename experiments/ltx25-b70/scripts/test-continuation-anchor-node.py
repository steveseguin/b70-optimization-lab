#!/usr/bin/env python3
"""Stdlib integration checks; deliberately do not execute the Torch tensor path."""
import ast
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
import continuation_anchor_node as node

spec = importlib.util.spec_from_file_location('bound_graph', SCRIPTS / 'bind-continuation-anchor.py')
bound = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bound)

FRAME_BYTES = 256 * 256 * 3 * 4
# Negative zero, negative/out-of-range finite values and a tiny subnormal must
# survive intact. A convenient-looking clamp or image conversion would fail.
PATTERN = struct.pack('<IIII', 0x80000000, 0xbf800000, 0x40000000, 0x00000001)
PAYLOAD = PATTERN * (FRAME_BYTES // len(PATTERN))
SHA = hashlib.sha256(PAYLOAD).hexdigest()


def write_capture(output_root, name='continuation-prior'):
    folder = output_root / 'validation' / name
    folder.mkdir(parents=True)
    header = json.dumps({'images': {'dtype': 'F32', 'shape': [25, 256, 256, 3],
                                  'data_offsets': [0, 25 * FRAME_BYTES]}}).encode()
    header += b' ' * (-len(header) % 8)
    capture = folder / 'tensors.safetensors'
    with capture.open('xb') as stream:
        stream.write(struct.pack('<Q', len(header)))
        stream.write(header)
        stream.seek(24 * FRAME_BYTES, 1)
        stream.write(PAYLOAD)
    return capture


class ProviderIntegrationTests(unittest.TestCase):
    def test_reads_exact_predecessor_float_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_capture(root)
            payload, _ = node.read_predecessor(root, 'continuation-prior', SHA)
            self.assertEqual(payload, PAYLOAD)

    def test_corruption_is_rejected_even_with_same_run_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            capture = write_capture(root)
            node.read_predecessor(root, 'continuation-prior', SHA)
            with capture.open('r+b') as stream:
                stream.seek(-1, 2)
                stream.write(b'\x01')
            with self.assertRaises(ValueError):
                node.read_predecessor(root, 'continuation-prior', SHA)

    def test_missing_or_unsafe_capture_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ('../escape', '/tmp/escape', 'HasUppercase', '', None):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    node.read_predecessor(tmp, name, SHA)
            with self.assertRaises((ValueError, OSError)):
                node.read_predecessor(tmp, 'missing', SHA)

    def test_capture_directory_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            capture = write_capture(root)
            (root / 'validation' / 'alias').symlink_to(capture.parent, target_is_directory=True)
            with self.assertRaises(ValueError):
                node.read_predecessor(root, 'alias', SHA)

    def test_changed_hook_does_not_allow_stale_cached_anchor(self):
        self.assertTrue(math.isnan(node.LTXLoadFloatContinuationAnchor.IS_CHANGED('same', SHA)))

    def test_fault_rejects_before_any_tensor_runtime_import(self):
        original = node.FAULT_ROOT
        try:
            with tempfile.TemporaryDirectory() as tmp:
                node.FAULT_ROOT = Path(tmp)
                (Path(tmp) / 'FAULT.json').write_text('{}')
                with self.assertRaisesRegex(RuntimeError, 'fault'):
                    node.LTXLoadFloatContinuationAnchor().load('continuation-prior', SHA)
                self.assertNotIn('torch', sys.modules)
                self.assertNotIn('folder_paths', sys.modules)
        finally:
            node.FAULT_ROOT = original

    def test_native_provider_schema_matches_graph(self):
        cls = node.LTXLoadFloatContinuationAnchor
        self.assertEqual(cls.INPUT_TYPES(), {'required': {
            'predecessor_run': ('STRING',), 'expected_sha256': ('STRING',)}})
        self.assertEqual(cls.RETURN_TYPES, ('IMAGE',))
        self.assertEqual(cls.FUNCTION, 'load')
        self.assertIs(node.NODE_CLASS_MAPPINGS[bound.PROVIDER_CLASS], cls)

    def test_first_graph_preserves_reference(self):
        got = bound.build_bound_chunk(0, 'continuation-first')
        old = bound.load_builder().build_chunk(0, 'continuation-first')
        self.assertEqual(got['graph'], old['graph'])
        self.assertIsNone(got['anchor_input'])

    def test_completed_graph_has_only_one_provider_delta(self):
        got = bound.build_bound_chunk(1, 'continuation-next', predecessor_run='continuation-prior',
                                      anchor_sha256=SHA)
        expected = bound.load_builder().build_chunk(1, 'continuation-next',
                    anchor_edge=[bound.PROVIDER_ID, 0], anchor_sha256=SHA)['graph']
        provider = got['graph'].pop(bound.PROVIDER_ID)
        self.assertEqual(got['graph'], expected)
        self.assertEqual(provider, {'class_type': bound.PROVIDER_CLASS, 'inputs': {
            'predecessor_run': 'continuation-prior', 'expected_sha256': SHA}})
        self.assertEqual(got['chunk']['new_video_frames'], 24)
        self.assertEqual(got['chunk']['delivery_frame_start'], 1)

    def test_provenance_does_not_claim_runtime_validation(self):
        got = bound.build_bound_chunk(1, 'continuation-next', predecessor_run='continuation-prior',
                                      anchor_sha256=SHA)
        self.assertTrue(got['anchor_input']['provider_implemented'])
        for key in ('payload_hash_verified', 'provider_native_tensor_qualified', 'predecessor_lineage_verified'):
            self.assertFalse(got['anchor_input'][key])
        self.assertFalse(got['ready_for_submission'])
        self.assertFalse(got['qualification']['gpu_execution'])
        self.assertFalse(got['chunk']['output_slicing_implemented'])
        self.assertFalse(got['audio']['modified'])
        for name, digest in got['implementation']['source_sha256'].items():
            self.assertEqual(digest, hashlib.sha256((SCRIPTS / name).read_bytes()).hexdigest())

    def test_invalid_binding_is_rejected(self):
        cases = [dict(chunk_index=0, run_name='continuation-A'),
                 dict(chunk_index=0, run_name='continuation-first', predecessor_run='prior'),
                 dict(chunk_index=1, run_name='continuation-next'),
                 dict(chunk_index=1, run_name='continuation-next', predecessor_run='../prior', anchor_sha256=SHA),
                 dict(chunk_index=1, run_name='continuation-next', predecessor_run='continuation-next', anchor_sha256=SHA),
                 dict(chunk_index=1, run_name='continuation-next', predecessor_run='prior', anchor_sha256='bad')]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                bound.build_bound_chunk(**case)

    def test_imports_and_ast_checks_do_not_import_native_libraries(self):
        for name in ('continuation_anchor_node.py', 'bind-continuation-anchor.py'):
            ast.parse((SCRIPTS / name).read_bytes())
        for name in ('torch', 'numpy', 'safetensors', 'folder_paths'):
            self.assertNotIn(name, sys.modules)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', type=Path,
                        default=SCRIPTS.parent / 'data/continuation-anchor-node-cpu-01.json')
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ProviderIntegrationTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    receipt = {
        'status': 'passed-stdlib-provider-integration-only' if result.wasSuccessful() else 'failed',
        'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
        'source_sha256': {name: hashlib.sha256((SCRIPTS / name).read_bytes()).hexdigest()
                          for name in ('test-continuation-anchor-node.py', 'continuation_anchor_node.py',
                                       'continuation_anchor_io.py', 'bind-continuation-anchor.py',
                                       'build-continuation-graph.py')},
        'torch_imported': 'torch' in sys.modules, 'gpu_requests': 0,
        'native_tensor_path_executed': False,
        'limitations': ['Synthetic captures only; no actual generated payload loaded',
                        'Torch frombuffer/reshape/clone path remains unqualified',
                        'No runtime deployment, inference, seam review, speed or endurance result'],
    }
    out = args.receipt
    with out.open('x') as stream:
        stream.write(json.dumps(receipt, indent=2) + '\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
