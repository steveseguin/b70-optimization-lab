"""Loopback-only chat adapter for mini-SWE-agent; no HTTP retries or cloud fallback."""
import importlib.util
import json
from pathlib import Path
import time
import urllib.parse
import urllib.request

ROOT=Path(__file__).resolve().parents[1]

def module_at(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise RuntimeError('Local model endpoint redirected; refusing to leave the configured endpoint')


def local_base(value):
    parsed=urllib.parse.urlsplit(value)
    if parsed.scheme!='http' or parsed.hostname not in ('127.0.0.1','::1') or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('','/','/v1','/v1/'):
        raise ValueError('Use a plain HTTP loopback endpoint such as http://127.0.0.1:18124; remote endpoints and credentials are not supported')
    if not parsed.port or not 1024<=parsed.port<=65535:raise ValueError('An explicit unprivileged local port is required')
    return f'http://{parsed.netloc}'

class LocalModel:
    def __init__(self,base_url,model,out_dir,max_input_tokens=28000,max_output_tokens=2048):
        self.base=local_base(base_url);self.model=model;self.out=Path(out_dir);self.out.mkdir()
        self.max_input=max_input_tokens;self.max_output=max_output_tokens;self.calls=[]
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
        self.wire=module_at('worker_practical_wire',ROOT/'experiments/qwen38-27b-b70/scripts/check-fp8-practical-session.py')
        self.metrics_wire=module_at('worker_prefill_wire',ROOT/'experiments/qwen38-27b-b70/scripts/bench-short-prefill.py')
    def fetch(self,path,payload=None):
        request=urllib.request.Request(self.base+path,data=json.dumps(payload).encode() if payload is not None else None,headers={'Content-Type':'application/json'})
        return self.opener.open(request,timeout=180)
    def query(self,messages,**kwargs):
        from minisweagent.models.utils.actions_text import parse_regex_actions
        clean=[{'role':m['role'],'content':m['content']} for m in messages if m['role'] in ('system','user','assistant')]
        directory=self.out/f'{len(self.calls)+1:03d}';directory.mkdir()
        with self.fetch('/tokenize',{'model':self.model,'messages':clean,'add_generation_prompt':True,'chat_template_kwargs':{'enable_thinking':False}}) as response:count=json.load(response)['count']
        if count>self.max_input:raise RuntimeError(f'Context budget reached: {count} input tokens, limit {self.max_input}. Task stopped without discarding conversation history.')
        payload={'model':self.model,'messages':clean,'temperature':0,'top_p':1,'seed':42,'max_tokens':self.max_output,'n':1,'stream':True,'stream_options':{'include_usage':True},'return_token_ids':True,'chat_template_kwargs':{'enable_thinking':False}}
        self.wire.write_json(directory/'token-count.json',{'input_tokens':count,'limit':self.max_input})
        with self.fetch('/metrics') as response:before=response.read().decode()
        (directory/'metrics-before.txt').write_text(before)
        print(f'Model step {len(self.calls)+1}: {count} input tokens',flush=True)
        attempt={'directory':directory.name,'status':'attempted','prompt_tokens':count}
        self.calls.append(attempt)
        try:
            result=self.wire.request_one(self.base,payload,directory,opener=self.opener.open)
            with self.fetch('/metrics') as response:after=response.read().decode()
            (directory/'metrics-after.txt').write_text(after)
            result.update(self.metrics_wire.metric_delta(before,after,result['prompt_tokens']))
            self.wire.write_json(directory/'response.json',result)
        except Exception as exc:
            attempt.update(status='failed',error=f'{type(exc).__name__}: {exc}')
            self.wire.write_json(directory/'attempt.json',attempt)
            raise
        attempt.update({'status':'completed','prompt_tokens':result['prompt_tokens'],'completion_tokens':result['completion_tokens'],'http_ttft_s':result['http_ttft_s'],'server_prefill_s':result.get('server_prefill_s'),'server_prefill_tokens_s':result.get('server_prefill_tokens_per_s'),'decode_stream_proxy_tokens_s':result['decode_stream_proxy_tokens_s'],'elapsed_s':result['elapsed_s']})
        self.wire.write_json(directory/'attempt.json',attempt)
        actions=parse_regex_actions(result['text'],action_regex=r'```bash[ \t]*\n(.*?)\n```',format_error_template='Return exactly one bash command block. {{error}}')
        return {'role':'assistant','content':result['text'],'extra':{'actions':actions,'cost':0.0,'timestamp':time.time(),'evidence':str(directory)}}
    def format_message(self,**kwargs):return kwargs
    def format_observation_messages(self,message,outputs,template_vars=None):
        return [{'role':'user','content':json.dumps({'returncode':o['returncode'],'output':o['output']},ensure_ascii=False),'extra':{'timestamp':time.time()}} for o in outputs]
    def get_template_vars(self,**kwargs):return {'model_name':self.model}
    def serialize(self):return {'info':{'model':{'provider':'local-loopback-only','base_url':self.base,'model':self.model,'http_retries':0,'cloud_fallback':False,'max_input_tokens':self.max_input,'max_output_tokens':self.max_output},'requests':self.calls}}
