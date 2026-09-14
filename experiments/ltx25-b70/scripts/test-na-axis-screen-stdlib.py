#!/usr/bin/env python3
"""Synthetic decoder-receipt/graph/admission tests; stdlib only, no endpoint."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
LANE = Path(__file__).resolve().parents[1]
SOURCE = LANE / 'scripts/run-na-axis-screen.py'
spec = importlib.util.spec_from_file_location('axis_client_cpu', SOURCE)
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)
validator = client.validators
PACKET = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-na-axis-09')
decoder = PACKET / 'source/comfy/ldm/lightricks/vae/na_diffusion_decoder.py'
sd = PACKET / 'source/comfy/sd.py'
config = validator.checkpoint_config('/mnt/fast-ai/llm-models/LTX-2.5-baseline/vae/ltx-2.5-video-vae-bf16.safetensors')
contract = validator.source_contract(decoder.read_text(), sd.read_text(), config)
sources = client.source_identity(PACKET)


def fixture(mode='original'):
    calls = validator.expected_calls(contract, [1, 128, 4, 8, 8])
    for row in calls:
        row['mode'] = mode
    return {'schema': 'ltx.na-axis-decode.v1', 'status': 'passed-decode-route', 'run_name': 'cpu-r01-boat',
        'mode': mode, 'source_identity': sources,
        'identity': {'server_identity_sha256': 'test-identity', 'model_verification_sha256': validator.MODEL_SHA},
        'owners': {'vae': 10, 'patcher': 20, 'first_stage_model': 30, 'decoder': 40},
        'input': {'nested': False, 'shape': [1, 128, 4, 8, 8], 'dtype': 'torch.float32', 'device': 'cpu'},
        'output': {'nested': False, 'shape': [25, 256, 256, 3], 'dtype': 'torch.float32', 'device': 'cpu'},
        'decoder_config': copy.deepcopy(config), 'started_monotonic_ns': 1, 'finished_monotonic_ns': 2,
        'context_clear_after': True, 'quality_qualified': False, 'native_sequence_qualified': False,
        'route': {'schema': 'ltx.na-axis-route.v1', 'status': 'passed-route-coverage', 'run_name': 'cpu-r01-boat',
            'mode': mode, 'thread_id': 123, 'original_sha256': validator.ORIGINAL_SHA,
            'candidate_sha256': validator.CANDIDATE_SHA, 'calls': calls, 'scope_reset': True}}


def validate(row, previous=None):
    return validator.validate_receipt(row, run_name='cpu-r01-boat', mode=row['mode'],
        identity_sha='test-identity', sources=sources, contract=contract, previous=previous)


class Tests(unittest.TestCase):
    def test_source_derived_stages(self):
        expected = [(6, 8, 8, 32)] * 4 + [(6, 16, 16, 16)] * 6 + [(11, 16, 16, 8)] * 4 + \
                   [(21, 32, 32, 8)] * 2 + [(25, 64, 64, 4)] * 8
        calls = validator.expected_calls(contract, [1, 128, 4, 8, 8], config)
        self.assertEqual([tuple(row['inputs'][0]['shape'][1:5]) for row in calls], expected)
        self.assertTrue(all(row['inputs'][0]['shape'][-1] == 64 for row in calls))

    def test_config_metadata_accepted_numerical_override_rejected(self):
        self.assertIn('resampler_kind', config['decoder'])
        validator.expected_calls(contract, [1, 128, 4, 8, 8], config)
        changed = copy.deepcopy(config)
        changed['decoder']['head_dim'] = 32
        with self.assertRaises(RuntimeError):
            validator.source_contract(decoder.read_text(), sd.read_text(), changed)
        with self.assertRaises(RuntimeError):
            validator.expected_calls(contract, [1, 128, 4, 8, 8], changed)

    def test_valid_original_cache_original(self):
        original = fixture()
        self.assertEqual(validate(original)['call_count'], 24)
        validate(fixture('axis-cache'), original)
        validate(fixture(), original)

    def test_cannot_discover_from_cache(self):
        with self.assertRaises(RuntimeError):
            validate(fixture('axis-cache'))

    def test_sequence_mutations(self):
        for kind in ('missing', 'order', 'kernel', 'causal', 'scale', 'shape', 'dtype', 'device', 'mode', 'output', 'status'):
            row = fixture()
            call = row['route']['calls'][4]
            if kind == 'missing':
                row['route']['calls'].pop()
            elif kind == 'order':
                row['route']['calls'][0], row['route']['calls'][4] = row['route']['calls'][4], row['route']['calls'][0]
            elif kind == 'kernel':
                call['kernel_size'] = [3, 5, 5]
            elif kind == 'causal':
                call['is_causal'] = None
            elif kind == 'scale':
                call['scale'] = 0.125
            elif kind == 'shape':
                call['inputs'][0]['shape'][1] -= 1
            elif kind == 'dtype':
                call['inputs'][1]['dtype'] = 'torch.float32'
            elif kind == 'device':
                call['inputs'][2]['device'] = 'xpu:2'
            elif kind == 'mode':
                call['mode'] = 'axis-cache'
            elif kind == 'output':
                call['output']['shape'][-1] = 32
            else:
                call['status'] = 'started'
            with self.subTest(kind=kind), self.assertRaises(RuntimeError):
                validate(row)

    def test_owner_context_and_source_mutations(self):
        for kind in ('owner', 'thread', 'context', 'reset', 'source', 'identity'):
            row, old = fixture(), fixture()
            if kind == 'owner':
                row['owners']['decoder'] = 44
            elif kind == 'thread':
                row['route']['thread_id'] = 124
            elif kind == 'context':
                row['context_clear_after'] = False
            elif kind == 'reset':
                row['route']['scope_reset'] = False
            elif kind == 'source':
                row['source_identity'] = {**sources, 'node_sha256': 'changed'}
            else:
                row['identity']['server_identity_sha256'] = 'another-process'
            with self.subTest(kind=kind), self.assertRaises(RuntimeError):
                validate(row, old)

    def test_started_result_binding(self):
        row = fixture()
        started = copy.deepcopy(row)
        started.update(status='started', route=None)
        validator.validate_started(started, row)
        started['owners']['vae'] = 11
        with self.assertRaises(RuntimeError):
            validator.validate_started(started, row)

    def test_schedule_and_graph_scope(self):
        rows = client.schedule('na-axis-screen-01')
        self.assertEqual(len(rows), 11)
        self.assertEqual([row['mode'] for row in rows[:2]], ['bare', 'bare'])
        self.assertEqual([row['mode'] for row in rows[2:]], ['original', 'axis-cache', 'original'] * 3)
        base = json.loads((LANE / 'data/speed-resident-split-api.json').read_text())
        bare = client.expected_graph(base, 'bare')
        for mode in ('original', 'axis-cache'):
            graph = client.expected_graph(base, mode)
            self.assertNotIn('422', graph)
            graph['374'] = copy.deepcopy(bare['374'])
            self.assertEqual(graph, bare)
        with self.assertRaises(RuntimeError):
            client.schedule('../unsafe')

    def test_numbered_retention_ownership(self):
        campaign = 'na-axis-screen-01'
        runs = {row['run'] for row in client.schedule(campaign)}
        with tempfile.TemporaryDirectory(prefix='na-axis-retention-cpu-') as tmp:
            root = Path(tmp)
            for run in runs:
                path = root / 'output/validation' / run / 'tensors.safetensors'
                path.parent.mkdir(parents=True)
                path.write_bytes(b'CPU fixture, not a real archive')
                record = client.retention.inventory(root, campaign, runs, run, path.relative_to(root))
                with self.assertRaises(RuntimeError):
                    client.retention.delete_owned(root, campaign, runs, record, parity_passed=False, receipts=root / 'deletions.jsonl')
                self.assertTrue(path.exists())
                client.retention.delete_owned(root, campaign, runs, record, parity_passed=True, receipts=root / 'deletions.jsonl')
                self.assertFalse(path.exists())

    def test_timing_pair_direction(self):
        rows = client.schedule('cpu')
        for row in rows:
            row.update(status='passed', preview_ready_seconds=5.0 if row['mode'] == 'axis-cache' else 6.0,
                       decoder_node_seconds=0.4 if row['mode'] == 'axis-cache' else 0.6)
        result = client.paired_results(rows)
        self.assertEqual(result['paired_samples'], 3)
        self.assertEqual(result['median_preview_delta'], -1.0)

    def test_stdlib_only(self):
        self.assertNotIn('torch', sys.modules)

    def test_public_none_normalization_from_actual_cpu_route(self):
        evidence = json.loads((LANE / 'data/na-axis-router-cpu-01/receipt.json').read_text())
        observed = evidence['example_receipts'][0]['calls'][0]['is_causal']
        self.assertEqual(observed, [False, False, False])
        self.assertTrue(all(call['is_causal'] == observed for call in validator.expected_calls(contract, [1, 128, 4, 8, 8])))

    def test_object_info_admission(self):
        expected = {'LTXNAAxisDecode': {'input': {'required': {
            'samples': ['LATENT', {'tooltip': 'The latent to be decoded.'}],
            'vae': ['VAE', {'tooltip': 'The VAE model used for decoding the latent.'}],
            'mode': [['original', 'axis-cache']],
            'run_name': ['STRING', {'default': 'assign-unique-request-name'}]}},
            'output': ['IMAGE'], 'output_is_list': [False], 'is_input_list': False,
            'output_node': False, 'name': 'LTXNAAxisDecode', 'category': 'lab/validation',
            'python_module': 'custom_nodes.ltx_na_axis_decode_lab'}}
        client.validate_node_info(expected)
        with self.assertRaises(RuntimeError):
            client.validate_node_info({})
        expected['LTXNAAxisDecode']['output'] = ['LATENT']
        with self.assertRaises(RuntimeError):
            client.validate_node_info(expected)

    def test_bool_cannot_impersonate_shape_or_scale(self):
        for kind in ('shape', 'scale'):
            row = fixture()
            if kind == 'shape':
                row['route']['calls'][0]['inputs'][0]['shape'][0] = True
            else:
                row['route']['calls'][0]['scale'] = True
            with self.subTest(kind=kind), self.assertRaises(RuntimeError):
                validate(row)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    report = {'status': 'passed' if result.wasSuccessful() else 'failed', 'tests': result.testsRun,
        'client_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'validator_sha256': hashlib.sha256((LANE / 'scripts/ltx_na_axis_receipts.py').read_bytes()).hexdigest(),
        'driver_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'checkpoint_header_sha256': validator.HEADER_SHA, 'torch_imported': 'torch' in sys.modules,
        'native_requests': 0, 'scope': 'Synthetic receipts plus actual pinned source/config; no native decoder qualification'}
    print(json.dumps(report, sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)
