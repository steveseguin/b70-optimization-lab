"""Hand-computed accounting and manifest/oracle CPU guards; never starts ranks."""
import ast,hashlib,json,unittest
from pathlib import Path
from unittest.mock import patch
import pipeline,suite,suite_metrics as m
P=Path(__file__).resolve().parent
class Metrics(unittest.TestCase):
 def request(self,n=128,step=.25,eos=False,retain='none',device=True):
  tokens=[7]*n
  if eos:tokens[-1]=248044
  result=dict(tokens=tokens,timing_rows=[dict(token_id=t,completed_monotonic=10+i*step) for i,t in enumerate(tokens)])
  return m.request_metrics(result,80,128,retain,8,100,device)
 def test_hand_computed_reference(self):
  r=self.request();self.assertEqual(r['reference64']['first'],10);self.assertEqual(r['reference64']['last'],25.75)
  self.assertEqual(r['reference64']['numerator'],63);self.assertEqual(r['decode_tok_s'],63/15.75)
 def test_hand_computed_submission(self):
  r=self.request();self.assertEqual(r['submission100']['last'],34.75)
  self.assertEqual(r['submission100']['numerator'],99);self.assertEqual(r['tok_s_1_100_intervals_after_ttft'],99/24.75)
 def test_nonuniform_is_span_not_median_instant_rate(self):
  points=[0.,1.,2.,6.];self.assertEqual(m.window(points,4)['rate'],3/6)
  self.assertNotEqual(m.window(points,4)['rate'],m.median([1,1,1/4]))
 def test_eos_event64_fixed_valid_historical_63(self):
  r=self.request(64,eos=True);self.assertEqual(r['fixed64_tok_s'],4);self.assertEqual(r['reference64']['event_count'],64);self.assertEqual(r['reference_table']['event_count'],63)
 def test_eos_event_100_submission_valid(self):
  r=self.request(100,eos=True);self.assertTrue(r['submission100']['complete']);self.assertEqual(r['tok_s_1_100_intervals_after_ttft'],4)
 def test_eos_before100_submission_null(self):self.assertIsNone(self.request(99,eos=True)['tok_s_1_100_intervals_after_ttft'])
 def test_reference_early_eos(self):
  r=self.request(3,eos=True);self.assertEqual(r['reference_table']['event_count'],2);self.assertEqual(r['decode_tok_s'],4)
 def test_fixed64_short_null(self):
  r=self.request(63);self.assertIsNone(r['fixed64_tok_s']);self.assertFalse(r['reference64']['complete']);self.assertEqual(r['reference_table']['rate'],4)
 def test_late_timestamp_invalid(self):
  result=dict(tokens=[7]*128,timing_rows=[dict(completed_monotonic=float(i)) for i in range(128)])
  result['timing_rows'][-1]['completed_monotonic']=float('nan')
  with self.assertRaises(ValueError):m.request_metrics(result,80,128,'none')
 def test_timestamp_count_mismatch(self):
  with self.assertRaises(ValueError):m.request_metrics(dict(tokens=[7],timing_rows=[]),80,128,'none')
 def test_immediate_eos_reference_null(self):self.assertIsNone(self.request(1,eos=True)['decode_tok_s'])
 def test_retention_diagnostic(self):
  for retain in ('1-8','1-8,97-104'):
   r=self.request(retain=retain);self.assertTrue(r['diagnostic']);self.assertIsNone(r['decode_tok_s']);self.assertFalse(r['metric_window_eligible']);self.assertEqual(r['submission100']['rate'],4)
 def test_cpu_no_speed(self):self.assertIsNone(self.request(device=False)['decode_tok_s'])
 def test_ttft_wall(self):
  r=self.request(100);self.assertEqual(r['ttft_ms'],2000);self.assertEqual(r['wall_tok_s'],100/26.75)
 def test_guards(self):
  for stamps in ([0,0],[1,0],[0,float('nan')],[0,float('inf')]):
   with self.assertRaises(ValueError):m.window(stamps,2)
 def test_class_aggregation_hand_computed(self):
  # code median 2, prose median 20 => class median 11; all-prompt median 3.
  rows=[dict(prompt_id=str(i),repeat=1,passed=True,prompt_class=c,decode_tok_s=v,tok_s_1_100_intervals_after_ttft=v) for i,(c,v) in enumerate([('code',1),('code',2),('code',3),('prose',20)])]
  r=m.aggregate(rows);self.assertEqual(r['class_balanced_tok_s_1_100_intervals_after_ttft']['median'],11)
  self.assertEqual(r['submission100_statistics']['median'],2.5)
 def test_repeats_not_pooled_for_primary(self):
  rows=[dict(prompt_id='x',repeat=i,passed=True,prompt_class='code',decode_tok_s=v,tok_s_1_100_intervals_after_ttft=v) for i,v in [(1,10),(2,100)]]
  r=suite.summarize(rows,False);self.assertEqual(r['decode_median_tok_s'],10);self.assertEqual(r['reference_table_pooled_observed_median_tok_s'],55)
  self.assertEqual(r['repeat_decode_medians'],{'1':10,'2':100});self.assertFalse(r['realistic_final_gate']['passed'])
 def test_partial_manifest_even_complete_flag(self):
  r=suite.summarize([dict(prompt_id='x',repeat=1,passed=True)],True)
  self.assertTrue(r['partial_suite']);self.assertFalse(r['complete'])
 def test_retention_ranges(self):
  self.assertEqual(pipeline.retention_steps('none',128),[])
  self.assertEqual(pipeline.retention_steps('1-8,97-104',100),list(range(1,9))+list(range(97,101)))
  for value in ('','0','9-2','-1','all','1,,2','1-9999999999'):
   with self.assertRaises(ValueError):pipeline.retention_steps(value,128)
 def test_suite_cap_prefix(self):
  self.assertEqual(m.admit_cap(dict(arithmetic='iq3-p17-detmath-v2',token_cap=64),32),64)
  self.assertEqual(m.admit_cap(dict(arithmetic='iq3-p17-detmath-v2',token_cap=128),32),128)
  with self.assertRaises(ValueError):m.admit_cap(dict(arithmetic='iq3-p17-detmath-v2',token_cap=128),129)
 def test_retention_canonical(self):
  self.assertEqual(pipeline.canonical_retention('5-8,1-4,1-8',64),'1-8')
  self.assertEqual(pipeline.canonical_retention('97-104',64),'none')
  self.assertEqual(pipeline.canonical_retention('1-8,97-104',100),'1-8,97-100')
  for value in ('1-8,1-8','8,7,6,5,4,3,2,1'):
   self.assertEqual(pipeline.retention_steps(pipeline.canonical_retention(value,4),4),[1,2,3,4])
 def test_max_new_alias(self):
  args=pipeline.parser().parse_args(['--output','unused','--max-new','128','--retain-steps','none'])
  self.assertEqual(args.tokens,128);self.assertEqual(args.retain_steps,'none')
 def test_max_new_guards(self):
  for n in ('0','-1','257'):
   with self.assertRaises(ValueError):pipeline.parser().parse_args(['--output','unused','--max-new',n])
 def test_class_map_matches_repository(self):
  tree=ast.parse((suite.ROOT/'scripts/qualify_realistic_window_metrics.py').read_text())
  mapping=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PROMOTION_PROMPT_CLASSES' for t in n.targets))
  self.assertEqual(m.PROMPT_CLASSES,mapping)
 def test_manifest_and_all_token_oracles(self):
  for cap in (64,128):
   path=suite.ROOT/f'experiments/own-xpu-runtime/stage2/suite-inputs-20261012{"-cap128" if cap==128 else ""}/suite-manifest.json'
   manifest=json.loads(path.read_text());self.assertEqual(len(manifest['prompts']),12)
   checker=suite.checker_module(suite.CHECKER if cap==64 else suite.CHECKER.parent.with_name('arithmetic-v2-detmath-20261012-suite128')/'suite_check.py')
   for entry in manifest['prompts']:
    oracle=suite.ROOT/entry['oracle_directory'];tokens=checker.token_record(oracle)
    result=dict(passed=True,tokens=tokens,requested_max_new=cap,retain_steps='none')
    suite.compare_request(P,result,entry,checker);self.assertTrue(result['passed']);self.assertEqual(result['oracle_check']['tokens'],len(tokens))
    bad=dict(result,tokens=tokens[:-1]+[tokens[-1]^1]);suite.compare_request(P,bad,entry,checker);self.assertFalse(bad['passed'])
    prefix=dict(passed=True,tokens=tokens[:32],requested_max_new=32,retain_steps='none');suite.compare_request(P,prefix,entry,checker);self.assertTrue(prefix['passed'])
 def test_fixture_failure_does_not_abort_next(self):
  with patch.object(suite,'collect_fixtures',side_effect=[ValueError('missing fixture'),None,None]) as collect:
   rows=[suite.collect_request_fixtures(P,dict(passed=True,tokens=[7]),True,'1-8') for _ in range(3)]
  self.assertEqual([r['passed'] for r in rows],[False,True,True]);self.assertEqual(collect.call_count,3)
 def test_comparison_failure_does_not_abort_next(self):
  class Checker:
   source_sha256='fake'
   def token_record(self,p):return [7]
  entry=dict(oracle_directory='fake',oracle_receipt_sha256='a')
  with patch.object(pipeline,'sha',return_value='a'),patch.object(Path,'read_text',return_value='{"result_sha256":"a"}'):
   outcomes=[suite.compare_request(P,dict(passed=True,tokens=t,requested_max_new=1,retain_steps='none'),entry,Checker())['passed'] for t in ([8],[7],[7])]
  self.assertEqual(outcomes,[False,True,True])
if __name__=='__main__':
 test=unittest.defaultTestLoader.loadTestsFromTestCase(Metrics);r=unittest.TextTestRunner(verbosity=2).run(test)
 receipt=dict(passed=r.wasSuccessful(),gates=r.testsRun,failures=len(r.failures),errors=len(r.errors),device_executed=False,rank_processes_started=0,
  source_sha256={n:hashlib.sha256((P/n).read_bytes()).hexdigest() for n in ('suite.py','suite_metrics.py','pipeline.py','test_suite_metrics.py')})
 (P/'suite-metric-gates.json').write_text(json.dumps(receipt,indent=2)+'\n')
 raise SystemExit(not r.wasSuccessful())
