#!/usr/bin/env python3
"""Prepare or run the separate fixed four-trial generated sparse-state screen."""
import argparse
import fcntl
import hashlib
import json
import os
import signal
from pathlib import Path
import subprocess
import sys

from engine import HERE, compiler, sha, verify_engine
from generator import COUNTS, encoded, make_case

PROTOCOL='sparse-state-development-v1'
ORDER=((8,'archive'),(8,'quoted'),(128,'quoted'),(128,'archive'))
DEFAULT_TOKENIZER=Path('/mnt/fast-ai/llm-models/qwen3.8-27b-fp8/tokenizer.json')
DEFAULT_PYTHON=Path('/mnt/fast-ai/venvs/clm/bin/python3')


class StopRequested(KeyboardInterrupt):
    pass


def stop_signal(signum,frame):
    raise StopRequested(f'sparse wrapper received signal {signum}')


def run_owned(argv,*,input=None,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=None,env=None):
    """Own and reap only the spawned CPU interpreter, including cancellation."""
    process=subprocess.Popen(argv,stdin=subprocess.PIPE if input is not None else None,
        stdout=stdout,stderr=stderr,text=True,env=env)
    try:
        output,error=process.communicate(input=input,timeout=timeout)
        return subprocess.CompletedProcess(argv,process.returncode,output,error)
    finally:
        if process.poll() is None:
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # The child is this wrapper's CPU HTTP/tokenizer interpreter,
                # never a GPU worker, container, server or unrelated process.
                process.kill();process.wait(timeout=5)


def atomic(path,value):
    temp=path.with_suffix(path.suffix+'.tmp');temp.write_bytes(encoded(value)+b'\n');os.replace(temp,path)


def source_hashes():
    return {p.name:sha(p) for p in sorted(HERE.glob('*.py')) if not p.name.startswith('test_')}|{'pinned-engine.json':sha(HERE/'pinned-engine.json')}


def expected_rows(cases):
    rows=[]
    for count,arm in ORDER:
        task=cases[count]['task'];case_id=task['document_id'];directory=f'{case_id}-{arm}'
        rows.append({'case_id':case_id,'counter_count':count,'arm':arm,'task_sha256':task['task_sha256'],
            'task_path':f'{case_id}-task.json','document_path':f'{case_id}-document.json',
            'result_path':f'{directory}/result.json','native_result_path':f'{directory}/native/result.json'})
    return rows


def budget_check(packet,trials,tokenizer,python):
    if not Path(tokenizer).is_file() or not Path(python).is_file():raise ValueError('local tokenizer/interpreter unavailable; preparation blocked')
    request={'tokenizer':str(Path(tokenizer).resolve()),'trials':[{**r,'task_path':str((packet/r['task_path']).resolve())} for r in trials]}
    result=run_owned([str(python),str(HERE/'budget.py')],input=json.dumps(request),
                          env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1'),timeout=120)
    if result.returncode:raise ValueError('local tokenizer budget check failed: '+result.stderr[-1500:])
    return json.loads(result.stdout)


def prepare(out,tokenizer=DEFAULT_TOKENIZER,tokenizer_python=DEFAULT_PYTHON):
    verify_engine();cases={count:make_case(count) for count in COUNTS};out=Path(out);out.mkdir(parents=True,exist_ok=False)
    trials=expected_rows(cases)
    for case in cases.values():
        stem=case['document']['id'];(out/f'{stem}-document.json').write_bytes(encoded(case['document']))
        atomic(out/f'{stem}-task.json',case['task'])
    budget=budget_check(out,trials,tokenizer,tokenizer_python)
    if not budget['all_reference_prompts_fit'] or not budget['all_reference_emissions_fit']:
        atomic(out/'budget-receipt.json',budget);raise ValueError('reference response or prompt does not fit unchanged caps')
    budget['wrapper_source_sha256']=source_hashes()
    budget['tokenizer_python']=str(Path(tokenizer_python).absolute())
    atomic(out/'budget-receipt.json',budget)
    files={p.name:sha(p) for p in out.glob('*.json')}
    plan={'schema':'sparse-state-plan.v1','protocol':PROTOCOL,'expected_trials':4,'trials':trials,
        'wrapper_source_sha256':source_hashes(),'engine_source_sha256':verify_engine()['source_sha256'],
        'files_sha256':files,'generation':{'seed':83,'counter_counts':[8,128],'initialization_chunk_max':16,
            'steady_batches':16,'updates_per_steady_batch':3,'question_counts':{'current':8,'history':8,'join':8}},
        'context_limit_utf8_bytes':32768,'memory_limit_utf8_bytes':6553,'max_ingestion_attempts':3,
        'max_retrieval':24,'max_answer_calls':32,
        'ingestion_generation':{'enable_thinking':False,'max_tokens':4096},
        'answer_generation':{'enable_thinking':True,'reasoning_effort':'medium','max_tokens':8192},
        'provenance':'Programmatically generated reference, independently replay-checked from controlled source grammar; no claimed independent annotations.',
        'speed_gate_passed':False,'holdout_admitted':False}
    atomic(out/'plan.json',plan)
    return validate_packet(out)


def validate_packet(packet):
    """CPU-only validation used by host preparation before any device action."""
    packet=Path(packet).resolve();plan=json.loads((packet/'plan.json').read_bytes());verify_engine()
    if plan.get('schema')!='sparse-state-plan.v1' or plan.get('protocol')!=PROTOCOL:raise ValueError('wrong sparse plan schema/protocol')
    if plan.get('wrapper_source_sha256')!=source_hashes() or plan.get('engine_source_sha256')!=verify_engine()['source_sha256']:
        raise ValueError('source pins changed since preparation')
    cases={count:make_case(count) for count in COUNTS}
    if plan.get('trials')!=expected_rows(cases) or plan.get('expected_trials')!=4:raise ValueError('fixed sparse matrix identity/order changed')
    policy={'generation':{'seed':83,'counter_counts':[8,128],'initialization_chunk_max':16,'steady_batches':16,
        'updates_per_steady_batch':3,'question_counts':{'current':8,'history':8,'join':8}},
        'context_limit_utf8_bytes':32768,'memory_limit_utf8_bytes':6553,'max_ingestion_attempts':3,
        'max_retrieval':24,'max_answer_calls':32,'ingestion_generation':{'enable_thinking':False,'max_tokens':4096},
        'answer_generation':{'enable_thinking':True,'reasoning_effort':'medium','max_tokens':8192},
        'speed_gate_passed':False,'holdout_admitted':False}
    if any(encoded(plan.get(k))!=encoded(v) for k,v in policy.items()):raise ValueError('fixed sparse protocol policy changed')
    expected_files={r[k] for r in plan['trials'] for k in ('task_path','document_path')}|{'budget-receipt.json'}
    if set(plan.get('files_sha256',{}))!=expected_files:raise ValueError('prepared artifact inventory differs')
    for relative,digest in plan['files_sha256'].items():
        path=(packet/relative).resolve()
        if not path.is_relative_to(packet) or not path.is_file() or sha(path)!=digest:raise ValueError('prepared artifact hash/path mismatch')
    tasks={}
    for count,case in cases.items():
        stem=case['document']['id'];doc=packet/f'{stem}-document.json';task=json.loads((packet/f'{stem}-task.json').read_bytes())
        if doc.read_bytes()!=encoded(case['document']) or task!=case['task']:raise ValueError('prepared generated document/task changed')
        compiler().verify(task);tasks[stem]=task
    budget=json.loads((packet/'budget-receipt.json').read_bytes())
    if (budget.get('schema')!='sparse-state-budget-receipt.v1' or budget.get('wrapper_source_sha256')!=source_hashes()
        or not Path(budget['tokenizer_path']).is_file() or sha(budget['tokenizer_path'])!=budget['tokenizer_sha256']):
        raise ValueError('tokenizer receipt/source identity mismatch')
    recomputed=budget_check(packet,plan['trials'],budget['tokenizer_path'],budget['tokenizer_python'])
    if {k:v for k,v in budget.items() if k not in ('wrapper_source_sha256','tokenizer_python')}!=recomputed:
        raise ValueError('budget receipt differs from independent CPU recomputation')
    if recomputed['all_reference_prompts_fit'] is not True or recomputed['all_reference_emissions_fit'] is not True:
        raise ValueError('fixed budgets do not fit')
    return {'plan':plan,'budget':budget,'tasks':tasks}


def phase_costs(calls,initialization_batches):
    groups={key:[] for key in ('initialization','steady','answer')}
    for call in calls:
        phase='answer' if call['phase']=='answer' else 'initialization' if call['batch_id']<=initialization_batches else 'steady'
        groups[phase].append(call)
    groups['total']=calls
    output={}
    for phase,rows in groups.items():
        value={'calls':len(rows),'client_call_seconds':sum(r['seconds'] for r in rows),
            'prompt_bytes':sum(r['prompt_bytes'] for r in rows)}
        for field in ('prompt_tokens','completion_tokens'):
            numbers=[r.get('usage',{}).get(field) if isinstance(r.get('usage'),dict) else None for r in rows]
            value[field]=sum(numbers) if rows and all(type(n) is int and n>=0 for n in numbers) else None
        cache=[]
        for row in rows:
            usage=row.get('usage');details=usage.get('prompt_tokens_details') if isinstance(usage,dict) else None
            n=details.get('cached_tokens') if isinstance(details,dict) else None;prompt=usage.get('prompt_tokens') if isinstance(usage,dict) else None
            cache.append(n if type(n) is int and type(prompt) is int and 0<=n<=prompt else None)
        value['cache_complete']=bool(rows) and all(n is not None for n in cache)
        value['cached_tokens']=sum(cache) if value['cache_complete'] else None
        output[phase]=value
    return output


def independent_quality(task,arm,native):
    """Check accepted raw responses and every checkpoint, not metric booleans."""
    rows=native.get('batches',[]);references=task['oracle']['after_batch']
    if len(rows)!=len(references):return False
    state={}
    for index,(row,reference,expected,source) in enumerate(zip(rows,references,task['oracle']['events'],task['batches']),1):
        accepted=[a for a in row.get('attempts',[]) if a.get('accepted') is True]
        if row.get('batch_id')!=index or len(accepted)!=1 or row.get('accepted') is not True:return False
        response=accepted[0].get('response',{})
        if arm=='archive':state=response.get('state')
        else:
            events=response.get('events')
            if not isinstance(events,list) or len(events)!=len(expected):return False
            for event,want in zip(events,expected):
                if (not isinstance(event,dict) or type(event.get('amount')) is not int
                    or any(event.get(k)!=want[k] for k in ('counter','op','amount'))
                    or not isinstance(event.get('quote'),str) or not event['quote'].strip()
                    or ' '.join(event['quote'].split()) not in ' '.join(source['text'].split())):return False
                name=event['counter'];amount=event['amount']
                state[name]=amount if event['op']=='set' else state[name]+(amount if event['op']=='add' else -amount)
        if not isinstance(state,dict) or any(type(v) is not int for v in state.values()) or state!=reference:return False
        if row.get('observed_state')!=reference:return False
    answers=native.get('answers')
    if not isinstance(answers,dict) or set(answers)!=set(task['oracle']['answers']):return False
    if any(type(answers[k]) is not type(v) or answers[k]!=v for k,v in task['oracle']['answers'].items()):return False
    return (native.get('status')=='completed' and native.get('protocol_complete') is True
            and native.get('ingestion_complete') is True and native.get('final_answer_complete') is True
            and native.get('resumed') is False)


def execute(packet,out,*,stub=False,endpoint=None,model='qwen38-27b-fp8',identity=None):
    bundle=validate_packet(packet);packet=Path(packet).resolve();out=Path(out);out.mkdir(parents=True,exist_ok=False)
    if not stub and (endpoint is None or identity is None):raise ValueError('explicit qualified endpoint and runtime identity required')
    runtime=None if stub else {'endpoint':endpoint,'model':model,'launch_sha256':sha(identity)}
    plan=bundle['plan'];atomic(out/'plan.json',plan);results=[];abort=None
    def summary():
        pairs={}
        for row in results:pairs.setdefault(str(row['counter_count']),{})[row['arm']]=row
        qualities={n:len(rows)==2 and all(r['quality_passed'] for r in rows.values()) for n,rows in pairs.items()}
        result={'schema':'sparse-state-summary.v1','protocol':PROTOCOL,'measurement_kind':'stub' if stub else 'model',
            'status':'failed' if abort else 'completed' if len(results)==4 else 'running',
            'infrastructure_abort':bool(abort),'infrastructure_error':abort,'expected_trials':4,'observed_trials':len(results),
            'completed_trials':sum(r['status']=='completed' for r in results),'failed_trials':sum(r['status']=='failed' for r in results),
            'trials':results,'paired_quality':qualities,'server_identity':runtime,'engine_source_sha256':verify_engine()['source_sha256'],
            'speed_gate_passed':False,'holdout_admitted':False,'scope':'One-server generated development screen; native semantic schema is low-level compatibility only.'}
        atomic(out/'summary.json',result);return result
    summary()
    try:
        for item in plan['trials']:
            validate_packet(packet)
            if not stub and sha(identity)!=runtime['launch_sha256']:raise ValueError('runtime identity changed')
            directory=out/Path(item['result_path']).parent;directory.mkdir()
            argv=[sys.executable,str(HERE/'engine.py'),'--task',str(packet/item['task_path']),'--out',str(directory/'native'),'--arm',item['arm']]
            if stub:argv.append('--stub')
            else:argv.extend(['--endpoint',endpoint,'--model',model,'--identity',str(identity)])
            atomic(directory/'command.json',{'argv':argv})
            with (directory/'worker.log').open('x') as log:
                worker=run_owned(argv,stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
            native_path=directory/'native/result.json'
            if not native_path.is_file():raise RuntimeError(f'engine exited {worker.returncode} without native result')
            native=json.loads(native_path.read_bytes());task=bundle['tasks'][item['case_id']]
            if (native.get('schema')!='semantic-live-trial.v1' or native.get('protocol')!='semantic-development-live-v1'
                or native.get('measurement_kind')!=('stub' if stub else 'model') or native.get('resumed') is not False
                or native.get('status') not in ('completed','failed')
                or native['task_sha256']!=item['task_sha256'] or native['arm']!=item['arm']
                or native['source_code_sha256']!=plan['engine_source_sha256'] or native['server_identity']!=runtime):
                raise ValueError('native engine result identity differs from sparse plan')
            for key in ('context_limit_utf8_bytes','memory_limit_utf8_bytes','max_ingestion_attempts',
                        'max_retrieval','max_answer_calls','ingestion_generation','answer_generation'):
                if encoded(native.get(key))!=encoded(plan[key]):raise ValueError('native policy differs from sparse plan')
            for record in native['artifacts'].values():
                path=(directory/'native'/record['path']).resolve()
                if not path.is_relative_to((directory/'native').resolve()) or sha(path)!=record['sha256']:
                    raise ValueError('native artifact hash/path mismatch')
            calls=[json.loads(line) for line in (directory/'native/calls.jsonl').read_text().splitlines()]
            costs=phase_costs(calls,task['generated_provenance']['initialization_batches'])
            reference_checks=independent_quality(task,item['arm'],native)
            quality=not stub and reference_checks
            result={'schema':'sparse-state-trial.v1','protocol':PROTOCOL,**item,'status':native['status'],
                'measurement_kind':native['measurement_kind'],'generated_provenance':task['generated_provenance'],
                'server_identity':runtime,'engine_source_sha256':plan['engine_source_sha256'],
                'wrapper_source_sha256':plan['wrapper_source_sha256'],'source_sha256':task['source_sha256'],
                'reference_checks_passed':reference_checks,'quality_passed':quality,
                'cold_cost_interpretation':not stub and costs['total']['cache_complete'] and costs['total']['cached_tokens']==0,
                'phase_costs':costs,'total_trial_wall_seconds':native['wall_seconds'],
                'non_call_overhead_seconds':native['wall_seconds']-costs['total']['client_call_seconds'],
                'native_sha256':sha(native_path),'native_artifacts':native['artifacts'],
                'speed_gate_passed':False,'holdout_admitted':False}
            atomic(directory/'result.json',result);results.append({**item,'status':native['status'],'quality_passed':quality})
            summary()
            if worker.returncode:raise RuntimeError('native engine infrastructure failure; no further trials')
            validate_packet(packet)
            if not stub and sha(identity)!=runtime['launch_sha256']:raise ValueError('runtime identity changed after trial')
    except BaseException as error:
        abort=f'{type(error).__name__}: {error}';summary();raise
    return summary()


def main():
    signal.signal(signal.SIGTERM,stop_signal);signal.signal(signal.SIGINT,stop_signal)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path);parser.add_argument('--packet',type=Path)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare-only',action='store_true');mode.add_argument('--validate-packet',action='store_true')
    mode.add_argument('--stub',action='store_true');mode.add_argument('--execute',action='store_true')
    parser.add_argument('--tokenizer',type=Path,default=DEFAULT_TOKENIZER);parser.add_argument('--tokenizer-python',type=Path,default=DEFAULT_PYTHON)
    parser.add_argument('--endpoint');parser.add_argument('--model',default='qwen38-27b-fp8');parser.add_argument('--identity',type=Path)
    args=parser.parse_args()
    if args.prepare_only:
        if args.out is None:parser.error('preparation requires a new --out packet directory')
        bundle=prepare(args.out,args.tokenizer,args.tokenizer_python);print(json.dumps(bundle['plan'],indent=2));return
    if args.packet is None:parser.error('--packet is required')
    if args.validate_packet:
        bundle=validate_packet(args.packet);print(json.dumps({'plan':bundle['plan'],'budget':bundle['budget']},indent=2));return
    if args.out is None:parser.error('execution requires a new --out results directory')
    if args.execute and (not args.endpoint or not args.identity):parser.error('live execution requires endpoint and identity')
    lock=Path('/tmp/context-durable-stub.lock' if args.stub else '/tmp/context-durable-model.lock')
    with lock.open('a') as guard:
        fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
        print(json.dumps(execute(args.packet,args.out,stub=args.stub,endpoint=args.endpoint,model=args.model,identity=args.identity),indent=2))


if __name__=='__main__':main()
