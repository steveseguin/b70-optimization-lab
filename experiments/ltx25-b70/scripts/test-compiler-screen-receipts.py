#!/usr/bin/env python3
"""CPU JSON fixture gates; never import the compiler node, Torch, or an endpoint."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
SOURCE = Path(__file__).with_name('run-compiler-screen.py')
spec = importlib.util.spec_from_file_location('compiler_client_cpu_test', SOURCE)
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)


def fixture(cold=True, mode='compiled'):
    identity = {'run_name': 'cpu-audit', 'block_index': 24,
        'server_identity_sha256': 'cpu-identity',
        'model_verification_sha256': '273ad9125c1cbe239e44ffaa29ce11a7eb8f89d252630de7ef8e6503a1c1cf0f',
        'passed': True, 'failures': []}
    request = {**identity, 'schema': 'ltx.compiler-request.v1', 'mode': mode,
        'adapter_sha256': '79ba260785e16d7e646bfe79b0816e99a8fab6db557a60408c35bd7675121577',
        'compiler_options': {'compile_threads': 1, 'emulate_precision_casts': True,
            'eager_numerics.division_rounding': True, 'triton.cudagraphs': False,
            'max_autotune': False, 'max_autotune_gemm': False},
        'qualified_stage_count': 0 if cold else 2,
        'original_id': 100, 'candidate_id': None if mode == 'eager' else 200}
    # Synthetic metadata exercises validator totals, not actual model architecture.
    records = [{'name': str(i), 'bytes': 1, 'dtype': 'torch.bfloat16',
                'device': 'xpu:1'} for i in range(84)]
    records[0]['bytes'] = 773349760 - 83
    calls = []
    for number in range(1, 12) if mode == 'compiled' else ():
        row = {**identity, 'schema': 'ltx.compiler-block-call.v1', 'call': number,
            'stage_signature': [
                {'shape': [1, 64 if number <= 8 else 256, 4096],
                 'dtype': 'torch.bfloat16', 'device': 'xpu:1'},
                {'shape': [1, 26, 2048], 'dtype': 'torch.bfloat16', 'device': 'xpu:1'}],
            'counter_delta': {'stats': {'unique_graphs': 1 if cold and number < 9 else 2}},
            'stage_check': cold and number in (1, 9),
            'qualified_stage_count': 1 if cold and number < 9 else 2,
            'state_census': {'records': records, 'bytes': 773349760,
                             'block_index': 24, 'route_device': 'xpu:1'},
            'eager_vs_compiled': [{'finite': True, 'bitwise_equal': True} for _ in range(2)],
            'compiled_vs_repeat': [{'finite': True, 'bitwise_equal': True} for _ in range(2)]}
        calls.append(row)
    return request, calls


class ReceiptTests(unittest.TestCase):
    def validate(self, data, qualified):
        request, calls = data
        with tempfile.TemporaryDirectory(prefix='ltx-compiler-cpu-') as tmp:
            root = Path(tmp)
            folder = root / 'compiler-cpu-audit'
            folder.mkdir()
            (folder / 'request.json').write_text(json.dumps(request))
            for i, row in enumerate(calls, 1):
                (folder / f'call-{i:02d}.json').write_text(json.dumps(row))
            return client.validate_compiler_receipts(root, 'cpu-audit', request['mode'],
                                                     'cpu-identity', qualified)

    def test_valid_cold_warm_eager_restored(self):
        for cold, mode in [(True, 'compiled'), (False, 'compiled'),
                           (True, 'eager'), (False, 'restored')]:
            with self.subTest(cold=cold, mode=mode):
                self.validate(fixture(cold, mode), 0 if cold else 2)

    def test_schedule_qualification(self):
        rows = client.schedule()
        self.assertEqual([r['qualified_before'] for r in rows], [0, 0, 0, 2, 2, 2, 2, 2, 2])
        self.assertEqual(len(set(r['run'] for r in rows)), 9)

    def test_cold_cannot_skip_qualification(self):
        with self.assertRaises(RuntimeError):
            self.validate(fixture(False), 0)

    def test_warm_cannot_claim_one_stage(self):
        data = fixture(False)
        data[0]['qualified_stage_count'] = 1
        with self.assertRaises(RuntimeError):
            self.validate(data, 2)

    def test_missing_or_wrong_stage_check(self):
        for index in (0, 8):
            data = fixture()
            data[1][index]['stage_check'] = False
            with self.subTest(index=index), self.assertRaises(RuntimeError):
                self.validate(data, 0)

    def test_nonfinite_and_unequal_rejected(self):
        for field in ('eager_vs_compiled', 'compiled_vs_repeat'):
            for bit in ('finite', 'bitwise_equal'):
                data = fixture()
                data[1][8][field][1][bit] = False
                with self.subTest(field=field, bit=bit), self.assertRaises(RuntimeError):
                    self.validate(data, 0)

    def test_counter_failures(self):
        for group, key, value in [('graph_break', 'reason', 1),
                ('unimplemented', 'reason', 1), ('stats', 'unique_graphs', 0),
                ('stats', 'unique_graphs', 3)]:
            data = fixture()
            data[1][0]['counter_delta'][group] = {key: value}
            with self.subTest(group=group, value=value), self.assertRaises(RuntimeError):
                self.validate(data, 0)

    def test_bad_receipt_identity_device_and_census(self):
        for kind in ('identity', 'device', 'census', 'count'):
            data = fixture()
            if kind == 'identity':
                data[1][0]['server_identity_sha256'] = 'another-process'
            elif kind == 'device':
                data[1][8]['stage_signature'][0]['device'] = 'cpu'
            elif kind == 'census':
                data[1][0]['state_census']['records'][0]['bytes'] -= 1
            else:
                data[1].pop()
            with self.subTest(kind=kind), self.assertRaises(RuntimeError):
                self.validate(data, 0)

    def test_owner_ids_and_continuity(self):
        eager = fixture(True, 'eager')[0]
        candidate = fixture()[0]
        client.validate_owner_continuity(eager, candidate)
        client.validate_owner_continuity(candidate, fixture(False, 'restored')[0])
        for field in ('original_id', 'candidate_id'):
            changed = copy.deepcopy(candidate)
            changed[field] += 1
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                client.validate_owner_continuity(candidate, changed)
        for invalid in (None, True, -1, 100):
            data = fixture()
            data[0]['candidate_id'] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(RuntimeError):
                self.validate(data, 0)

    def test_no_torch_import(self):
        self.assertNotIn('torch', sys.modules)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(ReceiptTests))
    print(json.dumps({'status': 'passed' if result.wasSuccessful() else 'failed',
        'tests': result.testsRun, 'client_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'driver_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'scope': 'Synthetic JSON CPU validation only; no actual compiler/model/GPU qualification',
        'torch_imported': 'torch' in sys.modules}, sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)
