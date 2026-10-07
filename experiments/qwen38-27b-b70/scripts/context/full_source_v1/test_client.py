import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,Mock
import client

class ClientTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  self.packet=self.root/'packet';self.bundle=client.prepare(self.packet);self.task=self.bundle['tasks']['t01-clinic']
  self.identity=self.root/'identity.json';self.identity.write_text('{"cpu_fixture":true}')
 def envelope(self,answers=None,finish='stop',usage=None,content=None):
  reply={'action':'submit','answers':self.task['oracle']['answers'] if answers is None else answers}
  return client.encoded({'choices':[{'finish_reason':finish,'message':{'content':json.dumps(reply) if content is None else content,'reasoning_content':'CPU fixture only'}}], 'usage':usage})
 def exchange_for(self,kind):
  seen=[]
  def exchange(endpoint,raw):
   case=client.CASES[len(seen)];seen.append(raw);task=self.bundle['tasks'][case]
   if kind=='infra' and len(seen)==1:return b'bad gateway',{'http_status':502,'error':'HTTP 502'}
   if kind=='envelope' and len(seen)==1:return b'{}',{'http_status':200,'error':None}
   content='{' if kind=='malformed' and len(seen)==1 else json.dumps({'action':'submit','answers':task['oracle']['answers']})
   finish='length' if kind=='capped' and len(seen)==1 else 'stop'
   return self.envelope(finish=finish,content=content),{'http_status':200,'error':None}
  return seen,exchange
 def run_fake(self,kind):
  seen,exchange=self.exchange_for(kind);out=self.root/kind
  with patch.object(client,'exchange',side_effect=exchange):result=client.execute(self.packet,out,'http://localhost:9999/v1','qwen38-27b-fp8',self.identity)
  return out,result,seen
 def test_packet_exact_source_and_no_reference_leak(self):
  self.assertEqual([r['case_id'] for r in self.bundle['plan']['trials']],list(client.CASES))
  for row in self.bundle['plan']['trials']:
   raw=(self.packet/row['request_path']).read_bytes();request=json.loads(raw);public=json.loads(request['messages'][1]['content'])
   self.assertEqual(client.digest(request),row['request_sha256']);self.assertEqual(len(public['questions']),24)
   self.assertEqual(set(public),{'instruction','reading_conventions','batches','questions'});self.assertEqual(len(public['batches']),12)
  path=self.packet/'t01-clinic-request.json';path.write_bytes(path.read_bytes()+b' ')
  with self.assertRaises(ValueError):client.validate_packet(self.packet)
 def test_policy_and_question_tamper(self):
  path=self.packet/'plan.json';original=path.read_bytes();plan=json.loads(original)
  for change in (lambda x:x.update(request_deadline_seconds=601),lambda x:x['trials'].reverse(),lambda x:x['trials'][0].update(question_sha256='x')):
   bad=copy.deepcopy(plan);change(bad);path.write_text(json.dumps(bad))
   with self.assertRaises(ValueError):client.validate_packet(self.packet)
   path.write_bytes(original)
 def test_stub_never_model_success_or_cold(self):
  out=self.root/'stub';summary=client.execute(self.packet,out,stub=True)
  self.assertEqual(summary['completed_trials'],2);self.assertFalse(summary['infrastructure_abort'])
  for row in summary['trials']:
   result=json.loads((out/row['result_path']).read_bytes());timing=json.loads((out/row['timing_path']).read_bytes())
   self.assertFalse(result['final_task_success']);self.assertFalse(result['cold_cost_interpretation'])
   self.assertEqual(result['response']['score']['correct'],24);self.assertIsNone(result['checkpoint_quality']);self.assertIsNone(result['event_quality'])
   self.assertEqual(timing['result_sha256'],client.sha(out/row['result_path']));self.assertGreaterEqual(timing['task_seconds'],timing['request_seconds'])
 def test_malformed_model_content_continues_second(self):
  out,summary,seen=self.run_fake('malformed');self.assertEqual(len(seen),2);self.assertEqual(summary['failed_trials'],1)
  self.assertEqual(summary['completed_trials'],1);self.assertFalse(summary['infrastructure_abort'])
  self.assertEqual(seen,[(self.packet/r['request_path']).read_bytes() for r in self.bundle['plan']['trials']])
 def test_capped_response_preserves_score_but_cannot_pass(self):
  out,summary,seen=self.run_fake('capped');result=json.loads((out/'t01-clinic/result.json').read_bytes())
  self.assertEqual(result['response']['score']['correct'],24);self.assertFalse(result['final_task_success']);self.assertEqual(result['status'],'failed');self.assertEqual(len(seen),2)
 def test_unknown_cache_not_zero(self):
  out,summary,seen=self.run_fake('complete');result=json.loads((out/'t01-clinic/result.json').read_bytes())
  self.assertTrue(result['final_task_success']);self.assertFalse(result['cold_cost_interpretation']);self.assertIsNone(result['response']['cache_usage']['cached_tokens'])
  for cached in (None,True,-1,101):
   self.assertFalse(client.cache_usage({'prompt_tokens':100,'prompt_tokens_details':{'cached_tokens':cached}})['complete'])
  self.assertEqual(client.cache_usage({'prompt_tokens':100,'prompt_tokens_details':{'cached_tokens':0}}),{'complete':True,'cached_tokens':0})
 def test_inconsistent_usage_preserves_correct_answers_but_disqualifies_cost(self):
  good={'prompt_tokens':100,'completion_tokens':20,'total_tokens':120,
        'prompt_tokens_details':{'cached_tokens':0},'completion_tokens_details':{'reasoning_tokens':15}}
  bad=[]
  for key,value in (('prompt_tokens',True),('completion_tokens',-1),('total_tokens',119),('total_tokens',None)):
   usage=copy.deepcopy(good);usage[key]=value;bad.append(usage)
  for key,value in (('cached_tokens',101),('cached_tokens',False),('cached_tokens',None)):
   usage=copy.deepcopy(good);usage['prompt_tokens_details'][key]=value;bad.append(usage)
  for value in (21,True,-1,None):
   usage=copy.deepcopy(good);usage['completion_tokens_details']['reasoning_tokens']=value;bad.append(usage)
  usage=copy.deepcopy(good);del usage['completion_tokens'];bad.append(usage)
  for usage in bad:
   self.assertFalse(client.usage_accounting_complete(usage))
   self.assertTrue(client.parse_response(self.envelope(usage=usage),self.task)['reference_final_exact'])
  self.assertTrue(client.usage_accounting_complete(good))
  optional=copy.deepcopy(good);del optional['total_tokens'];del optional['completion_tokens_details']
  self.assertTrue(client.usage_accounting_complete(optional))
  seen=[]
  def exchange(endpoint,raw):
   task=self.bundle['tasks'][client.CASES[len(seen)]];seen.append(raw)
   content=json.dumps({'action':'submit','answers':task['oracle']['answers']})
   inconsistent=copy.deepcopy(good);inconsistent['total_tokens']=999
   return self.envelope(content=content,usage=inconsistent),{'http_status':200,'error':None}
  out=self.root/'bad-usage'
  with patch.object(client,'exchange',side_effect=exchange):
   summary=client.execute(self.packet,out,'http://localhost:9999/v1','qwen38-27b-fp8',self.identity)
  self.assertEqual(summary['completed_trials'],2)
  for row in summary['trials']:
   result=json.loads((out/row['result_path']).read_bytes())
   self.assertTrue(result['final_task_success']);self.assertEqual(result['response']['cache_usage']['cached_tokens'],0)
   self.assertFalse(result['usage_accounting_complete']);self.assertFalse(result['cold_cost_interpretation']);self.assertFalse(result['descriptive_cost_eligible'])
 def test_transport_or_envelope_failure_aborts_with_second_unstarted(self):
  for kind in ('infra','envelope'):
   seen,exchange=self.exchange_for(kind);out=self.root/kind
   with patch.object(client,'exchange',side_effect=exchange):
    with self.assertRaises(RuntimeError):client.execute(self.packet,out,'http://localhost:9999/v1','qwen38-27b-fp8',self.identity)
   summary=json.loads((out/'summary.json').read_bytes());self.assertTrue(summary['infrastructure_abort']);self.assertEqual(summary['unstarted_trials'],['t02-theatre']);self.assertEqual(len(seen),1)
   self.assertTrue((out/'t01-clinic/response.bin').is_file());self.assertEqual(json.loads((out/'t01-clinic/result.json').read_bytes())['failure_kind'],'infrastructure')
 def test_duplicate_fields_wrong_types_extra_ids_and_null(self):
  for content in ('{"action":"submit","action":"submit","answers":{}}','{"action":"submit","answers":{"x":1,"x":2}}'):
   parsed=client.parse_response(self.envelope(content=content),self.task);self.assertFalse(parsed['protocol_complete'])
  answers=copy.deepcopy(self.task['oracle']['answers']);key=next(iter(answers))
  for value in (True,'1'):
   answers[key]=value;parsed=client.parse_response(self.envelope(answers),self.task);self.assertFalse(parsed['protocol_complete']);self.assertFalse(parsed['reference_final_exact'])
  answers[key]=None;parsed=client.parse_response(self.envelope(answers),self.task);self.assertTrue(parsed['protocol_complete']);self.assertEqual(parsed['score']['correct'],23)
  answers['unknown']=1;parsed=client.parse_response(self.envelope(answers),self.task);self.assertFalse(parsed['protocol_complete'])
 def test_raw_returned_model_and_envelope_validation(self):
  envelope=json.loads(self.envelope());envelope['model']='different-model'
  with self.assertRaises(ValueError):client.parse_response(client.encoded(envelope),self.task)
  envelope['model']='qwen38-27b-fp8';self.assertEqual(client.parse_response(client.encoded(envelope),self.task)['returned_model'],envelope['model'])
  envelope['choices'].append(envelope['choices'][0])
  with self.assertRaises(ValueError):client.parse_response(client.encoded(envelope),self.task)
 def test_http_one_attempt_timeout_and_original_bytes(self):
  # Mock the opener itself: no socket or HTTP request is made by this test.
  response=Mock();response.status=200;response.headers={'Content-Type':'application/json'}
  response.read.return_value=b'raw';response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
  opener=Mock();opener.open.return_value=response;old=client.signal.getsignal(client.signal.SIGALRM)
  with patch.object(client.urllib.request,'build_opener',return_value=opener):
   raw,metadata=client.exchange('http://localhost:9999/v1',b'exact request bytes')
  self.assertEqual(raw,b'raw');self.assertIsNone(metadata['error']);opener.open.assert_called_once()
  args,kwargs=opener.open.call_args;self.assertEqual(args[0].data,b'exact request bytes');self.assertEqual(kwargs['timeout'],600)
  self.assertEqual(args[0].full_url,'http://localhost:9999/v1/chat/completions')
  self.assertEqual(client.signal.getitimer(client.signal.ITIMER_REAL),(0,0));self.assertEqual(client.signal.getsignal(client.signal.SIGALRM),old)
  opener.reset_mock();opener.open.side_effect=TimeoutError('CPU timeout fixture')
  with patch.object(client.urllib.request,'build_opener',return_value=opener):raw,metadata=client.exchange('http://localhost:9999/v1',b'exact')
  self.assertIn('TimeoutError',metadata['error']);opener.open.assert_called_once()
 def test_model_mismatch_and_resume_refused(self):
  with self.assertRaises(ValueError):client.execute(self.packet,self.root/'bad',model='other',stub=True)
  with self.assertRaises(ValueError):client.execute(self.packet,self.root/'bad',stub=1)
  out=self.root/'used';out.mkdir()
  with self.assertRaises(FileExistsError):client.execute(self.packet,out,stub=True)

if __name__=='__main__':unittest.main()
