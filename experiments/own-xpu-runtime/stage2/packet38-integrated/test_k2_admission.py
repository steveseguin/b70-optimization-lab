#!/usr/bin/env python3
"""Packet35 CPU K2 admission regressions, preserved for packet37."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from k2_summary import aggregate
w=SimpleNamespace(HERE=Path(__file__).resolve().parent)

class K2Summary(unittest.TestCase):
 def rows(self,new=80):return [dict(**{'class':'norm'},variant=v,repetition=i,start_ns=100,end_ns=100+(100 if v=='packet18' else new),exact=True) for v in ('packet18','specialised') for i in range(200)]
 def test_faster_exact_selected(self):
  r=aggregate(self.rows(),['norm']);self.assertTrue(r['passed']);self.assertEqual(r['selection']['norm'],'specialised')
 def test_exact_ten_percent_not_selected(self):self.assertEqual(aggregate(self.rows(90),['norm'])['selection']['norm'],'packet18')
 def test_slower_stays_reference(self):self.assertEqual(aggregate(self.rows(110),['norm'])['selection']['norm'],'packet18')
 def test_one_percent_bad_allowed(self):
  rows=self.rows()
  for r in rows[:4]:r['end_ns']=r['start_ns']
  out=aggregate(rows,['norm']);self.assertTrue(out['passed']);self.assertEqual(out['invalid_duration_rows'],4)
 def test_more_than_one_percent_bad_fails(self):
  rows=self.rows()
  for r in rows[:5]:r['end_ns']=r['start_ns']-1
  self.assertFalse(aggregate(rows,['norm'])['passed'])
 def test_nan_duration_counted(self):
  rows=self.rows();rows[0]['end_ns']=float('nan');self.assertEqual(aggregate(rows,['norm'])['invalid_duration_rows'],1)
 def test_nonexact_fails(self):
  rows=self.rows();rows[0]['exact']=False;self.assertFalse(aggregate(rows,['norm'])['passed'])
 def test_missing_repetition_fails(self):self.assertFalse(aggregate(self.rows()[:-1],['norm'])['passed'])
 def test_missing_class_fails(self):self.assertFalse(aggregate(self.rows(),['norm','route'])['passed'])
 def test_budget_fails(self):
  rows=self.rows();rows[0]['end_ns']=5e9;self.assertFalse(aggregate(rows,['norm'])['passed'])
 def test_partial_repetition_excluded(self):
  rows=self.rows();rows.append(dict(rows[0],start_ns=0,end_ns=0))
  r=aggregate(rows,['norm']);self.assertEqual(r['classes']['norm']['variants']['packet18']['execution_sum']['count'],199)
 def test_event_sequence_sum(self):
  rows=self.rows();rows += [dict(r) for r in rows]
  r=aggregate(rows,['norm']);self.assertTrue(r['passed']);self.assertEqual(r['classes']['norm']['variants']['specialised']['execution_sum']['median_ns'],160)
 def test_noninteger_repetition_refused(self):
  rows=self.rows();rows[0]['repetition']=True
  with self.assertRaises(ValueError):aggregate(rows,['norm'])
 def test_baseline_only_cannot_win_by_noise(self):
  rows=self.rows()
  for row in rows:row['candidate_available']=False
  result=aggregate(rows,['norm']);self.assertEqual(result['selection']['norm'],'packet18')
 def test_named_candidate_can_win(self):
  rows=self.rows()
  for row in rows:row['class']='gemv:gdn.qkv';row['candidate_available']=True;row['implementation']='p25.rows4' if row['variant']=='specialised' else 'r5'
  result=aggregate(rows,{'gemv:gdn.qkv':dict(candidate_available=False)})
  self.assertEqual(result['selection']['gemv:gdn.qkv'],'specialised')
 def test_one_format_cannot_hide_another_regression(self):
  rows=[]
  for workload,old,new in [('q6',1000,100),('q8',100,110)]:
   for row in self.rows(new):
    row.update({'class':'gemv:gdn.qkv','workload':workload,'candidate_available':True,'implementation':'p25.rows4' if row['variant']=='specialised' else 'r5'})
    if row['variant']=='packet18':row['end_ns']=row['start_ns']+old
    rows.append(row)
  result=aggregate(rows,{'gemv:gdn.qkv':{'workloads':['q6','q8']}})
  self.assertTrue(result['passed']);self.assertEqual(result['selection']['gemv:gdn.qkv'],'packet18')
 def test_missing_gemv_workload_fails(self):
  rows=self.rows()
  for row in rows:row.update({'class':'gemv:gdn.qkv','workload':'q6','candidate_available':True})
  self.assertFalse(aggregate(rows,{'gemv:gdn.qkv':{'workloads':['q6','q8']}})['passed'])
 def test_duplicate_workload_cannot_mask_missing_repetition(self):
  rows=[]
  for workload in ('q6','q8'):
   for row in self.rows():
    row.update({'class':'gemv:gdn.qkv','workload':workload,'candidate_available':True});rows.append(row)
  row=next(x for x in rows if x['workload']=='q6' and x['variant']=='specialised' and x['repetition']==0)
  row['workload']='q8'
  result=aggregate(rows,{'gemv:gdn.qkv':{'workloads':['q6','q8']}})
  self.assertFalse(result['passed']);self.assertTrue(any('missing repetitions' in x for x in result['failures']))
 def test_empty_fails(self):self.assertFalse(aggregate([],['norm'])['passed'])

class K2Failures(unittest.TestCase):
 rows=K2Summary.rows
 def test_changed_gemv_identity_still_refused(self):
  from k2_summary import summarize
  with tempfile.TemporaryDirectory(dir=w.HERE/'build') as tmp:
   root=Path(tmp);rows=[dict(r,**{'class':'gemv:test'},implementation='r5' if r['variant']=='packet18' else 'p25.rows4',candidate_available=True) for r in self.rows()]
   rows[-1]['implementation']='p25.wide8'
   (root/'events.jsonl').write_text('\n'.join(json.dumps(r) for r in rows))
   report=summarize(root,classes={'gemv:test':dict(dispatch_section='gemv',dispatch_key='test')})
   self.assertFalse(report['passed']);self.assertTrue((root/'dispatch-measured.json').exists())
 def test_failed_candidates_continue_and_write_complete_table(self):
  from k2_summary import summarize
  with tempfile.TemporaryDirectory(dir=w.HERE/'build') as tmp:
   root=Path(tmp);rows=self.rows()
   rows += [dict(r,**{'class':'route'}) for r in self.rows() if r['variant']=='packet18']
   registry={k:dict(dispatch_section='classes',dispatch_key='test.'+k) for k in ('norm','route','streams')}
   rows += [dict(r,**{'class':'streams'}) for r in self.rows() if r['variant']=='packet18']
   (root/'events.jsonl').write_text('\n'.join(json.dumps(r) for r in rows))
   (root/'candidate-failures.jsonl').write_text('\n'.join(json.dumps(dict(**{'class':k},variant='specialised',error='mismatch')) for k in ('route','streams')))
   report=summarize(root,classes=registry)
   self.assertTrue(report['passed']);self.assertEqual(set(report['classes']),set(registry))
   dispatch=json.loads((root/'dispatch-measured.json').read_text())
   self.assertEqual({k:dispatch['classes']['test.'+k] for k in registry},dict(norm='specialised',route='packet18',streams='packet18'))
   # Excluding a candidate never waives its device execution budget.
   over=dict(self.rows()[0],**{'class':'route'},variant='specialised',end_ns=5e9)
   (root/'events.jsonl').write_text('\n'.join(json.dumps(r) for r in rows+[over]))
   self.assertFalse(summarize(root,classes=registry)['passed'])
   # A missing reference remains a failure even when its candidate was excluded.
   (root/'events.jsonl').write_text('\n'.join(json.dumps(r) for r in rows if not (r['class']=='route' and r['repetition']==1)))
   self.assertFalse(summarize(root,classes=registry)['passed'])
   self.assertTrue((root/'dispatch-measured.json').exists())

class Round2Selection(unittest.TestCase):
 def check_rows(self,rows,failures=()):
  from k2_summary import summarize
  with tempfile.TemporaryDirectory(dir=w.HERE/'build') as tmp:
   root=Path(tmp);(root/'events.jsonl').write_text('\n'.join(json.dumps(r) for r in rows))
   if failures:(root/'candidate-failures.jsonl').write_text('\n'.join(json.dumps(r) for r in failures))
   return summarize(root,classes={'route':dict(incumbent='specialised',dispatch_section='classes',dispatch_key='test.route')})
 def rows(self,candidate,duration,identity=None):
  return [dict(**{'class':'route'},variant=arm,candidate=candidate,implementation='specialised' if arm=='packet18' else (identity or candidate),repetition=i,event=1,start_ns=1,end_ns=1+(100 if arm=='packet18' else duration),exact=True) for i in range(200) for arm in ('packet18','specialised')]
 def test_incumbent_not_packet18(self):
  r=self.check_rows(self.rows('round2',95));self.assertTrue(r['passed']);self.assertEqual(r['selection']['route'],'specialised')
 def test_multiple_candidates_choose_measured_winner(self):
  r=self.check_rows(self.rows('round2',80)+self.rows('third',60));self.assertTrue(r['passed']);self.assertEqual(r['selection']['route'],'third')
 def test_alias_never_admitted(self):
  r=self.check_rows(self.rows('round2',50,'specialised'));self.assertTrue(r['passed']);self.assertEqual(r['selection']['route'],'specialised');self.assertTrue(r['classes']['route']['comparisons']['round2']['same_kernel'])

class Round2AdmissionReview(unittest.TestCase):
 def evaluate(self,rows,registry,failures=()):
  from k2_summary import summarize
  with tempfile.TemporaryDirectory(dir=w.HERE/'build') as tmp:
   root=Path(tmp);(root/'events.jsonl').write_text('\n'.join(json.dumps(r) for r in rows))
   if failures:(root/'candidate-failures.jsonl').write_text('\n'.join(json.dumps(r) for r in failures))
   return summarize(root,classes={'gemv:test':registry})
 def registry(self,**changes):
  result=dict(incumbent='r5',baseline_implementation='r5',dispatch_section='gemv',dispatch_key='test',candidate_available=True,workloads=['q6','q8'],candidates=['fast','other'])
  result.update(changes);return result
 def rows(self):
  return [dict(**{'class':'gemv:test'},candidate=candidate,workload=workload,variant=arm,implementation='r5' if arm=='packet18' else candidate,candidate_available=True,repetition=i,event=i*2+(arm=='specialised'),start_ns=1,end_ns=1+(100 if arm=='packet18' else (60 if candidate=='fast' else 80)),exact=True) for candidate in ('fast','other') for workload in ('q6','q8') for arm in ('packet18','specialised') for i in range(200)]
 def test_complete_named_candidates_choose_fastest(self):
  result=self.evaluate(self.rows(),self.registry());self.assertTrue(result['passed']);self.assertEqual(result['selection']['gemv:test'],'fast')
 def test_missing_candidate_cannot_be_hidden(self):
  result=self.evaluate([r for r in self.rows() if r['candidate']=='fast'],self.registry());self.assertFalse(result['passed'])
 def test_wrong_incumbent_never_qualifies(self):
  rows=self.rows()
  for r in rows:
   if r['variant']=='packet18':r['implementation']='packet18'
  result=self.evaluate(rows,self.registry());self.assertFalse(result['passed']);self.assertEqual(result['selection']['gemv:test'],'r5')
 def test_one_workload_alias_cannot_win(self):
  rows=self.rows()
  for r in rows:
   if r['candidate']=='fast' and r['workload']=='q6' and r['variant']=='specialised':r['implementation']='r5'
  result=self.evaluate(rows,self.registry());self.assertTrue(result['passed']);self.assertEqual(result['selection']['gemv:test'],'other');self.assertTrue(result['classes']['gemv:test']['comparisons']['fast']['same_kernel_by_workload']['q6'])
 def test_declared_same_kernel_cannot_win(self):
  rows=self.rows()
  for r in rows:
   if r['candidate']=='fast' and r['variant']=='specialised':r['same_kernel']=True
  self.assertEqual(self.evaluate(rows,self.registry())['selection']['gemv:test'],'other')
 def test_partial_candidate_workload_fails(self):
  rows=[r for r in self.rows() if not(r['candidate']=='fast' and r['workload']=='q8' and r['variant']=='specialised' and r['repetition']==199)]
  self.assertFalse(self.evaluate(rows,self.registry())['passed'])
 def test_failure_excludes_only_that_candidate(self):
  rows=[r for r in self.rows() if not(r['candidate']=='fast' and r['variant']=='specialised')]
  failures=[dict(**{'class':'gemv:test'},variant='specialised',implementation='fast',workload='q6',error='fixture mismatch')]
  result=self.evaluate(rows,self.registry(),failures);self.assertTrue(result['passed']);self.assertEqual(result['selection']['gemv:test'],'other')
 def test_nonexact_incumbent_is_not_bytes_equal(self):
  rows=self.rows();rows[0]['exact']=False
  result=self.evaluate(rows,self.registry());self.assertFalse(result['passed']);self.assertFalse(result['classes']['gemv:test']['comparisons']['fast']['bytes_equal'])
 def test_duplicate_recorded_event_is_rejected(self):
  rows=self.rows();rows.append(dict(rows[0]))
  self.assertFalse(self.evaluate(rows,self.registry())['passed'])
 def test_stage_count_complete_sequence_passes(self):
  rows=self.rows()
  for row in rows:row['stage_count']=1
  self.assertTrue(self.evaluate(rows,self.registry())['passed'])
 def test_uniformly_missing_declared_stage_fails(self):
  rows=self.rows()
  for row in rows:
   if row['candidate']=='fast' and row['variant']=='specialised':row['stage_count']=2
  result=self.evaluate(rows,self.registry());self.assertFalse(result['passed']);self.assertEqual(result['selection']['gemv:test'],'other')
 def test_malformed_declared_stage_count_fails(self):
  for malformed in (True,0,-1,'1',1.5):
   rows=self.rows();rows[0]['stage_count']=malformed
   self.assertFalse(self.evaluate(rows,self.registry())['passed'])
 def test_partial_stage_count_metadata_fails(self):
  rows=self.rows();first=rows[0];first['stage_count']=2;rows.append(dict(first,event=999999,stage_count=None))
  self.assertFalse(self.evaluate(rows,self.registry())['passed'])

class RotatedSelection(unittest.TestCase):
 def rows(self,rotated_new=80,reread_new=40):
  return [dict(**{'class':'gemv:expsdown'},variant=arm,candidate='p29.down.wg32',implementation='r5' if arm=='packet18' else 'p29.down.wg32',kernel_identity='r5' if arm=='packet18' else 'p29.down.wg32',candidate_available=True,workload='expsdown',timing_mode=mode,rotation_copies=8 if mode=='rotated' else 1,buffer_copy=(i+(4 if arm=='specialised' else 0))%8 if mode=='rotated' else 0,payload_bytes=9216000,full_payload_bytes=9216000,repetition=i,event=i*2+(arm=='specialised'),stage_count=1,start_ns=1,end_ns=1+(100 if arm=='packet18' else rotated_new if mode=='rotated' else reread_new),exact=True) for mode in ('rotated','reread') for arm in ('packet18','specialised') for i in range(200)]
 def report(self,rows):
  from k2_summary import summarize
  with tempfile.TemporaryDirectory(dir=w.HERE/'build') as tmp:
   root=Path(tmp);(root/'events.jsonl').write_text('\n'.join(json.dumps(r) for r in rows))
   registry={'gemv:expsdown':dict(dispatch_section='gemv',dispatch_key='expsdown',incumbent='r5',baseline_implementation='r5',candidates=['p29.down.wg32'],workloads=['expsdown'],timing_modes=['rotated','reread'],rotation_required=True)}
   return summarize(root,classes=registry)
 def test_rotated_winner(self):
  result=self.report(self.rows());self.assertTrue(result['passed']);self.assertEqual(result['selection']['gemv:expsdown'],'p29.down.wg32')
  part=result['classes']['gemv:expsdown']['comparisons']['p29.down.wg32'];self.assertIsNotNone(part['rotated']);self.assertIsNotNone(part['reread'])
 def test_reread_only_win_not_selected(self):
  result=self.report(self.rows(rotated_new=95));self.assertTrue(result['passed']);self.assertEqual(result['selection']['gemv:expsdown'],'r5')
 def test_rotated_exact_threshold_not_selected(self):self.assertEqual(self.report(self.rows(rotated_new=90))['selection']['gemv:expsdown'],'r5')
 def test_rotation_required(self):
  self.assertFalse(self.report([r for r in self.rows() if r['timing_mode']=='reread'])['passed'])
 def test_insufficient_buffers(self):
  rows=self.rows()
  for r in rows:
   if r['timing_mode']=='rotated':r['rotation_copies']=4;r['buffer_copy']=r['repetition']%4
  self.assertFalse(self.report(rows)['passed'])
 def test_reused_buffer_refused(self):
  rows=self.rows();rows[1]['buffer_copy']=rows[0]['buffer_copy'];self.assertFalse(self.report(rows)['passed'])
 def test_truncated_payload_refused(self):
  rows=self.rows();rows[0]['payload_bytes']=9216;self.assertFalse(self.report(rows)['passed'])
 def test_reread_bad_bytes_refused(self):
  rows=self.rows();rows[-1]['exact']=False;self.assertFalse(self.report(rows)['passed'])

if __name__=='__main__':
 import contextlib
 suite=unittest.defaultTestLoader.loadTestsFromModule(__import__(__name__))
 with contextlib.redirect_stdout(io.StringIO()):result=unittest.TextTestRunner(verbosity=1).run(suite)
 (w.HERE/'k2-admission-tests.json').write_text(json.dumps({'passed':result.wasSuccessful(),'tests':result.testsRun,'device_executed':False,'synthetic_only':True},indent=2)+'\n')
 raise SystemExit(not result.wasSuccessful())
