import unittest
from stage_pipeline_sim import simulate,pair_wave

class PipelineTests(unittest.TestCase):
    def test_two_three_targets_multiple_partial_chunks_actual_lease_order(self):
        for targets in (2,3):
            for n in (1,2,7):
                counts=[256]*(n-1)+[139];d=[[.3+(actor*.07)]*n for actor in range(targets+1)]
                r=simulate(counts,d);self.assertTrue(r['adopted']);self.assertEqual(r['frontiers'],[sum(counts)]*(targets+1));self.assertLessEqual(r['peak_unfinished_chunks'],2)
                issued=[e for e in r['events'] if e['event']=='issued'];acks={e['chunk']:e['time'] for e in r['events'] if e['event']=='full-ack'}
                for e in issued:
                    if e['actor']==0 and e['chunk']>=2:self.assertGreaterEqual(e['time'],acks[e['chunk']-2])
                for actor in range(targets+1):self.assertEqual([e['sequence'] for e in issued if e['actor']==actor],list(range(1,n+1)))
    def test_targets_overlap_before_provider_exists(self):
        r=simulate([256]*4,[[1]*4]*4);events=r['events']
        at={ (e['actor'],e['chunk']):e['time'] for e in events if e['event']=='issued'}
        self.assertEqual(at[1,0],at[0,1]);self.assertEqual(at[2,0],at[1,1]);self.assertEqual(at[3,0],at[2,1])
        self.assertLess(r['wall_seconds'],16);self.assertLessEqual(r['wall_seconds'],pair_wave([256]*4,[[1]*4]*4))
    def test_provider_bottleneck_does_not_release_parity_at_capture(self):
        r=simulate([256]*7,[[.1]*7]*3+[[4]*7]);acks={e['chunk']:e['time'] for e in r['events'] if e['event']=='full-ack'}
        for e in r['events']:
            if e['event']=='issued' and e['actor']==0 and e['chunk']>=2:self.assertGreaterEqual(e['time'],acks[e['chunk']-2])
    def test_fault_drains_all_existing_owners_no_new_issue_no_adoption(self):
        for actor in range(4):
            r=simulate([256]*7,[[1]*7]*4,fail_at=(actor,1));self.assertFalse(r['adopted']);self.assertTrue(r['drained']);fault=r['failed']['time']
            self.assertTrue(all(e['time']<fault for e in r['events'] if e['event']=='issued'))
if __name__=='__main__':unittest.main()
