#!/usr/bin/env python3
"""Focused stdlib-only positive/negative gates for packet04 RMS receipts."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
CLIENT = Path(__file__).with_name('run-compiler-screen-v3.py')
spec = importlib.util.spec_from_file_location('compiler_v3_receipt_tests', CLIENT)
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)


def row(number):
    replacements = []
    for index in range(15):
        weighted = index < 12
        width = 4096 if weighted else 2048
        replacements.append({'node': f'rms_{index}', 'normalized_shape': [width],
            'weighted': weighted, 'eps': 1e-5 if weighted else 1e-6,
            'input': {'shape': [1, 64, width], 'stride': [64 * width, width, 1],
                      'dtype': 'torch.bfloat16', 'device': 'xpu:1', 'contiguous': True},
            'weight': {'shape': [width], 'stride': [1], 'dtype': 'torch.bfloat16',
                       'device': 'xpu:1', 'contiguous': True} if weighted else None})
    return {'schema': 'ltx25.native-rms-fx-rewrite.v1', 'status': 'compiled-native-rms-boundary',
            'graph': number, 'source_sha256': client.NATIVE_RMS_BACKEND_SHA,
            'options': dict(client.NATIVE_RMS_OPTIONS), 'replacements': replacements}


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ltx-v3-receipts-')
        self.addCleanup(self.temp.cleanup)
        self.server = Path(self.temp.name)
        self.directory = self.server / 'native-rms-graphs'
        self.directory.mkdir()
        for number in (1, 2):
            self.write(number, row(number))
            for phase in ('before', 'after'):
                (self.directory / f'graph-{number:03d}-{phase}.py').write_text('# fixture only\n')

    def write(self, number, value):
        (self.directory / f'graph-{number:03d}.json').write_text(json.dumps(value))

    def reject(self, value):
        self.write(1, value)
        with self.assertRaises((RuntimeError, KeyError, TypeError, ValueError)):
            client.validate_native_rms_receipts(self.server)

    def test_valid_two_graph_receipts(self):
        result = client.validate_native_rms_receipts(self.server)
        self.assertEqual([r['graph'] for r in result], [1, 2])
        self.assertTrue(all(set(r['files']) == {'receipt', 'before', 'after'} for r in result))

    def test_missing_graph_rejected(self):
        (self.directory / 'graph-002.json').unlink()
        with self.assertRaises(RuntimeError):
            client.validate_native_rms_receipts(self.server)

    def test_extra_graph_rejected(self):
        self.write(3, row(3))
        with self.assertRaises(RuntimeError):
            client.validate_native_rms_receipts(self.server)

    def test_bad_status_schema_or_index_rejected(self):
        for key, value in [('status', 'failed'), ('schema', 'wrong'), ('graph', 2), ('graph', True)]:
            with self.subTest(key=key, value=value):
                changed = row(1)
                changed[key] = value
                self.reject(changed)

    def test_wrong_backend_rejected(self):
        changed = row(1)
        changed['source_sha256'] = '0' * 64
        self.reject(changed)

    def test_changed_options_rejected(self):
        changed = row(1)
        changed['options']['emulate_precision_casts'] = False
        self.reject(changed)

    def test_error_on_success_row_rejected(self):
        changed = row(1)
        changed['error'] = 'failure'
        self.reject(changed)

    def test_missing_or_duplicate_replacement_rejected(self):
        changed = row(1)
        changed['replacements'].pop()
        self.reject(changed)
        changed = row(1)
        changed['replacements'][-1] = copy.deepcopy(changed['replacements'][0])
        self.reject(changed)

    def test_changed_input_precision_device_or_layout_rejected(self):
        for key, value in [('dtype', 'torch.float16'), ('device', 'xpu:0'), ('contiguous', False)]:
            with self.subTest(key=key):
                changed = row(1)
                changed['replacements'][0]['input'][key] = value
                self.reject(changed)

    def test_changed_epsilon_weight_or_mix_rejected(self):
        changed = row(1)
        changed['replacements'][0]['eps'] = 1e-6
        self.reject(changed)
        changed = row(1)
        changed['replacements'][0]['weight']['shape'] = [2048]
        self.reject(changed)
        changed = row(1)
        changed['replacements'][0].update(weighted=False, weight=None, eps=1e-6)
        self.reject(changed)

    def test_missing_graph_source_rejected(self):
        (self.directory / 'graph-001-after.py').unlink()
        with self.assertRaises((RuntimeError, FileNotFoundError)):
            client.validate_native_rms_receipts(self.server)

    def test_symlink_receipt_rejected(self):
        path = self.directory / 'graph-001.json'
        moved = self.server / 'elsewhere.json'
        path.rename(moved)
        path.symlink_to(moved)
        with self.assertRaises(RuntimeError):
            client.validate_native_rms_receipts(self.server)


if __name__ == '__main__':
    unittest.main()
