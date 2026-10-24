import copy,importlib.util,json,unittest
from pathlib import Path
P=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('coverage_closed_audit',P/'audit.py');A=importlib.util.module_from_spec(s);s.loader.exec_module(A)
class Auditor(unittest.TestCase):
 def test_raw_precedes_enrichment_and_separate_decode_join(self):
  raw={'request':1,'result':{'tokens':[2,3]}};full=dict(raw,decoded_text='retained text',quality={'automated_passed':None},prefix_baseline_exact=True)
  decoded=dict(tokens=[2,3],text='retained text',quality=full['quality'],skip_special_tokens=False)
  A.join_raw(full,raw,decoded)
  broken=copy.deepcopy(raw);broken['result']['tokens'][1]=4
  with self.assertRaises(ValueError):A.join_raw(full,broken,decoded)
  decoded['text']='filtered text'
  with self.assertRaises(ValueError):A.join_raw(full,raw,decoded)
 def test_exact_admitted_plan_startup_vs_requests(self):
  p=json.loads((P/'launch-b/evidence/device-b/plan.json').read_text());A.startup_request_distinction(p)
  for layer in (p,p['suite'],p['adapter']):
   old=layer['startup_max_new'];layer['startup_max_new']=512
   with self.assertRaises(ValueError):A.startup_request_distinction(p)
   layer['startup_max_new']=old
  p['adapter']['rank_argv'][0][p['adapter']['rank_argv'][0].index('--max-new')+1]='512'
  with self.assertRaises(ValueError):A.startup_request_distinction(p)
 def test_quality_failure_retained_without_answer_repair(self):
  case=json.loads((P/'manifest.json').read_text())['cases'][2];good=json.dumps(case['rubric']['expected'])
  self.assertTrue(A.rubric_check(case,good,[],lambda _: '')['automated_passed'])
  self.assertFalse(A.rubric_check(case,good.replace('H7','H8'),[],lambda _: '')['automated_passed'])
  self.assertFalse(A.rubric_check(case,'```json\n'+good+'\n```',[],lambda _: '')['automated_passed'])
  self.assertTrue(A.rubric_check(case,good+'<EOS>',[248046],lambda _:'<EOS>')['automated_passed'])
 def test_early_eos_and_cap_are_distinct(self):
  r=dict(tokens=[2,248046],timing_rows=[dict(generated_index=1,token_id=2,completed_monotonic=1.),dict(generated_index=2,token_id=248046,completed_monotonic=1.5)],decode_intervals=1,decode_numerator=1,decode_wall_ms=500,prompt_wall_ms=1)
  self.assertEqual(A.B.timing(r,512)['termination'],'eos')
  r['tokens'][1]=3;r['timing_rows'][1]['token_id']=3
  self.assertEqual(A.B.timing(r,2)['termination'],'cap')
  with self.assertRaises(ValueError):A.B.timing(r,512)
if __name__=='__main__':unittest.main(verbosity=2)
