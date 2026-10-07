"""Bounded live-harness tests use local test doubles only, never a model endpoint."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import live
from tasks import load_packet


class FakeModel(live.StubClient):
    kind='model'
    def __init__(self,task,mode='gold'):
        super().__init__(task);self.mode=mode;self.messages=[];self.last_response_metadata=None
    def __call__(self,messages,phase,batch_id):
        self.messages.append((phase,json.loads(messages[1]['content'])))
        usage={'prompt_tokens':100,'completion_tokens':10,'prompt_tokens_details':{'cached_tokens':0}}
        self.last_response_metadata={'finish_reason':'stop','response_message':{'content':'fixture','reasoning_content':'fixture reasoning'},'usage':usage}
        if self.mode=='infrastructure':raise live.InfrastructureError('injected transport fault')
        if self.mode=='length':
            self.last_response_metadata['finish_reason']='length';raise live.TrialFailure('model finish_reason=length')
        if self.mode=='malformed' or (self.mode=='answer-malformed' and phase=='answer'):return '{',usage
        reply=json.loads(super().__call__(messages,phase,batch_id)[0])
        if self.mode=='null' and phase=='answer':reply['answers']={q['id']:None for q in self.task['questions']}
        if self.mode=='never-submit' and phase=='answer':reply['action']='update'
        if self.mode=='fetch' and phase=='answer':reply={'action':'fetch','batch_id':1}
        if self.mode=='memory' and phase=='quoted':reply['memory']='x'*(live.MEMORY_LIMIT+1)
        if self.mode=='unsupported' and phase=='quoted':reply['events'][0]['op']='remove';reply['events'][0]['amount']=None
        return json.dumps(reply),usage


class LiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=Path(__file__).resolve().parents[3]/'data/2026-10-07-context-semantic-development'
        cls.documents=cls.data/'documents.json';cls.annotations=cls.data/'adjudicated.json'
        cls.tasks=load_packet(cls.documents,cls.annotations)
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.out=Path(self.temp.name);self.task=self.tasks[0]
    def run_one(self,mode='gold',arm='quoted'):
        client=FakeModel(self.task,mode)
        return live.run_trial(self.task,arm,self.out/'trial',client),client

    def test_gold_all_arms_keep_reading_rules_and_hide_private_references(self):
        for arm in live.ARMS:
            client=FakeModel(self.task)
            result=live.run_trial(self.task,arm,self.out/arm,client)
            self.assertEqual(result['score']['correct'],7);self.assertTrue(result['protocol_complete'])
            self.assertEqual(result['processed_batches'],4);self.assertEqual(result['calls'],5)
            self.assertTrue(result['cold_cache_known'])
            self.assertEqual(result['cache_usage'],{'complete':True,'cached_tokens':0,'calls':5})
            self.assertFalse(result['speed_gate_passed']);self.assertFalse(result['holdout_admitted'])
            for phase,payload in client.messages:
                self.assertEqual(payload['reading_conventions'],self.task['reading_conventions'])
                self.assertEqual('questions' in payload,phase=='answer')
                for forbidden in ('oracle','after_batch','annotation_sha256','state_after'):
                    self.assertNotIn(forbidden,payload)
            self.assertIn('reasoning_content',(self.out/arm/'calls.jsonl').read_text())
            for record in result['artifacts'].values():self.assertEqual(record['sha256'],live.sha(self.out/arm/record['path']))

    def test_unknown_null_is_complete_but_incorrect(self):
        result,_=self.run_one('null')
        self.assertEqual(result['status'],'completed');self.assertEqual(result['score']['correct'],0)
        self.assertTrue(result['final_answer_complete'])

    def test_ingestion_protocol_exhaustion_keeps_partial_trace_and_missing_answers_wrong(self):
        result,client=self.run_one('malformed')
        self.assertEqual(len(client.messages),3);self.assertEqual(result['status'],'failed')
        self.assertEqual(result['processed_batches'],0);self.assertEqual(len(result['batches']),1)
        self.assertEqual(result['score']['asked'],7);self.assertEqual(result['score']['correct'],0)
        self.assertFalse(result['checkpoint_metrics_complete']);self.assertIsNone(result['all_checkpoint_states_exact'])
        self.assertEqual(result['batches'][0]['observed_state'],{})
        self.assertEqual(len(result['refusals']),3)

    def test_final_action_budget_requires_explicit_submit_even_with_correct_values(self):
        result,client=self.run_one('never-submit')
        self.assertEqual(result['answer_protocol']['calls'],32);self.assertEqual(len(client.messages),36)
        self.assertTrue(result['ingestion_complete']);self.assertFalse(result['final_answer_complete'])
        self.assertEqual(result['score']['correct'],7);self.assertEqual(result['status'],'failed')

    def test_memory_error_preserves_event_metrics_and_unsupported_ops_never_apply(self):
        for mode in ('memory','unsupported'):
            result=live.run_trial(self.task,'quoted',self.out/mode,FakeModel(self.task,mode))
            self.assertEqual(result['status'],'failed');self.assertEqual(result['processed_batches'],0)
            self.assertIn('events',result['batches'][0]['attempts'][0])
            self.assertFalse(result['batches'][0]['state']['exact'])

    def test_fresh_only_trial_refuses_existing_output(self):
        self.run_one()
        with self.assertRaises(FileExistsError):live.run_trial(self.task,'quoted',self.out/'trial',FakeModel(self.task))

    def test_cache_usage_does_not_guess_missing_or_invalid_counts(self):
        for value in (None,True,-1,101):
            count=live.cache_usage([{'usage':{'prompt_tokens':100,'prompt_tokens_details':{'cached_tokens':value}}}])
            self.assertFalse(count['complete']);self.assertIsNone(count['cached_tokens'])
        self.assertEqual(live.cache_usage([{'usage':{'prompt_tokens':100,'prompt_tokens_details':{'cached_tokens':5}}}])['cached_tokens'],5)

    def factory(self,first_mode):
        by_id={t['document_id']:t for t in self.tasks};order=live.make_plan(self.tasks)['trials'];index=0
        def create():
            nonlocal index
            item=order[index];mode=first_mode if index==0 else 'gold';index+=1
            return FakeModel(by_id[item['document_id']],mode)
        return create

    def test_bounded_model_failure_continues_entire_ordered_matrix(self):
        result=live.execute(self.documents,self.annotations,self.out/'campaign',self.factory('length'))
        self.assertEqual(result['observed_trials'],36);self.assertEqual(result['failed_trials'],1)
        self.assertFalse(result['infrastructure_abort']);self.assertEqual(result['completed_trials'],35)
        expected=live.make_plan(self.tasks)['trials']
        self.assertEqual([(r['document_id'],r['arm']) for r in result['trials']],[(r['document_id'],r['arm']) for r in expected])
        first=json.loads((self.out/'campaign'/result['trials'][0]['result_path']).read_bytes())
        self.assertEqual(first['calls'],1);self.assertEqual(first['failure_kind'],'model_or_protocol')

    def test_infrastructure_aborts_after_preserving_failed_native_trial(self):
        with self.assertRaises(live.InfrastructureError):
            live.execute(self.documents,self.annotations,self.out/'campaign',self.factory('infrastructure'))
        result=json.loads((self.out/'campaign/summary.json').read_bytes())
        self.assertTrue(result['infrastructure_abort']);self.assertEqual(result['observed_trials'],1)
        native=json.loads((self.out/'campaign'/result['trials'][0]['result_path']).read_bytes())
        self.assertEqual(native['failure_kind'],'infrastructure');self.assertIn('calls.jsonl',native['artifacts'])

    def test_retrieval_internal_storage_fault_is_infrastructure_not_model_feedback(self):
        with patch.object(live.CanonicalLedger,'get',side_effect=live.StorageError('injected storage fault')):
            with self.assertRaises(live.InfrastructureError):self.run_one('fetch')
        result=json.loads((self.out/'trial/result.json').read_bytes())
        self.assertEqual(result['failure_kind'],'infrastructure')
        self.assertEqual(result['answer_protocol']['calls'],1)

    def test_explicit_stub_matrix_is_labelled_wiring_only(self):
        result=live.execute(self.documents,self.annotations,self.out/'stub',stub=True)
        self.assertEqual(result['measurement_kind'],'stub');self.assertEqual(result['completed_trials'],36)
        native=json.loads((self.out/'stub'/result['trials'][0]['result_path']).read_bytes())
        self.assertFalse(native['cache_usage']['complete']);self.assertIsNone(native['cache_usage']['cached_tokens'])

    def test_http_policies_bounded_finish_and_malformed_envelope(self):
        client=live.HTTPClient('http://127.0.0.1:12345/v1','fixture')
        usage={'prompt_tokens':10,'completion_tokens':3,'prompt_tokens_details':{'cached_tokens':0}}
        def body(finish='stop'):
            return json.dumps({'choices':[{'message':{'content':'{}','reasoning_content':'kept'},'finish_reason':finish}],'usage':usage}).encode()
        for phase,policy in (('quoted',live.INGESTION_GENERATION),('answer',live.ANSWER_GENERATION)):
            with patch.object(live.urllib.request,'urlopen',return_value=io.BytesIO(body())) as network:
                client([],phase,1);request=json.loads(network.call_args.args[0].data)
                self.assertEqual(request['max_tokens'],policy['max_tokens'])
                self.assertEqual(request['chat_template_kwargs']['enable_thinking'],policy['enable_thinking'])
        for finish in ('length','content_filter','tool_calls'):
            with patch.object(live.urllib.request,'urlopen',return_value=io.BytesIO(body(finish))) as network:
                with self.assertRaises(live.TrialFailure):client([],'answer',None)
                self.assertEqual(network.call_count,1)
                self.assertEqual(client.last_response_metadata['response_message']['reasoning_content'],'kept')
        with patch.object(live.urllib.request,'urlopen',return_value=io.BytesIO(b'{"choices":[]}')):
            with self.assertRaises(live.InfrastructureError):client([],'answer',None)
            self.assertIn('raw_response_text',client.last_response_metadata)
        with patch.object(live.urllib.request,'urlopen',side_effect=OSError('connection refused')) as network:
            with self.assertRaises(live.InfrastructureError):client([],'answer',None)
            self.assertEqual(network.call_count,1)


if __name__=='__main__':unittest.main()
