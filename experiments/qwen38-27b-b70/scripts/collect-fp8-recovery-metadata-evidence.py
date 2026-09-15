#!/usr/bin/env python3
"""CPU/file-only recovery and native-MTP metadata evidence collector/verifier.

New packet; historical incident collectors/parsers remain untouched. Reuses their
bounded deterministic archive writer and strict/context/RPC replay functions.
Requires a final closure receipt; never collects a campaign still in progress.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import tarfile
import io
import importlib.util
import struct
import datetime as dt
import math

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
ROOT_DEFAULT=Path('/mnt/fast-ai/bench-results/fp8-mtp-recovery-metadata-20260914')
PACKET_DEFAULT=HERE.parent/'data/2026-09-14-fp8-mtp-recovery-metadata'
AMD_PACKET=HERE.parent/'data/2026-09-14-amd-transfer'
INCIDENT_PACKET=HERE.parent/'data/2026-09-14-mtp-lossless-transfer'
PHASES=('health','recovered-service','recovery-strict','recovery-strict-monitor','research-server','health-after-research-oom','client-campaign','client-monitor','final-service','final-strict','final-strict-monitor')
HEALTH_PHASES=('health','health-after-research-oom')
RESEARCH_POSTFLIGHT_SCHEMA='neural.download.research-server-postflight.v1'
SERVICES=('recovered-service','research-server','final-service')
FROZEN_RAW=Path('/mnt/fast-ai/bench-results/amd-transfer-fp8-20260914')
SOURCE_FILES=('collect-fp8-recovery-metadata-evidence.py','collect-mtp-transfer-evidence.py','collect-amd-transfer-evidence.py','bench-prefill-followup.py','bench-short-prefill.py','run-mtp-metadata-client-campaign.py','run-mtp-lossless-server.py','run-fp8-recovery-health.py','monitor-transfer-client.py')


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


prior=load('recovery_packet_prior',HERE/'collect-mtp-transfer-evidence.py')
sha,encoded,require=prior.sha,prior.encoded,prior.require


def closure_gate(closure):
    require(closure.get('status') in {'completed','blocked','closed-after-gpu-fault','closed-after-failure'},'Explicit terminal campaign status required')
    require(isinstance(closure.get('finished_at'),str) and bool(closure['finished_at'].strip()),'Closure finished_at required')
    require(closure.get('final_service',{}).get('status') in {'ready','stopped','failed','not-started','stop_unconfirmed'},'Explicit final service state required')


def oracle_from_frozen_archive():
    """Admit exact baseline bytes through their previously published archive pins."""
    manifest_raw=(AMD_PACKET/'manifest.json').read_bytes();manifest=json.loads(manifest_raw)
    archive=(AMD_PACKET/manifest['archive']).read_bytes()
    require(sha(archive)==manifest['archive_sha256'],'Frozen AMD oracle archive hash differs')
    prior.legacy.verify_archive(archive,manifest['members'])
    data={'provenance/frozen-oracle-manifest.json':manifest_raw}
    origins={}
    with tarfile.open(fileobj=io.BytesIO(archive),mode='r:gz') as stream:
        for member in stream:
            name=member.name
            if name=='control-identity.json' or name.startswith(('control-strict/','control-context/')):
                raw=stream.extractfile(member).read();target='frozen/'+name
                data[target]=raw
                origins[target]={'path':str(FROZEN_RAW/name),'bytes':len(raw),'origin_archive':str(AMD_PACKET/manifest['archive']),'origin_archive_member':name}
    require('frozen/control-strict/performance.json' in data and 'frozen/control-context/summary.json' in data,'Frozen oracle coverage absent')
    # The earlier fault is referenced through its closed repository packet, not
    # mutable raw state. No old operator workload or library is copied/reopened.
    old_manifest_raw=(INCIDENT_PACKET/'manifest.json').read_bytes();old_manifest=json.loads(old_manifest_raw)
    data['provenance/prior-incident-manifest.json']=old_manifest_raw
    old_summary_raw=(INCIDENT_PACKET/'summary.json').read_bytes()
    require(sha(old_summary_raw)==old_manifest['summary_sha256'],'Prior incident summary hash differs')
    data['provenance/prior-incident-summary.json']=old_summary_raw
    fault_member='raw/FAULT.json';pin=old_manifest['members'][fault_member]
    part=next(p for p in old_manifest['archives'] if p['name']==pin['archive'])
    digest,size=prior.hash_file(INCIDENT_PACKET/part['name'])
    require(digest==part['sha256'] and size==part['bytes'],'Prior fault archive hash differs')
    with tarfile.open(INCIDENT_PACKET/part['name'],'r:gz') as archive:
        member=archive.getmember(fault_member);require(member.isfile(),'Prior fault is not regular text')
        raw=archive.extractfile(member).read()
        require(sha(raw)==pin['sha256'] and len(raw)==pin['bytes'],'Prior fault member hash differs')
        data['provenance/prior-FAULT.json']=raw
    return data,origins


def select(args):
    root=args.root.resolve();closure_path=root/args.closure
    require(closure_path.is_file(),'Final closure receipt required before collection')
    closure=json.loads(closure_path.read_text());closure_gate(closure)
    client=root/'client-campaign'
    if (client/'summary.json').is_file():
        terminal=json.loads((client/'summary.json').read_text())
        require(terminal.get('passed') is True or (client/'ABORTED').is_file(),'Client campaign has no terminal receipt')
    else:
        reason=closure.get('client_not_run_reason')
        require(isinstance(reason,str) and bool(reason.strip()),'Absent client requires explicit client_not_run_reason')
    require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}',args.snapshot_label) is not None,'Explicit safe snapshot label required')
    data,origins=oracle_from_frozen_archive();sources={};service_logs={}
    def add(path,name):
        prior.safe_relative(name)
        require(path.resolve().is_relative_to(root) or path.resolve().is_relative_to(REPO),'Source escapes admitted roots')
        require(name not in sources,'Duplicate source path')
        sources[name]=path
    for path in sorted(root.glob('*')):
        if path.is_file() and (path.suffix in {'.json','.jsonl','.txt','.log'} or path.name in prior.MARKERS):
            # Root helper stdout may still be growing; its snapshot is always
            # labeled, even when the application happened to stop before close.
            name=f'point-in-time/{args.snapshot_label}/root/{path.name}' if path.suffix in {'.log','.jsonl'} else 'raw/'+path.name
            add(path,name)
    for phase in PHASES:
        directory=root/phase
        if not directory.is_dir():continue
        state=json.loads((directory/'state.json').read_text()) if (directory/'state.json').is_file() else {}
        if phase in SERVICES:
            confirmed=state.get('status')=='stopped' or (state.get('status')=='failed' and state.get('stop_confirmed') is True)
            semantics='closed stopped-service logs' if confirmed else ('closed logs; exit confirmed by later postflight inspection' if postflight_exit_confirmed(directory,state) else 'point-in-time snapshot; process exit is not claimed')
            service_logs[phase]={'reported_state':state.get('status'),'label':args.snapshot_label,'semantics':semantics}
        for path in sorted(directory.rglob('*')):
            parts=path.relative_to(directory).parts
            if any(p in {'cache','build','.git','__pycache__'} for p in parts):continue
            if not path.is_file() or not (path.suffix in prior.TEXT_SUFFIXES or path.name in prior.MARKERS):continue
            rel=str(path.relative_to(directory));name='raw/'+phase+'/'+rel
            if phase in SERVICES and path.suffix in {'.log','.jsonl'}:
                name=f'point-in-time/{args.snapshot_label}/{phase}/{rel}'
            add(path,name)
    for name in SOURCE_FILES:
        path=HERE/name
        if path.is_file():add(path,'sources/'+name)
    for relative in ['packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py','scripts/compare-strict-attempt-outputs.py','scripts/bench-openai-realistic-suite.py','scripts/neural-download-canaries.py','repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-mtp1-strict.sh','repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json','experiments/qwen38-27b-b70/data/2026-09-14-amd-transfer/corpus.json']:
        add(REPO/relative,'repository/'+relative)
    for relative in ['experiments/qwen38-27b-b70/probes/mtp-metadata-20260914','experiments/qwen38-27b-b70/probes/mtp-recovery-20260914']:
        for path in sorted((REPO/relative).glob('*')):
            if path.is_file() and path.suffix in prior.TEXT_SUFFIXES:add(path,'repository/'+str(path.relative_to(REPO)))
    for path in sorted(args.packet.glob('*')):
        if path.is_file() and path.suffix in {'.json','.patch'} and path.name not in {'manifest.json','summary.json','verification.json'}:
            add(path,'repository/'+str(path.resolve().relative_to(REPO)))
    for name,path in sources.items():
        before=prior.stable_file(path);require(before[2]<=prior.MAX_TEXT_FILE,'Text source exceeds archive bound')
        raw=path.read_bytes();require(prior.stable_file(path)==before,'Source changed while snapshotting: '+name)
        prior.legacy.secret_check(name,raw);data[name]=raw
        origins[name]={'path':str(path.resolve()),'bytes':len(raw),'mtime_ns':before[3]}
    require(sum(map(len,data.values()))<=prior.MAX_TEXT_TOTAL,'Text evidence exceeds archive bound')
    require(sha(data['raw/'+args.closure])==sha(closure_path.read_bytes()),'Closure changed during collection')
    selection={'schema':'neural.download.fp8-recovery-selection.v1','raw_root':str(root),'client_dir':'client-campaign','closure':closure,'closure_path':args.closure,'snapshot_label':args.snapshot_label,'service_logs':service_logs,'source_paths':origins,'phase_presence':{phase:(root/phase).is_dir() for phase in PHASES},'frozen_oracle_manifest_sha256':sha(data['provenance/frozen-oracle-manifest.json']),'prior_incident_manifest_sha256':sha(data['provenance/prior-incident-manifest.json']),'prior_fault_sha256':sha(data['provenance/prior-FAULT.json']),'prior_incident_repository_path':str(INCIDENT_PACKET.relative_to(REPO)),'exclusions':['model weights','native libraries','cache/build trees','unrelated operator stages','whole-system journals']}
    data['selection.json']=encoded(selection)
    return data


def parity_replay(data,name,origins):
    report=json.loads(data[name]);by_path={}
    for member,origin in origins.items():by_path.setdefault(origin['path'],[]).append(member)
    sides=[]
    for side in ('left','right'):
        artifacts=report[side]['artifacts'];selected={}
        for role in ('performance','canaries','identity'):
            pin=artifacts[role];matches=by_path.get(pin['path'],[])
            require(matches and all(member in data and sha(data[member])==pin['sha256'] for member in matches),'Parity artifact missing or changed: '+role)
            selected[role]=json.loads(data[matches[0]])
        sides.append(selected)
    left,right=sides
    rows=[{r['prompt_id']:r for r in side['performance']['rows']} for side in sides]
    require(set(rows[0])==set(rows[1]),'Parity prompt coverage differs')
    require(all(rows[0][key]['prompt_sha256']==rows[1][key]['prompt_sha256'] for key in rows[0]),'Parity prompt identity differs')
    exact=sum(rows[0][key]['token_ids']==rows[1][key]['token_ids'] for key in rows[0])
    require(exact==report['comparison']['exact_prompts'] and len(rows[0])==report['comparison']['total_prompts'],'Parity count does not match full token arrays')
    require((exact==len(rows[0])) is report['comparison']['complete_token_arrays_exact'],'Parity boolean differs from token arrays')
    gates=all(side['performance']['realistic_final_gate']['passed'] is True and side['performance']['fresh_response_validity']['valid'] is True and side['performance']['fresh_response_validity']['cached_tokens_all_zero'] is True and side['canaries']['pass_all'] is True for side in sides)
    require(report['qualification']['all_workload_and_canary_gates_passed'] is gates,'Parity workload/canary claim differs from raw artifacts')
    require(report['qualification']['strict_pair_qualified'] is (gates and exact==len(rows[0])),'Parity qualified claim differs from raw artifacts')
    return {'path':name,'exact_prompts':exact,'total_prompts':len(rows[0]),'reported_pair_qualified':report['qualification']['strict_pair_qualified']}




def health_replay(data,phase='health'):
    require(phase in HEALTH_PHASES,'Unregistered health phase')
    prefix=f'raw/{phase}/'
    if prefix+'state.json' not in data:
        return {'phase':phase,'status':'not-run','passed_verified':False}
    state=json.loads(data[prefix+'state.json'])
    if state.get('passed') is not True:
        return {'phase':phase,'status':state.get('status'),'passed_verified':False,'error':state.get('error')}
    done=json.loads(data[prefix+'DONE.json'])
    require(done.get('passed') is True and done.get('state_sha256')==sha(data[prefix+'state.json']),'Health completion/state binding differs')
    require(state.get('stop_confirmed') is True and state.get('finished_at'),'Passed health has no confirmed exit')
    stop=json.loads(data[prefix+'stop.json']);owners=json.loads(data[prefix+'owners-after.json'])
    require(stop.get('confirmed') is True and stop.get('client_returncode')==0,'Health client exit unconfirmed')
    require(owners.get('returncode')==1 and not owners.get('stdout','').strip(),'Health left render device owners')
    final=json.loads(data[prefix+'container-final.json'])
    require(final['Id']==state['container_id'] and final['Image']==state['image_id'] and final['State']['Running'] is False,'Health container final identity/exit differs')
    contract=json.loads(data[prefix+'source-contract.json'])
    for key,name in [('worker_sha256','snapshot/health_worker.py'),('controller_sha256','controller-source.py'),('helper_sha256','qualified-helper-source.py'),('original_control_sha256','qualified-control-identity.json'),('qualified_container_sha256','qualified-container-reference.json')]:
        require(sha(data[prefix+name])==contract[key],'Health source/identity pin differs: '+name)
    require(contract['historical_fault_sha256']==sha(data['provenance/prior-FAULT.json']),'Recovery admission refers to a different historical fault')
    monitor=load('recovery_packet_health_faults',HERE/'monitor-transfer-client.py')
    require(not any(monitor.FAULT.search(line) and not line.endswith('Xe device coredump has been deleted.') for line in data[prefix+'kernel.log'].decode().splitlines()),'Passed health kernel window contains fault')
    expected_copy=sha(b''.join(struct.pack('<e',i/8) for i in range(64))*64)
    expected_reduce={rows:sha(struct.pack('<e',3.0)*(rows*5120)) for rows in (1,512)}
    receipts=[]
    for rank in (0,1):
        row=json.loads(data[prefix+f'results/rank{rank}.json'])
        require(row.get('rank')==rank and row.get('local_rank')==rank and row.get('passed') is True and row.get('group_cleanup_completed') is True and row.get('group_initialized') is True,'Health rank/cleanup qualification failed')
        require(row.get('backend')=='xccl' and row.get('custom_ipc') is False and row.get('model_loaded') is False,'Health scope differs')
        checks=row['checks'];require(len(checks)==3,'Health check coverage differs')
        copy_check=checks[0]
        require(copy_check.get('kind')=='copy_compute' and copy_check.get('values')==4096 and copy_check.get('exact') is True and copy_check.get('output_sha256')==expected_copy,'Health copy/compute expected-value hash differs')
        for check,rows in zip(checks[1:],(1,512)):
            require(check.get('kind')=='all_reduce' and check.get('shape')==[rows,5120] and check.get('dtype')=='torch.float16' and check.get('rank_input')==rank+1 and check.get('expected')==3 and check.get('exact') is True and check.get('output_sha256')==expected_reduce[rows],'Health all-reduce expected-value hash differs')
        receipts.append(row)
    require(state.get('worker_receipts')==receipts,'Health state/rank receipt aggregation differs')
    return {'phase':phase,'status':'passed','passed_verified':True,'started_at':state.get('started_at'),'finished_at':state.get('finished_at'),'ranks':2,'expected_value_output_hashes_rederived':6,'normal_group_cleanup_reported_both_ranks':True,'container_exit_verified':True,'raw_tensor_outputs_archived':False,'boot_id':state.get('boot_id'),'scope':'Deterministic expected-value standard Torch/XCCL health check; reported output hashes match independently generated FP16 expected bytes. Not model quality or custom communicator qualification.'}

def timestamp(value):
    require(isinstance(value,str),'Timestamp must be an explicit ISO string')
    parsed=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
    require(parsed.tzinfo is not None,'Timestamp timezone required')
    return parsed.timestamp()


def artifact_bytes(data,path):
    prior.safe_relative(path)
    names=[name for name in data if name=='raw/'+path or (name.startswith('point-in-time/') and name.endswith('/'+path))]
    require(len(names)==1,'Missing or ambiguous archived binding artifact: '+path)
    return data[names[0]]


def service_binding_replay(data,binding_path,strict):
    binding=json.loads(artifact_bytes(data,binding_path))
    require(binding.get('schema')=='neural.download.fp8-service-strict-binding.v1','Unknown service/strict binding schema')
    service_dir=binding.get('service_dir');strict_dir=binding.get('strict_dir')
    require(service_dir in SERVICES and strict_dir in ('recovery-strict','final-strict'),'Binding uses unregistered service/strict directories')
    expected={'state':service_dir+'/qualification-state.json','launch':service_dir+'/launch.json','container':service_dir+'/qualification-container.json','strict_identity':strict_dir+'/campaign-identity.json','performance':strict_dir+'/performance.json','canaries':strict_dir+'/canaries.json'}
    require(set(binding['artifacts'])==set(expected),'Binding artifact coverage differs')
    decoded={}
    for role,path in expected.items():
        pin=binding['artifacts'][role];require(pin['path']==path,'Binding artifact crosses service/strict instance')
        raw=artifact_bytes(data,path);require(sha(raw)==pin['sha256'],'Binding artifact hash differs: '+role)
        decoded[role]=json.loads(raw)
    state=decoded['state'];container=decoded['container']
    if isinstance(container,list):
        require(len(container)==1,'Exactly one qualified container required');container=container[0]
    require(state.get('status')=='ready','Qualification state is not ready')
    require(re.fullmatch(r'[0-9a-f]{64}',binding.get('container_id','')) is not None,'Invalid bound container ID')
    require(state.get('container_id')==container['Id']==binding['container_id'],'Qualification container instance differs')
    require(state.get('image_id')==container['Image']==binding['image_id'],'Qualification image differs')
    require(binding['image_id'] in {'sha256:7cd7bb16b1fd2e679f0230a38b2f0242fe1c278853867e697c0ce139be2133d2','sha256:506fcc26897b12915cb9e27c28e0adc256d278666fa745602a1ae5e1dd8ea066'},'Unreviewed image identity')
    require(container['State']['Running'] is True and container['Name'].lstrip('/')==state['container_name'],'Qualification container name/state differs')
    port=state['port'];require(type(port) is int,'Service port must be an integer')
    expected_url=f'http://127.0.0.1:{port}'
    require(binding['base_url']==expected_url,'Binding endpoint differs from service port')
    ports=container['HostConfig']['PortBindings']
    require(ports.get('8000/tcp')==[{'HostIp':'127.0.0.1','HostPort':str(port)}],'Container endpoint binding differs')
    command=container['Config']['Cmd']
    require(command.count('--served-model-name')==1 and command[command.index('--served-model-name')+1]==binding['model'],'Bound model differs from actual container command')
    if 'model' in state:require(state['model']==binding['model'],'State/model identity differs')
    launch=decoded['launch']
    if 'environment' in launch:
        env=launch['environment']
        require(env.get('EXPECTED_IMAGE_ID')==binding['image_id'] and env.get('CONTAINER_NAME')==state['container_name'] and env.get('PORT')==str(port) and env.get('SERVED_MODEL_NAME')==binding['model'],'Bound launch differs from qualified service instance')
    else:
        argv=launch['argv']
        require(binding['image_id'] in argv and '--name' in argv and argv[argv.index('--name')+1]==state['container_name'] and '-p' in argv and argv[argv.index('-p')+1]==f'127.0.0.1:{port}:8000','Research launch differs from bound instance')
    identity=decoded['strict_identity'];performance=decoded['performance'];run=performance['run_identity']
    require(run['base_url'].rstrip('/')==expected_url and run['model']==binding['model'],'Strict endpoint/model differs from bound service')
    started=timestamp(state['started_at']);ready=timestamp(state['ready_at']);captured=timestamp(binding['captured_at'])
    require(started<=timestamp(container['State']['StartedAt'])<=ready,'Container creation falls outside this service startup')
    require(ready<=timestamp(identity['created_utc'])<=timestamp(run['created_at_utc'])<=captured,'Strict creation time falls outside bound ready instance')
    for row in performance['rows']:
        begin=row['request_started_epoch_s'];end=row['request_ended_epoch_s']
        require(type(begin) in (int,float) and type(end) in (int,float) and math.isfinite(begin) and math.isfinite(end),'Invalid strict request timestamps')
        require(ready<=begin<=end<=captured,'Strict request predates service readiness or postdates capture')
    require(strict.get('raw/'+strict_dir,{}).get('complete_12_prompt_qualification') is True,'Bound strict output is not fully qualified')
    if 'raw/health/state.json' in data:
        require(binding['boot_id']==json.loads(data['raw/health/state.json'])['boot_id'],'Bound service and recovery health boot differ')
    if state.get('boot_id') is not None:require(binding['boot_id']==state['boot_id'],'Bound service boot differs')
    window=binding['kernel_window'];require(window['path']==service_dir+'/qualification-kernel.log','Binding kernel window crosses service instance')
    require(timestamp(window['since'])==started and timestamp(window['through'])==captured,'Kernel window does not cover complete startup-to-qualification interval')
    kernel=artifact_bytes(data,window['path']);require(sha(kernel)==window['sha256'],'Bound kernel window hash differs')
    monitor=load('recovery_binding_faults',HERE/'monitor-transfer-client.py')
    require(not any(monitor.FAULT.search(line) and not line.endswith('Xe device coredump has been deleted.') for line in kernel.decode().splitlines()),'Bound qualification window contains GPU fault')
    return {'binding_receipt':binding_path,'binding_sha256':sha(artifact_bytes(data,binding_path)),'service_dir':service_dir,'strict_dir':strict_dir,'container_id':binding['container_id'],'image_id':binding['image_id'],'boot_id':binding['boot_id'],'base_url':binding['base_url'],'model':binding['model'],'captured_at':binding['captured_at'],'qualified_instance_and_outputs_verified':True}


def final_service_gate(data, strict, final, closed_at=None):
    if final['status'] != 'ready':
        return {'reported_status':final['status'],'ready_quality_verified':False}
    require('raw/FAULT.json' not in data,'Fresh recovery campaign fault forbids a ready claim; use a separately admitted recovery campaign')
    path=final.get('binding_receipt');require(isinstance(path,str) and bool(path),'Ready closure requires binding_receipt')
    replay=service_binding_replay(data,path,strict)
    require(replay['service_dir']==final.get('source_dir') and replay['strict_dir']==final.get('strict_dir'),'Final service/strict selection crosses the qualified instance')
    state=json.loads(data[f"raw/{replay['service_dir']}/state.json"])
    require(state.get('status')=='ready','Final ready claim disagrees with captured live service state')
    require(state.get('container_id')==replay['container_id'] and state.get('image_id')==replay['image_id'],'Final instance differs from qualified binding')
    qualified=json.loads(artifact_bytes(data,replay['service_dir']+'/qualification-state.json'))
    for field in ('container_name','port','started_at','ready_at'):
        require(state.get(field)==qualified.get(field),'Final live instance field differs: '+field)
    if closed_at is not None:require(timestamp(replay['captured_at'])<=timestamp(closed_at),'Qualification postdates campaign closure')
    monitor=load('recovery_final_faults',HERE/'monitor-transfer-client.py')
    for name,raw in data.items():
        if name.endswith('/'+replay['service_dir']+'/kernel.log'):
            require(not any(monitor.FAULT.search(line) and not line.endswith('Xe device coredump has been deleted.') for line in raw.decode().splitlines()),'Final service kernel snapshot contains later GPU fault')
    return {'reported_status':'ready','ready_quality_verified':True,**replay,'semantics':'This instance was ready and strictly qualified at closure; later availability is not implied'}


def utc_seconds(value):
    """Docker timestamps carry nanoseconds; compare at microsecond precision."""
    require(isinstance(value,str),'Timestamp must be an explicit ISO string')
    match=re.fullmatch(r'(.+?\.\d{1,6})\d*(Z|[+-]\d\d:\d\d)',value)
    return timestamp(match[1]+match[2] if match else value)


def postflight_exit_confirmed(directory,state):
    path=directory/'postflight.json'
    if not path.is_file():return False
    post=json.loads(path.read_text());container=post.get('container',{})
    return (post.get('schema')==RESEARCH_POSTFLIGHT_SCHEMA and post.get('exit_confirmed_by_later_inspection') is True
            and container.get('id')==state.get('container_id') and container.get('state',{}).get('Running') is False)


def research_postflight_replay(data):
    """Bind a later exit inspection to the unchanged owner receipts of the research stage."""
    prefix='raw/research-server/'
    if prefix+'state.json' not in data:return {'status':'not-run','exit_confirmed':False}
    state=json.loads(data[prefix+'state.json'])
    if prefix+'postflight.json' not in data:
        return {'status':state.get('status'),'exit_confirmed':state.get('status')=='stopped' or (state.get('status')=='failed' and state.get('stop_confirmed') is True)}
    post=json.loads(data[prefix+'postflight.json']);container=post.get('container',{})
    require(post.get('schema')==RESEARCH_POSTFLIGHT_SCHEMA,'Unknown research postflight schema')
    require(container.get('id')==state.get('container_id') and container.get('name')==state.get('container_name') and container.get('image')==state.get('image_id'),'Research postflight container identity differs')
    require(container.get('state',{}).get('Running') is False and post.get('exit_confirmed_by_later_inspection') is True,'Research postflight does not confirm exit')
    require(post.get('same_boot_as_launch') is True and post.get('boot_id')==state.get('boot_id'),'Research postflight boot differs')
    require(utc_seconds(state['started_at'])<=utc_seconds(container['state']['FinishedAt'])<=utc_seconds(post['at']),'Research postflight timeline differs')
    receipts=post.get('preserved_owner_receipts_sha256')
    require(isinstance(receipts,dict) and {'state.json','stop.json','server.log'}<=set(receipts),'Research postflight lacks owner receipt pins')
    for rel,digest in receipts.items():
        require(sha(artifact_bytes(data,'research-server/'+rel))==digest,'Research owner receipt changed after postflight: '+rel)
    monitor=load('research_postflight_faults',HERE/'monitor-transfer-client.py')
    require(post.get('gpu_fault_signature_lines')==[] and not any(monitor.FAULT.search(line) for line in post.get('xe_lines',[])),'Research incident window records a GPU fault signature')
    require(post.get('requests_served')==0 and post.get('endpoint_ever_ready') is False,'Research stage claims served requests')
    return {'status':'failed-during-load','exit_confirmed':True,'exit_code':container['state'].get('ExitCode'),'oom_killed':container['state'].get('OOMKilled'),'finished_at':container['state']['FinishedAt'],'requests_served':0,'global_oom_kills':len(post['global_oom_kills']),'page_allocation_failures':len(post['page_allocation_failures']),'allocation_failure_stack':post['last_allocation_failure_stack_kernel_clock'],'gib_outside_normal_counters_at_first_oom':post['first_oom_gib_outside_those_counters'],'gpu_fault_signature_lines':0,'owner_receipts_unchanged':sorted(receipts),'full_kernel_window_sha256':{name:window['sha256'] for name,window in post['kernel_windows'].items()},'full_kernel_windows_archived':False,'scope':'Host memory exhaustion during research target load; full kernel windows stay local because they contain whole-host process tables.'}


def ready_health_gate(final_verification,healths,research,final_started_at=None):
    """A ready closure needs the recovery admission; after a failed research stage also a later passing health check."""
    if not final_verification['ready_quality_verified']:return {'ready_claim':False}
    require(healths['health']['passed_verified'],'Ready recovery closure lacks verified health admission')
    if research['status'] in ('not-run','stopped'):return {'ready_claim':True,'post_incident_health_required':False}
    later=healths.get('health-after-research-oom',{})
    require(research.get('exit_confirmed') is True,'Ready closure requires confirmed research container exit')
    require(later.get('passed_verified') is True,'Ready closure after a failed research stage lacks a verified later health check')
    require(utc_seconds(research['finished_at'])<=utc_seconds(later['started_at'])<=utc_seconds(later['finished_at']),'Later health check does not follow the research container exit')
    require(final_started_at is not None and utc_seconds(later['finished_at'])<=utc_seconds(final_started_at),'Final service started before the later health check completed')
    return {'ready_claim':True,'post_incident_health_required':True,'post_incident_health_phase':later['phase'],'research_exit':research['finished_at'],'health_window':[later['started_at'],later['finished_at']],'final_service_started_at':final_started_at}


def summarize(data):
    selection=json.loads(data['selection.json']);closure=selection['closure'];closure_gate(closure)
    require(sha(data['provenance/frozen-oracle-manifest.json'])==selection['frozen_oracle_manifest_sha256'],'Frozen oracle provenance manifest changed')
    oracle_manifest=json.loads(data['provenance/frozen-oracle-manifest.json'])
    for name,raw in data.items():
        if name.startswith('frozen/'):
            pin=oracle_manifest['members'][name[len('frozen/'):]]
            require(sha(raw)==pin['sha256'] and len(raw)==pin['bytes'],'Frozen oracle member provenance changed')
    incident_manifest=json.loads(data['provenance/prior-incident-manifest.json'])
    require(sha(data['provenance/prior-incident-manifest.json'])==selection['prior_incident_manifest_sha256'],'Historical incident manifest changed')
    require(sha(data['provenance/prior-FAULT.json'])==selection['prior_fault_sha256']==incident_manifest['members']['raw/FAULT.json']['sha256'],'Historical fault provenance changed')
    require(sha(data['provenance/prior-incident-summary.json'])==incident_manifest['summary_sha256'],'Historical incident summary changed')
    for name in ('collect-mtp-transfer-evidence.py','collect-amd-transfer-evidence.py','bench-prefill-followup.py','bench-short-prefill.py','run-mtp-metadata-client-campaign.py','monitor-transfer-client.py'):
        require(sha((HERE/name).read_bytes())==sha(data['sources/'+name]),'Replay helper source drift: '+name)
    bench=load('recovery_packet_prefill',HERE/'bench-prefill-followup.py')
    frozen,reference=prior.strict_replay(data,'frozen/control-strict')
    require(frozen['complete_12_prompt_qualification'],'Frozen strict reference unqualified')
    frozen_context,context_reference=prior.context_replay(data,'frozen/control-context',bench,None)
    require(frozen_context['reported_passed'],'Frozen context reference unqualified')
    strict={};contexts={};parities=[]
    for name in sorted(data):
        if name.startswith('raw/') and name.endswith('/performance.json'):
            prefix=name[:-len('/performance.json')];strict[prefix]=prior.strict_replay(data,prefix,reference)[0]
        if name.startswith('raw/client-campaign/') and name.endswith('/context/summary.json'):
            prefix=name[:-len('/summary.json')];contexts[prefix]=prior.context_replay(data,prefix,bench,context_reference)[0]
        if name.startswith('raw/') and name.endswith('.json'):
            value=json.loads(data[name])
            if isinstance(value,dict) and value.get('schema')=='neural.download.strict-attempt-output-comparison.v1':parities.append(parity_replay(data,name,selection['source_paths']))
    campaign=json.loads(data['raw/client-campaign/summary.json']) if 'raw/client-campaign/summary.json' in data else {'passed':False,'not_run':True,'error':closure.get('client_not_run_reason')}
    require(not campaign.get('not_run') or bool(campaign['error']),'Client absence requires explicit reason')
    client_replay=None
    if campaign.get('passed') is True:
        client_strict={k:v for k,v in strict.items() if k.startswith('raw/client-campaign/')}
        require(len(client_strict)==5 and all(r['complete_12_prompt_qualification'] for r in client_strict.values()),'Completed metadata campaign lacks five exact full strict attempts')
        require(len(contexts)==4 and all(r['reported_passed'] and r['measured_requests']==18 and r['complete_outputs_match_frozen_and_repeats'] for r in contexts.values()),'Completed metadata campaign lacks four exact contexts')
        client=load('recovery_packet_client',HERE/'run-mtp-metadata-client-campaign.py')
        client_replay=prior.completed_client_replay(data,selection,campaign,client,client_strict,contexts)
    bindings=[]
    for name in sorted(data):
        if name.startswith('raw/') and name.endswith('.json'):
            value=json.loads(data[name])
            if isinstance(value,dict) and value.get('schema')=='neural.download.fp8-service-strict-binding.v1':bindings.append(service_binding_replay(data,name[len('raw/'):],strict))
    healths={phase:health_replay(data,phase) for phase in HEALTH_PHASES}
    research=research_postflight_replay(data)
    final_verification=final_service_gate(data,strict,closure['final_service'],closure['finished_at'])
    final_started=json.loads(artifact_bytes(data,final_verification['service_dir']+'/qualification-state.json'))['started_at'] if final_verification['ready_quality_verified'] else None
    admission=ready_health_gate(final_verification,healths,research,final_started)
    return {'schema':'neural.download.fp8-recovery-metadata-evidence-summary.v1','closure':closure,'health':healths['health'],'post_incident_health':healths['health-after-research-oom'],'research_stage':research,'ready_health_admission':admission,'final_service_verification':final_verification,'phase_presence':selection['phase_presence'],'frozen_reference':{'strict':frozen,'context':frozen_context},'strict_attempts':strict,'context_attempts':contexts,'parity_reports_replayed':parities,'service_strict_bindings_replayed':bindings,'metadata_campaign':{'status':'not-run' if campaign.get('not_run') else ('completed' if campaign.get('passed') is True else 'aborted'),'error':campaign.get('error'),'completed_rpc_and_counter_replay':client_replay,'promoted':False,'fresh_process_performance_confirmation':False},'service_log_snapshots':selection['service_logs'],'prior_incident':{'repository_path':selection['prior_incident_repository_path'],'manifest_sha256':selection['prior_incident_manifest_sha256'],'fault_sha256':selection['prior_fault_sha256'],'disposition':'Preserved historical incident; this recovery packet does not clear or overwrite its fault latch'},'interpretation':'Recovery quality and within-process metadata screening are separate. No one-process speed promotion or automatic recommendation.'}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',type=Path,default=ROOT_DEFAULT)
    ap.add_argument('--packet',type=Path,default=PACKET_DEFAULT)
    ap.add_argument('--closure',default='campaign-completion.json')
    ap.add_argument('--snapshot-label',default='campaign-close')
    ap.add_argument('--verify',action='store_true')
    args=ap.parse_args();prior.safe_relative(args.closure)
    if args.verify:
        manifest=json.loads((args.packet/'manifest.json').read_text())
        require(sha(Path(__file__).read_bytes())==manifest['collector_sha256'],'Recovery collector source drift')
        data,binary=prior.read_archives(args.packet,manifest);require(not binary,'Recovery packet does not admit binary payloads')
        summary=summarize(data);raw=(args.packet/'summary.json').read_bytes()
        require(sha(raw)==manifest['summary_sha256'] and json.loads(raw)==summary,'Recovery summary replay mismatch')
        print(json.dumps({'passed':True,'mode':'verify-only','members':len(manifest['members'])}));return
    require(not (args.packet/'manifest.json').exists(),'Existing packet is frozen; choose a new packet directory')
    data=select(args);args.packet.mkdir(parents=True,exist_ok=True)
    parts,members=prior.build_archives(args.packet,data,{})
    manifest={'schema':'neural.download.fp8-recovery-metadata-manifest.v1','collector_repository_path':str(Path(__file__).resolve().relative_to(REPO)),'collector_sha256':sha(Path(__file__).read_bytes()),'archives':parts,'members':members,'scope':'Bounded recovery/metadata stages with full numeric outputs and explicit point-in-time service log snapshots; historical fault remains preserved.'}
    replay,binary=prior.read_archives(args.packet,manifest,temporary=True);require(not binary,'Unexpected recovery binary payload')
    summary=summarize(replay);raw=encoded(summary);manifest['summary_sha256']=sha(raw)
    manifest['verification']={'all_archive_members_hash_verified':True,'strict_rates_and_token_parities_replayed':True,'context_raw_sse_and_histograms_replayed':True,'completed_metadata_rpc_and_counters_replayed':summary['metadata_campaign']['completed_rpc_and_counter_replay'] is not None,'historical_oracle_archive_verified':True}
    for part in parts:(args.packet/(part['name']+'.tmp')).replace(args.packet/part['name'])
    (args.packet/'summary.json').write_bytes(raw);(args.packet/'manifest.json').write_bytes(encoded(manifest))
    print(json.dumps({'passed':True,'members':len(members),'archive_bytes':sum(p['bytes'] for p in parts),'metadata_status':summary['metadata_campaign']['status']}))

if __name__=='__main__':main()
