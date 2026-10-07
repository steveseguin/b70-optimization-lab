import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import analyze as A


def fixture():
    pci = ['0000:%s:00.0' % bus for bus in ('23', '27', '43', '47')]
    header = {'schema': 'ltx.raw-drm-snapshots.v1',
              'limits': {'bytes': 131072, 'interval': 2, 'samples': 64, 'seconds': 120},
              'ordered_xpu_mapping': [{'pci': p} for p in pci]}
    rows = []
    for i in range(8):
        clients = {}
        descriptors = {}
        for j,p in enumerate(pci):
            key = p + '/' + str(j)
            engines = {e: {'busy': i*10+j, 'total': i*100+100, 'busy_watermark': i*10+j,
                           'total_watermark': i*100+100, 'capacity': 1, 'capacity_defaulted': True}
                       for e in A.ENGINES}
            clients[key] = {'pci': p, 'client': str(j), 'selected_fd': str(j+10),
                            'engines': engines, 'duplicate_observations': []}
            descriptors[str(j+10)] = {'target': '/dev/dri/renderD%d' % (128+j), 'client_key': key}
        mono = (1+i*2)*10**9
        rows.append({'monotonic_start_ns': mono, 'monotonic_end_ns': mono+10_000_000,
                     'unix_start_ns': mono+100*10**9, 'complete': True, 'issues': [],
                     'clients': clients, 'render_descriptors': descriptors,
                     'render_descriptors_after': copy.deepcopy(descriptors), 'child_pids': []})
    return [header, *rows, {'terminal': 'output-cap', 'samples_recorded': 8, 'missed_slots': 0}]


class AnalyzeTests(unittest.TestCase):
    def setUp(self):
        self.rows = fixture()

    def run_analysis(self):
        return A.analyze_records(self.rows, 101000, 115000)

    def test_general_interior_not_hardcoded(self):
        result = self.run_analysis()
        self.assertFalse(result['diagnostic_valid'])
        self.assertEqual([x['sample_indexes'] for x in result['accepted_pairs']],
                         [[1,2], [2,3], [3,4], [4,5], [5,6]])
        first = result['accepted_pairs'][0]
        self.assertEqual(first['client_engines']['0000:23:00.0/0']['ccs']['busy_cycles_delta'], 10)
        self.assertEqual(first['counter_read_elapsed_bounds_ns'], [1990000000, 2010000000])
        self.assertEqual(result['conservative_monotonic_inner_ns'], [1011000000,15000000000])

    def test_incomplete_excludes_both_neighbors_not_entire_other_subset(self):
        self.rows[4].update(complete=False, issues=['descriptor-vanished'])
        accepted = self.run_analysis()['accepted_pairs']
        self.assertEqual([x['sample_indexes'] for x in accepted], [[1,2],[4,5],[5,6]])

    def test_gap_never_bridged(self):
        self.rows.insert(4, {'incomplete': 'missed-cadence'})
        self.rows[-1]['missed_slots'] = 1
        result = self.run_analysis()
        self.assertNotIn([2,3], [x['sample_indexes'] for x in result['accepted_pairs']])
        self.assertTrue(any('intervening-record-gap' in x['reasons'] for x in result['excluded_pairs']))

    def test_regression_rejected(self):
        key = '0000:23:00.0/0'
        self.rows[4]['clients'][key]['engines']['ccs'].update(busy=0, busy_watermark=0)
        result = self.run_analysis()
        self.assertNotIn([2,3], [x['sample_indexes'] for x in result['accepted_pairs']])

    def test_watermark_rejected(self):
        self.rows[4]['clients']['0000:23:00.0/0']['engines']['bcs']['busy_watermark'] += 1
        self.assertTrue(any('counter-below-watermark' in x['reasons'] for x in self.run_analysis()['excluded_pairs']))

    def test_capacity_default_change_rejected(self):
        self.rows[4]['clients']['0000:23:00.0/0']['engines']['ccs']['capacity_defaulted'] = False
        self.assertTrue(any('capacity-changed' in x['reasons'] for x in self.run_analysis()['excluded_pairs']))

    def test_zero_total_rejected(self):
        e = self.rows[4]['clients']['0000:23:00.0/0']['engines']['ccs']
        e.update(total=300,total_watermark=300)
        self.assertNotIn([2,3], [x['sample_indexes'] for x in self.run_analysis()['accepted_pairs']])

    def test_render_retarget_rejected(self):
        self.rows[4]['render_descriptors_after']['10']['target'] = '/dev/dri/renderD900'
        self.assertTrue(any('render-ownership-changed' in x['reasons'] for x in self.run_analysis()['excluded_pairs']))

    def test_missing_card_refused(self):
        del self.rows[4]['clients']['0000:23:00.0/0']
        with self.assertRaisesRegex(ValueError, 'coverage'):
            self.run_analysis()

    def test_duplicate_observation_excluded(self):
        self.rows[4]['clients']['0000:23:00.0/0']['duplicate_observations'] = [{'fd': '33'}]
        self.assertTrue(any('duplicate-client-observations-not-admitted' in x['reasons'] for x in self.run_analysis()['excluded_pairs']))

    def test_clock_step_refused(self):
        self.rows[4]['unix_start_ns'] += 20_000_000
        with self.assertRaisesRegex(ValueError, 'intersection'):
            self.run_analysis()

    def test_duplicate_clock_sample_refused(self):
        self.rows[4]['monotonic_start_ns'] = self.rows[3]['monotonic_start_ns']
        with self.assertRaisesRegex(ValueError, 'clock'):
            self.run_analysis()

    def test_all_interior_incomplete_refused(self):
        for row in self.rows[1:-1]:
            row.update(complete=False, issues=['descriptor-vanished'])
        with self.assertRaisesRegex(ValueError, 'No defensible'):
            self.run_analysis()

    def test_terminal_count_refused(self):
        self.rows[-1]['samples_recorded'] += 1
        with self.assertRaisesRegex(ValueError, 'count'):
            self.run_analysis()

    def test_strict_duplicate_key_and_nonfinite(self):
        for raw in ('{"x":1,"x":2}', '{"x":NaN}'):
            with self.assertRaises(ValueError):
                A.strict(raw)

    def test_bound_read_hash_and_symlink_refusal(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)/'input'; p.write_bytes(b'original')
            self.assertEqual(A.bound_read(p, A.digest(b'original')), b'original')
            with self.assertRaisesRegex(ValueError, 'hash'):
                A.bound_read(p, '0'*64)
            link = Path(temp)/'link';link.symlink_to(p)
            with self.assertRaisesRegex(ValueError, 'Unsafe'):
                A.bound_read(link, A.digest(b'original'))

    def test_missing_postcompletion_pin_refused_before_reads(self):
        with patch.object(A, 'QUALITY_PIN', None), patch.object(A, 'bound_read') as read:
            with self.assertRaisesRegex(ValueError, 'post-completion'):
                A.load_fixed()
            read.assert_not_called()

    def synthetic_bound_inputs(self):
        bindings = {role: {'path': str(A.PINS[key][0]), 'sha256': A.PINS[key][1]}
                    for role,key in [('mapping_evidence','mapping'),('plan','plan'),
                                     ('runtime_manifest','manifest'),('server_identity','identity')]}
        contract = {'bindings': bindings, 'ordered_xpu_mapping': self.rows[0]['ordered_xpu_mapping'],
                    'pid': 17, 'start_ticks': '100', 'boot_id': 'boot', 'collector_sha256': 'c'*64,
                    'plan_sha256': A.PLAN_SHA}
        self.rows[0].update(contract)
        self.rows[0]['contract_sha256'] = A.PINS['contract'][1]
        executions = [{'fill': True} for _ in range(4)] + [
            {'fill': False, 'emitted_index': i, 'timing_scope': 'sampler-driver-accounting',
             'parity_status': 'four-tensors-exact', 'success_ms': 101000+i*1500}
            for i in range(10)]
        fast = {'runtime_manifest_sha256': A.PINS['manifest'][1], 'server_identity_sha256': A.PINS['identity'][1],
                'plan_sha256': A.PLAN_SHA, 'status': 'timed_fast_verified',
                'four_tensor_exact_clips': 10, 'distinct_fixtures': 10, 'fills_not_scored': 4,
                'executions': executions}
        values = {'contract': contract, 'fast': fast, 'campaign': {'diagnostic_valid': False,
                  'driver_accounting': {'valid': False}, 'passed': True},
                  'mapping': {'ordered_xpu_mapping': contract['ordered_xpu_mapping'], 'evidence_sources': []},
                  'manifest': {'files': {'resolution/components/candidate_gate.py': 'v'*64,
                                        'resolution/components/driver_accounting.py': 'c'*64}},
                  'identity': {'pid': 17, 'proc_start_ticks': '100', 'boot_id': 'boot',
                               'source_packet_manifest_sha256': A.PINS['manifest'][1]}, 'plan': {},
                  'quality': {'schema': 'ltx.sampler106.post-completion-proof.v1', 'passed': True,
                              'runtime_manifest_sha256': A.PINS['manifest'][1],
                              'fast_receipt_sha256': A.PINS['fast'][1],
                              'verifier': str(A.PACKET/'resolution/components/candidate_gate.py'),
                              'verifier_sha256': 'v'*64}}
        def reader(path, sha):
            if Path(path) == A.PINS['raw'][0]:
                return b'\n'.join(json.dumps(r).encode() for r in self.rows)+b'\n'
            for key,(p,_) in {**A.PINS,'quality':A.QUALITY_PIN}.items():
                if Path(path) == p:
                    return json.dumps(values[key]).encode()
            return b'synthetic source'
        return values, reader

    def test_quality_dependency_and_global_invalid_preserved(self):
        values, reader = self.synthetic_bound_inputs()
        with patch.object(A, 'bound_read', side_effect=reader):
            self.assertFalse(A.load_fixed()['diagnostic_valid'])
            values['quality']['fast_receipt_sha256'] = 'wrong'
            with self.assertRaisesRegex(ValueError, 'quality proof'):
                A.load_fixed()

    def test_global_valid_cannot_be_relabelled(self):
        values, reader = self.synthetic_bound_inputs()
        values['campaign']['diagnostic_valid'] = True
        with patch.object(A, 'bound_read', side_effect=reader):
            with self.assertRaisesRegex(ValueError, 'invalid diagnostic'):
                A.load_fixed()

    def test_unscored_fixture_cannot_be_claimed(self):
        values, reader = self.synthetic_bound_inputs()
        values['fast']['executions'][-1]['parity_status'] = 'mismatch'
        with patch.object(A, 'bound_read', side_effect=reader):
            with self.assertRaisesRegex(ValueError, 'Scored scope'):
                A.load_fixed()

    def test_output_exclusive(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)/'result'
            A.write_exclusive(p,b'one')
            with self.assertRaises(FileExistsError):
                A.write_exclusive(p,b'two')
            self.assertEqual(p.read_bytes(),b'one')


if __name__ == '__main__':
    unittest.main()
