"""CPU-only orchestration and real-local-tokenizer checks; no model endpoint."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch
import engine
import materials
import runner

class PortableTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  for relative,data in materials.input_bytes().items():
   p=self.root/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
  self.cases=materials.cases_from(self.root)
 def test_exact_matrix_tasks_questions_and_pins(self):
  rows=materials.expected_rows(self.cases)
  self.assertEqual([(r['case_id'],r['condition']) for r in rows],list(materials.ORDER))
  self.assertEqual(set(self.cases),{'t01-clinic','t02-theatre'})
  full=engine.compiler().load_packet(self.root/'source/documents.json',self.root/'source/adjudicated.json')
  self.assertEqual({t['document_id']:t for t in full if t['document_id'] in self.cases},{n:c['task'] for n,c in self.cases.items()})
  for row in rows:
   self.assertEqual((row['arm'],row['retrieval_mode']),materials.CONDITIONS[row['condition']])
   self.assertEqual(row['question_sha256'],engine.compiler().digest(self.cases[row['case_id']]['task']['questions']))
  for name in ('documents.json','adjudicated.json','annotations-independent.json','annotations-review.json'):
   p=self.root/'source'/name;old=p.read_bytes();p.write_bytes(old+b' ')
   with self.assertRaises(ValueError):materials.cases_from(self.root)
   p.write_bytes(old)
 def test_caps_no_api_bypass_and_no_auto_extension(self):
  self.assertEqual((runner.POLICY['context_limit_utf8_bytes'],runner.POLICY['memory_limit_utf8_bytes'],runner.POLICY['max_retrieval'],runner.POLICY['max_answer_calls']),(32768,6553,24,32))
  self.assertFalse(runner.CONTINUATION_RULE['automatic_extension'])
  self.assertEqual(runner.CONTINUATION_RULE['history_to_source_elapsed_max_ratio'],0.9)
  with self.assertRaises(ValueError):runner.execute(self.root,self.root/'bad',stub=1)
  with self.assertRaises(ValueError):runner.execute(self.root,self.root/'bad',stub=False)
 def test_owned_cpu_worker_cancellation(self):
  child=Mock();child.communicate.side_effect=runner.StopRequested('cancel');child.poll.return_value=None
  child.wait.side_effect=[subprocess.TimeoutExpired('owned',5),0]
  with patch.object(runner.subprocess,'Popen',return_value=child):
   with self.assertRaises(runner.StopRequested):runner.run_owned(['owned-cpu-worker'])
  child.terminate.assert_called_once();child.kill.assert_called_once();self.assertEqual(child.wait.call_count,2)
 def test_raw_action_counts_and_missing_cache(self):
  calls=[{'phase':'answer','response':json.dumps(reply),'seconds':1,'prompt_bytes':10,'usage':{}} for reply in
         [{'action':'state_at','batch_id':1},{'action':'state_at','batch_id':1},{'action':'submit','answers':{}}]]
  native={'answer_protocol':{'cache':{'state_at:{"batch_id":1,"counters":null}':{}},'calls':3},'failure':None}
  (self.root/'retrieval.jsonl').write_text('\n'.join(json.dumps({'action':'state_at','batch_id':1,'state':{}}) for _ in range(2)))
  counts=runner.action_counts(calls,native,self.root)
  self.assertEqual(counts['requested_actions']['state_at'],2);self.assertEqual(counts['successful_distinct_retrievals']['state_at'],1)
  self.assertEqual(counts['repeated_retrieval_responses']['state_at'],1)
  self.assertFalse(runner.phase_costs(calls,1)['total']['cache_complete']);self.assertIsNone(runner.phase_costs(calls,1)['total']['cached_tokens'])
  for v in (True,-1,float('nan'),float('inf')):
   with self.assertRaises(ValueError):runner.finite_seconds(v)

@unittest.skipUnless(runner.DEFAULT_TOKENIZER.is_file() and runner.DEFAULT_PYTHON.is_file(),'actual local tokenizer/interpreter required; no fabricated measurements')
class LocalTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name);cls.packet=cls.root/'packet';cls.bundle=runner.prepare(cls.packet)
 @classmethod
 def tearDownClass(cls):cls.temp.cleanup()
 def test_actual_tokenizer_full_retrieval_schedule_fits(self):
  budget=self.bundle['budget'];self.assertTrue(budget['all_reference_prompts_fit']);self.assertTrue(budget['all_reference_emissions_fit'])
  self.assertEqual(len(budget['trials']),8)
  for row in budget['trials']:
   self.assertEqual(row['phases']['answer']['calls'],22 if row['retrieval_mode']=='history' else 13)
   for phase,metrics in row['phases'].items():
    self.assertLessEqual(metrics['max_prompt_bytes_with_ascii_memory_allowance'],32768)
    self.assertLessEqual(metrics['max_reference_response_tokens'],8192 if phase=='answer' else 4096)
    self.assertLessEqual(metrics['max_response_tokens_with_ascii_memory_allowance'],8192 if phase=='answer' else 4096)
 def test_plan_policy_mode_question_and_order_tampering(self):
  p=self.packet/'plan.json';saved=p.read_bytes();plan=json.loads(saved)
  for change in (lambda p:p['trials'].reverse(),lambda p:p['trials'][0].update(retrieval_mode='history'),lambda p:p['trials'][0].update(question_sha256='0'*64),lambda p:p.update(expected_trials=8.0),lambda p:p.update(max_answer_calls=33),lambda p:p['continuation_rule'].update(automatic_extension=True)):
   altered=copy.deepcopy(plan);change(altered);p.write_text(json.dumps(altered))
   try:
    with self.assertRaises(ValueError):runner.validate_packet(self.packet)
   finally:p.write_bytes(saved)
 def test_eight_fresh_stubs_never_admit_model_quality_or_extension(self):
  out=self.root/'gold';summary=runner.execute(self.packet,out,stub=True)
  self.assertEqual(summary['observed_trials'],8);self.assertEqual(summary['completed_trials'],8);self.assertEqual(summary['unstarted_trials'],[])
  self.assertFalse(summary['extension_admitted']);self.assertFalse(summary['continuation_evaluated'])
  for row in summary['trials']:
   outer=json.loads((out/row['result_path']).read_bytes());native=json.loads((out/row['native_result_path']).read_bytes())
   self.assertTrue(outer['reference_checks_passed']);self.assertTrue(outer['snapshot_audit']['integrity_passed'])
   self.assertFalse(outer['quality_passed']);self.assertFalse(outer['cold_cost_interpretation']);self.assertEqual(outer['measurement_kind'],'stub')
   self.assertEqual(native['retrieval_mode'],row['retrieval_mode']);self.assertEqual(native['processed_batches'],12)
   self.assertEqual(outer['score']['correct'],24);self.assertEqual(outer['action_counts']['requested_actions']['submit'],1)
   self.assertEqual(set(outer['native_auxiliary']),{'canonical.sqlite','identity.json'})
 def inject_first_failure(self,infra):
  original=runner.run_owned;seen=[]
  def injected(argv,**kwargs):
   if str(engine.HERE/'engine.py') not in argv:return original(argv,**kwargs)
   seen.append(argv)
   if len(seen)>1:return original(argv,**kwargs)
   get=lambda flag:argv[argv.index(flag)+1]
   code="""import sys,json
from pathlib import Path
sys.path.insert(0,sys.argv[1]);import live
class Failing(live.StubClient):
 def __call__(self,*args):
  if sys.argv[6]=='infra':raise live.InfrastructureError('CPU fixture fault')
  return '{',{}
task=json.loads(Path(sys.argv[2]).read_bytes())
live.run_trial(task,sys.argv[3],Path(sys.argv[4]),Failing(task),retrieval_mode=sys.argv[5])
"""
   return original([sys.executable,'-c',code,str(engine.ENGINE),get('--task'),get('--arm'),get('--out'),get('--retrieval-mode'),'infra' if infra else 'bounded'],**kwargs)
  return seen,injected
 def test_bounded_failure_continues_all_eight_rows(self):
  seen,worker=self.inject_first_failure(False);out=self.root/'bounded'
  with patch.object(runner,'run_owned',side_effect=worker):summary=runner.execute(self.packet,out,stub=True)
  self.assertEqual(len(seen),8);self.assertEqual(summary['observed_trials'],8);self.assertEqual(summary['failed_trials'],1)
  self.assertEqual(summary['completed_trials'],7);self.assertFalse(summary['infrastructure_abort']);self.assertEqual(summary['unstarted_trials'],[])
 def test_infrastructure_failure_preserves_partial_and_seven_unstarted(self):
  seen,worker=self.inject_first_failure(True);out=self.root/'infra'
  with patch.object(runner,'run_owned',side_effect=worker):
   with self.assertRaises(RuntimeError):runner.execute(self.packet,out,stub=True)
  summary=json.loads((out/'summary.json').read_bytes());self.assertEqual(len(seen),1);self.assertTrue(summary['infrastructure_abort'])
  self.assertEqual(len(summary['trials']),8);self.assertEqual(len(summary['unstarted_trials']),7);self.assertEqual(summary['failed_trials'],1)
  row=summary['trials'][0];self.assertTrue((out/row['native_result_path']).is_file());self.assertTrue((out/row['result_path']).is_file())
 def test_tampered_snapshot_and_unsafe_artifact_refused(self):
  item=self.bundle['plan']['trials'][0];out=self.root/'tamper';task=self.bundle['tasks'][item['case_id']]
  result=runner.run_owned([sys.executable,str(engine.HERE/'engine.py'),'--task',str(self.packet/item['task_path']),'--out',str(out),'--arm',item['arm'],'--retrieval-mode',item['retrieval_mode'],'--stub'])
  self.assertEqual(result.returncode,0);native=json.loads((out/'result.json').read_bytes())
  bad=copy.deepcopy(native);bad['artifacts']['calls.jsonl']['path']='../escape'
  with self.assertRaises(ValueError):runner.audit_native(out,bad,task,item,self.bundle['plan'],None,'stub')
  (out/'snapshots/batch-2.json').write_text('{}')
  with self.assertRaises(ValueError):runner.audit_native(out,native,task,item,self.bundle['plan'],None,'stub')

if __name__=='__main__':unittest.main()
