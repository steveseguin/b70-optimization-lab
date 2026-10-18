#!/usr/bin/env python3
"""Synthetic CPU tests of K2 choice logic; no timing or speed evidence."""
import copy
import json
import unittest
from pathlib import Path
from k2_summary import resolve_fusions
from merge_dispatch import validate

HERE=Path(__file__).resolve().parent

def part(ns):
 return {'variants':{'packet18':{'execution_sum':{'median_ns':ns}},'specialised':{'execution_sum':{'median_ns':ns}}},'workloads':{},'bytes_equal':True,'candidate_failures':[]}

def fixture(fusion=19,low=10,inject=10,enabled=True):
 classes={
 'fusion:small.hc':{'dispatch_section':'fusions','dispatch_key':'small.hc','workloads':['small.hc']},
 'gemv:hc.a.low':{'dispatch_section':'gemv','dispatch_key':'hc.a.low'},
 'gemv:hc.a.inject':{'dispatch_section':'gemv','dispatch_key':'hc.a.inject'}}
 table={name:{'selected_comparison':'round2' if name.startswith('fusion:') else 'p33.dense.segment','comparisons':{'round2' if name.startswith('fusion:') else 'p33.dense.segment':part(ns)}} for name,ns in [('fusion:small.hc',fusion),('gemv:hc.a.low',low),('gemv:hc.a.inject',inject)]}
 for suffix in ('low','inject'):
  classes['gemv:hc.f.'+suffix]={'dispatch_section':'gemv','dispatch_key':'hc.f.'+suffix}
  table['gemv:hc.f.'+suffix]=copy.deepcopy(table['gemv:hc.a.'+suffix])
 dispatch={'schema':'packet26.dispatch.v1','classes':{},'gemv':{'hc.a.low':'p33.dense.segment','hc.a.inject':'p33.dense.segment','hc.f.low':'p33.dense.segment','hc.f.inject':'p33.dense.segment','hc.low':'p33.dense.segment'},'fusions':{'small.hc':'round2' if enabled else 'packet18'}}
 return dispatch,table,classes

class Selection(unittest.TestCase):
 def resolve(self,*args,**kw):
  d,t,c=fixture(*args,**kw);result=resolve_fusions(d,t,c);validate(d);return result,d
 def test_fusion_compares_with_sum(self):
  result,d=self.resolve();self.assertEqual(result[0]['selected'],'fusion');self.assertEqual(result[0]['comparisons'][0]['selected_members_ns'],20)
 def test_faster_members_win(self):
  result,d=self.resolve(fusion=21);self.assertEqual(result[0]['selected'],'members');self.assertEqual(d['gemv']['hc.a.low'],'p33.dense.segment')
 def test_tie_selects_members(self):self.assertEqual(self.resolve(fusion=20)[0][0]['selected'],'members')
 def test_disabled_candidate_reconsidered(self):self.assertEqual(self.resolve(enabled=False)[0][0]['selected'],'fusion')
 def test_no_conflict_still_compared(self):
  d,t,c=fixture(fusion=21);d['gemv']={k:'r5' for k in d['gemv']};self.assertEqual(resolve_fusions(d,t,c)[0]['selected'],'members')
 def test_aliases_not_double_counted(self):self.assertEqual(self.resolve()[0][0]['comparisons'][0]['selected_members_ns'],20)
 def test_both_hc_sites_must_win(self):
  d,t,c=fixture();t['gemv:hc.f.low']['comparisons']['p33.dense.segment']=part(1)
  self.assertEqual(resolve_fusions(d,t,c)[0]['selected'],'members')
 def test_failed_candidate_disabled(self):
  d,t,c=fixture();t['fusion:small.hc']['comparisons']['round2']['bytes_equal']=False;self.assertEqual(resolve_fusions(d,t,c)[0]['selected'],'members')
 def test_missing_member_fails_closed(self):
  d,t,c=fixture();del t['gemv:hc.a.low']
  with self.assertRaises(ValueError):resolve_fusions(d,t,c)
 def test_nonfinite_member_fails_closed(self):
  d,t,c=fixture(low=float('nan'))
  with self.assertRaises(ValueError):resolve_fusions(d,t,c)
 def test_all_formats_must_win(self):
  d,t,c=fixture();c['fusion:small.hc']['workloads']=['small.hc.q6','small.hc.q8'];t['fusion:small.hc']['comparisons']['round2']['workloads']={'small.hc.q6':part(19),'small.hc.q8':part(21)}
  self.assertEqual(resolve_fusions(d,t,c)[0]['selected'],'members')
 def test_registry_p33_closed(self):
  reg=json.loads((HERE/'kernel-registry.json').read_text())
  for name,values in reg['gemv'].items():self.assertIn('p33.gate.restrict' if name=='expsgate' else 'p33.down.select' if name=='expsdown' else 'p33.dense.segment',values)
  self.assertIn('p33.down.bank',reg['gemv']['expsdown']);self.assertIn('p33.qsa.shape',reg['classes']['qsa.attention'])
 def test_registry_incumbents_and_candidates(self):
  c=json.loads((HERE/'k2-class-registry.json').read_text())['classes'];base=json.loads((HERE/'dispatch-incumbent.json').read_text())
  for name,row in c.items():
   if name.startswith('gemv:'):
    self.assertEqual(row['baseline_implementation'],base['gemv'].get(row['dispatch_key'],'r5'))
    self.assertEqual(len(row['candidates']),len(set(row['candidates'])))

if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Selection))
 (HERE/'k2-selection-tests.json').write_text(json.dumps({'passed':result.wasSuccessful(),'tests':result.testsRun,'device_executed':False,'synthetic_only':True},indent=2)+'\n')
 raise SystemExit(not result.wasSuccessful())
