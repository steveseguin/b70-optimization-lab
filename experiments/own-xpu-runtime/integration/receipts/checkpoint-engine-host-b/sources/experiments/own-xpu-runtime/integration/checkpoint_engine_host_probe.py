#!/usr/bin/env python3
"""Prepared isolated GNU HOST_ONLY integration probe; --plan never runs native code."""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import sys
import time

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PACKET = ROOT/'experiments/own-xpu-runtime/stage2/packet198-postreply-checkpoint'
DEFAULT_OUTPUT = PACKET/'build/engine-integration-b'
SAVE_BOUND = 8*1024**2  # Tiny context64 fixture only; no real-model bound claim.
FLOOR = 27_000_000_000
SYNTHETIC_IDENTITY = ''.join(f'synthetic-host-shard-{n} 0 0 0 0 0\n' for n in range(3)).encode()

from checkpoint_bridge import IDENTITY_FIELDS
from checkpoint_engine import CheckpointEngine
from native_checkpoint_store import NativeCheckpointStore
from request_front.client_v2 import NativeFront


def read(path): return json.loads(Path(path).read_text())
def sha(path):
    with Path(path).open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
def require(condition,reason):
    if not condition: raise RuntimeError(reason)
def save(path,row): Path(path).write_text(json.dumps(row,indent=2)+'\n')


def synthetic_model_identity(data):
    """Match the native writer's three-row fixture shape without model I/O."""
    rows=[]
    for line in data.decode('ascii').splitlines():
        if not line:continue
        fields=line.split()
        require(len(fields)==6 and Path(fields[0]).name==fields[0], 'synthetic identity row shape')
        values=[int(value) for value in fields[1:]]
        require(all(0<=value<2**64 for value in values), 'synthetic identity unsigned stat values')
        rows.append(dict(zip(('name','size','dev','ino','mtime','ctime'),[fields[0],*values])))
    require(len(rows)==3 and len({row['name'] for row in rows})==3, 'three distinct synthetic shard rows required')
    return dict(identity_tsv_sha256=hashlib.sha256(data).hexdigest(),shard_stat_rows=rows)


def modules():
    def load(name,path):
        spec=importlib.util.spec_from_file_location(name,path)
        module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
        return module
    return (load('checkpoint_probe_parking',ROOT/'tools/ctxkeeper/parking.py'),
            load('checkpoint_probe_host_parent',PACKET/'host_probe.py'))


def plan(output):
    require(output.parent == PACKET/'build' and output.name.startswith('engine-integration-'), 'fresh packet build scratch required')
    require(not output.exists(), 'output exists; preserve it, never retry or overwrite')
    ready=read(PACKET/'READY-FOR-DEVICE.json')
    for path in (PACKET/'evidence/build-compile-only.json',PACKET/'evidence/host-probe.json',PACKET/'host_probe.py',
                 PACKET/'evidence/host-probe-artifacts.json',HERE/'request_front/client_v2.py'):
        require(sha(path)==ready['files_sha256'][str(path.relative_to(ROOT))], 'sealed fixture input drift: '+str(path))
    build=read(PACKET/'evidence/build-compile-only.json');host=next(p for p in build['plans'] if p['target']=='host')
    require(build['passed'] and build['device_executed'] is False and build['native_executed'] is False, 'compile-only receipt required')
    require(host['commands'][0][0]=='/usr/bin/g++' and '-DOWN_RT_HOST_ONLY' in host['commands'][0], 'GNU HOST_ONLY executable required')
    binary=Path(host['binary']);require(binary==PACKET/'build/host/own-rt-iq3' and sha(binary)==host['binary_sha256'],'host binary identity changed')
    proof=read(PACKET/'evidence/host-probe.json')
    require(proof['passed'] and proof['device_executed'] is False and proof['binary_sha256']==host['binary_sha256'], 'prior host proof mismatch')
    prior=Path(proof['lifecycle']['run_directory']);manifest=prior/'checkpoints/s1/manifest.json';tokenizer=prior/'tokenizer.tsv'
    artifacts=read(PACKET/'evidence/host-probe-artifacts.json')
    # The sealed artifact manifest binds these previously recorded tiny fixtures.
    require(all(artifacts['files_sha256'].get(str(p.relative_to(ROOT)))==sha(p) for p in (manifest,tokenizer)),
            'prior fixture digest not retained in sealed inventory')
    expected={key:copy.deepcopy(read(manifest)[key]) for key in IDENTITY_FIELDS}
    require(expected['geometry']['context']==64 and expected['geometry']['vocab']==16 and
            expected['engine']['binary_sha256']==host['binary_sha256'], 'tiny same-binary fixture required')
    # Mini never reads model shards. Its checkpoint writer nevertheless requires
    # three stat rows whenever --identity is supplied. These named zero-stat rows
    # are explicit synthetic metadata, never claims about actual model files.
    expected['model']=synthetic_model_identity(SYNTHETIC_IDENTITY)
    argv=[str(binary),'--mini','--pipeline-mini','--context','64','--retain-steps','none',
          '--identity',str(output/'synthetic-identity.tsv'),'--native-nice','19','--seconds','180',
          '--request-front','--request-front-max-requests','8','--request-front-idle-seconds','30',
          '--request-front-checkpoints',str(output/'checkpoints'),'--request-front-tokenizer-identity',str(output/'tokenizer.tsv'),
          '--output',str(output/'owner')]
    sources=[Path(__file__),HERE/'checkpoint_engine.py',HERE/'checkpoint_bridge.py',HERE/'native_checkpoint_store.py',
             HERE/'request_front/client_v2.py',ROOT/'tools/ctxkeeper/parking.py']
    return dict(passed=True,device_executed=False,native_executed=False,output=str(output),argv=argv,
                binary_sha256=host['binary_sha256'],prior_manifest=str(manifest),prior_manifest_sha256=sha(manifest),
                tokenizer_source=str(tokenizer),tokenizer_sha256=sha(tokenizer),expected_identity=expected,
                synthetic_identity_bytes=len(SYNTHETIC_IDENTITY),synthetic_identity_sha256=hashlib.sha256(SYNTHETIC_IDENTITY).hexdigest(),
                synthetic_identity_text=SYNTHETIC_IDENTITY.decode('ascii'),
                save_bound_bytes=SAVE_BOUND,disk_floor_bytes=FLOOR,expected_requests=8,expected_controls=8,
                scope='Tiny HOST_ONLY arithmetic and adapter/store integration only; no real-model/device/HTTP qualification',
                sources_sha256={str(p.relative_to(ROOT)):sha(p) for p in sources})


def state_hashes(directory):
    files=sorted(Path(directory).glob('*.bin'))
    require(files and sum(p.stat().st_size for p in files)<SAVE_BOUND,'tiny fixture state bound')
    return {p.name:sha(p) for p in files}


def execute(spec):
    require(os.getpriority(os.PRIO_PROCESS,0)==19 and set(os.sched_getaffinity(0)) <= set(range(8,16))|set(range(24,32)),
            'nice19 helper cores required')
    require(shutil.disk_usage(ROOT).free >= FLOOR+8*SAVE_BOUND,'root floor after bounded tiny fixture writes')
    output=Path(spec['output']);require(plan(output)==spec,'inputs changed before owner launch')
    policy_module,parent=modules();environment=parent.parent_environment()
    tool_environment={key:environment[key] for key in ('PATH','OMP_NUM_THREADS','LD_LIBRARY_PATH')}
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
    output.mkdir();(output/'checkpoints').mkdir()
    (output/'synthetic-identity.tsv').write_bytes(SYNTHETIC_IDENTITY)
    (output/'tokenizer.tsv').write_bytes(Path(spec['tokenizer_source']).read_bytes())
    save(output/'plan.json',spec)
    owner=None;incident_sent=False
    result=dict(passed=False,device_executed=False,native_host_executed=False,plan=spec,events=[])
    try:
        with (output/'stderr.log').open('wb') as log:
            owner=subprocess.Popen(spec['argv'],env=environment,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log)
            result.update(native_host_executed=True,pid=owner.pid)
            front=NativeFront(owner,context=64,vocab=16,max_requests=8,startup_timeout=30,request_timeout=30)
            with NativeCheckpointStore(output/'checkpoints',Path(spec['argv'][0]),spec['binary_sha256'],tool_environment) as store:
                engine=CheckpointEngine(front,store,root=output/'checkpoints',expected_identity=spec['expected_identity'],
                    admitted_contract='v1.2+p198',save_size_bound_bytes=SAVE_BOUND,
                    storage_available=lambda path:shutil.disk_usage(path).free,floor_bytes=FLOOR)
                def parking(budget):
                    return policy_module.Parking(engine,lambda messages:messages,lambda messages:list(messages[0]['tokens']),
                        budget_bytes=budget,accepted_contracts={('experimental-postreply-front','v1.2+p198')})
                cached,uncached,same=parking(4*SAVE_BOUND),parking(0),parking(2*SAVE_BOUND)
                def messages(tokens):return [{'role':'synthetic-host-token-fixture','tokens':tokens}]
                def turn(policy,session,rid,tokens,cap):
                    row=engine.run_turn(policy,session,messages(tokens),request_id=rid,max_new=cap)
                    result['events'].append(dict(request_id=rid,action=row['decision'].action,reason=row['decision'].reason,
                        tokens=row['response']['tokens'],checkpoint=row['parked'].checkpoint_id if row['parked'] else None,
                        released=row['release'] is not None))
                    return row
                a,b=[2,5,3,7,1],[4,6,2,8]
                first=turn(cached,'a','a-park',a,8)
                first_b=turn(uncached,'b','b-release',b,4)
                appended=a+first['response']['tokens']+[4,6,9,2,8,3]
                append=turn(cached,'a','a-append',appended,4)
                require(append['decision'].action=='restore','append did not restore')
                append_state=state_hashes(output/'checkpoints'/append['parked'].checkpoint_id)
                fresh=turn(cached,'fresh','fresh-append',appended,4)
                fresh_state=state_hashes(output/'checkpoints'/fresh['parked'].checkpoint_id)
                require(append['response']['tokens']==fresh['response']['tokens'] and append_state==fresh_state,
                        'append differs from fresh tokens/state')
                edited=turn(cached,'a','a-edited',[9,5,3,7,1],4)
                require(edited['decision'].action=='prefill' and 'not a prefix' in edited['decision'].reason,'edited prompt did not prefill')
                initial_same=turn(same,'same','same-initial',a,8)
                # Deliberate fresh replay isolates Parking's same-ID shortcut.
                # A normal before_request on this shorter prompt would drop it.
                response=engine.generate(a,8,request_id='same-replay')
                count=front.completed_controls
                same_hit=same.park('same',messages(a),response['tokens'])
                require(same_hit is initial_same['parked'] and front.completed_controls==count and
                        front.state=='awaiting-disposition','same-ID path unexpectedly saved/disposed')
                engine.release()
                result['events'].append(dict(request_id='same-replay',action='explicit-fresh-replay',tokens=response['tokens'],
                    checkpoint=same_hit.checkpoint_id,released=True,same_id_reinspected=True))
                final=turn(uncached,'b','final-b-release',b,4)
                require(first_b['response']['tokens']==final['response']['tokens'],'B repeat mismatch')
                require(front.state=='draining' and front.pending is None,'final RELEASE did not start clean drain')
                stopped=front.close(timeout=30)
                require(stopped['reason']=='request-limit' and stopped['completed_requests']==stopped['completed_controls']==8
                        and stopped['discarded_pending'] is False and stopped['pending_request_id']=='','unclean stopped proof')
                native=read(output/'owner/receipt.json')
                require(native['passed'] and native['safe_to_exit'] and native['device_executed'] is False and owner.returncode==0,
                        'HOST_ONLY teardown proof failed')
                result.update(passed=True,stopped=stopped,model_loads=front.ready['model_loads'],owner_returncode=owner.returncode,
                    append_fresh_tokens_exact=True,append_fresh_state_exact=True,append_state_sha256=append_state,
                    fresh_state_sha256=fresh_state,edited_prefill=True,same_id_reinspected_then_released=True,
                    completed_controls=front.completed_controls,policy_status=cached.status(),native_receipt_sha256=sha(output/'owner/receipt.json'))
    except BaseException as error:
        result['error']=str(error)
        if owner is not None and owner.poll() is None:
            incident_sent=True
            try:owner.send_signal(signal.SIGTERM)
            except ProcessLookupError:require(owner.poll() is not None,'host owner vanished without exit proof')
            try:owner.wait(timeout=65)
            except subprocess.TimeoutExpired:pass
        result.update(incident_sigterm_count=int(incident_sent),owner_retained=owner is not None and owner.poll() is None)
        raise
    finally:
        result['finished_utc_ns']=time.time_ns();save(output/'result.json',result)
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__);mode=ap.add_mutually_exclusive_group(required=True)
    mode.add_argument('--plan',action='store_true');mode.add_argument('--run-host-only',action='store_true')
    ap.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    args=ap.parse_args();spec=plan(args.output.absolute())
    if args.plan:print(json.dumps(spec,indent=2));return
    result=execute(spec);print(json.dumps(dict(passed=result['passed'],device_executed=False,
        requests=len(result['events']),controls=result['completed_controls'],output=spec['output'])))


if __name__=='__main__':main()
