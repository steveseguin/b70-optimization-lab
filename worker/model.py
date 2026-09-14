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
    def __init__(self,base_url,model,out_dir,max_input_tokens=28000,max_output_tokens=2048,generation=None,observation_format="json"):
        self.base=local_base(base_url);self.model=model;self.out=Path(out_dir);self.out.mkdir()
        self.max_input=max_input_tokens;self.max_output=max_output_tokens;self.calls=[]
        options=dict(generation or {})
        allowed={'enable_thinking','reasoning_effort','temperature','top_p','top_k','min_p','presence_penalty','repetition_penalty','seed'}
        if set(options)-allowed:raise ValueError('Unknown generation options: '+str(sorted(set(options)-allowed)))
        self.thinking=options.pop('enable_thinking',False)
        if type(self.thinking) is not bool:raise ValueError('enable_thinking must be boolean')
        self.effort=options.pop('reasoning_effort','low' if self.thinking else None)
        if self.thinking and self.effort not in ('low','medium','xhigh'):raise ValueError('Invalid reasoning effort')
        if not self.thinking and self.effort is not None:raise ValueError('Reasoning effort requires thinking mode')
        self.template_kwargs={'enable_thinking':self.thinking}
        if self.thinking:self.template_kwargs.update(reasoning_effort=self.effort,preserve_thinking=True)
        self.sampling={'temperature':0,'top_p':1,'seed':42,**options}
        if observation_format not in ('json','tool_response'):raise ValueError('Unknown observation format')
        self.observation_format=observation_format
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
        self.wire=module_at('worker_practical_wire',ROOT/'experiments/qwen38-27b-b70/scripts/check-fp8-practical-session.py')
        self.metrics_wire=module_at('worker_prefill_wire',ROOT/'experiments/qwen38-27b-b70/scripts/bench-short-prefill.py')
        self.thinking_wire=module_at('worker_thinking_wire',ROOT/'worker/stream.py') if self.thinking else None
    def fetch(self,path,payload=None):
        request=urllib.request.Request(self.base+path,data=json.dumps(payload).encode() if payload is not None else None,headers={'Content-Type':'application/json'})
        return self.opener.open(request,timeout=180)
    def query(self,messages,**kwargs):
        from minisweagent.models.utils.actions_text import parse_regex_actions
        from minisweagent.exceptions import FormatError
        clean=[]
        for message in messages:
            if message['role'] not in ('system','user','assistant'):continue
            item={'role':message['role'],'content':message['content']}
            if self.thinking and message['role']=='assistant':
                reasoning=message.get('reasoning_content','')
                if not isinstance(reasoning,str):raise ValueError('Assistant reasoning history must be text')
                # vLLM chat accepts the legacy alias; /tokenize requires canonical reasoning.
                item['reasoning']=reasoning
            clean.append(item)
        directory=self.out/f'{len(self.calls)+1:03d}';directory.mkdir()
        with self.fetch('/tokenize',{'model':self.model,'messages':clean,'add_generation_prompt':True,'chat_template_kwargs':self.template_kwargs}) as response:count=json.load(response)['count']
        if count>self.max_input:raise RuntimeError(f'Context budget reached: {count} input tokens, limit {self.max_input}. Task stopped without discarding conversation history.')
        payload={'model':self.model,'messages':clean,**self.sampling,'max_tokens':self.max_output,'n':1,'stream':True,'stream_options':{'include_usage':True},'return_token_ids':True,'chat_template_kwargs':self.template_kwargs}
        self.wire.write_json(directory/'token-count.json',{'input_tokens':count,'limit':self.max_input})
        with self.fetch('/metrics') as response:before=response.read().decode()
        (directory/'metrics-before.txt').write_text(before)
        print(f'Model step {len(self.calls)+1}: {count} input tokens',flush=True)
        attempt={'directory':directory.name,'status':'attempted','prompt_tokens':count}
        self.calls.append(attempt)
        generation_started=time.perf_counter()
        try:
            transport=self.thinking_wire if self.thinking else self.wire
            result=transport.request_one(self.base,payload,directory,opener=self.opener.open)
            if result['prompt_tokens']!=count:raise ValueError('Tokenizer and generation input-token counts disagree')
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
        answer=result['answer_content'] if self.thinking else result['text']
        message={'role':'assistant','content':answer,'extra':{'cost':0.0,'timestamp':time.time(),'evidence':str(directory)}}
        if self.thinking:message['reasoning_content']=result['reasoning_content']
        result['generation_profile']={'chat_template_kwargs':self.template_kwargs,'sampling':self.sampling}
        try:
            actions=parse_regex_actions(answer,action_regex=r'```bash[ \t]*\n(.*?)\n```',format_error_template='Return exactly one bash command block. {{error}}')
        except FormatError as exc:
            # Preserve the complete assistant turn before requesting a correction.
            # No action from a malformed answer is executed.
            result['action_format_valid']=False
            self.wire.write_json(directory/'response.json',result)
            exc.messages=(message,*exc.messages)
            raise
        result['action_ready_s']=time.perf_counter()-generation_started
        result['action_format_valid']=True
        self.wire.write_json(directory/'response.json',result)
        message['extra']['actions']=actions
        return message
    def format_message(self,**kwargs):return kwargs
    def format_observation_messages(self,message,outputs,template_vars=None):
        observations=[]
        for output in outputs:
            if self.observation_format=='tool_response':
                content=f'<tool_response>\nExit status: {output["returncode"]}\nOutput:\n{output["output"]}\n</tool_response>'
            else:content=json.dumps({'returncode':output['returncode'],'output':output['output']},ensure_ascii=False)
            observations.append({'role':'user','content':content,'extra':{'timestamp':time.time()}})
        return observations
    def get_template_vars(self,**kwargs):return {'model_name':self.model}
    def serialize(self):return {'info':{'model':{'provider':'local-loopback-only','base_url':self.base,'model':self.model,'http_retries':0,'cloud_fallback':False,'max_input_tokens':self.max_input,'max_output_tokens':self.max_output,'chat_template_kwargs':self.template_kwargs,'sampling':self.sampling,'observation_format':self.observation_format},'requests':self.calls}}
