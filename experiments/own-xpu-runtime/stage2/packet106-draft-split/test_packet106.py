"""CPU refusal checks for smoke ordering, views, memory and proposal identity."""
import ast,copy,json,unittest
from pathlib import Path
from unittest.mock import patch
from bundle_selection import aliases,selection
from memory_plans import plan
from build_engine import P
class Packet106(unittest.TestCase):
 def test_views(self):
  self.assertEqual(set(aliases()),{'production','head-split','draft-split','head-split+draft-split'})
  rows=[selection(v) for v in aliases().values()]
  self.assertTrue(all(r['draft']==rows[0]['draft'] for r in rows))
 def test_exact_memory_deltas(self):
  rows={k:plan(v)['placements']['1']['capacities']['4096']['ranks'] for k,v in aliases().items()}
  for label,delta in [('head-split',(157322272,-155750384)),('draft-split',(153826336,16)),('head-split+draft-split',(311148608,-155750368))]:
   for r in (0,1):self.assertEqual(rows[label][r]['arena_device_bytes']-rows['production'][r]['arena_device_bytes'],delta[r])
 def test_smoke_refused_if_missing(self):
  import screen_jobs
  with patch.object(screen_jobs,'smoke_output',return_value=P/'build/no-such-smoke'):
   with self.assertRaises(FileNotFoundError):screen_jobs.require_smoke()
 def test_one_prompt_smoke_source(self):
  tree=ast.parse((P/'smoke_worker.py').read_text())
  requests=[n.value for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='requests' for t in n.targets)]
  self.assertEqual(len(requests),1);self.assertIsInstance(requests[0],ast.List);self.assertEqual(len(requests[0].elts),1)
  self.assertEqual(ast.literal_eval(requests[0].elts[0].elts[-1]),64)
 def test_grid_requires_smoke(self):
  import screen_job
  from screen_jobs import output,jobs
  # No launch: reject before reaching the shared screen runner.
  with patch.object(screen_job,'verify'),patch.object(screen_job,'jobs',return_value=[dict(index=0,choice='production',lane='B',mode='grid',out='mock')]),patch.object(screen_job,'require_smoke',side_effect=ValueError('missing smoke')):
   dest=screen_job.output(dict(out='mock'))
   with self.assertRaisesRegex(ValueError,'missing smoke'):
    screen_job.main(['--lane','B','--index','0','--output',str(dest),'--fault-review','mock','--authorized-device-window'])
 def test_no_parent_ops_in_dependency_map(self):
  pins=json.loads((P/'dependency-pins.json').read_text())
  self.assertFalse(any('/ops/' in k or 'selection-dry-run' in k for k in pins))
 def test_confirmation_refuses_before_B(self):
  import confirm_job
  from screen_jobs import confirm_jobs,output
  with patch('screen_jobs.sha',return_value='fixture'):job=confirm_jobs()[0]
  with patch.object(confirm_job,'verify'),patch.object(confirm_job,'require_smoke'),patch.object(confirm_job,'qualified_winner',side_effect=ValueError('B incomplete')):
   with self.assertRaisesRegex(ValueError,'B incomplete'):
    confirm_job.main(['--index','0','--output',str(output(job)),'--fault-review','mock','--authorized-device-window'])
 def test_memory_refuses_changed_arena_limit(self):
  from memory_gate import configuration
  ledger=plan(aliases()['head-split+draft-split']);ledger['arena_limit_bytes']=31*1024**3
  with self.assertRaisesRegex(ValueError,'arena cap changed'):configuration(ledger,4096,1,0)
 def test_compare_refuses_proposal_changes(self):
  from compare import compare_grid
  from screen_jobs import ORDER
  rows=[dict(choice=c,index=i,rate=50+i%3,all_13_exact=True,exact=True,exact_count=13,boot_id='same',lane='B',started_utc_ns=2*i,finished_utc_ns=2*i+1,acceptance_counts=[1],proposal_sequences=[[1,2]],acceptance=.5) for i,c in enumerate(ORDER)]
  compare_grid(rows)
  rows[2]['proposal_sequences']=[[1,3]]
  with self.assertRaisesRegex(ValueError,'draft proposals changed'):compare_grid(rows)
if __name__=='__main__':unittest.main()
