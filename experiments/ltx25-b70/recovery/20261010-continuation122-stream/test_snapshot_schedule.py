"""120 safety trade: real CandidateSafety, fake device callbacks, no device imports."""
import unittest
import test_snapshot_fingerprint as base
from test_snapshot_fingerprint import CARDS, PRE_BYTES, GIB, m_storage, SafetyRefusal

class Schedule(unittest.TestCase):
    def build(self):
        w, ctl, inspector, sync, latches = base.ThroughCandidateSafety().build('fingerprint')
        inspector.schedule = 'a-xpu3-sync'
        inspector.bind_synchronize(ctl)
        w.torch.xpu.synchronize = sync.append
        w.torch.xpu.mem_get_info = lambda c: (w.free[c], 32 * GIB)
        return w, ctl, inspector, sync, latches

    def test_only_two_a_barriers_reduce_all_floors_and_readings_stay(self):
        w,c,i,s,_ = self.build()
        rows = base.ThroughCandidateSafety().request(c,i,'stream122-s00000001',1)
        self.assertEqual([r['synchronized'] for r in rows],
                         [list(CARDS), ['xpu:3'], ['xpu:3'], list(CARDS), list(CARDS), list(CARDS)])
        # Four full controller loops, two narrow controller + two narrow inspector barriers.
        self.assertEqual(s, list(CARDS)+['xpu:3']*4+list(CARDS)*3)
        for r in c.receipts:
            if 'snapshot' in r:
                self.assertEqual(set(r['snapshot']['physical_free_bytes']), set(CARDS))
                self.assertEqual(set(r['required_physical_free_bytes']), set(CARDS))

    def test_every_twentieth_chunk_retains_full_barriers(self):
        w,c,i,s,_=self.build()
        rows=base.ThroughCandidateSafety().request(c,i,'stream122-s00000020',20)
        self.assertTrue(all(r['synchronized']==list(CARDS) and r['dual'] for r in rows))
        self.assertEqual(s,list(CARDS)*6)

    def test_qualification_retains_full(self):
        w,c,i,s,_=self.build();i.begin_request(-1,'stream_qualification');i.expect('A-before')
        c._snapshot('conditioning-A-before',PRE_BYTES)
        self.assertEqual(s,list(CARDS));self.assertTrue(i.records[-1]['dual'])

    def test_floor_violation_on_unsynchronized_card_still_refuses(self):
        w,c,i,s,_=self.build();i.begin_request(1,'stream');i.expect('A-before');w.free['xpu:0']=1
        with self.assertRaises(SafetyRefusal):c._snapshot('conditioning-A-before',PRE_BYTES)
        self.assertIsNotNone(c.failed)

    def test_residence_change_on_unsynchronized_card_still_refuses(self):
        w,c,i,s,_=self.build();i.begin_request(1,'stream');i.expect('A-before');m_storage(w,'sampler_primary')
        with self.assertRaises(SafetyRefusal):c._snapshot('conditioning-A-before',PRE_BYTES)

    def test_near_floor_escalates_this_and_following_snapshot(self):
        w,c,i,s,_=self.build();i.begin_request(1,'stream');i.expect('A-before','A-after')
        w.free['xpu:0']=PRE_BYTES['xpu:0']+1
        c._snapshot('conditioning-A-before',PRE_BYTES)
        w.free['xpu:0']=10*GIB
        c._snapshot('conditioning-A-after',{k:2*GIB for k in CARDS})
        self.assertTrue(all(r['dual'] and r['synchronized']==list(CARDS) for r in i.records))

    def test_full_option_leaves_original_callback(self):
        w,c,i,s,_=base.ThroughCandidateSafety().build('fingerprint')
        original=c.synchronize;i.bind_synchronize(c);self.assertIs(c.synchronize,original)
