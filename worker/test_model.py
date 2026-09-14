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

if __name__=='__main__':unittest.main()
