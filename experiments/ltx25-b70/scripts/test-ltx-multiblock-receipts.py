#!/usr/bin/env python3
"""Synthetic stdlib receipt contracts; no native runtime imports or requests."""
import copy
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest
import ltx_multiblock_receipts as receipts

IDENTITY = 'a' * 64
RUN = 'synthetic-multiblock'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True))


def metadata(shape, device):
    strides = [math.prod(shape[i + 1:]) for i in range(len(shape))]
    return {'shape': shape, 'stride': strides, 'dtype': 'torch.bfloat16', 'device': device}


def graph(number, device):
    tokens = 64 if number == 1 else 256
    rms = []
    for n in range(15):
        weighted = n < 12
        rms.append({'node': f'rms{n}', 'normalized_shape': [4096], 'weighted': weighted,
                    'eps': 1e-5 if weighted else 1e-6,
                    'input': {**metadata([1, tokens, 4096], device), 'contiguous': True},
                    'weight': {**metadata([4096], device), 'contiguous': True} if weighted else None})
    activations = []
    shapes = [('sigmoid', [1, tokens, 32])] * 3 + [('sigmoid', [1, 26, 32])] * 3
    shapes += [('gelu', [1, tokens, 16384]), ('gelu', [1, 26, 8192])]
    for n, (kind, shape) in enumerate(shapes):
        row = {'node': f'act{n}', 'kind': kind, 'input': {**metadata(shape, device), 'contiguous': True}}
        if kind == 'gelu':
            row['approximate'] = 'tanh'
        activations.append(row)
    return {'schema': 'ltx25.native-activations-fx-rewrite.v1',
            'status': 'compiled-native-activations-boundary', 'graph': number,
            'source_sha256': receipts.NATIVE_ACTIVATIONS_BACKEND_SHA,
            'dependency_sha256': receipts.NATIVE_RMS_BACKEND_SHA, 'expected_count': 15,
            'expected_activation_counts': {'sigmoid': 6, 'gelu': 2},
            'options': receipts.NATIVE_RMS_OPTIONS, 'replacements': rms,
            'activation_replacements': activations}


def make_fixture(root, mode='compiled', selection='single24', qualified=0):
    indices = receipts.SELECTIONS[selection]
    directory = root / ('compiler-' + RUN)
    identity = {'run_name': RUN, 'selection': selection, 'server_identity_sha256': IDENTITY,
                'model_verification_sha256': receipts.MODEL_SHA, 'passed': True, 'failures': []}
    q = {str(i): qualified for i in indices}
    request = {'schema': 'ltx.multiblock-request.v1', **identity, 'mode': mode,
               'block_indices': list(indices), 'extension_sha256s': receipts.EXTENSIONS,
               'compiler_options': receipts.NATIVE_RMS_OPTIONS,
               'dynamo_limits': {'recompile_limit': 8, 'accumulated_recompile_limit': 256},
               'qualified_before': q, 'qualified_stage_counts': q,
               'original_id': 123, 'candidate_id': None if mode == 'original' and qualified == 0 else 124,
               'retained_candidate_count': 0 if mode == 'original' and qualified == 0 else 1}
    write(directory / 'request.json', request)
    if mode != 'compiled':
        return
    for index in indices:
        device = f'xpu:{0 if index < 21 else 1}'
        graphdir = root / ('native-multiblock-' + selection) / f'block-{index:02d}'
        hashes = []
        for n in (1, 2):
            path = graphdir / f'graph-{n:03d}.json'
            write(path, graph(n, device))
            files = {'receipt': receipts.sha(path)}
            for phase in ('before', 'after'):
                source = graphdir / f'graph-{n:03d}-{phase}.py'
                source.write_text(f'# Synthetic {selection} block {index}, stage {n}, {phase}\n')
                files[phase] = receipts.sha(source)
            hashes.append({'graph': n, 'files': files})
        for n in range(1, 12):
            shapes = [[1, 64 if n <= 8 else 256, 4096], [1, 26, 2048]]
            new_stage = qualified == 0 and n in (1, 9)
            count = 1 if qualified == 0 and n <= 8 else 2
            row = {'schema': 'ltx.multiblock-call.v1', **identity, 'block_index': index,
                   'call': n, 'stage_signature': [metadata(s, device) for s in shapes],
                   'stage_check': new_stage, 'qualified_stage_count': count,
                   'counter_delta': {'stats': {'unique_graphs': int(new_stage)}}, 'state_census': None}
            if n == 1:
                records = []
                for r in range(84):
                    size = 1 if r < 83 else 773349760 // 2 - 83
                    records.append({'name': f'parameter{r}', 'kind': 'parameter', 'tensor_id': 1000 + r,
                                    'bytes': 2 * size, **metadata([size], device)})
                row['state_census'] = {'records': records, 'bytes': 773349760, 'block_id': 456 + index,
                    'diffusion_id': 789, 'owner_id': 789 if index < 21 else 790,
                    'container_id': 791 if index < 21 else 792,
                    'registration': '_ltx_primary_blocks' if index < 21 else 'blocks',
                    'slot': index if index < 21 else index - 21, 'block_index': index, 'route_device': device}
            if new_stage:
                outputs = [{'output': name, 'finite': True, 'metadata_equal': True, 'bitwise_equal': True,
                            'unequal_bytes': 0, 'expected_sha256': 'b' * 64, 'actual_sha256': 'b' * 64,
                            'expected': metadata(shape, device), **metadata(shape, device)}
                           for name, shape in zip(('video', 'audio'), shapes)]
                row['eager_vs_compiled'] = outputs
                row['compiled_vs_repeat'] = copy.deepcopy(outputs)
            if new_stage or n == 11:
                row['native_graphs'] = hashes[:count]
            write(directory / f'block-{index:02d}' / f'call-{n:02d}.json', row)


class Contracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.selection, self.mode, self.qualified = 'single24', 'compiled', 0
        make_fixture(self.root)

    def validate(self):
        return receipts.validate_compiler_receipts(self.root, RUN, self.mode, self.selection, IDENTITY, self.qualified)

    def change(self, relative, mutate):
        path = self.root / relative
        row = json.loads(path.read_text())
        mutate(row)
        write(path, row)

    def call_change(self, mutate, number=1):
        self.change(f'compiler-{RUN}/block-24/call-{number:02d}.json', mutate)

    def request_change(self, mutate):
        self.change(f'compiler-{RUN}/request.json', mutate)

    def reject(self):
        with self.assertRaises((ValueError, OSError, KeyError, TypeError)):
            self.validate()

    def test_valid_cold(self):
        result = self.validate()
        self.assertEqual(set(result['blocks']), {'24'})
        self.assertEqual(len(result['blocks']['24']['calls']), 11)

    def test_valid_all_selections_and_modes(self):
        for selection in receipts.SELECTIONS:
            for mode, qualified in [('compiled', 0), ('compiled', 2), ('original', 0), ('original', 2), ('restored', 2)]:
                with self.subTest(selection=selection, mode=mode, qualified=qualified), tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    make_fixture(root, mode, selection, qualified)
                    result = receipts.validate_compiler_receipts(root, RUN, mode, selection, IDENTITY, qualified)
                    self.assertEqual(len(result['blocks']), len(receipts.SELECTIONS[selection]) if mode == 'compiled' else 0)

    def test_forged_pass_missing_call(self):
        (self.root / f'compiler-{RUN}/block-24/call-11.json').unlink()
        self.reject()

    def test_swapped_block(self):
        self.call_change(lambda r: r.update(block_index=23))
        self.reject()

    def test_swapped_selection(self):
        self.call_change(lambda r: r.update(selection='all48'))
        self.reject()

    def test_swapped_device(self):
        self.call_change(lambda r: r['stage_signature'][0].update(device='xpu:0'))
        self.reject()

    def test_warm_new_stage_mismatch(self):
        self.call_change(lambda r: r.update(stage_check=True), 2)
        self.reject()

    def test_cold_fallback_zero_graphs(self):
        self.call_change(lambda r: r['counter_delta']['stats'].update(unique_graphs=0))
        self.reject()

    def test_warm_recompile(self):
        self.call_change(lambda r: r['counter_delta']['stats'].update(unique_graphs=1), 2)
        self.reject()

    def test_graph_break(self):
        self.call_change(lambda r: r['counter_delta'].update(graph_break={'break': 1}))
        self.reject()

    def test_graph_source_drift(self):
        path = self.root / 'native-multiblock-single24/block-24/graph-001-before.py'
        path.write_text('# changed\n')
        self.reject()

    def test_graph_receipt_drift(self):
        self.change('native-multiblock-single24/block-24/graph-001.json', lambda r: r.update(extra='drift'))
        self.reject()

    def test_wrong_operation_census(self):
        self.change('native-multiblock-single24/block-24/graph-001.json', lambda r: r['activation_replacements'].pop())
        self.reject()

    def test_symlink_call(self):
        path = self.root / f'compiler-{RUN}/block-24/call-02.json'
        data = path.read_text()
        target = self.root / 'elsewhere.json'
        target.write_text(data)
        path.unlink()
        path.symlink_to(target)
        self.reject()

    def test_cross_block_graph_symlink(self):
        root = self.root / 'native-multiblock-single24'
        directory = root / 'block-24'
        target = self.root / 'foreign-block'
        directory.rename(target)
        directory.symlink_to(target, target_is_directory=True)
        self.reject()

    def test_forged_parity_flag(self):
        self.call_change(lambda r: r['eager_vs_compiled'][0].update(actual_sha256='c' * 64))
        self.reject()

    def test_unequal_bytes(self):
        self.call_change(lambda r: r['compiled_vs_repeat'][0].update(unequal_bytes=1))
        self.reject()

    def test_state_census_size(self):
        self.call_change(lambda r: r['state_census']['records'][0].update(bytes=4))
        self.reject()

    def test_bad_owner(self):
        self.request_change(lambda r: r.update(candidate_id=True))
        self.reject()

    def test_bool_qualification(self):
        self.request_change(lambda r: r['qualified_before'].update({'24': False}))
        self.reject()

    def test_changed_limits(self):
        self.request_change(lambda r: r['dynamo_limits'].update(recompile_limit=100))
        self.reject()

    def test_bool_compiler_option(self):
        self.request_change(lambda r: r['compiler_options'].update(compile_threads=True))
        self.reject()

    def test_changed_pin(self):
        self.request_change(lambda r: r['extension_sha256s'].update({'ltx_multiblock_compile.py': '0' * 64}))
        self.reject()

    def test_original_rejects_block_receipts(self):
        self.mode = 'original'
        self.request_change(lambda r: r.update(mode='original', candidate_id=None))
        self.reject()

    def test_incomplete_final_stage(self):
        self.call_change(lambda r: r.update(qualified_stage_count=1), 11)
        self.reject()

    def test_invalid_run_name(self):
        with self.assertRaises(ValueError):
            receipts.validate_compiler_receipts(self.root, 'has_underscore', 'compiled', 'single24', IDENTITY, 0)

    def test_extra_graph(self):
        write(self.root / 'native-multiblock-single24/block-24/graph-003.json', {})
        self.reject()


if __name__ == '__main__':
    unittest.main(verbosity=2)
