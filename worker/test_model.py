import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import urllib.error

HERE=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location('worker_model',HERE/'model.py');MODULE=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(MODULE)

class Response(io.BytesIO):
    headers={}

class FakeOpener:
    def __init__(self,fail=False,cached=0):self.urls=[];self.metric_reads=0;self.fail=fail;self.cached=cached
    def open(self,request,timeout):
        self.urls.append(request.full_url)
        if request.full_url.endswith('/tokenize'):return Response(b'{"count": 100}')
        if request.full_url.endswith('/metrics'):
            count=self.metric_reads;self.metric_reads+=1
            return Response(f'vllm:request_prefill_time_seconds_count {count}\nvllm:request_prefill_time_seconds_sum {count*0.1}\nvllm:prompt_tokens_total {count*100}\n'.encode())
        if self.fail:raise urllib.error.HTTPError(request.full_url,500,'failed',{},io.BytesIO(b'fault'))
        payload=json.loads(request.data);assert payload['messages']==[{'role':'user','content':'Fix it'}]
        text='A short command.\n```bash\necho hello\n```'
        data={'choices':[{'index':0,'delta':{'content':text},'token_ids':[1,2,3],'finish_reason':'stop'}],'usage':{'prompt_tokens':100,'completion_tokens':3,'prompt_tokens_details':{'cached_tokens':self.cached}}}
        return Response(('data: '+json.dumps(data)+'\n\ndata: [DONE]\n\n').encode())


class ThinkingOpener(FakeOpener):
    def __init__(self, *, separated=False, content=None, fail=False):
        super().__init__(fail=fail)
        self.payloads=[];self.separated=separated;self.content=content
    def open(self,request,timeout):
        self.payloads.append((request.full_url,json.loads(request.data) if request.data else None))
        if not request.full_url.endswith('/chat/completions'):
            return super().open(request,timeout)
        self.urls.append(request.full_url)
        if self.fail:raise urllib.error.HTTPError(request.full_url,503,'busy',{},io.BytesIO(b'busy'))
        thought='Inspect first.\n```bash\necho MUST_NOT_EXECUTE\n```\n'
        answer='```bash\necho safe\n```'
        if self.content is not None:
            deltas=[{'content':self.content}]
        elif self.separated:
            deltas=[{'reasoning_content':thought},{'content':answer}]
        else:
            deltas=[{'content':thought+'</thi'},{'content':'nk>\n\n'+answer}]
        rows=[]
        for index,delta in enumerate(deltas):
            rows.append({'choices':[{'index':0,'delta':delta,'token_ids':[100+index]}]})
        rows.append({'choices':[{'index':0,'delta':{},'finish_reason':'stop'}],
                     'usage':{'prompt_tokens':100,'completion_tokens':len(deltas),'prompt_tokens_details':{'cached_tokens':0}}})
        return Response((''.join('data: '+json.dumps(row)+'\n\n' for row in rows)+'data: [DONE]\n\n').encode())

class LocalModelTests(unittest.TestCase):
    def test_loopback_only(self):
        for endpoint in ['https://example.com','http://localhost:18124','http://127.0.0.1:18124@evil.example','http://127.0.0.1:18124/v1?other=1']:
            with self.assertRaises(ValueError):MODULE.local_base(endpoint)
        self.assertEqual(MODULE.local_base('http://127.0.0.1:18124/v1'),'http://127.0.0.1:18124')
    def test_redirect_is_not_followed(self):
        with self.assertRaises(RuntimeError):MODULE.NoRedirect().redirect_request(None,None,302,None,None,'https://example.com')
    def test_preserves_actions_usage_and_server_prefill(self):
        with tempfile.TemporaryDirectory() as directory:
            model=MODULE.LocalModel('http://127.0.0.1:18124','qwen38-27b-fp8',Path(directory)/'requests');model.opener=FakeOpener()
            answer=model.query([{'role':'user','content':'Fix it','extra':{'private':'not sent'}}])
            self.assertEqual(answer['extra']['actions'],[{'command':'echo hello'}]);self.assertAlmostEqual(model.calls[0]['server_prefill_s'],0.1)
            self.assertTrue((model.out/'001/response.sse').is_file())
    def test_http_failure_does_not_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            model=MODULE.LocalModel('http://127.0.0.1:18124','qwen',Path(directory)/'requests');model.opener=FakeOpener(fail=True)
            with self.assertRaises(urllib.error.HTTPError):model.query([{'role':'user','content':'Fix it'}])
            self.assertEqual(sum(x.endswith('/chat/completions') for x in model.opener.urls),1)
            self.assertEqual(len(model.calls),1)
            self.assertEqual(model.calls[0]['status'],'failed')
            self.assertIn('HTTPError',model.calls[0]['error'])
    def test_context_limit_prevents_generation(self):
        with tempfile.TemporaryDirectory() as directory:
            model=MODULE.LocalModel('http://127.0.0.1:18124','qwen',Path(directory)/'requests',max_input_tokens=50);model.opener=FakeOpener()
            with self.assertRaisesRegex(RuntimeError,'Context budget'):model.query([{'role':'user','content':'Fix it'}])
            self.assertEqual(len(model.opener.urls),1)
    def test_cached_response_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            model=MODULE.LocalModel('http://127.0.0.1:18124','qwen',Path(directory)/'requests');model.opener=FakeOpener(cached=5)
            with self.assertRaisesRegex(ValueError,'cached_tokens'):model.query([{'role':'user','content':'Fix it'}])

    def test_thinking_history_tokenizer_agreement_and_only_final_actions(self):
        for separated in [False,True]:
            with self.subTest(separated=separated), tempfile.TemporaryDirectory() as directory:
                model=MODULE.LocalModel('http://127.0.0.1:18124','qwen',Path(directory)/'requests',
                    generation={'enable_thinking':True,'reasoning_effort':'low','temperature':0.6,'top_k':20},
                    observation_format='tool_response')
                model.opener=ThinkingOpener(separated=separated)
                messages=[{'role':'system','content':'Work carefully'}, {'role':'user','content':'Fix it'}]
                first=model.query(messages)
                self.assertEqual(first['extra']['actions'],[{'command':'echo safe'}])
                self.assertIn('MUST_NOT_EXECUTE',first['reasoning_content'])
                self.assertNotIn('MUST_NOT_EXECUTE',first['content'])
                observations=model.format_observation_messages(first,[{'returncode':0,'output':'line one\nline two\n'}])
                messages.extend([first,*observations])
                second=model.query(messages)
                self.assertEqual(second['extra']['actions'],[{'command':'echo safe'}])
                tokenizations=[p for u,p in model.opener.payloads if u.endswith('/tokenize')]
                generations=[p for u,p in model.opener.payloads if u.endswith('/chat/completions')]
                self.assertEqual(len(generations),2)
                for tokenize,generate in zip(tokenizations,generations):
                    self.assertEqual(tokenize['messages'],generate['messages'])
                    self.assertEqual(tokenize['chat_template_kwargs'],generate['chat_template_kwargs'])
                    self.assertEqual(generate['chat_template_kwargs'],{'enable_thinking':True,'reasoning_effort':'low','preserve_thinking':True})
                    self.assertEqual(generate['temperature'],0.6)
                    self.assertEqual(generate['top_k'],20)
                    self.assertNotIn('extra',str(generate['messages']))
                previous=generations[1]['messages'][2]
                self.assertEqual(previous['content'],first['content'])
                self.assertEqual(previous['reasoning_content'],first['reasoning_content'])
                self.assertEqual(generations[1]['messages'][:2],generations[0]['messages'])
                self.assertIn('Output:\nline one\nline two\n',generations[1]['messages'][-1]['content'])
                receipt=json.loads((model.out/'002/response.json').read_text())
                self.assertEqual(receipt['answer_content'],second['content'])
                self.assertIn('action_ready_s',receipt)

    def test_default_profile_remains_nonthinking_and_json(self):
        with tempfile.TemporaryDirectory() as directory:
            model=MODULE.LocalModel('http://127.0.0.1:18124','qwen',Path(directory)/'requests')
            model.opener=FakeOpener()
            model.query([{'role':'user','content':'Fix it'}])
            payload=json.loads((model.out/'001/request.json').read_text())
            self.assertEqual(payload['chat_template_kwargs'],{'enable_thinking':False})
            self.assertEqual((payload['temperature'],payload['top_p'],payload['seed']),(0,1,42))
            self.assertEqual(payload['max_tokens'],2048)
            self.assertIsNone(model.thinking_wire)
            observation=model.format_observation_messages({},[{'returncode':1,'output':'a\nb'}])[0]
            self.assertEqual(json.loads(observation['content']),{'returncode':1,'output':'a\nb'})

    def test_reasoning_only_or_missing_boundary_never_returns_actions(self):
        for content in ['```bash\necho MUST_NOT_EXECUTE\n```', '```bash\necho MUST_NOT_EXECUTE\n```</think>\n']:
            with self.subTest(content=content), tempfile.TemporaryDirectory() as directory:
                model=MODULE.LocalModel('http://127.0.0.1:18124','qwen',Path(directory)/'requests',generation={'enable_thinking':True})
                model.opener=ThinkingOpener(content=content)
                with self.assertRaises(ValueError):model.query([{'role':'user','content':'Fix it'}])
                self.assertEqual(model.calls[0]['status'],'failed')
                self.assertEqual(sum(u.endswith('/chat/completions') for u in model.opener.urls),1)

    def test_thinking_http_error_does_not_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            model=MODULE.LocalModel('http://127.0.0.1:18124','qwen',Path(directory)/'requests',generation={'enable_thinking':True})
            model.opener=ThinkingOpener(fail=True)
            with self.assertRaises(urllib.error.HTTPError):model.query([{'role':'user','content':'Fix it'}])
            self.assertEqual(len(model.calls),1)
            self.assertEqual(model.calls[0]['status'],'failed')
            self.assertEqual(sum(u.endswith('/chat/completions') for u in model.opener.urls),1)

    def test_invalid_thinking_history_refused_before_http(self):
        with tempfile.TemporaryDirectory() as directory:
            model=MODULE.LocalModel('http://127.0.0.1:18124','qwen',Path(directory)/'requests',generation={'enable_thinking':True})
            model.opener=ThinkingOpener()
            with self.assertRaisesRegex(ValueError,'reasoning history'):
                model.query([{'role':'assistant','content':'answer','reasoning_content':{'bad':'type'}}])
            self.assertEqual(model.opener.urls,[])

    def test_unsupported_profile_keys_refused(self):
        for generation in [{'enable_thinking':'true'}, {'enable_thinking':True,'reasoning_effort':'high'},
                           {'reasoning_effort':'low'}, {'api_key':'secret'}, {'messages':[]}]:
            with self.subTest(generation=generation), tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(ValueError):
                    MODULE.LocalModel('http://127.0.0.1:18124','qwen',Path(directory)/'requests',generation=generation)

    def test_tokenizer_generation_mismatch_fails_before_actions(self):
        class MismatchOpener(ThinkingOpener):
            def open(self,request,timeout):
                if request.full_url.endswith('/tokenize'):
                    return Response(b'{"count": 101}')
                return super().open(request,timeout)
        with tempfile.TemporaryDirectory() as directory:
            model=MODULE.LocalModel('http://127.0.0.1:18124','qwen',Path(directory)/'requests',generation={'enable_thinking':True})
            model.opener=MismatchOpener()
            with self.assertRaisesRegex(ValueError,'input-token counts disagree'):
                model.query([{'role':'user','content':'Fix it'}])
            self.assertEqual(model.calls[0]['status'],'failed')

    def test_format_error_keeps_answer_and_reasoning_in_recovery_history(self):
        from minisweagent.exceptions import FormatError
        with tempfile.TemporaryDirectory() as directory:
            model=MODULE.LocalModel('http://127.0.0.1:18124','qwen',Path(directory)/'requests',generation={'enable_thinking':True})
            model.opener=ThinkingOpener(content='Useful reasoning</think>I forgot the command fence.')
            history=[{'role':'user','content':'Fix it'}]
            with self.assertRaises(FormatError) as caught:
                model.query(history)
            recovery=caught.exception.messages
            self.assertEqual([m['role'] for m in recovery],['assistant','user'])
            self.assertEqual(recovery[0]['content'],'I forgot the command fence.')
            self.assertEqual(recovery[0]['reasoning_content'],'Useful reasoning')
            self.assertNotIn('actions',recovery[0].get('extra',{}))
            model.opener=ThinkingOpener()
            answer=model.query(history+list(recovery))
            self.assertEqual(answer['extra']['actions'],[{'command':'echo safe'}])
            generate=next(p for u,p in model.opener.payloads if u.endswith('/chat/completions'))
            self.assertEqual(generate['messages'][1]['reasoning_content'],'Useful reasoning')
            self.assertIn('Expected exactly 1 action',generate['messages'][2]['content'])

if __name__=='__main__':unittest.main()
