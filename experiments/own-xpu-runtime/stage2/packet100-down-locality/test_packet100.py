import copy,json,unittest
from pathlib import Path
import micro_gate as micro
import screen_jobs as jobs
from bundle_selection import views,choices
from route_inputs import require_ready

def samples(n=2,ratio=.8):
 rows=[]
 for route in range(n):
  for name in micro.CANDIDATES:
   rows.append(dict(kind='correctness',view=name,route=route,fp32_exact=True,bf16_exact=True,status_exact=True,rows=2560,columns=640,count=10,experts=512))
   for rep in range(40):
    for pos in range(2):
     candidate=pos^(rep&1);rows.append(dict(kind='sample',pair=name,view=name if candidate else 'production',route=route,repeat=rep,position=pos,event_ns=1000*ratio if candidate else 1000,rows=2560,columns=640,count=10,experts=512,sg=32,wg=64,scrub_bytes=536870912,diagnostic_only=True))
 rows.append(dict(kind='summary',passed=True,drained=True,diagnostic_only=True,rows=2560,columns=640,count=10,experts=512,route_count=n));return rows

class Packet100(unittest.TestCase):
 def test_gate(self):self.assertEqual(micro.analyze(samples(),2)['qualified'],list(micro.CANDIDATES))
 def test_boundary(self):self.assertEqual(len(micro.analyze(samples(ratio=.85),2)['qualified']),2);self.assertFalse(micro.analyze(samples(ratio=.851),2)['qualified'])
 def test_slow_route_refuses(self):
  rows=samples()
  for r in rows:
   if r.get('kind')=='sample' and r['route']==1 and r['view']!='production':r['event_ns']=900
  self.assertFalse(micro.analyze(rows,2)['qualified'])
 def test_slow_order_refuses(self):
  rows=samples()
  for r in rows:
   if r.get('kind')=='sample' and r['repeat']%2 and r['view']!='production':r['event_ns']=900
  self.assertFalse(micro.analyze(rows,2)['qualified'])
 def test_bad_records(self):
  for key,value in [('event_ns',float('nan')),('event_ns',0),('wg',32),('scrub_bytes',0),('experts',10),('repeat',2),('position',1),('view','bogus'),('diagnostic_only',False)]:
   with self.subTest(key=key,value=value):
    rows=samples();next(r for r in rows if r['kind']=='sample')[key]=value
    with self.assertRaises(ValueError):micro.analyze(rows,2)
 def test_missing_duplicate_correctness(self):
  for mutation in ('missing','duplicate','wrong'):
   rows=samples()
   if mutation=='missing':rows.pop(0)
   if mutation=='duplicate':rows.insert(0,rows[0])
   if mutation=='wrong':rows[0]['fp32_exact']=False
   with self.assertRaises(ValueError):micro.analyze(rows,2)
 def test_missing_samples(self):
  rows=samples();rows.pop(1)
  with self.assertRaises(ValueError):micro.analyze(rows,2)
 def test_empty_routes(self):
  with self.assertRaises(ValueError):micro.analyze(samples(),0)
 def test_unavailable_route_bytes(self):
  with self.assertRaisesRegex(ValueError,'route hashes only'):require_ready()
 def test_single_candidate_brackets(self):
  outs=[]
  for direction in jobs.DIRECTIONS:
   source,confirm=jobs.lanes(direction)
   for name in jobs.VIEWS[1:]:
    for lane in (source,confirm):
     batch=jobs.jobs(lane,name,direction,(name,));self.assertEqual([r['choice'] for r in batch],['production',name,'production']);outs.extend(r['out'] for r in batch)
  self.assertEqual(len(outs),len(set(outs)))
  with self.assertRaises(ValueError):jobs.jobs('B',qualified=jobs.VIEWS[1:])
 def test_winner_exact_acceptance(self):
  name=jobs.VIEWS[1];rows=[dict(choice=c,exact=True,rate=r,acceptance_counts=[(9,10)]) for c,r in zip(('production',name,'production'),(100,101,100))]
  self.assertEqual(jobs.choose(rows,(name,))['choice'],name)
  for key,value in [('exact',False),('rate',99),('acceptance_counts',[(8,10)])]:
   broken=copy.deepcopy(rows);broken[1][key]=value
   with self.assertRaises(ValueError):jobs.choose(broken,(name,))
 def test_composition_corners(self):
  self.assertEqual(len(views()),17)
  for name in views():self.assertEqual(set(choices(name)),set(choices('production')))
 def test_chain_consumers_refuse(self):
  import prepare_chain,merge_dispatch,packet56_submission,selection_gate
  for module in (prepare_chain,merge_dispatch,packet56_submission):
   with self.assertRaisesRegex(ValueError,'records must run on lane A'):module.main()
  for name in views():
   with self.assertRaises(ValueError):selection_gate.validate_choices(choices(name))
 def test_mode_layout_negative_receipts(self):
  report=json.loads(Path(__file__).with_name('evidence').joinpath('full-shape.json').read_text())
  self.assertTrue(report['passed']);self.assertEqual(len(report['runs']),34);self.assertEqual(len(report['negative_allocations']),68);self.assertEqual(report['unsupported_modes_rejected'],14)
 def test_native_selection_consumers(self):
  report=json.loads(Path(__file__).with_name('evidence').joinpath('full-shape.json').read_text());self.assertTrue(all(r['selection_key_consumers_verified'] for r in report['runs']))
if __name__=='__main__':unittest.main()
