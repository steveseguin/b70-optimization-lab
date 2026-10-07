import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pilot import HTTPClient, ANSWER_GENERATION, INGESTION_GENERATION, ask, run, StubClient
from tasks import make_task


class GenerationTests(unittest.TestCase):
    def request(self, phase, response=None):
        body=response or {'choices':[{'finish_reason':'stop','message':{'content':'{}','reasoning_content':'checked sources'}}], 'usage':{'prompt_tokens':10,'completion_tokens':20}}
        captured=[]
        def send(request,timeout):
            captured.append(json.loads(request.data))
            return io.BytesIO(json.dumps(body).encode())
        client=HTTPClient('http://127.0.0.1:18196/v1','test')
        with patch('pilot.busy_endpoint',return_value=False),patch('pilot.urllib.request.urlopen',side_effect=send):
            result=client([{'role':'user','content':'test'}],phase,None)
        return captured[0],result,client

    def test_only_answer_phase_uses_bounded_reasoning(self):
        request,_,client=self.request('answer')
        self.assertEqual(request['max_tokens'],8192)
        self.assertEqual(request['chat_template_kwargs'],{'enable_thinking':True,'reasoning_effort':'medium'})
        self.assertEqual(client.last_response_metadata['generation'],ANSWER_GENERATION)
        self.assertEqual(client.last_response_metadata['response_message']['reasoning_content'],'checked sources')
        for phase in ('summary','archive','quoted','extract'):
            request,_,client=self.request(phase)
            self.assertEqual(request['max_tokens'],4096)
            self.assertEqual(request['chat_template_kwargs'],{'enable_thinking':False})
            self.assertEqual(client.last_response_metadata['generation'],INGESTION_GENERATION)

    def test_length_finish_keeps_evidence_and_never_continues(self):
        client=HTTPClient('http://localhost:18196/v1','test')
        body={'choices':[{'finish_reason':'length','message':{'content':'','reasoning_content':'unfinished'}}]}
        with patch('pilot.busy_endpoint',return_value=False),patch('pilot.urllib.request.urlopen',return_value=io.BytesIO(json.dumps(body).encode())) as send:
            with self.assertRaisesRegex(RuntimeError,'no continuation'):client([],'answer',None)
            self.assertEqual(send.call_count,1)
        self.assertEqual(client.last_response_metadata['response_message']['reasoning_content'],'unfinished')

    def test_broken_http_json_is_fatal_not_model_format_retry(self):
        client=HTTPClient('http://localhost:18196/v1','test')
        with patch('pilot.busy_endpoint',return_value=False),patch('pilot.urllib.request.urlopen',return_value=io.BytesIO(b'bad envelope')) as send:
            with self.assertRaisesRegex(RuntimeError,'HTTP response envelope'):client([],'answer',None)
            self.assertEqual(send.call_count,1)

    def test_value_error_from_request_is_not_retried(self):
        task=make_task(7,4,0)
        class Client(StubClient):
            answer_calls=0
            def __call__(self,messages,phase,batch_id):
                if phase=='answer':
                    self.answer_calls+=1
                    raise ValueError('bad envelope')
                return super().__call__(messages,phase,batch_id)
        client=Client(task)
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'bad envelope'):run(task,'quoted',d,client)
            self.assertEqual(client.answer_calls,1)
            self.assertFalse((Path(d)/'result.json').exists())
            session=json.loads((Path(d)/'answer-session.json').read_text())
            self.assertEqual(session['calls'],1)
            self.assertIn('pending_log_index',session)

    def test_fixed_budget_cannot_be_silently_overridden(self):
        with self.assertRaises(ValueError):HTTPClient('http://localhost/v1','test',8192)

    def test_falsey_nontext_content_is_fatal_envelope_error(self):
        for content in ([], 0, False):
            with self.subTest(content=content):
                body={'choices':[{'finish_reason':'stop','message':{'content':content}}]}
                client=HTTPClient('http://localhost/v1','test')
                with patch('pilot.busy_endpoint',return_value=False),patch('pilot.urllib.request.urlopen',return_value=io.BytesIO(json.dumps(body).encode())) as send:
                    with self.assertRaisesRegex(RuntimeError,'HTTP response envelope'):
                        client([],'answer',None)
                    self.assertEqual(send.call_count,1)

    def test_length_failure_logs_real_usage_and_reasoning_metadata(self):
        usage={'prompt_tokens':57,'completion_tokens':8192,
               'completion_tokens_details':{'reasoning_tokens':8192}}
        message={'role':'assistant','content':None,'reasoning':'still checking source facts'}
        body={'choices':[{'finish_reason':'length','message':message}],'usage':usage}
        client=HTTPClient('http://localhost/v1','test')
        with tempfile.TemporaryDirectory() as directory:
            with patch('pilot.busy_endpoint',return_value=False),patch('pilot.urllib.request.urlopen',return_value=io.BytesIO(json.dumps(body).encode())) as send:
                with self.assertRaisesRegex(RuntimeError,'no continuation'):
                    ask(client,Path(directory),{'instruction':'test'},'answer',None,12000)
                self.assertEqual(send.call_count,1)
            call=json.loads((Path(directory)/'calls.jsonl').read_text())
            self.assertEqual(call['model_response']['usage'],usage)
            self.assertEqual(call['model_response']['response_message'],message)
            self.assertEqual(call['model_response']['generation'],ANSWER_GENERATION)
            self.assertEqual(call['model_response']['finish_reason'],'length')
            self.assertNotIn('response',call)

    def test_success_preserves_both_reasoning_aliases_and_nested_usage(self):
        message={'role':'assistant','content':'{}','reasoning':'new field','reasoning_content':'legacy field'}
        usage={'prompt_tokens':10,'completion_tokens':20,
               'completion_tokens_details':{'reasoning_tokens':18}}
        _,(_,returned_usage),client=self.request('answer',{'choices':[{'finish_reason':'stop','message':message}],'usage':usage})
        self.assertEqual(returned_usage,usage)
        self.assertEqual(client.last_response_metadata['response_message'],message)

    def test_failed_next_call_does_not_reuse_previous_reasoning(self):
        _,_,client=self.request('answer')
        with patch('pilot.busy_endpoint',return_value=False),patch('pilot.urllib.request.urlopen',return_value=io.BytesIO(b'bad envelope')):
            with self.assertRaisesRegex(RuntimeError,'HTTP response envelope'):
                client([],'extract',1)
        self.assertEqual(client.last_response_metadata,{'generation':INGESTION_GENERATION})

if __name__=='__main__':unittest.main()
