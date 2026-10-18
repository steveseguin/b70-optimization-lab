import copy,json,math,unittest
from source_decision import P,O,selections
from verify_ready import qualify_bracket
class Policy(unittest.TestCase):
 def row(self):
  views=[dict(index=i,choice='candidate' if i%2 else 'control',lane='B',all_13_exact=True,exact_count=13,rate=r,acceptance_counts=[{'hits':7,'guesses':9}],draft_proposals={'p':'hash'}) for i,r in enumerate((100,101.6,101,101.6,100.5))]
  return dict(result=dict(passed=True,kind='bracket',model_lifetimes=1,views=views),selection_sha256='s',window_sha256='w',summary_sha256='r',evidence_path='fixture')
 def test_boundary(self):
  row=self.row();self.assertTrue(qualify_bracket(row)['passed'])
  row['result']['views'][1]['rate']=101*1.005;self.assertTrue(qualify_bracket(row)['passed'])
 def test_refusals(self):
  for key,value in [('rate',101.4),('all_13_exact',False),('lane','A'),('acceptance_counts',[]),('draft_proposals',{})]:
   row=self.row();row['result']['views'][1][key]=value
   with self.assertRaises(AssertionError):qualify_bracket(row)
  for rate in (101.0001,float('nan'),float('inf'),-1,True):
   row=self.row();row['result']['views'][2]['rate']=rate
   with self.assertRaises(AssertionError):qualify_bracket(row)
  row=self.row();row['result']['model_lifetimes']=5
  with self.assertRaises(AssertionError):qualify_bracket(row)
 def test_ignores_stored_verdict(self):
  row=self.row();row['result'].update(candidate_qualified=True,control_drift_percent=0,strict_gain_percent=99);row['result']['views'][1]['rate']=100
  with self.assertRaises(AssertionError):qualify_bracket(row)
 def test_composition(self):
  from bundle_selection import aliases,selection
  self.assertEqual(selection(aliases()['both']),json.loads((P.with_name('packet137-token-input')/'v5/lineage/candidate.json').read_text()))
  a,b=selections();self.assertEqual({k:v for k,v in a.items() if k!='token_input'},{k:v for k,v in b.items() if k!='token_input'})
 def test_unit_and_environment(self):
  from bootstrap import install
  install()
  import smoke_screen
  from proposal_plan import proposal
  import lanequeue
  from confirm136 import LIBRARIES
  from pathlib import Path
  from common import W
  job=proposal()[0];cmd=lanequeue.command(job,'/cpu-review',Path('/tmp/cpu-receipt.json'),LIBRARIES)
  unit=next(x.split('=',1)[1] for x in cmd if x.startswith('--unit='))+'.service'
  smoke_screen.unit_gate('0::/user@1000.service/'+unit)
  with self.assertRaises(ValueError):smoke_screen.unit_gate('0::/user@1000.service/'+job['name']+'.service')
  env=lanequeue.closed_env(LIBRARIES);W.closed_environment(env)
  for extra in ('PYTHONDONTWRITEBYTECODE','UNREGISTERED_TOKEN_INPUT'):
   with self.assertRaises(ValueError):W.closed_environment(dict(env,**{extra:'1'}))
 def test_notes_follow_ledger(self):
  from submission_evidence import submission_notes
  bundle=json.loads((P/'bundle-selection.json').read_text())
  for name,rate in [('bundle8-posted-id',59.8),('previous-record-id',58.223834)]:
   text=submission_notes(bundle,dict(reference_submission=name,threshold_tok_s=rate));self.assertIn(name,text);self.assertIn(str(rate),text);self.assertIn('bundle9',text);self.assertNotIn('cmvdx8urg0068rf01vvb32bcs',text)
if __name__=='__main__':unittest.main()
