"""CPU-only arithmetic, metadata, identity and fail-closed tests."""
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import memory_plan as m


class ArithmeticTests(unittest.TestCase):
    def test_one_owner_no_double_counting(self):
        self.assertEqual(m.host_phase(10, [100, 200], [4, 5], [7, 0], [8, 9], 11, 12, 13), 379)

    def test_unknown_is_not_zero(self):
        with self.assertRaises(ValueError):
            m.host_phase(0, [100], [None], [0], [0], 0, 0, 0)

    def test_negative_refused(self):
        with self.assertRaises(ValueError):
            m.host_phase(-1, [0], [0], [0], [0], 0, 0, 0)

    def test_different_rank_vector_lengths_refused(self):
        with self.assertRaises(ValueError):
            m.host_phase(0, [1, 2], [0], [0], [0], 0, 0, 0)

    def gate(self, host=m.HOST_LIMIT, vram=28*m.GIB, available=50*m.GIB, growth=18*m.GIB):
        return m.gate_arithmetic({'construction': host, 'serve': host-1},
                                 {'construction': [vram], 'serve': [vram-1]},
                                 [32*m.GIB], available, growth)

    def test_exact_limits_pass(self):
        result = self.gate()
        self.assertEqual(result['refusal_reasons'], [])
        self.assertEqual(result['host_peak_bytes'], 90_000_000_000)
        self.assertEqual(result['vram_reserve_bytes_per_rank'], [4*m.GIB])

    def test_decimal_gb_ceiling_one_byte(self):
        self.assertTrue(self.gate(host=m.HOST_LIMIT+1)['refusal_reasons'])

    def test_vram_one_byte_below_reserve(self):
        self.assertTrue(self.gate(vram=28*m.GIB+1)['refusal_reasons'])

    def test_posthash_one_byte_short(self):
        self.assertTrue(self.gate(available=50*m.GIB-1)['refusal_reasons'])

    def test_peak_is_max_not_sum(self):
        self.assertEqual(self.gate()['host_peak_bytes'], m.HOST_LIMIT)

    def test_unknown_phase_refuses(self):
        result = m.gate_arithmetic({'load': None}, {'load': [None]}, [None])
        self.assertIsNone(result['host_peak_bytes'])
        self.assertEqual(len(result['refusal_reasons']), 3)

    def test_known_phase_never_masks_unknown(self):
        result = m.gate_arithmetic({'load': None, 'serve': 1}, {'load': [None], 'serve': [1]}, [32*m.GIB])
        self.assertIsNone(result['vram_peak_bytes_per_rank'][0])

    def test_generic_budget_overshoots_one_parameter(self):
        parameters = [{'name': 'a', 'bytes': 40}, {'name': 'b', 'bytes': 80}, {'name': 'c', 'bytes': 20}]
        selected, size = m.select_offload(parameters, 41)
        self.assertEqual(size, 120)
        self.assertEqual([p['name'] for p in selected], ['a', 'b'])

    def test_generic_exact_budget_stops(self):
        self.assertEqual(m.select_offload([{'bytes': 40}, {'bytes': 80}], 40)[1], 40)

    def test_zero_budget_selects_nothing(self):
        self.assertEqual(m.select_offload([{'bytes': 80}], 0), ([], 0))

    def test_screen1_actual_registration_budget(self):
        params = []
        for layer in range(48):
            if layer == 1:
                params.append({'bytes': 12_800_061_440})
            params.extend([{'bytes': 419_430_400}, {'bytes': 209_715_200}])
        _, size = m.select_offload(params, int(16.25*m.GIB))
        self.assertEqual(size, 17_623_511_040)
        self.assertEqual(size*4 + 20*m.GIB + 256*m.MIB, 92_237_316_096)

    def test_early_memavailable_threshold(self):
        self.assertTrue(m.should_stop({'mem_available_bytes': 32*m.GIB, 'accounted_pressure_bytes': 1}))

    def test_early_pressure_threshold(self):
        self.assertTrue(m.should_stop({'mem_available_bytes': 60*m.GIB, 'accounted_pressure_bytes': 80_000_000_000}))

    def test_next_allocation_admission(self):
        sample = {'mem_available_bytes': 33*m.GIB, 'accounted_pressure_bytes': 1}
        self.assertFalse(m.should_stop(sample))
        self.assertTrue(m.should_stop(sample, m.GIB))

    def test_meminfo_pressure_not_rss_sum(self):
        self.assertEqual(m.pressure_sample('MemTotal: 1000 kB\nMemAvailable: 700 kB\n'),
                         {'mem_total_bytes': 1024000, 'mem_available_bytes': 716800, 'accounted_pressure_bytes': 307200})


class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / 'config.json').write_text('{}')
        self.tensor = {'dtype': 'BF16', 'shape': [2, 3], 'data_offsets': [0, 12]}
        self.write_fixture()

    def tearDown(self):
        self.temp.cleanup()

    def write_fixture(self):
        header = json.dumps({'weight': self.tensor}).encode()
        (self.root / 'model.safetensors').write_bytes(struct.pack('<Q', len(header)) + header + b'PAYLOADNOPE!')
        (self.root / 'model.safetensors.index.json').write_text(json.dumps({'metadata': {'total_size': 12}, 'weight_map': {'weight': 'model.safetensors'}}))

    def test_header_only_read_and_hash(self):
        _, tensors, identity = m.read_metadata(self.root)
        self.assertEqual(tensors['weight']['bytes'], 12)
        self.assertIn('model.safetensors', identity['safetensors_header_sha256'])

    def test_unknown_dtype_refuses(self):
        self.tensor['dtype'] = 'MYSTERY'
        self.write_fixture()
        with self.assertRaises(ValueError): m.read_metadata(self.root)

    def test_shape_offset_disagreement_refuses(self):
        self.tensor['shape'] = [2, 4]
        self.write_fixture()
        with self.assertRaises(ValueError): m.read_metadata(self.root)

    def test_oversized_header_refuses_before_allocating(self):
        (self.root / 'model.safetensors').write_bytes(struct.pack('<Q', 33*m.MIB))
        with self.assertRaises(ValueError): m.read_metadata(self.root)

    def test_index_coverage_refuses(self):
        p = self.root / 'model.safetensors.index.json'
        d = json.loads(p.read_text()); d['weight_map']['missing'] = 'model.safetensors'; p.write_text(json.dumps(d))
        with self.assertRaises(ValueError): m.read_metadata(self.root)

    def test_index_path_escape_refuses(self):
        p = self.root / 'model.safetensors.index.json'
        d = json.loads(p.read_text()); d['weight_map']['weight'] = '../model.safetensors'; p.write_text(json.dumps(d))
        with self.assertRaises(ValueError): m.read_metadata(self.root)

    def test_missing_accounting_refuses_snapshot(self):
        observed = m.collect_observations(self.root, self.root)
        self.assertFalse(observed['snapshot_complete'])
        self.assertGreater(len(observed['errors']), 0)
        self.assertFalse(m.paired_observations(observed, observed)['required_observations_complete'])

    def test_complete_accounting_pair(self):
        (self.root/'self').mkdir()
        (self.root/'meminfo').write_text('MemTotal: 1000 kB\nMemAvailable: 700 kB\n')
        for name in ('status', 'stat', 'smaps_rollup'):
            (self.root/'self'/name).write_text('fixture')
        (self.root/'self'/'cgroup').write_text('0::/fixture\n')
        (self.root/'fixture').mkdir()
        for name in ('memory.current', 'memory.peak', 'memory.events', 'memory.stat'):
            (self.root/'fixture'/name).write_text('0')
        observed = m.collect_observations(self.root, self.root)
        self.assertTrue(observed['snapshot_complete'])
        pair = m.paired_observations(observed, observed)
        self.assertTrue(pair['required_observations_complete'])
        self.assertEqual(pair['post_hash_mem_available_bytes'], 716800)


class QualificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root/'source.py').write_text('# identity')
        self.bounds = json.loads((m.HERE/'memory-bounds.json').read_text())
        self.bounds.update(source_root=str(self.root), source_sha256={'source.py': m.sha256(self.root/'source.py')},
                           model_config_sha256='config', model_index_sha256='index', qualified=True,
                           qualified_launch_sha256='launch', qualified_overlay_manifest_sha256=m.sha256(m.HERE/'overlay-manifest.json'),
                           remaining_committed_growth_bytes=0, physical_vram_bytes_per_rank=[32*m.GIB]*4)
        for phase in self.bounds['phases']:
            self.bounds['phases'][phase] = dict(other_host=0, private_per_rank=[0]*4,
                copies_per_rank=[0]*4, retained_per_rank=[0]*4, active_files=0, driver=0, safety=0,
                vram_peak_per_rank=[0]*4)
        self.metadata = ({'text_config': {'mtp_use_dedicated_embeddings': False}},
                         {'target.weight': {'bytes': 16}},
                         {'config_sha256': 'config', 'index_sha256': 'index'})
        self.identity = dict(tensor_parallel_size=4, cpu_offload_bytes_per_rank=1,
                             mtp_depth=1, kv_bytes_per_rank=0, command_sha256='launch')

    def tearDown(self):
        self.temp.cleanup()

    def predict(self):
        path = self.root/'bounds.json'; path.write_text(json.dumps(self.bounds))
        with patch.object(m, 'read_metadata', return_value=self.metadata), \
             patch.object(m, 'launch_identity', return_value=self.identity), \
             patch.object(m, 'planned_parameters', return_value=[{'name':'x','bytes':1}]):
            return m.build_prediction([], bounds_path=path, observations={
                'required_observations_complete': True, 'post_hash_mem_available_bytes':100*m.GIB})

    def test_qualified_exact_identity_can_admit(self):
        self.assertEqual(self.predict()['refusal_reasons'], [])

    def test_source_drift_refuses(self):
        (self.root/'source.py').write_text('# drift')
        self.assertIn('source drift: source.py', self.predict()['refusal_reasons'])

    def test_config_drift_refuses(self):
        self.bounds['model_config_sha256'] = 'drift'
        self.assertIn('model config/index identity differs from phase manifest', self.predict()['refusal_reasons'])

    def test_launch_identity_drift_refuses(self):
        self.bounds['qualified_launch_sha256'] = 'drift'
        self.assertIn('qualified bound does not match exact launch flags/environment', self.predict()['refusal_reasons'])

    def test_overlay_identity_drift_refuses(self):
        self.bounds['qualified_overlay_manifest_sha256'] = 'drift'
        self.assertIn('qualified phase bound does not match overlay manifest identity', self.predict()['refusal_reasons'])

    def test_preflight_waives_only_absent_observations(self):
        p = {'refusal_reasons':['post-hash MemAvailable/remaining committed growth unknown'],
             'remaining_committed_growth_bytes':1}
        m.enforce_prediction(p, require_post_hash=False)
        with self.assertRaises(RuntimeError): m.enforce_prediction(p)

    def test_preflight_never_waives_unknown_growth(self):
        p = {'refusal_reasons':['post-hash MemAvailable/remaining committed growth unknown'],
             'remaining_committed_growth_bytes':None}
        with self.assertRaises(RuntimeError): m.enforce_prediction(p, require_post_hash=False)

    def test_preflight_never_waives_known_bad_availability(self):
        p = {'refusal_reasons':['post-hash MemAvailable cannot cover growth and shutdown margin'],
             'remaining_committed_growth_bytes':1}
        with self.assertRaises(RuntimeError): m.enforce_prediction(p, require_post_hash=False)


class ReceiptTests(unittest.TestCase):
    def test_checked_in_candidate_refuses(self):
        receipt = json.loads((m.HERE/'host-memory-prediction.json').read_text())
        self.assertEqual(receipt['final_pins_total_bytes'], 16_704_864_256)
        self.assertEqual(receipt['illustrative_host_peak_bytes'], 35_504_613_400)
        self.assertIsNone(receipt['host_peak_bytes'])
        with self.assertRaises(RuntimeError): m.enforce_prediction(receipt)

    def test_no_generic_cap_joint_fit_under_note_allowances(self):
        receipt = json.loads((m.HERE/'host-memory-prediction.json').read_text())
        self.assertEqual(len(receipt['generic_budget_sweep']), 25)
        self.assertFalse(any(row['joint_scenario_possible'] for row in receipt['generic_budget_sweep']))
        self.assertTrue(receipt['joint_gate_obstruction']['cannot_fit_even_nominal_32gib'])

    def test_printed_table_labels_unknown_and_assumed(self):
        receipt = json.loads((m.HERE/'host-memory-prediction.json').read_text())
        text = m.format_table(receipt)
        self.assertIn('unqualified allowances', text)
        self.assertIn('Qualified Hpred: None', text)
        self.assertIn('LOWER bound', text)


if __name__ == '__main__':
    unittest.main()
