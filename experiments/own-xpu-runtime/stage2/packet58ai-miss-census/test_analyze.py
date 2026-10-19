import copy,math,unittest
import analyze as A

def sample(arm=1,misses=1,ns=10000,index=2):
    events=[];layers=[];now=100
    for layer in range(48):
        layers.append(dict(layer=layer,hits=10-misses,misses=misses,hit_ids=list(range(10-misses)),miss_ids=list(range(10-misses,10)),hit_bytes=(10-misses)*100,miss_bytes=misses*100))
        for projection,part in ([(2,0),(0,0),(1,0)] if arm==1 else [(2,0),(0,1),(0,2),(1,1),(1,2)]):
            events.append(dict(layer=layer,projection=projection,partition=part,start_ns=now,end_ns=now+ns));now+=ns+100
    return dict(schema='packet58ai.token.v1',arm=arm,generated_index=index,position=12,token_id=9,layers=layers,events=events,extra_waits=0)
class Analyze(unittest.TestCase):
    def test_zero_misses_bound_zero(self):
        r=A.paired([sample(misses=0)],[sample(2,misses=0)])
        self.assertEqual(r['upper_bound_ms_per_token'],0);self.assertEqual(r['decision'],'close-rank-4')
    def test_all_misses_no_resident_overlap(self):
        r=A.paired([sample(misses=10)],[sample(2,misses=10)])
        self.assertEqual(r['means']['resident_kernel_ms'],0);self.assertEqual(r['means']['split_overlap_available_ms'],0)
    def test_no_double_counting_gaps(self):
        r=A.paired([sample()],[sample(2)])
        self.assertAlmostEqual(r['upper_bound_ms_per_token'],.96)
        self.assertEqual(r['decision'],'between-thresholds-measure-tighter-bound')
    def test_brief_boundary(self):
        r=A.paired([sample(ns=11000)],[sample(2,ns=11000)])
        self.assertEqual(r['decision'],'brief-transfer-mechanism')
    def test_missing_layer(self):
        r=sample();r['layers'].pop()
        with self.assertRaises(ValueError):A.token(r)
    def test_duplicate_event(self):
        r=sample();r['events'].append(r['events'][0])
        with self.assertRaises(ValueError):A.token(r)
    def test_reverse_interval(self):
        r=sample();r['events'][0]['end_ns']=1
        with self.assertRaises(ValueError):A.token(r)
    def test_nonfinite_timestamp(self):
        r=sample();r['events'][0]['start_ns']=math.nan
        with self.assertRaises(ValueError):A.token(r)
    def test_same_count_different_route_refused(self):
        a,b=sample(),sample(2);b['layers'][0]['miss_ids']=[27]
        result=A.paired([a],[b]);self.assertFalse(result['cache_demand_identical']);self.assertFalse(result['cross_schedule_cost_subtraction_allowed'])
    def test_duplicate_route(self):
        r=sample();r['layers'][0]['hit_ids'][1]=0
        with self.assertRaises(ValueError):A.token(r)
    def test_output_change_refused(self):
        a,b=sample(),sample(2);b['token_id']=10
        with self.assertRaises(ValueError):A.paired([a],[b])
    def test_prefill_separate(self):
        r=A.paired([sample(index=0),sample()],[sample(2,index=0),sample(2)])
        self.assertEqual(r['counts']['count'],1)
    def test_empty_partition_not_useful_service(self):
        r=A.token(sample(2,misses=0))[0]
        self.assertEqual(r['miss_kernel_ms'],0);self.assertGreater(r['empty_partition_ms'],0)
    def test_overhead_both_warm_controls(self):
        r=A.overhead({k:[v]*12 for k,v in [('A0',200),('A1',100),('A2',110),('B0',120),('B1',150)]})
        self.assertAlmostEqual(r['percent_by_instrument_and_control']['B1']['A1'],50)
        self.assertAlmostEqual(r['percent_by_instrument_and_control']['B0']['A2'],100*(120/110-1))
    def test_threshold_not_false_two_percent(self):
        self.assertGreater(A.gain(.670),2);self.assertLess(A.PERIOD_MS-A.PERIOD_MS/1.02,.670)
    def test_no_evidence_is_pending(self):
        import tempfile
        with tempfile.TemporaryDirectory() as p:self.assertEqual(A.analyze(p)['status'],'pending-device')
    def test_unbound_census_file_refused(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'run/run').mkdir(parents=True)
            files={'summary.json','kernel-before.jsonl','kernel-window.jsonl','run/receipt.json','run/summary.json','run/run/receipt.json'}
            for name in files:(p/name).write_text('{}')
            receipt={'native_files':dict.fromkeys(files,'test')}
            A.native_closure(p,receipt)
            (p/'run/measure.jsonl').write_text('{}')
            with self.assertRaises(ValueError):A.native_closure(p,receipt)
if __name__=='__main__':unittest.main()
