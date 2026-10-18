import copy,json,unittest
from pathlib import Path
from bundle_selection import aliases,selection
from memory_plans import plan
from memory_gate import configuration,check
from build_engine import P

class Packet105(unittest.TestCase):
 def test_only_head_and_copy_placement_change(self):
  rows=[selection(v) for v in aliases().values()];base=copy.deepcopy(rows[0]);base['choices'].pop('head')
  for row in rows:
   row=copy.deepcopy(row);row['choices'].pop('head');self.assertEqual(row,base)
 def test_actual_census_and_exact_delta(self):
  shape=json.loads((P/'evidence/full-shape.json').read_text());rows=shape['runs']
  control={r['rank']:r for r in rows if r['view'].split('--')[-2]=='production'}
  for r in rows:
   if r['view'].split('--')[-2]=='production':continue
   delta=r['postload_device_bytes']-control[r['rank']]['postload_device_bytes']
   self.assertEqual(delta,157322272 if r['rank']==0 else -155750384)
   self.assertGreater(r['arena_headroom_bytes'],0)
 def test_memory_refuses_overcommit(self):
  for v in aliases().values():
   row=plan(v);configuration(row,4096,1,0)
   bad=copy.deepcopy(row);bad['placements']['1']['capacities']['4096']['ranks'][0]['allocation_margin_passed']=False
   with self.assertRaises(ValueError):configuration(bad,4096,1,0)
   bad=copy.deepcopy(row);bad['arena_limit_bytes']=31*1024**3
   with self.assertRaises(ValueError):configuration(bad,4096,1,0)
 def test_kd_projection_keeps_all_draft_choices(self):
  from kd_reference import project
  for v in aliases().values():
   target=selection(v);reference=project(target)
   self.assertEqual(reference['draft'],target['draft']);self.assertEqual(reference['choices']['head'],'production');self.assertEqual(reference['choices']['experts'],'wide64')
 def rows(self,rates,lane='B'):
  from screen_jobs import ORDER
  return [dict(choice=c,all_13_exact=True,boot_id='boot',lane=lane,started_utc_ns=i*10+1,finished_utc_ns=i*10+5,exact=True,exact_count=13,acceptance_counts=[dict(hits=8,guesses=10)],acceptance=.8,rate=float(rate)) for i,(c,rate) in enumerate(zip(ORDER,rates))]
 def test_compare_two_independent_brackets(self):
  from compare import compare_grid
  r=compare_grid(self.rows([50,51,50,49,50]));self.assertEqual(r['winners'],['head-split-compute']);self.assertFalse(r['record_ready'])
  # Lane A must independently reproduce the result, never inherit B's win.
  r=compare_grid(self.rows([50,49,50,49,50],'A'));self.assertEqual(r['winners'],[])
 def test_compare_rejects_acceptance_or_output_change(self):
  from compare import compare_grid
  for key,value in [('acceptance_counts',[dict(hits=9,guesses=10)]),('all_13_exact',False),('lane','A'),('boot_id','other')]:
   rows=self.rows([50,51,50,51,50]);rows[1][key]=value
   with self.assertRaises(ValueError):compare_grid(rows)
 def test_every_window_present(self):
  r=json.loads((P/'startup97e.json').read_text());self.assertEqual((r['compositions'],r['windows_per_composition'],r['total_windows']),(3,11,33));self.assertTrue(r['passed']);self.assertFalse(r['device_executed'])

if __name__=='__main__':
 from build_engine import limits,ROOT,sha,save
 limits();result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Packet105))
 sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('test_p105.py','compare.py','bundle_selection.py','memory_plans.py','base-memory-plan.json','memory_gate.py','kd_reference.py','screen_jobs.py','evidence/full-shape.json','startup97e.json')}
 save(P/'evidence/guardrails.json',dict(passed=result.wasSuccessful(),device_executed=False,tests=result.testsRun,sources=sources))
 raise SystemExit(0 if result.wasSuccessful() else 1)
