"""CPU-only boundaries: a prepared head view is not chain qualification."""
import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from screen_jobs import P, WRAPPER
from bundle_selection import VIEWS, choices, selection
from lane_admission import Reservation, admission_scope


class ConsumerBoundaryTest(unittest.TestCase):
 def test_parent_dispatch_and_promotion_consumers(self):
  code=r'''
import copy,json,sys
from pathlib import Path
parent,packet=map(Path,sys.argv[1:]);sys.path.insert(0,str(parent))
import merge_dispatch,packet56_submission,p49d_k2,selection_gate
base=json.loads((parent/'bundle-selection.json').read_text())
original=json.loads((parent/'selection.json').read_text())
dispatch=json.loads((packet/'dispatch-speed6.json').read_text())
assert merge_dispatch.merge([dispatch])[0]==dispatch
packet56_submission.validate_bundle(base,original)
legacy=dict(route='production',recurrence='production',hc='production')
selection_gate.validate_choices(legacy)
for name in ('production','head-plane','head-transpose'):
 s=copy.deepcopy(original);s['choices']['head']=name
 try:packet56_submission.validate_bundle(base,s)
 except ValueError as error:assert str(error)=='composed choices differ',str(error)
 else:raise AssertionError('parent submission accepts new head key: '+name)
 s['choices']=dict(legacy,head=name)
 try:p49d_k2.measured_coverage('/nonexistent/packet93-not-a-chain',s)
 except ValueError as error:assert str(error)=='selection must name exactly route/recurrence/hc',str(error)
 else:raise AssertionError('legacy K2 accepts new head key: '+name)
 full=json.loads((packet/'selection.json').read_text());full['choices']['head']=name
 try:p49d_k2.measured_coverage('/nonexistent/packet93-not-a-chain',full)
 except ValueError as error:assert str(error)=='selection must name exactly route/recurrence/hc',str(error)
 else:raise AssertionError('legacy K2 accepts complete packet93 selection: '+name)
print('unchanged dispatch passes; all new head keys refuse legacy K2/submission')
'''
  subprocess.run(['/usr/bin/python3','-B','-c',code,str(P.parent/'packet84-record-bundle'),str(P)],env={'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2'},stdin=subprocess.DEVNULL,check=True,timeout=60)

 def test_default_and_single_choice_scope(self):
  baseline=choices('production')
  self.assertEqual(baseline,json.loads((P/'selection.json').read_text())['choices'])
  self.assertEqual(baseline['head'],'production')
  self.assertEqual(baseline['packed_dense'],'production')
  self.assertEqual(baseline['experts'],'wide64')
  self.assertEqual(baseline['hc_gate'],'wide')
  self.assertEqual(baseline['host_retire'],'ordered')
  self.assertEqual(baseline['recurrence'],'rec-parallel')
  for view in VIEWS:
   with self.subTest(view=view):
    c=choices(view);self.assertEqual(c['head'],view)
    c['head']='production';self.assertEqual(c,baseline)
    self.assertEqual(selection(view)['draft'],selection('production')['draft'])
    self.assertEqual(selection(view)['draft']['head_format'],'production')
  with self.assertRaises(ValueError):choices('unknown')

 def test_closed_worker_import(self):
  code='import sys;sys.path.insert(0,sys.argv[1]);import tp2_worker;from lane_admission import admission_scope;assert admission_scope("A","screen")=="lane-A";assert admission_scope("B","screen")=="lane-B"'
  subprocess.run(['/usr/bin/python3','-B','-c',code,str(WRAPPER)],env={'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2'},stdin=subprocess.DEVNULL,check=True,timeout=30)

 def test_lane_admission(self):
  for lane in ('A','B'):
   self.assertEqual(admission_scope(lane,'screen'),'lane-'+lane)
   with tempfile.TemporaryDirectory(prefix='packet93-consumer-') as directory:
    self.assertEqual(Reservation(lane,window='screen',root=Path(directory)).scope,'lane-'+lane)

 def test_memory_plan_layout_and_real_draft_offset(self):
  from memory_plans import plan,DELTA,TARGET_SAVING,DRAFT_PREFIX
  from memory_gate import configuration,arena_bytes
  self.assertEqual(TARGET_SAVING,317849600)
  self.assertEqual(DRAFT_PREFIX,308904960)
  base=configuration(plan('production'),4096,1,0)['ranks']
  for view in VIEWS:
   ledger=plan(view)
   self.assertEqual(set(ledger['placements']),{'1'})
   self.assertEqual(set(ledger['placements']['1']['capacities']),{'4096'})
   self.assertEqual(DELTA[view],(0,0 if view=='production' else -8944640))
   ranks=configuration(ledger,4096,1,0)['ranks']
   for rank,(r,b) in enumerate(zip(ranks,base)):
    with self.subTest(view=view,rank=rank):
     target_delta=-TARGET_SAVING if rank==1 and view!='production' else 0
     draft_delta=DRAFT_PREFIX if rank==1 and view!='production' else 0
     self.assertEqual(r['target_modeled_allocations_bytes']-b['target_modeled_allocations_bytes'],target_delta)
     self.assertEqual(r['draft_duplicate_head_bytes']-b['draft_duplicate_head_bytes'],draft_delta)
     self.assertEqual(r['draft_total_bytes'],b['draft_total_bytes'])
     self.assertEqual(r['arena_device_bytes']-b['arena_device_bytes'],DELTA[view][rank])
     self.assertEqual(arena_bytes(r)-arena_bytes(b),DELTA[view][rank])
     self.assertEqual(r['free_with_mtp_bytes']-b['free_with_mtp_bytes'],-DELTA[view][rank])
   for context,draft_rank,split in ((4096,0,0),(4096,1,23),(4096,0,24),(32768,1,0),(256,1,0)):
    with self.subTest(view=view,context=context,draft_rank=draft_rank,split=split),self.assertRaises(ValueError):configuration(ledger,context,draft_rank,split)
   corrupted=copy.deepcopy(ledger)
   corrupted['placements']['1']['capacities']['4096']['ranks'][1]['draft_duplicate_head_bytes']+=1
   with self.assertRaisesRegex(ValueError,'inconsistent arena'):configuration(corrupted,4096,1,0)


if __name__=='__main__':unittest.main()
