import copy
import unittest
from analyze_capture_overlap import analyze

def event(owner,sequence,kind,time,op=27,fixture=2,row_id=9):
    value=dict(sequence=sequence,event=kind,monotonic_s=time,op=op,row=dict(fixture=fixture,id=row_id,position=20))
    value['owner' if owner=='provider' else 'stage']=owner
    return value

def records():
    return [event('provider',1,'issued',1),event('provider',1,'parent-captured',2),
            event(2,1,'issued',2.5,24),event(1,1,'issued',3,25),event(1,1,'completed',4,25),
            event('provider',1,'completed',5),event(2,1,'completed',6,24)]

class HostOverlap(unittest.TestCase):
    def test_partial_host_interval(self):
        result=analyze(records(),2)
        self.assertEqual(result['provider_windows'],1)
        self.assertEqual(result['windows_with_final_ROW_issue'],1)
        self.assertEqual(result['host_final_ROW_inflight_intersection']['sum_s'],2.5)
        self.assertEqual(result['counts']['same_seed_final_ROW_issued'],1)
        self.assertEqual(result['counts'].get('final_ROW_completed_inside',0),0)
    def test_full_host_interval(self):
        rows=records();rows[-1]['monotonic_s']=4.5;rows[-2:]=[rows[-1],rows[-2]]
        result=analyze(rows,2)
        self.assertEqual(result['counts']['final_ROW_completed_inside'],1)
        self.assertEqual(result['host_final_ROW_inflight_intersection']['sum_s'],2.)
    def test_equal_clock_uses_event_order(self):
        rows=records();rows[2]['monotonic_s']=2
        self.assertEqual(analyze(rows,2)['windows_with_final_ROW_issue'],1)
    def test_first_fixture_excluded(self):
        rows=records()
        for row in rows:row['row']['fixture']=1
        with self.assertRaises(ValueError):analyze(rows,2)
    def test_missing_duplicate_or_late_capture(self):
        rows=records()
        for bad in ([rows[0]]+rows[2:],rows[:2]+[copy.deepcopy(rows[1])]+rows[2:]):
            with self.assertRaises(ValueError):analyze(bad,2)
    def test_nonmonotonic_trace_refused(self):
        rows=records();rows[3]['monotonic_s']=1
        with self.assertRaises(ValueError):analyze(rows,2)
    def test_other_seed_not_counted_as_same(self):
        rows=records();rows[2]['row']['id']=10
        result=analyze(rows,2)
        self.assertEqual(result['counts']['same_seed_final_ROW_issued'],0)
        self.assertEqual(result['counts']['other_seed_final_ROW_issued'],1)

if __name__=='__main__':unittest.main()
