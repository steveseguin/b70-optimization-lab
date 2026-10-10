"""CPU fake end-to-end auxiliary scope/identity gates, never hardware evidence."""
import copy
import unittest

import stream_contract as c
import stream_receipts as receipts
from test_gate_receipts import passing
from test_runtime_flow import harness


class AuxiliaryRuntime123(unittest.TestCase):
    def run_aux(self, frames=169, *extra):
        return harness('--frames', str(frames), '--anchor', 'frame', '--decoder-graph', '0',
                       '--aux-residency', 'xpu2', '--stream-chunks', '2',
                       '--decode-delay', '0.01', '--audio-delay', '0.01', *extra)

    def check169(self, data):
        self.assertIsNone(data.get('error'), data.get('error'))
        self.assertIsNone(data.get('halted'), data.get('halted'))
        self.assertTrue(data['verdict']['passed'], data['verdict'])
        self.assertFalse(data['xpu_initialized'])
        self.assertEqual(data['captures'], 9)
        self.assertEqual(len(data['chunks']), 11)
        self.assertTrue(data['geometry_record']['matches'])
        self.assertEqual(data['geometry_record']['frames'], 169)
        self.assertEqual([row['delivery_new_frames'] for row in data['chunks'][-2:]], [169, 168])
        qid = c.qualification_id(169, 'two-way20-28', 'frame', 0)
        for row in data['chunks']:
            self.assertEqual(row['server_options']['aux_residency'], 'xpu2')
            self.assertEqual(row['server_options']['residency_qualification_id'],
                             c.residency_qualification_id(qid, 'xpu2'))
        self.assertTrue(all(row['anchor_decode']['equal'] for row in data['chunks'][3:]))

    def test_169_aux_three_chains_and_stream(self):
        self.check169(self.run_aux())

    def test_169_aux_display_replica_refused_by_workspace_admission(self):
        with self.assertRaisesRegex(ValueError, 'Auxiliary residency plus display replica lacks workspace margin'):
            c.check_residency_scope(169, 'two-way20-28', 'frame', 0, 'cone', 'xpu2', 'xpu:2')

    def test_145_aux_refuses_fake_bytes_against_frozen_real_baseline(self):
        data = self.run_aux(145, '--reference', 'sealed')
        self.assertIsNone(data.get('error'), data.get('error'))
        self.assertIs(data['verdict']['passed'], False)
        mismatches = [why for why in data['verdict']['failures']
                      if why.startswith('Eager chain differs from the packet-121 reference at chunk ')]
        self.assertEqual(len(mismatches), 3)
        self.assertEqual(len(data['verdict_file']['reference_check']), 3)

    def test_169_legacy_is_refused(self):
        with self.assertRaisesRegex(ValueError, '169 requires xpu2'):
            c.check_residency_scope(169, 'two-way20-28', 'frame', 0, 'cone', 'legacy', 'xpu:3')

    def test_145_dg1_replica_stays_refused(self):
        with self.assertRaisesRegex(ValueError, 'memory-inadmissible'):
            c.check_residency_scope(145, 'two-way20-28', 'frame', 1, 'cone', 'legacy', 'xpu:2')

    def test_receipt_cannot_tamper_residency_identity(self):
        rows, _, _ = passing(frames=145, anchor='frame', decoder_graph=0)
        row = copy.deepcopy(rows[0])
        row['server_options'].update(aux_residency='xpu2', residency_qualification_id='0'*64)
        with self.assertRaisesRegex(ValueError, 'Residency identity differs'):
            receipts.validate_measurements(row)


if __name__ == '__main__':
    unittest.main()
