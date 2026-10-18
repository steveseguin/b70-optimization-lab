"""CPU-only failure cases for the measurement reader and admission gates."""
import copy,json,math,unittest
from unittest.mock import patch
import analyze as A
import readiness
from exec_limits import check,snapshot

def views():
    return [dict(label=label,exact_oracle=True,request_count=12,requested_max_new=64,cached_tokens=0,request_decode_ms=[100.0]*12) for label in A.RULES['required_views']]
def publication():
    return dict(arm=1,extra_waits=0,pack_ms=.06,publication_wait_ms=1.1,publication_boundary_ms=1.231,publications=1,
        events=[dict(layer=-1,projection=0,start_ns=1,end_ns=800001),dict(layer=-1,projection=1,start_ns=800001,end_ns=900001)])
class Measurements(unittest.TestCase):
    def test_zero_overhead(self):self.assertTrue(A.overhead(views())['passed'])
    def test_two_percent_strict(self):
        v=views();v[1]['request_decode_ms']=[102.0]*12;self.assertFalse(A.overhead(v)['passed'])
    def test_both_controls(self):
        v=views();v[4]['request_decode_ms']=[98.1]*12;v[1]['request_decode_ms']=[101.0]*12;self.assertFalse(A.overhead(v)['passed'])
    def test_drift(self):
        v=views();v[4]['request_decode_ms']=[97.0]*12;self.assertFalse(A.overhead(v)['passed'])
    def test_a0_exact(self):
        v=views();v[0]['exact_oracle']=False
        with self.assertRaises(ValueError):A.overhead(v)
    def test_missing_view(self):
        with self.assertRaises(ValueError):A.overhead(views()[:-1])
    def test_bad_time(self):
        v=views();v[1]['request_decode_ms'][0]=math.nan
        with self.assertRaises(ValueError):A.overhead(v)
    def test_wait_not_added(self):
        r=A.publication([publication()]);self.assertAlmostEqual(r['per_token_mean']['boundary_ms'],1.231)
        self.assertAlmostEqual(r['per_token_mean']['h2d_ms'],.8);self.assertAlmostEqual(r['per_token_mean']['scatter_ms'],.1)
    def test_missing_event(self):
        r=publication();r['events'].pop()
        with self.assertRaises(ValueError):A.publication([r])
    def test_invalid_interval(self):
        r=publication();r['events'][0]['end_ns']=0
        with self.assertRaises(ValueError):A.publication([r])
    def test_extra_wait(self):
        r=publication();r['extra_waits']=1
        with self.assertRaises(ValueError):A.publication([r])
    def test_aggregate_is_not_stall(self):
        rows=[]
        for i in range(48):
            rows.append(dict(arm=2,extra_waits=0,sample_layer=i,layers=[dict(layer=j,hits=9,misses=1,hit_bytes=90,miss_bytes=10) for j in range(48)],
                events=[dict(layer=i,projection=j,start_ns=1,end_ns=1001) for j in (0,1)]))
        report=A.misses(rows);self.assertFalse(report['measurement_complete'])
        self.assertTrue(all(r['miss_stall_ms'] is None and r['resident_slot_compute_ms'] is None and r['overlap_window_ms'] is None for r in report['per_layer']))
        with self.assertRaises(ValueError):A.misses(rows[:-1])
    def test_boolean_cannot_enable_launch(self):
        with patch.object(readiness.Path,'read_text',return_value='{"ready_for_device":true}'):
            with self.assertRaisesRegex(ValueError,'separate resident/miss'):readiness.verify_ready()
    def test_limit_gate(self):
        before=snapshot()
        with patch('resource.getrlimit',return_value=(4*1024**3,4*1024**3)):
            with self.assertRaises(ValueError):check()
        self.assertEqual(snapshot(),before)
if __name__=='__main__':unittest.main()
