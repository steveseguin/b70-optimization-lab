"""Length-bound replica memory proofs reject stale121 budgets at145."""
import unittest
import stream_contract as c
import stream_schedule_gate as gate
from test_live_replica_gate import replica_fixture

GIB=2**30

def long_fixture():
    r,d=replica_fixture();r[0]['frames']=145
    res=d[0]['display_replica']['residency'];budget=c.display_transient_bytes(145)
    res['transient_budget_bytes']=budget
    res['last_decode']['before'].update(free_bytes=9*GIB,transient_budget_bytes=budget,
                                       margin_bytes=9*GIB-2*GIB-budget)
    return r,d

class LengthBudget(unittest.TestCase):
    def test_145_proof_passes(self):
        self.assertTrue(gate.check(*long_fixture())['passed'])

    def test_old_length_resident_budget_refused(self):
        r,d=long_fixture();d[0]['display_replica']['residency']['transient_budget_bytes']=4*GIB
        self.assertFalse(gate.check(r,d)['passed'])

    def test_old_length_free_floor_refused(self):
        r,d=long_fixture();d[0]['display_replica']['residency']['last_decode']['before']['free_bytes']=6*GIB
        self.assertFalse(gate.check(r,d)['passed'])

    def test_old_length_before_decode_budget_refused(self):
        r,d=long_fixture();d[0]['display_replica']['residency']['last_decode']['before']['transient_budget_bytes']=4*GIB
        self.assertFalse(gate.check(r,d)['passed'])

    def test_observed_growth_exceeding_new_allowance_refused(self):
        r,d=long_fixture();m=d[0]['display_replica']['residency']['last_decode'];growth=c.display_transient_bytes(145)+1
        m['allocator_after']['peak_allocated']=m['allocator_before']['allocated']+growth
        m['observed_peak_or_reservation_growth_bytes']=growth
        self.assertFalse(gate.check(r,d)['passed'])

    def test_deferred169_allowance_refused(self):
        with self.assertRaises(ValueError):c.display_transient_bytes(169)
