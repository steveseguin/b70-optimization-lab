#!/usr/bin/env python3
"""One persistent research endpoint, fail-closed MTP metadata qualification/screen.

Client only: no GPU ownership, Docker, service launch/stop/reload or retry.
Parent must provide exclusive endpoint admission and wrap with the fault monitor.
"""
from __future__ import annotations
import argparse
import datetime as dt
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
SOURCE_SHA = '95b0a3c079cb63f04a1a0b78b290c7496c63cc5ebc4dc567962de335ea894b9a'
CANDIDATE_AST = '30d6d181060d10f9132c4cbe4163d97931b5a7a177ad6f63d7145b8fce8b17c0'
CONTROL_IMAGE = 'sha256:506fcc26897b12915cb9e27c28e0adc256d278666fa745602a1ae5e1dd8ea066'
ORIGINAL_IDENTITY = Path('/mnt/fast-ai/bench-results/amd-transfer-fp8-20260914/control-identity.json')
MODEL_DIR = '/mnt/fast-ai/llm-models/qwen3.8-27b-fp8'
ARMS = (('control-1','control'),('candidate-1','candidate'),('control-2','control'),('candidate-2','candidate'))
# Qualified service env the recorded contract omits; the research launcher adds it (2026-09-15).
QUALIFIED_ENV = {'PYTORCH_ALLOC_CONF': 'expandable_segments:True', 'FI_PROVIDER': 'tcp',
                 'FI_TCP_IFACE': 'lo', 'PYTHONHASHSEED': '0', 'TORCHINDUCTOR_DETERMINISTIC': '1'}


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value): Path(path).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
def read(path): return json.loads(Path(path).read_text())


def repeated_values(argv, flag):
    return [argv[i+1] for i, value in enumerate(argv[:-1]) if value == flag]


def one_value(argv, flag):
    values = repeated_values(argv, flag)
    if len(values) != 1:
        raise RuntimeError(f'Expected exactly one {flag}, found {len(values)}')
    return values[0]


def server_identity_gate(path, model):
    """Bind the controller launch to its ready state, immutable image and files."""
    path = Path(path).resolve()
    launch = read(path); state = read(path.parent/'state.json'); images = read(path.parent/'image.json')
    if (state.get('status') != 'ready' or state.get('image_id') != CONTROL_IMAGE
            or state.get('port') != 18129 or not isinstance(state.get('container_id'), str)
            or not re.fullmatch(r'[0-9a-f]{64}', state['container_id'])
            or state.get('boot_id') != Path('/proc/sys/kernel/random/boot_id').read_text().strip()):
        raise RuntimeError('Research controller is not ready under the current boot and admitted image')
    if len(images) != 1 or images[0].get('Id') != CONTROL_IMAGE:
        raise RuntimeError('Research image receipt differs from the reviewed control')
    argv = launch['argv']
    if argv[:2] != ['docker', 'run'] or argv.count(CONTROL_IMAGE) != 1:
        raise RuntimeError('Unexpected research Docker launch')
    index = argv.index(CONTROL_IMAGE); docker_args = argv[:index]; model_args = argv[index+1:]
    original = read(ORIGINAL_IDENTITY)
    if launch.get('original_control_sha256') != sha(ORIGINAL_IDENTITY):
        raise RuntimeError('Historical control identity differs from launch receipt')
    if model_args != original['command'] + ['--worker-extension-cls', 'mtp_transfer_worker.MtpTransferWorkerExtension']:
        raise RuntimeError('Model flags differ from unchanged native-MTP control plus research extension')
    required_flags = {'--model':'/model','--tensor-parallel-size':'2','--dtype':'float16',
        '--quantization':'fp8','--kv-cache-dtype':'auto','--max-model-len':'33024','--max-num-seqs':'1'}
    if (any(one_value(model_args,key) != value for key,value in required_flags.items())
            or '--no-enable-prefix-caching' not in model_args
            or json.loads(one_value(model_args,'--speculative-config')) != {'method':'qwen3_next_mtp','num_speculative_tokens':1}):
        raise RuntimeError('FP8/native-MTP1 target, KV, context or caching contract differs')
    if one_value(model_args, '--served-model-name') != model:
        raise RuntimeError('Requested model alias differs from admitted server')
    expected_env = dict(e.split('=',1) for e in original['env'])
    expected_env.update(QUALIFIED_ENV, PYTHONPATH='/research', VLLM_SERVER_DEV_MODE='1')
    pairs = [e.split('=',1) for e in repeated_values(docker_args,'--env')]
    actual_env = dict(pairs)
    if len(actual_env) != len(pairs) or actual_env != expected_env or actual_env.get('VLLM_USE_V2_MODEL_RUNNER') != '0':
        raise RuntimeError('Runtime environment differs from unchanged V1 control plus local RPC support')
    if one_value(docker_args,'--name') != state['container_name'] or one_value(docker_args,'-p') != '127.0.0.1:18129:8000' or one_value(docker_args,'--restart') != 'no':
        raise RuntimeError('Container ownership, localhost exposure or restart policy differs')
    if (one_value(docker_args,'--cap-add') != 'SYS_PTRACE'
            or one_value(docker_args,'--network') != 'bridge'
            or one_value(docker_args,'--ipc') != 'host'):
        raise RuntimeError('Qualified pidfd IPC capability, network or IPC mode differs')
    snapshot = path.parent/'research-extension'
    mounts = repeated_values(docker_args,'--mount')
    if f'type=bind,source={MODEL_DIR},target=/model,readonly' not in mounts or f'type=bind,source={snapshot},target=/research,readonly' not in mounts:
        raise RuntimeError('Required official read-only model or frozen extension mount differs')
    expected_files = ('mtp_transfer_worker.py','mtp_native_metadata_gate.py')
    if set(launch.get('extensions',{})) != set(expected_files):
        raise RuntimeError('Extension manifest coverage differs')
    bound = [path, path.parent/'image.json', ORIGINAL_IDENTITY]
    for name in expected_files:
        frozen = snapshot/name; reviewed = HERE.parent/'probes/mtp-metadata-20260914'/name
        if sha(frozen) != launch['extensions'][name] or sha(reviewed) != launch['extensions'][name]:
            raise RuntimeError('Mounted extension differs from its launch hash or reviewed source')
        bound.append(frozen)
    for marker in (path.parent/'STOP_UNCONFIRMED', path.parent/'STOP', path.parent.parent/'FAULT.json'):
        if marker.exists():
            raise RuntimeError(f'Server stop/fault latch present: {marker}')
    return launch, bound


def source_gate(records):
    for row in records:
        if sha(row['path']) != row['sha256']:
            raise RuntimeError(f'Pinned client, identity or frozen oracle changed: {row["path"]}')


def counter_gate(before, after, mode):
    other = 'candidate' if mode == 'control' else 'control'
    deltas = []
    for rank in (0,1):
        b = next(r for r in before if r['rank'] == rank)['calls']
        a = next(r for r in after if r['rank'] == rank)['calls']
        if a[mode] <= b[mode] or a[other] != b[other]:
            raise RuntimeError('Rank did not execute exclusively the selected metadata arm')
        deltas.append(a[mode]-b[mode])
    if deltas[0] != deltas[1]:
        raise RuntimeError('Ranks executed different numbers of metadata calls')
    return deltas[0]


def idle_metrics(text):
    found={'running':[],'waiting':[]}
    for line in text.splitlines():
        match=re.fullmatch(r'vllm:num_requests_(running|waiting)(?:\{[^}]*\})?\s+(\S+)(?:\s+\d+)?',line)
        if match: found[match[1]].append(float(match[2]))
    if not all(values and all(math.isfinite(v) and v == 0 for v in values) for values in found.values()):
        raise RuntimeError(f'Endpoint must be idle with explicit running/waiting metrics: {found}')
    return found


def statuses(response, mode, native=None):
    rows=response.get('results')
    if not isinstance(rows,list) or len(rows)!=2 or any(not isinstance(r,dict) for r in rows):
        raise RuntimeError('RPC must return exactly two rank dictionaries')
    if any(type(r.get('rank')) is not int for r in rows) or {r.get('rank') for r in rows}!={0,1}: raise RuntimeError('RPC rank coverage differs')
    for row in rows:
        if row.get('source_sha256')!=SOURCE_SHA or row.get('mode')!=mode:
            raise RuntimeError('Rank source/mode mismatch')
        if mode=='unwrapped-control':
            if row.get('installed') is not False or row.get('wrapper_active') is not False:
                raise RuntimeError('Fresh-base qualification requires unwrapped control')
        elif row.get('installed') is not True or row.get('wrapper_active') is not True or row.get('candidate_ast_sha256')!=CANDIDATE_AST:
            raise RuntimeError('Rank dispatch/AST mismatch')
        if mode != 'unwrapped-control':
            calls = row.get('calls')
            if (not isinstance(calls,dict) or set(calls) != {'control','candidate'}
                    or any(type(v) is not int or v < 0 for v in calls.values())):
                raise RuntimeError('Rank call counters are missing or invalid')
        if native is not None and row.get('native_gate_passed') is not native:
            raise RuntimeError('Rank native gate mismatch')
    return rows


def strict_gate(directory):
    p=read(directory/'performance.json')
    c=read(directory/'canaries.json')
    rows=p['rows']
    assert p['realistic_final_gate']['passed'] is True
    assert p['fresh_response_validity']['performance_gate_eligible'] is True
    assert p['fresh_response_validity']['cached_tokens_all_zero'] is True
    assert c['pass_all'] is True and len(rows)==12
    assert len({r['prompt_id'] for r in rows})==12
    for row in rows:
        ids=row['token_ids']
        assert type(row['cached_tokens']) is int and row['cached_tokens']==0
        assert isinstance(ids,list) and 100 <= len(ids) == row['completion_tokens'] <= 512
        assert all(type(token) is int and token>=0 for token in ids)
    return p


def parity_gate(path):
    result=read(path)
    comparison=result['comparison']
    if (comparison['exact_prompts']!=12 or comparison['total_prompts']!=12 or
            comparison['complete_token_arrays_exact'] is not True or
            result['qualification']['strict_pair_qualified'] is not True):
        raise RuntimeError('Full strict token parity failed; stop all later requests')
    return result


def native_gate(response):
    rows=response.get('results')
    if not isinstance(rows,list) or len(rows)!=2 or any(not isinstance(r,dict) or type(r.get('rank')) is not int for r in rows) or {r.get('rank') for r in rows}!={0,1}:
        raise RuntimeError('Native gate needs both ranks')
    for row in rows:
        result=row['result']; cases=result['cases']
        if result.get('passed') is not True or result.get('case_count')!=36 or len(cases)!=36:
            raise RuntimeError('Native gate did not complete all 36 cases')
        if len({(c['case'],c['full_graph_metadata']) for c in cases})!=36:
            raise RuntimeError('Native case coverage duplicates')
        for c in cases:
            if c.get('exact_fields')!=24 or c.get('aliases_equal') is not True or c.get('retained_views_equal') is not True or c.get('inputs_unmodified_except_documented_cache') is not True or c.get('buffer_reuses')!=3:
                raise RuntimeError('Native field/alias/lifetime gate incomplete')
    statuses({'results':[row['status'] for row in rows]},'control',True)
    return rows


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base-url',default='http://127.0.0.1:18129')
    ap.add_argument('--model',required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--frozen-strict',type=Path,required=True)
    ap.add_argument('--frozen-context',type=Path,required=True)
    ap.add_argument('--server-identity',type=Path,required=True,help='Parent verified immutable launch/server identity receipt')
    ap.add_argument('--check-only',action='store_true')
    args=ap.parse_args()
    parsed=urllib.parse.urlsplit(args.base_url)
    if parsed.scheme!='http' or parsed.hostname!='127.0.0.1' or parsed.port!=18129 or parsed.path not in ('','/'):
        ap.error('This preregistration admits only localhost research port18129')
    strict_gate(args.frozen_strict)
    assert read(args.frozen_context).get('passed') is True
    identity, identity_paths=server_identity_gate(args.server_identity,args.model)
    paths=[Path(__file__),ROOT/'repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-mtp1-strict.sh', ROOT/'scripts/bench-openai-realistic-suite.py',ROOT/'scripts/neural-download-canaries.py',ROOT/'scripts/compare-strict-attempt-outputs.py',HERE/'bench-prefill-followup.py',HERE/'bench-short-prefill.py',ROOT/'repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json',HERE.parent/'data/2026-09-14-amd-transfer/corpus.json',HERE.parent/'probes/mtp-metadata-20260914/mtp_transfer_worker.py',HERE.parent/'probes/mtp-metadata-20260914/mtp_native_metadata_gate.py',args.server_identity]
    paths += identity_paths + [args.frozen_strict/name for name in ('performance.json','canaries.json','campaign-identity.json')] + [args.frozen_context]
    paths = list(dict.fromkeys(p.resolve() for p in paths))
    prereg={'schema':'neural.download.mtp-metadata-client-prereg.v1','created_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'base_url':args.base_url,'model':args.model,'server_identity':identity,'files':[{'path':str(p.resolve()),'sha256':sha(p)} for p in paths],'sequence':['unwrapped-strict-vs-frozen','prepare-wrapper-in-control','native-36-cases-both-ranks']+[f'{label}:strict+context' for label,mode in ARMS]+['leave-wrapped-control'],'full_strict_attempts':5,'strict_prompts_per_attempt':12,'strict_response_cap':512,'context_lengths':[512,2048,16384],'context_repeats_per_arm':2,'context_output_tokens':128,'context_measured_requests_per_arm':18,'context_warmups_per_arm':3,'cache_tokens_required':0,'concurrent_users':1,'fresh_server_confirmation':False,'promotion':False,'stopping':'Any request failure, non-idle transition, token/cache/native/rank mismatch or parent fault latch stops subsequent requests. No retries, no service control, no automatic recovery RPC.'}
    if args.check_only:
        print(json.dumps({'check_only':True,'passed':True,'preregistration':prereg},indent=2));return
    args.out.mkdir(parents=True,exist_ok=False)
    save(args.out/'preregistration.json',prereg)
    lock=open('/tmp/qwen-mtp-metadata-campaign.lock','a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    state={'schema':'neural.download.mtp-metadata-client-campaign.v1','passed':False,'promoted':False,'arms':[],'preregistration_sha256':sha(args.out/'preregistration.json')}
    save(args.out/'summary.json',state)
    rpc_index=0
    child=None
    def faults():
        source_gate(prereg['files'])
        server_identity_gate(args.server_identity,args.model)
        for directory in (args.out,args.out.parent):
            if (directory/'FAULT.json').exists(): raise RuntimeError('Parent fault latch present; no requests admitted')
    def http(path,payload=None,timeout=20):
        faults()
        request=urllib.request.Request(args.base_url.rstrip('/')+path,data=None if payload is None else json.dumps(payload).encode(),headers={'Content-Type':'application/json'} if payload is not None else {})
        with urllib.request.urlopen(request,timeout=timeout) as response: return response.read()
    def idle(label):
        for sample in range(2):
            text=http('/metrics').decode()
            (args.out/f'{label}-idle-{sample}.txt').write_text(text)
            idle_metrics(text)
            if sample==0: time.sleep(.25)
    def rpc(method,kwargs=None,timeout=180):
        nonlocal rpc_index
        rpc_index+=1
        label=f'rpc-{rpc_index:02d}-{method}'
        idle(label)
        payload={'method':method,'args':[],'kwargs':kwargs or {},'timeout':timeout}
        save(args.out/f'{label}-request.json',payload)
        raw=http('/collective_rpc',payload,timeout+15)
        (args.out/f'{label}-response.json').write_bytes(raw)
        return json.loads(raw)
    def run(label,command,env=None,timeout=3600):
        nonlocal child
        faults()
        save(args.out/f'{label}-command.json',{'argv':list(map(str,command)),'explicit_env':env})
        with (args.out/f'{label}.log').open('w') as log:
            child=subprocess.Popen(list(map(str,command)),cwd=ROOT,env={**os.environ,**(env or {})},stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            try:
                code=child.wait(timeout=timeout)
                if code: raise RuntimeError(f'{label} client exited {code}; later requests skipped')
            finally:
                if child.poll() is None:
                    os.killpg(child.pid,signal.SIGINT)
                    try: child.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        (args.out/'CLIENT_EXIT_UNCONFIRMED').write_text(str(child.pid)+'\n')
                        raise
                child=None
        faults()
    def strict(label):
        directory=args.out/label/'strict'
        directory.parent.mkdir(exist_ok=False)
        run(label+'-strict',['bash',paths[1]],{'OUT_DIR':str(directory),'BASE_URL':args.base_url,'MODEL_NAME':args.model,'PROFILE_LABEL':'mtp-metadata-lossless-screen','ATTEMPT_LABEL':label,'SUITE':str(paths[7])})
        strict_gate(directory)
        parity=args.out/f'{label}-frozen-strict-parity.json'
        run(label+'-parity',[sys.executable,ROOT/'scripts/compare-strict-attempt-outputs.py',args.frozen_strict,directory,'--output',parity])
        parity_gate(parity)
        return directory
    def terminate(signum,frame): raise KeyboardInterrupt(f'signal {signum}; no further requests')
    signal.signal(signal.SIGINT,terminate);signal.signal(signal.SIGTERM,terminate)
    try:
        statuses(rpc('mtp_transfer_status'),'unwrapped-control',False)
        strict('unwrapped-base')
        state['refreshed_unwrapped_base_12_of_12_exact']=True
        save(args.out/'summary.json',state)
        statuses(rpc('mtp_transfer_status'),'unwrapped-control',False)
        statuses(rpc('mtp_transfer_prepare'),'control',False)
        native_gate(rpc('mtp_transfer_native_gate',timeout=300))
        state['native_36_cases_both_ranks_passed']=True
        save(args.out/'summary.json',state)
        for label,mode in ARMS:
            before=statuses(rpc('mtp_transfer_set_mode',{'mode':mode}),mode,True)
            strict_dir=strict(label)
            context=args.out/label/'context'
            # Every arm must match the frozen full continuation IDs. Matching one
            # fixed oracle also enforces exact cross-arm and repeat determinism.
            run(label+'-context',[sys.executable,HERE/'bench-prefill-followup.py','--base-url',args.base_url,'--model',args.model,'--out',context,'--corpus',paths[8],'--lengths','512,2048,16384','--max-model-len','33024','--max-tokens','128','--repeats','2','--baseline',args.frozen_context])
            context_result=read(context/'summary.json')
            if context_result.get('passed') is not True or len(context_result['rows'])!=18:
                raise RuntimeError('Context repeat/quality gate incomplete')
            after=statuses(rpc('mtp_transfer_status'),mode,True)
            matched_rank_calls=counter_gate(before,after,mode)
            performance=read(strict_dir/'performance.json')
            state['arms'].append({'label':label,'mode':mode,'strict_performance_sha256':sha(strict_dir/'performance.json'),'context_summary_sha256':sha(context/'summary.json'),'class_balanced_decode_tok_s':performance['summary']['class_balanced_tok_s_1_100_intervals_after_ttft']['median'],'context_by_length':context_result['by_length'],'rank_status_before':before,'rank_status_after':after,'matched_metadata_calls_per_rank':matched_rank_calls,'complete_outputs_match_frozen':True})
            save(args.out/'summary.json',state)
        state['final_rank_status']=statuses(rpc('mtp_transfer_set_mode',{'mode':'control'}),'control',True)
        state['passed']=True
        state['interpretation']='Single persistent-process screen only. All outputs exact versus frozen reference; matched control/candidate results retained. No independent-process confirmation or promotion.'
        (args.out/'SCREEN_COMPLETED').write_text('Wrapped control selected; no performance promotion.\n')
    except BaseException as exc:
        state['error']=f'{type(exc).__name__}: {exc}'
        state['endpoint_mode']='Unknown/current arm; no recovery request sent. Parent must inspect preserved evidence.'
        (args.out/'ABORTED').write_text(state['error']+'\n')
        raise
    finally:
        save(args.out/'summary.json',state)
        lock.close()
    print(json.dumps({'passed':state['passed'],'promoted':False,'out':str(args.out)}))

if __name__=='__main__':main()
