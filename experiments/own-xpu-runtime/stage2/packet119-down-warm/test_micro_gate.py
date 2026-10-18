import copy
import unittest
import micro_gate as m

def fixture(ratio=.8):
 rows=[dict(kind='cache_device',runtime_reported_global_cache_bytes=16*1024**2,capacity_measurement=False,diagnostic_only=True)]
 rows += [dict(kind='cache_probe',bytes=n*1024**2,repeat=i,repetitions=8,scrub_bytes=536870912,stride_bytes=64,cold_ns=200,warm_ns=100,diagnostic_only=True) for n in (1,2,4,8,16,24,32,48,64) for i in range(8)]
 for route in range(m.ROUTE_COUNT):
  rows.append(dict(kind='correctness',route=route,**{k:True for k in ('all_bytes_exact','gate_exact','up_exact','activation_exact','down_exact','status_exact','control_exact')}))
  for rep in (0,1):
   for pos in (0,1):
    warm=pos^(rep&1);t=1000*ratio if warm else 1000
    rows.append(dict(kind='sample',route=route,repeat=rep,position=pos,view='p119' if warm else 'production',gate_ns=t/2,down_ns=t/2,activation_ns=100,event_ns=t,rows_gate=640,rows_down=2560,count=10,experts=512,scrub_bytes=536870912,scrub_between_operators=False,diagnostic_only=True,all_bytes_exact=True))
 rows.append(dict(kind='summary',passed=True,drained=True,diagnostic_only=True,route_count=m.ROUTE_COUNT,candidates=['p119']))
 return rows
class Gate(unittest.TestCase):
 def test_qualifies_at_threshold(self):self.assertEqual(m.analyze(fixture(.85))['qualified'],['p119'])
 def test_kills_slow(self):self.assertEqual(m.analyze(fixture(.851))['qualified'],[])
 def test_one_order_insufficient(self):
  rows=fixture(.7)
  for row in rows:
   if row.get('kind')=='sample' and row['repeat']==1 and row['view']=='p119':row.update(gate_ns=500,down_ns=500,event_ns=1000)
  self.assertEqual(m.analyze(rows)['qualified'],[])
 def test_missing_routes_refused(self):
  rows=fixture();rows.pop(-2)
  with self.assertRaises(ValueError):m.analyze(rows)
 def test_duplicate_sample_refused(self):
  rows=fixture();rows.insert(-1,copy.deepcopy(rows[-2]))
  with self.assertRaises(ValueError):m.analyze(rows)
 def test_all_output_checks(self):
  for field in ('gate_exact','up_exact','activation_exact','down_exact','status_exact','control_exact'):
   rows=fixture();next(r for r in rows if r['kind']=='correctness')[field]=False
   with self.subTest(field=field),self.assertRaises(ValueError):m.analyze(rows)
 def test_timed_bytes_refused(self):
  rows=fixture();next(r for r in rows if r['kind']=='sample')['all_bytes_exact']=False
  with self.assertRaises(ValueError):m.analyze(rows)
 def test_intervening_scrub_refused(self):
  rows=fixture();next(r for r in rows if r['kind']=='sample')['scrub_between_operators']=True
  with self.assertRaises(ValueError):m.analyze(rows)
 def test_wrong_sum_refused(self):
  rows=fixture();next(r for r in rows if r['kind']=='sample')['event_ns']+=1
  with self.assertRaises(ValueError):m.analyze(rows)
 def test_cache_probe_complete(self):
  rows=fixture();rows.pop(1)
  with self.assertRaises(ValueError):m.analyze(rows)
 def test_fresh_processes(self):
  windows=[dict(repeat=n,passed=True,device_executed=True,drained=True,lease_released=True,pid=100+n,process_start_ticks=n,boot_id='a',started_utc_ns=n*10,finished_utc_ns=n*10+1) for n in (1,2)]
  self.assertEqual(len(m.validate_processes(windows)),2)
  windows[1].update(pid=101,process_start_ticks=1)
  with self.assertRaises(ValueError):m.validate_processes(windows)
if __name__=='__main__':unittest.main()
