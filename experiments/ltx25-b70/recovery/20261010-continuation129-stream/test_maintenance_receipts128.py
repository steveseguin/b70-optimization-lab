"""Maintenance mode must pass receipt schema and bind all three quality chains."""
import unittest
import stream_contract as c
import stream_receipts as receipts
from test_gate_receipts import passing, decide

class MaintenanceReceipts(unittest.TestCase):
    def candidate(self):
        rows, decodes, captures = passing(frames=145, anchor='frame', decoder_graph=0,
                                         levers=('cone', 1, 1), snapshot_mode='fingerprint')
        for row in rows:
            row['server_options'].update(maintenance_mode='idle', aux_residency='legacy',
                display_worker='serial', residency_qualification_id=c.residency_qualification_id(row['qualification_id'], 'legacy'))
        for decoded in decodes.values():
            decoded.update(display_worker='serial', completion_worker='serial',
                display_worker_timing={'queued_ns': None, 'start_ns': None, 'gated_inline': decoded['kind'] in c.GATED_KINDS})
        return rows, decodes, captures

    def gate(self, rows, decodes, captures):
        return decide(rows, decodes, captures, frames=145, anchor='frame', decoder_graph=0, levers=('cone', 1, 1))

    def test_explicit_parent_option_accepted(self):
        rows, decodes, captures = passing()
        for row in rows:
            row['server_options']['maintenance_mode'] = 'parent'
            receipts.validate_measurements(row)
        result = decide(rows, decodes, captures)
        self.assertTrue(result['passed'], result['failures'])

    def test_idle_candidate_all_three_chains_pass(self):
        rows, decodes, captures = self.candidate()
        for row in rows:
            receipts.validate_measurements(row)
        result = self.gate(rows, decodes, captures)
        self.assertTrue(result['passed'], result['failures'])

    def test_mixed_maintenance_modes_fail_qualification(self):
        rows, decodes, captures = self.candidate()
        rows[4]['server_options']['maintenance_mode'] = 'parent'
        self.assertFalse(self.gate(rows, decodes, captures)['passed'])

    def test_invalid_mode_fails_schema_and_gate(self):
        for value in ('other', 1, True, None):
            rows, decodes, captures = self.candidate()
            for row in rows:
                row['server_options']['maintenance_mode'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                receipts.validate_measurements(rows[0])
            self.assertFalse(self.gate(rows, decodes, captures)['passed'])

    def test_idle_outside_candidate_scope_fails(self):
        rows, decodes, captures = passing()
        for row in rows:
            row['server_options']['maintenance_mode'] = 'idle'
        with self.assertRaises(ValueError):
            receipts.validate_measurements(rows[0])
        self.assertFalse(decide(rows, decodes, captures)['passed'])
