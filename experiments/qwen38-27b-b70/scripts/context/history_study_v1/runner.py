#!/usr/bin/env python3
"""Prepare or run the fixed eight-trial historical accepted-state study."""
import argparse
import fcntl
import hashlib
import json
import math
import os
import signal
from pathlib import Path
import subprocess
import sys

from engine import HERE, compiler, sha, verify_engine
from materials import ORDER, encoded, pins, input_bytes, cases_from, expected_rows
import native_audit
import snapshot_audit

PROTOCOL='historical-state-study-v1'
POLICY={'context_limit_utf8_bytes':32768,'memory_limit_utf8_bytes':6553,'max_ingestion_attempts':3,
        'max_retrieval':24,'max_answer_calls':32,
        'ingestion_generation':{'enable_thinking':False,'max_tokens':4096},
        'answer_generation':{'enable_thinking':True,'reasoning_effort':'medium','max_tokens':8192}}
CONTINUATION_RULE={'next_documents':['t03-depot','t04-meals'],
    'requires_complete_auditable_evidence':True,'requires_all_history_trials_exact':True,
    'requires_no_same_arm_current_or_temporal_accuracy_regression':True,
    'improvement_alternatives':['at_least_one_same_arm_temporal_answer_gain',
        'one_arm_exact_in_both_modes_and_history_total_elapsed_at_most_0.9_times_source_only_on_both_documents_with_known_zero_cache'],
    'history_to_source_elapsed_max_ratio':0.9,'automatic_extension':False,
    'scope':'Development continuation only; separately frozen extension, no speed or holdout promotion.'}
DEFAULT_TOKENIZER=Path('/mnt/fast-ai/llm-models/qwen3.8-27b-fp8/tokenizer.json')
DEFAULT_PYTHON=Path('/mnt/fast-ai/venvs/clm/bin/python3')


class StopRequested(KeyboardInterrupt):
    pass


def stop_signal(signum,frame):
    raise StopRequested(f'history study wrapper received signal {signum}')


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
    return {p.name:sha(p) for p in sorted(HERE.glob('*.py')) if not p.name.startswith('test_')}|{name:sha(HERE/name) for name in ('pinned-engine.json','input-pins.json','copied-auditors.json')}


def budget_check(packet,trials,tokenizer,python):
    if not Path(tokenizer).is_file() or not Path(python).is_file():raise ValueError('local tokenizer/interpreter unavailable; preparation blocked')
    request={'tokenizer':str(Path(tokenizer).resolve()),'trials':[{**r,'task_path':str((packet/r['task_path']).resolve())} for r in trials]}
    result=run_owned([str(python),str(HERE/'budget.py')],input=json.dumps(request),
                          env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1'),timeout=120)
    if result.returncode:raise ValueError('local tokenizer budget check failed: '+result.stderr[-1500:])
    return json.loads(result.stdout)


def prepare(out,tokenizer=DEFAULT_TOKENIZER,tokenizer_python=DEFAULT_PYTHON):
    verify_engine();out=Path(out);out.mkdir(parents=True,exist_ok=False)
    for relative,data in input_bytes().items():
        path=out/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    cases=cases_from(out);trials=expected_rows(cases)
    for case in cases.values():
        stem=case['document']['id'];(out/f'{stem}-document.json').write_bytes(encoded(case['document']))
        atomic(out/f'{stem}-task.json',case['task'])
    budget=budget_check(out,trials,tokenizer,tokenizer_python)
    if not budget['all_reference_prompts_fit'] or not budget['all_reference_emissions_fit']:
        atomic(out/'budget-receipt.json',budget);raise ValueError('reference response or prompt does not fit unchanged caps')
    budget['wrapper_source_sha256']=source_hashes();budget['tokenizer_python']=str(Path(tokenizer_python).absolute())
    atomic(out/'budget-receipt.json',budget)
    files={str(path.relative_to(out)):sha(path) for path in out.rglob('*') if path.is_file()}
    plan={'schema':'history-study-plan.v1','protocol':PROTOCOL,'expected_trials':8,'trials':trials,
        'wrapper_source_sha256':source_hashes(),'engine_source_sha256':verify_engine()['source_sha256'],
        'files_sha256':files,'input_pins':pins(),'continuation_rule':CONTINUATION_RULE,**POLICY,
        'provenance':'Two fixed authored temporal cases; exact frozen adjudication and two assistant annotations. No independent human validation.',
        'extension_admitted':False,'speed_gate_passed':False,'holdout_admitted':False}
    atomic(out/'plan.json',plan);return validate_packet(out)


def validate_packet(packet):
    packet=Path(packet).resolve();plan=json.loads((packet/'plan.json').read_bytes());verify_engine()
    if plan.get('schema')!='history-study-plan.v1' or plan.get('protocol')!=PROTOCOL:raise ValueError('wrong history study plan identity')
    if plan.get('wrapper_source_sha256')!=source_hashes() or plan.get('engine_source_sha256')!=verify_engine()['source_sha256']:
        raise ValueError('source pins changed since preparation')
    cases=cases_from(packet)
    if (encoded(plan.get('trials'))!=encoded(expected_rows(cases))
        or type(plan.get('expected_trials')) is not int or plan['expected_trials']!=8):
        raise ValueError('fixed history matrix identity/order changed')
    policy={**POLICY,'input_pins':pins(),'continuation_rule':CONTINUATION_RULE,
            'extension_admitted':False,'speed_gate_passed':False,'holdout_admitted':False}
    if any(encoded(plan.get(k))!=encoded(v) for k,v in policy.items()):raise ValueError('fixed history study policy changed')
    expected_files={r[k] for r in plan['trials'] for k in ('task_path','document_path')}|{'budget-receipt.json'}|{r['copy_path'] for r in pins()['files']}
    if set(plan.get('files_sha256',{}))!=expected_files:raise ValueError('prepared artifact inventory differs')
    for relative,digest in plan['files_sha256'].items():
        path=(packet/relative).resolve()
        if not path.is_relative_to(packet) or not path.is_file() or sha(path)!=digest:raise ValueError('prepared artifact hash/path mismatch')
    tasks={}
    for stem,case in cases.items():
        task=json.loads((packet/f'{stem}-task.json').read_bytes())
        if ((packet/f'{stem}-document.json').read_bytes()!=encoded(case['document'])
            or (packet/f'{stem}-task.json').read_bytes()!=encoded(case['task'])+b'\n'):
            raise ValueError('compiled task or public document differs from pinned source/adjudication')
        compiler().verify(task);tasks[stem]=task
    budget=json.loads((packet/'budget-receipt.json').read_bytes())
    if (budget.get('schema')!='history-study-budget.v1' or budget.get('wrapper_source_sha256')!=source_hashes()
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


def action_counts(calls,native,directory):
    requested={k:0 for k in ('search','fetch','state_at','update','submit','invalid')}
    retrievals={k:0 for k in ('search','fetch','state_at')};responses=dict(retrievals);errors=0
    answer_calls=[call for call in calls if call['phase']=='answer']
    for call in answer_calls:
        try:
            reply=json.loads(call.get('response',''));action=reply.get('action')
            if action is None:
                action='search' if 'query' in reply or 'search' in reply else 'fetch' if 'batch_id' in reply or 'batch' in reply else 'update' if 'answers' in reply else None
            requested[action if isinstance(action,str) and action in requested else 'invalid']+=1
        except (ValueError,TypeError,AttributeError):requested['invalid']+=1
    for key in native['answer_protocol']['cache']:
        action=key.split(':',1)[0]
        if action not in retrievals:raise ValueError('unknown native retrieval cache action')
        retrievals[action]+=1
    path=Path(directory)/'retrieval.jsonl'
    for response in ([json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []):
        if 'error' in response:errors+=1;continue
        action='state_at' if response.get('action')=='state_at' else 'search' if 'search' in response else 'fetch' if 'batch_id' in response and 'text' in response else None
        if action is None:raise ValueError('unknown retained retrieval response')
        responses[action]+=1
    repeated={k:responses[k]-retrievals[k] for k in responses}
    if any(v<0 for v in repeated.values()):raise ValueError('cache has no successful retrieval evidence')
    return {'requested_actions':requested,'successful_distinct_retrievals':retrievals,
        'successful_retrieval_responses':responses,'repeated_retrieval_responses':repeated,
        'retrieval_error_responses':errors,'answer_calls_logged':len(answer_calls),
        'answer_call_slots_used':native['answer_protocol']['calls'],
        'answer_call_exhausted':native.get('failure')=='answer protocol budget exhausted'}


def finite_seconds(value):
    if type(value) not in (int,float) or not math.isfinite(value) or value<0:raise ValueError('invalid elapsed time')
    return value


def check_frozen(packet,bundle,plan_sha,interpreter_sha):
    """After one full validation, check immutable bytes at every trial boundary."""
    plan=bundle['plan'];budget=bundle['budget']
    if sha(packet/'plan.json')!=plan_sha or source_hashes()!=plan['wrapper_source_sha256']:
        raise ValueError('study plan or wrapper changed during execution')
    if verify_engine()['source_sha256']!=plan['engine_source_sha256']:
        raise ValueError('frozen history engine changed')
    for relative,digest in plan['files_sha256'].items():
        path=(packet/relative).resolve()
        if not path.is_relative_to(packet) or sha(path)!=digest:raise ValueError('packet artifact changed during execution')
    if sha(budget['tokenizer_path'])!=budget['tokenizer_sha256'] or sha(budget['tokenizer_python'])!=interpreter_sha:
        raise ValueError('local tokenizer/interpreter changed during execution')


def audit_native(directory,native,task,item,plan,runtime,kind):
    directory=Path(directory).resolve()
    for name in ('canonical.sqlite','identity.json','result.json'):
        path=(directory/name).resolve()
        if not path.is_relative_to(directory) or not path.is_file():raise ValueError('native auxiliary path missing/unsafe')
    auxiliary={name:{'path':name,'sha256':sha(directory/name)} for name in ('canonical.sqlite','identity.json')}
    inner={**POLICY,'protocol':'historical-state-development-v1','measurement_kind':kind,
           'source_code_sha256':plan['engine_source_sha256'],'server_identity':runtime}
    audited=native_audit.audit_trial(directory,native,task,
        {'document_id':item['case_id'],'arm':item['arm'],'task_sha256':item['task_sha256']},inner)
    snapshots=snapshot_audit.audit(directory,task)
    if snapshots['integrity_passed'] is not True:raise ValueError('snapshot integrity audit failed: '+str(snapshots['issues']))
    for record in auxiliary.values():
        if sha(directory/record['path'])!=record['sha256']:raise ValueError('native auxiliary changed during audit')
    exact=(audited['status']=='completed' and audited['correct']==audited['asked']==24
        and audited['source_delivery_complete'] and audited['checkpoints_checked']==audited['checkpoints_exact']==len(task['batches'])
        and snapshots['complete_snapshot_evidence'] is True
        and (item['arm']=='archive' or audited['all_accepted_events_exact'] is True
             and audited['accepted_events']['batches']==len(task['batches'])))
    return exact,audited,snapshots,auxiliary


def execute(packet,out,*,stub=False,endpoint=None,model='qwen38-27b-fp8',identity=None):
    if type(stub)is not bool:raise ValueError('stub must be an explicit boolean')
    if not stub and (endpoint is None or identity is None):raise ValueError('explicit qualified endpoint and runtime identity required')
    bundle=validate_packet(packet);packet=Path(packet).resolve();out=Path(out);out.mkdir(parents=True,exist_ok=False)
    runtime=None if stub else {'endpoint':endpoint,'model':model,'launch_sha256':sha(identity)}
    kind='stub' if stub else 'model';plan=bundle['plan'];atomic(out/'plan.json',plan)
    plan_sha=sha(packet/'plan.json');interpreter_sha=sha(bundle['budget']['tokenizer_python'])
    results={};abort=None;started=set();finished=False
    def summary():
        rows=[]
        for item in plan['trials']:
            key=(item['case_id'],item['condition'])
            if key in results:rows.append(results[key])
            else:rows.append({**item,'status':'incomplete' if key in started else 'unstarted',
                'unstarted_reason':'campaign-infrastructure-abort' if abort else 'not-started'})
        value={'schema':'history-study-summary.v1','protocol':PROTOCOL,'measurement_kind':kind,
            'status':'failed' if abort else 'completed' if finished else 'running',
            'infrastructure_abort':bool(abort),'infrastructure_error':abort,'expected_trials':8,'observed_trials':len(results),
            'completed_trials':sum(r['status']=='completed' for r in results.values()),
            'failed_trials':sum(r['status']=='failed' for r in results.values()),'trials':rows,
            'unstarted_trials':[r for r in rows if r['status']=='unstarted'],
            'server_identity':runtime,'engine_source_sha256':plan['engine_source_sha256'],
            'continuation_rule':CONTINUATION_RULE,'continuation_evaluated':False,'extension_admitted':False,
            'speed_gate_passed':False,'holdout_admitted':False,
            'scope':'Fixed authored temporal2x2 development comparison; no pooled speed or automatic extension.'}
        atomic(out/'summary.json',value);return value
    summary()
    try:
        for item in plan['trials']:
            check_frozen(packet,bundle,plan_sha,interpreter_sha)
            if not stub and sha(identity)!=runtime['launch_sha256']:raise ValueError('runtime identity changed')
            directory=out/Path(item['result_path']).parent;directory.mkdir();key=(item['case_id'],item['condition']);started.add(key);summary()
            argv=[sys.executable,str(HERE/'engine.py'),'--task',str(packet/item['task_path']),
                  '--out',str(directory/'native'),'--arm',item['arm'],'--retrieval-mode',item['retrieval_mode']]
            if stub:argv.append('--stub')
            else:argv.extend(['--endpoint',endpoint,'--model',model,'--identity',str(identity)])
            atomic(directory/'command.json',{'argv':argv})
            with (directory/'worker.log').open('x') as log:
                worker=run_owned(argv,stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
            native_path=directory/'native/result.json'
            if not native_path.is_file():raise RuntimeError(f'engine exited {worker.returncode} without native result')
            native=json.loads(native_path.read_bytes());task=bundle['tasks'][item['case_id']]
            if (native.get('schema')!='history-live-trial.v1' or native.get('protocol')!='historical-state-development-v1'
                or native.get('measurement_kind')!=kind or native.get('resumed') is not False
                or native.get('status') not in ('completed','failed') or native.get('retrieval_mode')!=item['retrieval_mode']
                or native.get('case_id')!=item['case_id'] or native.get('document_id')!=item['case_id']
                or native.get('source_sha256')!=task['source_sha256'] or native.get('adjudication_sha256')!=task.get('adjudication_sha256')
                or native.get('task_sha256')!=item['task_sha256'] or native.get('arm')!=item['arm']
                or native.get('source_code_sha256')!=plan['engine_source_sha256'] or native.get('server_identity')!=runtime):
                raise ValueError('native engine identity differs from frozen history study')
            for k,v in POLICY.items():
                if encoded(native.get(k))!=encoded(v):raise ValueError('native policy differs from study plan')
            for name,record in native['artifacts'].items():
                path=(directory/'native'/record['path']).resolve()
                if Path(record['path']).is_absolute() or not path.is_relative_to((directory/'native').resolve()) or sha(path)!=record['sha256']:
                    raise ValueError('native artifact hash/path mismatch')
            calls=[json.loads(line) for line in (directory/'native/calls.jsonl').read_text().splitlines()]
            for call in calls:finite_seconds(call['seconds'])
            wall=finite_seconds(native['wall_seconds']);costs=phase_costs(calls,item['initialization_batches'])
            if wall+0.000001<costs['total']['client_call_seconds']:raise ValueError('native total elapsed shorter than summed calls')
            actions=action_counts(calls,native,directory/'native')
            audit_error=None;reference_checks=False;audited=snapshots=None;auxiliary={}
            try:reference_checks,audited,snapshots,auxiliary=audit_native(directory/'native',native,task,item,plan,runtime,kind)
            except Exception as error:audit_error=f'{type(error).__name__}: {error}'
            quality=not stub and reference_checks
            value={'schema':'history-study-trial.v1','protocol':PROTOCOL,**item,'status':native['status'],
                'measurement_kind':kind,'server_identity':runtime,'engine_source_sha256':plan['engine_source_sha256'],
                'wrapper_source_sha256':plan['wrapper_source_sha256'],'source_sha256':task['source_sha256'],
                'adjudication_sha256':task['adjudication_sha256'],'annotation_sources':task['annotation_sources'],
                'reference_provenance':'Assistant-authored and independently assistant-annotated temporal development source.',
                'reference_checks_passed':reference_checks,'quality_passed':quality,'audit_error':audit_error,
                'native_audit':audited,'snapshot_audit':snapshots,'native_auxiliary':auxiliary,'score':native['score'],
                'cold_cost_interpretation':not stub and costs['total']['cache_complete'] and costs['total']['cached_tokens']==0,
                'phase_costs':costs,'action_counts':actions,'total_trial_wall_seconds':wall,
                'non_call_overhead_seconds':wall-costs['total']['client_call_seconds'],
                'native_sha256':sha(native_path),'native_artifacts':native['artifacts'],
                'extension_admitted':False,'speed_gate_passed':False,'holdout_admitted':False}
            atomic(directory/'result.json',value);results[key]={**item,'status':native['status'],'quality_passed':quality};summary()
            if worker.returncode or native.get('failure_kind')=='infrastructure' or audit_error:
                raise RuntimeError('native infrastructure or audit failure; no further trials: '+str(audit_error))
            check_frozen(packet,bundle,plan_sha,interpreter_sha)
            if not stub and sha(identity)!=runtime['launch_sha256']:raise ValueError('runtime identity changed after trial')
        finished=True
    except BaseException as error:abort=f'{type(error).__name__}: {error}';summary();raise
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
