"""CPU fixtures exercise arbitrary-stage coverage and sealed-state refusals."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('pipeline_compare', Path(__file__).with_name('compare_pipeline_state.py'))
COMPARE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COMPARE)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def make_set(root, boundaries, spares=False):
    root.mkdir()
    stages = []
    for ordinal, (begin, end) in enumerate(zip(boundaries, boundaries[1:])):
        folder = root / str(ordinal)
        dump = folder / 'state'
        dump.mkdir(parents=True)
        buffers = {name[:-4]: struct.pack('<i', 7) for name in COMPARE.GLOBAL_ALL}
        buffers['streams'] = struct.pack('<f', 100 + end)
        buffers['next_token'] = struct.pack('<i', 37 if end == boundaries[-1] else 0)
        for layer in range(begin, end):
            buffers[f'blk.{layer}.gdn.state'] = struct.pack('<2f', layer + 0.5, layer + 1.5)
            buffers[f'blk.{layer}.attention'] = struct.pack('<f', layer + 2.5)
        if ordinal == 0:
            buffers['token_history'] = struct.pack('<2i', 6, 7)
            buffers['ple_metadata'] = struct.pack('<i', 12)
            buffers['embedding'] = struct.pack('<f', 1)
        if end == boundaries[-1]:
            buffers['logits'] = struct.pack('<2f', 1, 2)
        descriptors = [{'name': key, 'dtype': 'f32', 'shape': [len(value) // 4], 'bytes': len(value)}
                       for key, value in buffers.items()]
        inactive = []
        if spares and ordinal == 0:
            for layer in range(begin, end):
                name = f'blk.{layer}.gdn.state'
                inactive.append(name)
                buffers['alternate:' + name] = bytes(len(buffers[name]))
        launches = [{'op': 'gdn', 'inputs': [name], 'outputs': [f'blk.{layer}.attention', name]}
                    for layer in range(begin, end) for name in [f'blk.{layer}.gdn.state']]
        (folder / 'layout.json').write_text(json.dumps({'buffers': descriptors, 'launches': launches}))
        (folder / 'pipeline-stage.json').write_text(json.dumps({
            'schema': 'ownrt.pipeline-stage.v1', 'mode': 'target-only', 'speculation_enabled': False,
            'stage_id': ordinal, 'stage_count': len(boundaries) - 1, 'begin': begin, 'end': end,
            'first': ordinal == 0, 'final': end == boundaries[-1], 'boundaries': boundaries,
            'activation_dtype': 'F32', 'stream_bytes': 4,
            'inactive_alternate_banks': inactive}))
        payload, rows, hashes = bytearray(), ['GSQ_STATE_BUNDLE_V1'], {}
        for key, value in sorted(buffers.items()):
            hashes[key] = digest(value)
            physical = 'alternate-' + key[len('alternate:'):] if key.startswith('alternate:') else key
            rows.append(f'{physical}.bin\t{len(payload)}\t{len(value)}\t{digest(value)}')
            payload.extend(value)
        state = json.dumps({'history0': 6, 'history1': 7, 'buffers': hashes}).encode()
        index = ('\n'.join(rows) + '\n').encode()
        (dump / 'state.bundle').write_bytes(payload)
        (dump / 'state-index.tsv').write_bytes(index)
        (dump / 'state.json').write_bytes(state)
        (dump / 'state-seal.txt').write_text('\n'.join(['GSQ_STATE_SEAL_V1', str(len(payload)),
                                                     digest(payload), digest(index), digest(state)]) + '\n')
        stages.append({'id': ordinal, 'begin': begin, 'end': end,
                       'dump': f'{ordinal}/state', 'plan': f'{ordinal}/layout.json', 'metadata': f'{ordinal}/pipeline-stage.json'})
    manifest = {'schema': 'ownrt.pipeline-state-set.v1', 'mode': 'target-only', 'layer_count': boundaries[-1],
                'input_identity': {'model_sha256': 'a' * 64, 'prompt_token_sha256': 'b' * 64,
                                   'output_token_sha256': 'c' * 64, 'arithmetic': 'test-f32', 'position': 7},
                'stages': stages}
    path = root / 'set.json'
    path.write_text(json.dumps(manifest))
    return path


class StateComparisonTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.reference = make_set(self.root / 'pp2', [0, 2, 4])
        self.candidate = make_set(self.root / 'pp4', [0, 1, 2, 3, 4])

    def test_all_layer_state_survives_four_stage_repartition(self):
        result = COMPARE.compare(COMPARE.load_set(self.reference), COMPARE.load_set(self.candidate))
        self.assertTrue(result['passed'])
        self.assertIn('blk.3.gdn.state.bin', result['compared_source_keys'])
        self.assertEqual(len(result['candidate']['excluded']), 6)

    def test_duplicated_layer_range_refused(self):
        data = json.loads(self.candidate.read_text())
        data['stages'][1]['begin'] = 0
        self.candidate.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'partition|gaps/overlaps'):
            COMPARE.load_set(self.candidate)

    def test_only_declared_inactive_physical_spares_may_disappear_on_repartition(self):
        reference = make_set(self.root / 'banked2', [0, 2, 4], spares=True)
        candidate = make_set(self.root / 'banked4', [0, 1, 2, 3, 4], spares=True)
        result = COMPARE.compare(COMPARE.load_set(reference), COMPARE.load_set(candidate))
        self.assertTrue(result['passed'])
        self.assertIn('blk.1.gdn.state.bin', result['compared_source_keys'])
        self.assertTrue(any(row['source_key'] == 'alternate-blk.1.gdn.state.bin'
                            for row in result['reference']['excluded']))

    def test_shape_change_with_equal_byte_count_still_fails(self):
        layout = self.candidate.parent / '2/layout.json'
        data = json.loads(layout.read_text())
        next(b for b in data['buffers'] if b['name'] == 'blk.2.gdn.state')['shape'] = [1, 2]
        layout.write_text(json.dumps(data))
        result = COMPARE.compare(COMPARE.load_set(self.reference), COMPARE.load_set(self.candidate))
        self.assertFalse(result['passed'])
        self.assertEqual(result['errors'][0]['source_key'], 'blk.2.gdn.state.bin')
        self.assertIn('shape', result['errors'][0]['fields'])

    def test_layout_without_dtype_fails_closed(self):
        layout = self.candidate.parent / '0/layout.json'
        data = json.loads(layout.read_text())
        del data['buffers'][0]['dtype']
        layout.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'dtype or shape'):
            COMPARE.load_set(self.candidate)

    def test_claiming_absent_inactive_bank_is_rejected(self):
        meta = self.candidate.parent / '0/pipeline-stage.json'
        data = json.loads(meta.read_text())
        data['inactive_alternate_banks'] = ['blk.0.gdn.state']
        meta.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'alternate-bank inventory differs'):
            COMPARE.load_set(self.candidate)

    def test_speculative_state_cannot_use_inactive_bank_exception(self):
        meta = self.candidate.parent / '0/pipeline-stage.json'
        data = json.loads(meta.read_text())
        data['speculation_enabled'] = True
        meta.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'no-speculation metadata required'):
            COMPARE.load_set(self.candidate)

    def test_inactive_bank_declaration_requires_actual_temporal_producer(self):
        candidate = make_set(self.root / 'banked-no-producer', [0, 2, 4], spares=True)
        layout = candidate.parent / '0/layout.json'
        data = json.loads(layout.read_text())
        data['launches'] = []
        layout.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'registered temporal producer'):
            COMPARE.load_set(candidate)

    def test_corrupted_payload_refused(self):
        bundle = self.candidate.parent / '3/state/state.bundle'
        data = bytearray(bundle.read_bytes())
        data[-1] ^= 1
        bundle.write_bytes(data)
        with self.assertRaisesRegex(ValueError, 'buffer bytes differ'):
            COMPARE.load_set(self.candidate)

    def test_missing_persistent_buffer_fails_comparison(self):
        reference, candidate = COMPARE.load_set(self.reference), COMPARE.load_set(self.candidate)
        del candidate['canonical']['blk.2.gdn.state.bin']
        result = COMPARE.compare(reference, candidate)
        self.assertFalse(result['passed'])
        self.assertEqual(result['errors'][0]['source_key'], 'blk.2.gdn.state.bin')

    def test_legacy_mtp_oracle_cannot_be_promoted_to_target_only_proof(self):
        legacy = self.root / 'legacy.json'
        legacy.write_text(json.dumps({'state': {'rank0': {'position.bin': '0' * 64}}}))
        with self.assertRaises((ValueError, KeyError)):
            COMPARE.load_set(legacy)


if __name__ == '__main__':
    unittest.main()
