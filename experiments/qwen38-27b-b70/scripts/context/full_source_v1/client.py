#!/usr/bin/env python3
"""Two fixed full-source requests. CPU preparation never calls a model."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PROTOCOL='direct-full-source-screen-v1'
CASES=('t01-clinic','t02-theatre')
POLICY={'message_limit_bytes':32768,'request_deadline_seconds':600,'max_requests_per_trial':1,
        'temperature':0,'answer_generation':{'enable_thinking':True,'reasoning_effort':'medium','max_tokens':8192}}
MAX_RESPONSE=2*1024*1024


def encoded(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def digest(value):return hashlib.sha256(encoded(value)).hexdigest()
def require(condition,message):
    if not condition:raise ValueError(message)
def write(path,data):
    path=Path(path)
    with path.open('wb') as handle:handle.write(data);handle.flush();os.fsync(handle.fileno())
def save(path,value):write(path,encoded(value)+b'\n')
def strict_json(raw):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('duplicate JSON key')
            result[key]=value
        return result
    def bad(value):raise ValueError('nonfinite JSON value')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=bad)
def source_hashes():
    return {p.name:sha(p) for p in sorted(HERE.glob('*.py')) if not p.name.startswith('test_')}|{'input-pins.json':sha(HERE/'input-pins.json')}
def pins():return json.loads((HERE/'input-pins.json').read_bytes())
def compiler():
    record=pins()['compiler'];path=ROOT/record['path'];require(sha(path)==record['sha256'],'compiler hash changed')
    spec=importlib.util.spec_from_file_location('full_source_frozen_tasks',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def path_in(root,name):
    path=(root/name).resolve()
    require(not Path(name).is_absolute() and path.is_relative_to(root.resolve()),'unsafe artifact path')
    return path


def materials(packet):
    for target,record in pins()['files'].items():
        require(sha(path_in(packet,target))==record['sha256'],'packet source hash changed: '+target)
    tasks={t['document_id']:t for t in compiler().load_packet(packet/'source/documents.json',packet/'source/adjudicated.json')}
    feasibility=json.loads((packet/'feasibility.json').read_bytes())
    rows={r['document_id']:r for r in feasibility['documents']}
    requests={};items=[]
    for case in CASES:
        task=tasks[case];candidate=rows[case];request=candidate['candidate_request']
        require(digest(request)==candidate['request_json_sha256'],'candidate request hash mismatch')
        require(digest(request['messages'])==candidate['message_json_sha256'],'candidate messages hash mismatch')
        require(len(encoded(request['messages']))<=POLICY['message_limit_bytes'],'prompt cap exceeded')
        public=json.loads(request['messages'][1]['content'])
        require(public['batches']==task['batches'] and public['questions']==task['questions'] and public['reading_conventions']==task['reading_conventions'],'public source/question mismatch')
        require(set(public)=={'instruction','batches','questions','reading_conventions'},'private field in candidate')
        require(request['temperature']==0 and request['max_tokens']==8192 and request['chat_template_kwargs']=={'enable_thinking':True,'reasoning_effort':'medium'},'generation changed')
        requests[case]=request
        items.append({'case_id':case,'task_sha256':task['task_sha256'],'question_sha256':digest(task['questions']),
                      'request_sha256':candidate['request_json_sha256'],'request_path':case+'-request.json',
                      'task_path':case+'-task.json','result_path':case+'/result.json','timing_path':case+'/timing.json'})
    return {c:tasks[c] for c in CASES},requests,items


def prepare(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    for target,record in pins()['files'].items():
        source=ROOT/record['path'];require(sha(source)==record['sha256'],'original input hash changed')
        destination=out/target;destination.parent.mkdir(parents=True,exist_ok=True);write(destination,source.read_bytes())
    tasks,requests,items=materials(out)
    for row in items:
        write(out/row['request_path'],encoded(requests[row['case_id']]))
        save(out/row['task_path'],tasks[row['case_id']])
    plan={'schema':'full-source-plan.v1','protocol':PROTOCOL,'expected_trials':2,'trials':items,**POLICY,
          'source_code_sha256':source_hashes(),'input_pins':pins(),
          'files_sha256':{str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()},
          'launch_admitted':False,'speed_gate_passed':False,'holdout_admitted':False}
    save(out/'plan.json',plan);return validate_packet(out)


def validate_packet(packet):
    packet=Path(packet).resolve();plan=json.loads((packet/'plan.json').read_bytes())
    require(plan['schema']=='full-source-plan.v1' and plan['protocol']==PROTOCOL,'wrong plan identity')
    require(plan['source_code_sha256']==source_hashes() and plan['input_pins']==pins(),'source inventory changed')
    require(all(encoded(plan.get(k))==encoded(v) for k,v in POLICY.items()),'policy changed')
    require(all(plan.get(k) is False for k in ('launch_admitted','speed_gate_passed','holdout_admitted')),'admission changed')
    tasks,requests,items=materials(packet)
    require(encoded(plan['trials'])==encoded(items) and type(plan['expected_trials']) is int and plan['expected_trials']==2,'fixed rows changed')
    expected=set(pins()['files'])|{r[k] for r in items for k in ('task_path','request_path')}
    require(set(plan['files_sha256'])==expected,'packet inventory changed')
    for name,expected_sha in plan['files_sha256'].items():require(sha(path_in(packet,name))==expected_sha,'packet file changed')
    for row in items:
        require((packet/row['request_path']).read_bytes()==encoded(requests[row['case_id']]),'request bytes changed')
        require(json.loads((packet/row['task_path']).read_bytes())==tasks[row['case_id']],'task changed')
    return {'plan':plan,'tasks':tasks,'requests':requests}


def score(task,answers):
    ids={q['id'] for q in task['questions']};groups={};typed={};invalid=[]
    for q in task['questions']:
        key=q['id'];actual=answers.get(key);kind=int if q['answer_type']=='int' else str
        if key in answers and actual is not None and type(actual) is not kind:invalid.append(key)
        correct=type(actual) is kind and actual==task['oracle']['answers'][key]
        for table,label in ((groups,q['category']),(typed,q['answer_type'])):
            row=table.setdefault(label,{'asked':0,'correct':0});row['asked']+=1;row['correct']+=correct
    return {'asked':len(ids),'correct':sum(r['correct'] for r in groups.values()),'valid':not(set(answers)-ids),
            'exact_question_coverage':set(answers)==ids,'answer_types_valid':not invalid,'invalid_type_ids':invalid,
            'missing_ids':sorted(ids-set(answers)),'unknown_ids':sorted(set(answers)-ids),'by_category':groups,'by_answer_type':typed}


def cache_usage(usage):
    if not isinstance(usage,dict):return {'complete':False,'cached_tokens':None}
    prompt=usage.get('prompt_tokens');details=usage.get('prompt_tokens_details')
    cached=details.get('cached_tokens') if isinstance(details,dict) else None
    valid=type(prompt) is int and prompt>=0 and type(cached) is int and 0<=cached<=prompt
    return {'complete':valid,'cached_tokens':cached if valid else None}


def usage_accounting_complete(usage):
    """Optional reported counters must agree; absent required counters are unknown."""
    if not isinstance(usage,dict):return False
    count=lambda value:type(value) is int and value>=0
    prompt=usage.get('prompt_tokens');completion=usage.get('completion_tokens')
    if not count(prompt) or not count(completion) or not cache_usage(usage)['complete']:return False
    if 'total_tokens' in usage and (not count(usage['total_tokens']) or usage['total_tokens']!=prompt+completion):return False
    details=usage.get('completion_tokens_details')
    if details is not None and not isinstance(details,dict):return False
    if isinstance(details,dict) and 'reasoning_tokens' in details:
        reasoning=details['reasoning_tokens']
        if not count(reasoning) or reasoning>completion:return False
    return True


def parse_response(raw,task,expected_model='qwen38-27b-fp8'):
    # Broken HTTP/API envelopes are infrastructure; valid envelopes with bad model
    # content, length or other finish reasons are bounded observed model outcomes.
    envelope=strict_json(raw)
    require(isinstance(envelope,dict) and isinstance(envelope.get('choices'),list) and len(envelope['choices'])==1,'invalid HTTP response envelope')
    require('model' not in envelope or envelope['model']==expected_model,'returned model identity mismatch')
    choice=envelope['choices'][0];require(isinstance(choice,dict),'invalid choice')
    message=choice.get('message');finish=choice.get('finish_reason')
    require(isinstance(message,dict) and isinstance(finish,str),'invalid message/finish envelope')
    content=message.get('content');require(content is None or isinstance(content,str),'invalid response content envelope')
    error=None;answers={};reply=None
    try:
        reply=strict_json(content or '')
        if isinstance(reply,dict) and isinstance(reply.get('answers'),dict):answers=reply['answers']
        require(isinstance(reply,dict) and set(reply)=={'action','answers'} and reply['action']=='submit' and isinstance(reply['answers'],dict),'expected exact submit/answers object')
        answers=reply['answers']
    except (ValueError,TypeError) as e:error=str(e)
    grade=score(task,answers)
    complete=error is None and grade['valid'] and grade['answer_types_valid'] and grade['exact_question_coverage']
    exact=complete and finish=='stop' and grade['correct']==grade['asked']
    return {'returned_model':envelope.get('model'),'finish_reason':finish,'response_message':message,'usage':envelope.get('usage'),
            'cache_usage':cache_usage(envelope.get('usage')),'parsed_reply':reply,'answers':answers,'score':grade,
            'protocol_complete':complete,'response_error':error,'reference_final_exact':exact}


def exchange(endpoint,request_bytes):
    """One HTTP request, no redirects/retries, one wall-clock deadline, raw bytes."""
    parsed=urlsplit(endpoint)
    require(parsed.scheme=='http' and parsed.hostname in ('localhost','127.0.0.1','::1') and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment,'local HTTP endpoint required')
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):return None
    def timeout(*args):raise TimeoutError('600-second request deadline exceeded')
    previous=signal.getsignal(signal.SIGALRM)
    require(signal.getitimer(signal.ITIMER_REAL)==(0.0,0.0),'existing alarm conflicts with request deadline')
    signal.signal(signal.SIGALRM,timeout);signal.setitimer(signal.ITIMER_REAL,600)
    raw=b'';metadata={};error=None
    try:
        req=urllib.request.Request(endpoint.rstrip('/')+'/chat/completions',data=request_bytes,headers={'Content-Type':'application/json'})
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
        try:response=opener.open(req,timeout=600)
        except urllib.error.HTTPError as e:response=e
        with response:
            metadata={'http_status':response.status,'headers':dict(response.headers)}
            raw=response.read(MAX_RESPONSE+1)
        require(len(raw)<=MAX_RESPONSE,'response exceeds bounded 2 MiB envelope')
        require(metadata['http_status']==200,'non-200 HTTP status')
    except Exception as e:error=f'{type(e).__name__}: {e}'
    finally:signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous)
    metadata.update(error=error,raw_truncated=len(raw)>MAX_RESPONSE)
    return raw,metadata


def execute(packet,out,endpoint=None,model='qwen38-27b-fp8',identity=None,stub=False):
    require(type(stub) is bool,'stub must be boolean')
    require(stub or (endpoint and identity),'live execution needs endpoint and identity')
    packet=Path(packet).resolve();bundle=validate_packet(packet);plan=bundle['plan']
    require(all(r['model']==model for r in bundle['requests'].values()),'model must match exact frozen request')
    identity_path=Path(identity).resolve() if identity else None
    runtime=None if stub else {'endpoint':endpoint,'model':model,'launch_sha256':sha(identity_path)}
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    plan_sha=sha(packet/'plan.json');kind='stub' if stub else 'model';records={};abort=None
    def summary():
        rows=[{**r,**records.get(r['case_id'],{'status':'unstarted'})} for r in plan['trials']]
        value={'schema':'full-source-summary.v1','protocol':PROTOCOL,'measurement_kind':kind,'expected_trials':2,
               'infrastructure_abort':abort is not None,'error':abort,'server_identity':runtime,'trials':rows,
               'completed_trials':sum(r['status']=='completed' for r in rows),'failed_trials':sum(r['status']=='failed' for r in rows),
               'unstarted_trials':[r['case_id'] for r in rows if r['status']=='unstarted'],
               'source_code_sha256':plan['source_code_sha256'],'plan_sha256':plan_sha,
               'checkpoint_quality':None,'event_quality':None,'speed_gate_passed':False,'holdout_admitted':False}
        save(out/'summary.json',value);return value
    summary()
    try:
        for item in plan['trials']:
            validate_packet(packet);require(sha(packet/'plan.json')==plan_sha,'plan changed')
            if not stub:require(sha(identity_path)==runtime['launch_sha256'],'launch identity changed')
            case=item['case_id'];task=bundle['tasks'][case];records[case]={'status':'incomplete'};summary()
            directory=out/case;directory.mkdir()
            start=time.monotonic();request_bytes=(packet/item['request_path']).read_bytes();write(directory/'request.json',request_bytes)
            if identity_path:write(directory/'identity.json',identity_path.read_bytes())
            raw=b'';transport={};parsed=None;error=None;request_seconds=0
            try:
                before=time.monotonic()
                if stub:
                    raw=encoded({'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'action':'submit','answers':task['oracle']['answers']})}}]})
                    transport={'http_status':None,'error':None,'raw_truncated':False,'stub':True}
                else:raw,transport=exchange(endpoint,request_bytes)
                request_seconds=time.monotonic()-before
                write(directory/'response.bin',raw);save(directory/'transport.json',transport)
                require(not transport.get('error'),transport.get('error'))
                parsed=parse_response(raw,task,model)
            except BaseException as e:
                request_seconds=max(request_seconds,time.monotonic()-before)
                error=f'{type(e).__name__}: {e}'
                write(directory/'response.bin',raw);save(directory/'transport.json',{**transport,'client_error':error})
            exact=bool(parsed and parsed['reference_final_exact']);cache=parsed['cache_usage'] if parsed else {'complete':False,'cached_tokens':None}
            usage=parsed['usage'] if parsed and isinstance(parsed['usage'],dict) else {}
            costs_known=usage_accounting_complete(usage)
            result={'schema':'full-source-trial.v1','protocol':PROTOCOL,**item,**POLICY,'measurement_kind':kind,'resumed':False,
                    'server_identity':runtime,'source_code_sha256':plan['source_code_sha256'],
                    'source_sha256':task['source_sha256'],'adjudication_sha256':task['adjudication_sha256'],
                    'annotation_sources':task['annotation_sources'],'status':'completed' if parsed and parsed['protocol_complete'] and parsed['finish_reason']=='stop' else 'failed',
                    'failure_kind':'infrastructure' if error else 'model_or_protocol' if not exact else None,'error':error,
                    'response':parsed,'request_seconds':request_seconds,'final_task_success':not stub and exact,
                    'usage_accounting_complete':costs_known,
                    'cold_cost_interpretation':not stub and costs_known and cache['complete'] and cache['cached_tokens']==0,
                    'descriptive_cost_eligible':not stub and exact and costs_known and cache['complete'] and cache['cached_tokens']==0,
                    'checkpoint_quality':None,'event_quality':None,'speed_gate_passed':False,'holdout_admitted':False,
                    'artifacts':{p.name:{'path':p.name,'sha256':sha(p),'bytes':p.stat().st_size} for p in directory.iterdir() if p.is_file()}}
            save(directory/'result.json',result)
            timing={'schema':'full-source-timing.v1','case_id':case,'request_seconds':request_seconds,
                    'task_seconds':time.monotonic()-start,'result_sha256':sha(directory/'result.json'),
                    'boundary':'Before request persistence through durable result write; excludes this timing receipt and campaign/offline audit.'}
            save(directory/'timing.json',timing)
            records[case]={'status':result['status'],'result_sha256':sha(directory/'result.json'),'timing_sha256':sha(directory/'timing.json')};summary()
            if error:raise RuntimeError(error)
            validate_packet(packet)
            if not stub:require(sha(identity_path)==runtime['launch_sha256'],'launch identity changed')
    except BaseException as e:abort=f'{type(e).__name__}: {e}';summary();raise
    return summary()


def main():
    def stop(signum,frame):raise InterruptedError(f'client cancelled by signal {signum}')
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    p=argparse.ArgumentParser(description=__doc__);mode=p.add_mutually_exclusive_group(required=True)
    for name in ('prepare','validate-packet','execute','stub'):mode.add_argument('--'+name,action='store_true')
    p.add_argument('--packet',type=Path);p.add_argument('--out',type=Path);p.add_argument('--endpoint');p.add_argument('--model',default='qwen38-27b-fp8');p.add_argument('--identity',type=Path)
    args=p.parse_args()
    if args.prepare:
        if args.out is None:p.error('--out required')
        result=prepare(args.out)['plan']
    elif args.validate_packet:
        if args.packet is None:p.error('--packet required')
        result=validate_packet(args.packet)['plan']
    else:
        if args.packet is None or args.out is None:p.error('--packet and --out required')
        result=execute(args.packet,args.out,args.endpoint,args.model,args.identity,args.stub)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
