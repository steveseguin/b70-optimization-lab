"""CPU-only adversarial saved-receipt checks. No runtime or device imports."""
import unittest
import stream_schedule_gate as gate
from test_schedule_gate import fixture

GIB = 2**30


def replica_fixture():
    receipts, decodes = fixture(display='eager-display')
    receipts[0]['server_options']['display_device'] = 'xpu:2'
    decodes[0]['display_device'] = 'xpu:2'
    decodes[0]['display_replica'] = {
        'device': 'xpu:2', 'reference_device': 'xpu:3', 'mode': 'eager-uncached', 'equal': None,
        'residency': {'device': 'xpu:2', 'resident_bytes': 834268000, 'encoder_bytes': 0,
            'graph_pool_bytes': 0, 'weight_copy_bitwise_equal': True, 'single_decode_thread': True,
            'native_seed': 0, 'dtype': 'torch.bfloat16', 'floor_bytes': 2*GIB,
            'transient_budget_bytes': 4*GIB, 'calls': 10,
            'last_decode': {
                'before': {'free_bytes': 7*GIB, 'new_resident_bytes': 0, 'floor_bytes': 2*GIB,
                           'transient_budget_bytes': 4*GIB, 'margin_bytes': GIB},
                'after_free_bytes': 5*GIB, 'seconds': 2.8,
                'allocator_before': {'allocated': 17*GIB, 'reserved': 18*GIB, 'peak_allocated': 18*GIB},
                'allocator_after': {'allocated': 17*GIB, 'reserved': 20*GIB, 'peak_allocated': 19*GIB},
                'observed_peak_or_reservation_growth_bytes': 2*GIB,
                'peak_is_device_global_not_reset': True}}}
    return receipts, decodes


class LiveReplicaAudit(unittest.TestCase):
    def setUp(self):
        self.r, self.d = replica_fixture()
        self.proof = self.d[0]['display_replica']
        self.residency = self.proof['residency']
        self.memory = self.residency['last_decode']

    def reject(self, text):
        result = gate.check(self.r, self.d)
        self.assertFalse(result['passed'], result)
        self.assertTrue(any(text in row for row in result['failures']), result)

    def test_replica_evidence_passes_without_speed_claim(self):
        result = gate.check(self.r, self.d)
        self.assertTrue(result['passed'], result)
        self.assertFalse(result['performance_qualified'])

    def test_off_retains_parent_schedule(self):
        self.assertTrue(gate.check(*fixture())['passed'])

    def test_missing_selected_device(self):
        del self.r[0]['server_options']['display_device']
        self.reject('display device')

    def test_decode_device_mismatch(self):
        self.d[0]['display_device'] = 'xpu:3'
        self.reject('Display device')

    def test_missing_replica_proof(self):
        del self.d[0]['display_replica']
        self.reject('Live replica proof')

    def test_off_cannot_carry_replica_proof(self):
        self.r[0]['server_options']['display_device'] = self.d[0]['display_device'] = 'xpu:3'
        self.reject('Replica ran')

    def test_wrong_geometry(self):
        self.r[0]['frames'] = 97
        self.reject('launch scope')

    def test_live_full_image_claim_rejected(self):
        self.proof['equal'] = True
        self.reject('unperformed')

    def test_live_equal_field_required(self):
        del self.proof['equal']
        self.reject('Live replica proof')

    def test_wrong_reference_card(self):
        self.proof['reference_device'] = 'xpu:2'
        self.reject('Live replica proof')

    def test_encoder_or_graph_residency_rejected(self):
        for key in ('encoder_bytes', 'graph_pool_bytes'):
            with self.subTest(key=key):
                self.residency[key] = 1
                self.reject('residency policy')
                self.residency[key] = 0

    def test_unverified_weights(self):
        self.residency['weight_copy_bitwise_equal'] = False
        self.reject('residency policy')

    def test_no_decode_calls(self):
        self.residency['calls'] = 0
        self.reject('residency policy')

    def test_wrong_floor(self):
        self.residency['floor_bytes'] = GIB
        self.reject('residency policy')

    def test_low_before_free(self):
        self.memory['before']['free_bytes'] = 6*GIB-1
        self.reject('memory evidence')

    def test_low_after_free(self):
        self.memory['after_free_bytes'] = 2*GIB-1
        self.reject('memory evidence')

    def test_fabricated_margin(self):
        self.memory['before']['margin_bytes'] += 1
        self.reject('memory evidence')

    def test_missing_allocator_counters(self):
        del self.memory['allocator_after']
        self.reject('allocator counters')

    def test_bool_allocator_counter(self):
        self.memory['allocator_before']['allocated'] = True
        self.reject('allocator counters')

    def test_forged_growth(self):
        self.memory['observed_peak_or_reservation_growth_bytes'] = 0
        self.reject('allocator growth')

    def test_peak_exceeds_transient_allowance(self):
        self.memory['allocator_after']['peak_allocated'] = 22*GIB
        self.memory['observed_peak_or_reservation_growth_bytes'] = 5*GIB
        self.reject('allocator growth')

    def test_reservation_exceeds_transient_allowance(self):
        self.memory['allocator_after']['reserved'] = 23*GIB
        self.memory['observed_peak_or_reservation_growth_bytes'] = 5*GIB
        self.reject('allocator growth')

    def test_peak_reset_rejected(self):
        self.memory['peak_is_device_global_not_reset'] = False
        self.reject('allocator growth')

    def test_live_anchor_difference_still_fails(self):
        self.d[0]['anchor_decode']['equal'] = False
        self.reject('byte check')


if __name__ == '__main__':
    unittest.main()
