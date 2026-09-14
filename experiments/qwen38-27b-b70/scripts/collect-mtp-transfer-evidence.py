#!/usr/bin/env python3
"""Collect/verify completed MTP transfer stages; local CPU/files only.

Explicit allowlists, immutable receipts and labeled running-log snapshots.
Operator output bits are deduplicated and streamed into bounded archive parts.
No models, native libraries, build/cache trees, server actions or network.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import gzip
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
import statistics
import tarfile

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
DEFAULT_ROOT=Path('/mnt/fast-ai/bench-results/mtp-lossless-transfer-20260914')
DEFAULT_PACKET=HERE.parent/'data/2026-09-14-mtp-lossless-transfer'
PART_LIMIT=64*1024*1024
MAX_TEXT_FILE=32*1024*1024
MAX_TEXT_TOTAL=256*1024*1024
MAX_BINARY_FILE=64*1024*1024
TEXT_SUFFIXES={'.json','.jsonl','.txt','.log','.stdout','.py','.cpp','.h','.hpp','.patch','.md','.sh','.sha256'}
MARKERS={'DONE','ABORTED','STOP','SCREEN_COMPLETED','CLIENT_EXIT_UNCONFIRMED','STOP_UNCONFIRMED'}


def sha(data):return hashlib.sha256(data).hexdigest()
def encoded(value):return (json.dumps(value,indent=2,sort_keys=True,ensure_ascii=False)+'\n').encode()
def require(value,message):
    if not value:raise ValueError(message)
def close(a,b,message):require(math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-12),message)
def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


# Reuse credential screening rather than silently redacting hash-bound evidence.
legacy=load_module('mtp_packet_legacy',HERE/'collect-amd-transfer-evidence.py')


def stable_file(path):
    require(not path.is_symlink() and path.is_file(),f'Not a regular unlinked input: {path}')
    st=path.stat()
    return (st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns)


def hash_file(path):
    before=stable_file(path);h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    require(stable_file(path)==before,f'Input changed during hashing: {path}')
    return h.hexdigest(),before[2]


def safe_relative(value):
    path=PurePosixPath(value)
    require(not path.is_absolute() and '..' not in path.parts and str(path) not in ('','.','/'),f'Unsafe relative path: {value}')
    return path


def select(args):
    root=args.root.resolve();packet=args.packet.resolve()
    final=root/args.final_receipt
    require(final.is_file(),'Final campaign closure receipt required before collection')
    closure=json.loads(final.read_text())
    require(closure.get('status') in {'completed','closed-after-gpu-fault'} and isinstance(closure.get('finished_at'),str) and bool(closure['finished_at'].strip()),'Explicit completed or closed-after-gpu-fault status and finished_at required')
    require(closure.get('final_service',{}).get('status') in {'ready','stopped','failed','stop_unconfirmed'},'Final service status must be explicit in closure')
    stages=args.operator_stage
    require(len(stages)==len(set(stages)), 'Duplicate operator stage')
    require({'communication-native-01','communication-native-02'}.issubset(stages),'Preserve the two failed setup stages')
    for stage in stages:
        require(re.fullmatch(r'communication-native-\d{2}',stage) is not None,'Operator stage must be explicit canonical name')
        state=json.loads((root/stage/'state.json').read_text())
        require(state.get('finished') and state.get('stop_confirmed') is True,f'Operator stage not closed: {stage}')
    client=root/args.client_dir
    client_absent_reason=closure.get('client_not_run_reason')
    if (client/'summary.json').is_file():
        client_summary=json.loads((client/'summary.json').read_text())
        require(client_summary.get('passed') is True or (client/'ABORTED').is_file(),'Client campaign has no terminal receipt')
    else:
        require(isinstance(client_absent_reason,str) and bool(client_absent_reason.strip()),'Absent client requires explicit client_not_run_reason in closure receipt')
    sources={}
    def add(path,name):
        safe_relative(name)
        require(path.resolve().is_relative_to(root) or path.resolve().is_relative_to(REPO) or path.resolve().is_relative_to(args.frozen_root.resolve()),'Input escapes admitted roots')
        require(name not in sources or sources[name]==path,'Duplicate archive name')
        sources[name]=path
    def tree(directory,prefix,recursive=True,binary=False):
        if not directory.is_dir():return
        for path in sorted(directory.rglob('*') if recursive else directory.glob('*')):
            if path.is_file() and (path.suffix in TEXT_SUFFIXES or path.name in MARKERS or (binary and path.suffix=='.bin')):
                if any(part in {'cache','build','.git','__pycache__'} for part in path.relative_to(directory).parts):continue
                add(path,prefix+'/'+str(path.relative_to(directory)))
    for name in ['nightly-image.json','nightly-pull.log','post-original-stop.json','FAULT.json','post-fault-state.json','postflight.json',args.final_receipt]:
        if (root/name).is_file():add(root/name,'raw/'+name)
    tree(client,'raw/'+args.client_dir)
    for stage in stages:tree(root/stage,'raw/'+stage,binary=True)
    for directory in ['control-source','control-source-initial','extension-source-review']:
        tree(root/directory,'raw/'+directory)
    # Controller snapshots are selected explicitly, not by a recursive live tree.
    server=root/args.server_dir
    for name in ['launch.json','state.json','image.json','source-pins.json','controller-contract.json','container-created.json','container-final.json','completion.json','stop.json','container-before-stop.json','container-inspect.json','STOP_UNCONFIRMED','STOP','preflight.json','postflight.json','CLIENT-FAILED.json','GPU-FAULT.json']:
        if (server/name).is_file():add(server/name,'raw/'+args.server_dir+'/'+name)
    tree(server/'research-extension','raw/'+args.server_dir+'/research-extension')
    if args.running_log_snapshot_label:
        require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}',args.running_log_snapshot_label) is not None,'Invalid snapshot label')
        for name in ['server.log','kernel.log','memory.jsonl']:
            if (server/name).is_file():add(server/name,f'running-log-snapshot/{args.running_log_snapshot_label}/{name}')
    elif any((server/name).is_file() for name in ['server.log','kernel.log','memory.jsonl']):
        server_state=json.loads((server/'state.json').read_text())
        require(server_state.get('status')=='stopped' or (server_state.get('status')=='failed' and server_state.get('stop_confirmed') is True),'Running or unconfirmed service logs require an explicit snapshot label')
        for name in ['server.log','kernel.log','memory.jsonl']:
            if (server/name).is_file():add(server/name,'raw/'+args.server_dir+'/'+name)
    add(args.frozen_root/'control-identity.json','frozen/control-identity.json')
    for directory in ['control-strict','control-context']:
        tree(args.frozen_root/directory,'frozen/'+directory)
    for path in packet.glob('*'):
        if path.suffix in {'.json','.patch'} and path.name not in {'summary.json','manifest.json','verification.json'}:
            add(path,'repository/'+str(path.relative_to(REPO)))
    for relative in ['experiments/qwen38-27b-b70/probes/mtp-metadata-20260914','experiments/qwen38-27b-b70/probes/mtp-exact-tp2-20260914','experiments/qwen38-27b-b70/docker/mtp-lossless-transfer-20260914']:
        tree(REPO/relative,'repository/'+relative)
    scripts=['collect-mtp-transfer-evidence.py','collect-amd-transfer-evidence.py','run-mtp-metadata-client-campaign.py','validate-mtp-query-lens-offline.py','bench-prefill-followup.py','bench-short-prefill.py','monitor-transfer-client.py','run-mtp-lossless-server.py']
    for name in scripts:add(HERE/name,'sources/'+name)
    for relative in ['packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py','scripts/compare-strict-attempt-outputs.py','scripts/bench-openai-realistic-suite.py','scripts/neural-download-canaries.py','repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-mtp1-strict.sh','repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json','experiments/qwen38-27b-b70/data/2026-09-14-amd-transfer/corpus.json']:
        add(REPO/relative,'repository/'+relative)
    data={};objects={};binary_paths={};source_map={}
    total=0
    for name,path in sorted(sources.items()):
        before=stable_file(path)
        if path.suffix=='.bin':
            require(re.fullmatch(r'raw/communication-native-\d{2}/results/rank[01]-rows(?:1|2|512|4096)-[a-z_]+-[01]\.(?:candidate|xccl)\.bin',name) is not None,'Unregistered binary input; only raw operator fixture outputs allowed')
            require(before[2]<=MAX_BINARY_FILE,'Operator output exceeds registered maximum')
            digest,size=hash_file(path);member=f'operator-output-bits/{digest}.bin'
            binary_paths[name]={'member':member,'sha256':digest,'bytes':size}
            objects.setdefault(member,path)
        else:
            require(before[2]<=MAX_TEXT_FILE,f'Text input too large: {name}')
            raw=path.read_bytes();require(stable_file(path)==before,f'Text changed while reading: {name}')
            legacy.secret_check(name,raw);data[name]=raw;total+=len(raw)
        source_map[name]={'path':str(path.resolve()),'bytes':before[2],'mtime_ns':before[3]}
    require(total<=MAX_TEXT_TOTAL,'Text evidence exceeds packet bound')
    index={'schema':'neural.download.mtp-transfer-selection.v1','raw_root':str(root),'client_dir':args.client_dir,'server_dir':args.server_dir,'operator_stages':stages,'closure_receipt':args.final_receipt,'client_not_run_reason':client_absent_reason,'service_metadata_semantics':'Captured identity/state receipts; a running state is a point-in-time snapshot, not a final stopped-state claim','running_logs':None if not args.running_log_snapshot_label else {'label':args.running_log_snapshot_label,'scope':'Point-in-time text snapshots of a possibly running service; not final immutable full logs'},'source_paths':source_map,'operator_binary_paths':binary_paths,'exclusions':['model weights','native .so libraries','cache/build trees','whole-system journals'],'closure':closure}
    data['selection.json']=encoded(index)
    return data,objects


def strict_replay(data,prefix,reference=None):
    p=json.loads(data[prefix+'/performance.json']);rows=p['rows'];classes=defaultdict(list)
    by_id={r['prompt_id']:r for r in rows}
    require(len(by_id)==len(rows),'Duplicate strict prompt IDs')
    output_exact=True;cache_zero=True;event_coverage=True
    for row in rows:
        ids=row['token_ids'];offsets=row['token_id_offsets_s']
        require(isinstance(ids,list) and all(type(x) is int and x>=0 for x in ids),'Invalid strict numeric outputs')
        require(len(ids)==row['completion_tokens'],'Strict token accounting mismatch')
        event_coverage &= (100 <= len(ids) <= 512 and len(offsets)==len(ids))
        require(all(type(v) in (int,float) and math.isfinite(v) for v in offsets),'Invalid strict event timestamps')
        require(all(a<=b for a,b in zip(offsets,offsets[1:])),'Strict timestamps are not monotonic')
        cache_zero &= type(row['cached_tokens']) is int and row['cached_tokens']==0
        if len(offsets)>=100:
            require(offsets[99]>offsets[0],'Strict interval duration must be positive')
            speed=99/(offsets[99]-offsets[0]);close(speed,row['tok_s_1_100_intervals_after_ttft'],'Strict interval arithmetic mismatch')
            classes[row['prompt_class']].append(speed)
        if reference is not None:
            old=reference.get(row['prompt_id'])
            require(old is not None and row['prompt_sha256']==old['prompt_sha256'],'Strict prompt identity differs')
            output_exact &= ids==old['token_ids']
    rate=statistics.median(statistics.median(v) for v in classes.values()) if classes else None
    if rate is not None:close(rate,p['summary']['class_balanced_tok_s_1_100_intervals_after_ttft']['median'],'Strict class-balanced aggregate mismatch')
    canaries=json.loads(data[prefix+'/canaries.json']) if prefix+'/canaries.json' in data else None
    declared=p.get('realistic_final_gate',{}).get('passed') is True
    result={'prompts':len(rows),'class_balanced_decode_tok_s':rate,'cache_zero':cache_zero,'complete_outputs_match_frozen':output_exact,'workload_gate_reported_passed':declared,'canaries_passed':canaries is not None and canaries.get('pass_all') is True,'complete_12_prompt_qualification':len(rows)==12 and event_coverage and output_exact and cache_zero and declared and canaries is not None and canaries.get('pass_all') is True}
    return result,by_id


def context_replay(data,prefix,bench,reference):
    state=json.loads(data[prefix+'/summary.json'])
    if prefix+'/corpus.json' not in data:
        require(state.get('passed') is not True and not state.get('rows') and not state.get('warmups'),'Missing completed context corpus')
        return {'reported_passed':False,'measured_requests':0,'warmups':0,'complete_outputs_match_frozen_and_repeats':False,'by_length':None,'incomplete_reason':'Client failed before copied corpus or output evidence'},{}
    require(sha(data[prefix+'/corpus.json'])==state['corpus_sha256'],'Context corpus hash differs')
    require(sha(data['sources/bench-prefill-followup.py'])==state['client_sha256'],'Context client hash differs')
    require(sha(data['sources/bench-short-prefill.py'])==state['parser_sha256'],'Context parser hash differs')
    rows=[];outputs={};exact=True
    for original in state['warmups']+state['rows']:
        stem=f"{prefix}/{original['phase']}-{original['key']}-{original['repeat']}"
        request=json.loads(data[stem+'-request.json']);prompt=state['prompts'][original['key']]
        require(request['prompt']==prompt,'Context request/prompt differs')
        parsed=bench.parse_events([json.loads(line) for line in data[stem+'-sse.jsonl'].splitlines()],len(prompt),request['max_tokens'])
        metrics=bench.required_metric_delta(data[stem+'-metrics-before.txt'].decode(),data[stem+'-metrics-after.txt'].decode(),len(prompt))
        require({**original,**parsed,**metrics}==original,'Raw context SSE/metric replay differs')
        require(parsed['usage']['prompt_tokens_details']['cached_tokens']==0,'Context cache nonzero')
        ids=parsed['token_ids'];key=original['key']
        if key in outputs:exact &= ids==outputs[key]
        if reference is not None:
            require(key in reference,'Missing frozen context key');exact &= ids==reference[key]
        outputs[key]=ids
        if original['phase']=='measure':rows.append(original)
    rates=None
    if state.get('passed') is True:
        rates=bench.aggregate(rows,state['prompts'],sorted({len(p) for p in state['prompts'].values()}),state['args']['repeats'])
        require(rates==state['by_length'],'Context aggregate differs')
        require(exact,'Passed context report contains output mismatch')
    return {'reported_passed':state.get('passed') is True,'measured_requests':len(rows),'warmups':len(state['warmups']),'complete_outputs_match_frozen_and_repeats':exact,'by_length':rates},outputs


def completed_client_replay(data,selection,campaign,client,strict,contexts):
    """Check completed mode transitions and arm claims against archived raw RPCs."""
    prefix='raw/'+selection['client_dir']
    sequence=[('mtp_transfer_status','unwrapped-control',False),
              ('mtp_transfer_status','unwrapped-control',False),
              ('mtp_transfer_prepare','control',False),
              ('mtp_transfer_native_gate','control',True)]
    for _,mode in client.ARMS:
        sequence += [('mtp_transfer_set_mode',mode,True),('mtp_transfer_status',mode,True)]
    sequence += [('mtp_transfer_set_mode','control',True)]
    names=sorted(n for n in data if n.startswith(prefix+'/rpc-') and n.endswith('-response.json'))
    require(len(names)==len(sequence),'Completed campaign RPC count differs')
    statuses=[]
    for number,(name,(method,mode,native)) in enumerate(zip(names,sequence),1):
        require(name==f'{prefix}/rpc-{number:02d}-{method}-response.json','Completed RPC order differs')
        request=json.loads(data[name.replace('-response.json','-request.json')])
        require(request.get('method')==method and request.get('args')==[],'RPC request method/args differ')
        require(request.get('kwargs')==({'mode':mode} if method=='mtp_transfer_set_mode' else {}),'RPC request selector differs')
        response=json.loads(data[name])
        if method=='mtp_transfer_native_gate':
            client.native_gate(response)
            response={'results':[row['status'] for row in response['results']]}
        statuses.append(client.statuses(response,mode,native))
    require(campaign.get('refreshed_unwrapped_base_12_of_12_exact') is True and campaign.get('native_36_cases_both_ranks_passed') is True,'Completed campaign prerequisite claims absent')
    arms=campaign.get('arms',[])
    require(len(arms)==len(client.ARMS),'Completed arm coverage differs')
    for index,(arm,(label,mode)) in enumerate(zip(arms,client.ARMS)):
        require((arm.get('label'),arm.get('mode'))==(label,mode),'Completed arm ordering differs')
        before,after=statuses[4+2*index:6+2*index]
        calls=client.counter_gate(before,after,mode)
        require(arm.get('rank_status_before')==before and arm.get('rank_status_after')==after and arm.get('matched_metadata_calls_per_rank')==calls,'Reported arm counters differ from raw RPCs')
        strict_prefix=f'{prefix}/{label}/strict';context_prefix=f'{prefix}/{label}/context'
        require(sha(data[strict_prefix+'/performance.json'])==arm.get('strict_performance_sha256'),'Arm strict file hash differs')
        require(sha(data[context_prefix+'/summary.json'])==arm.get('context_summary_sha256'),'Arm context file hash differs')
        close(arm['class_balanced_decode_tok_s'],strict[strict_prefix]['class_balanced_decode_tok_s'],'Arm strict aggregate differs')
        require(arm.get('context_by_length')==contexts[context_prefix]['by_length'] and arm.get('complete_outputs_match_frozen') is True,'Arm context aggregate or output claim differs')
    require(campaign.get('final_rank_status')==statuses[-1],'Final wrapped-control status differs from RPC')
    prereg=json.loads(data[prefix+'/preregistration.json'])
    require(sha(data[prefix+'/preregistration.json'])==campaign.get('preregistration_sha256'),'Campaign preregistration hash differs')
    by_path=defaultdict(list)
    for name,source in selection['source_paths'].items():by_path[source['path']].append(name)
    for pin in prereg['files']:
        names=by_path[pin['path']]
        require(names and all(name in data and sha(data[name])==pin['sha256'] for name in names),'Preregistered source/oracle/identity missing or changed: '+pin['path'])
    return {'ordered_rpc_transitions_verified':len(sequence),'matched_arms_verified':len(arms),'preregistered_file_hashes_verified':len(prereg['files'])}


def summarize(data,binary_members):
    selection=json.loads(data['selection.json']);client_prefix='raw/'+selection['client_dir']
    for name in ['bench-prefill-followup.py','bench-short-prefill.py','collect-amd-transfer-evidence.py']:
        require(sha((HERE/name).read_bytes())==sha(data['sources/'+name]),'Replay source drift; use the packet-matched source files')
    bench=load_module('mtp_packet_prefill',HERE/'bench-prefill-followup.py')
    frozen_strict,reference=strict_replay(data,'frozen/control-strict')
    require(frozen_strict['complete_12_prompt_qualification'],'Frozen strict reference unqualified')
    frozen_context,context_reference=context_replay(data,'frozen/control-context',bench,None)
    require(frozen_context['reported_passed'],'Frozen context reference unqualified')
    strict={};contexts={}
    for name in sorted(data):
        if name.startswith(client_prefix+'/') and name.endswith('/strict/performance.json'):
            prefix=name[:-len('/performance.json')];strict[prefix]=strict_replay(data,prefix,reference)[0]
        if name.startswith(client_prefix+'/') and name.endswith('/context/summary.json'):
            prefix=name[:-len('/summary.json')];contexts[prefix]=context_replay(data,prefix,bench,context_reference)[0]
    rpc=[];native=[]
    for name in sorted(data):
        if name.startswith(client_prefix+'/rpc-') and name.endswith('-response.json'):
            response=json.loads(data[name]);rpc.append({'path':name,'sha256':sha(data[name])})
            if 'mtp_transfer_native_gate' in name:
                native.append({'path':name,'response':response})
    campaign=json.loads(data[client_prefix+'/summary.json']) if client_prefix+'/summary.json' in data else {'passed':False,'error':selection['client_not_run_reason'],'not_run':True}
    require(not campaign.get('not_run') or campaign['error'],'Missing client without explicit reason')
    client_replay=None
    if campaign.get('passed') is True:
        require(len(strict)==5 and all(r['complete_12_prompt_qualification'] for r in strict.values()),'Completed campaign lacks five exact strict attempts')
        require(len(contexts)==4 and all(r['reported_passed'] and r['measured_requests']==18 and r['complete_outputs_match_frozen_and_repeats'] for r in contexts.values()),'Completed campaign lacks four exact context attempts')
        require(len(native)==1,'Completed campaign native receipt missing')
        client=load_module('mtp_packet_client',HERE/'run-mtp-metadata-client-campaign.py')
        require(sha((HERE/'run-mtp-metadata-client-campaign.py').read_bytes())==sha(data['sources/run-mtp-metadata-client-campaign.py']),'Client verifier source differs')
        client.native_gate(native[0]['response'])
        client_replay=completed_client_replay(data,selection,campaign,client,strict,contexts)
    operators=[]
    binary_paths=selection['operator_binary_paths']
    for stage in selection['operator_stages']:
        prefix='raw/'+stage;state=json.loads(data[prefix+'/state.json'])
        records=[]
        for rank in (0,1):
            key=f'{prefix}/results/rank{rank}-quality.json'
            if key not in data:continue
            for row in json.loads(data[key]):
                stem=f"{prefix}/results/rank{rank}-rows{row['rows']}-{row['kind']}-{row['repeat']}"
                outputs=[]
                for arm in ('candidate','xccl'):
                    item=binary_paths[stem+'.'+arm+'.bin'];member=binary_members[item['member']]
                    require(item['sha256']==member['sha256']==row[arm+'_sha256'],'Operator raw hash differs')
                    require(item['bytes']==member['bytes']==row['rows']*5120*2,'Operator output byte count differs')
                    outputs.append(item['sha256'])
                actual_exact=outputs[0]==outputs[1]
                # An exact flag also includes the independently recorded input lifetime gate.
                require(row['exact']==(actual_exact and row['input_unchanged']),'Operator exactness classification inconsistent')
                records.append({'rank':rank,**row,'raw_outputs_verified':True,'raw_candidate_equals_xccl':actual_exact})
        analysis=json.loads(data[prefix+'/analysis.json']) if prefix+'/analysis.json' in data else None
        timing_replay=[]
        analyzer_path=HERE.parent/'probes/mtp-exact-tp2-20260914/analyze.py'
        if analysis is not None:
            require(prefix+'/snapshot/analyze.py' in data and sha(analyzer_path.read_bytes())==sha(data[prefix+'/snapshot/analyze.py']),'Operator analyzer source drift')
            analyzer=load_module('mtp_packet_operator_analysis',analyzer_path)
            for shape in analysis.get('shapes',[]):
                rows=shape['rows']
                rank_timings=[json.loads(data[f'{prefix}/results/rank{rank}-rows{rows}-timing.json']) for rank in (0,1)]
                rebuilt=analyzer.paired_latency(rank_timings)
                require(all(shape[k]==v for k,v in rebuilt.items()),'Operator paired timing arithmetic differs')
                timing_replay.append({'rows':rows,**rebuilt})
            if analysis.get('quality_passed') is True:
                expected={(rank,rows,kind,repeat) for rank in (0,1) for rows in analyzer.SHAPES for kind in analyzer.KINDS for repeat in (0,1)}
                require(len(records)==len(expected) and {(r['rank'],r['rows'],r['kind'],r['repeat']) for r in records}==expected,'Operator quality coverage incomplete')
                require(all(r['raw_candidate_equals_xccl'] and r['input_unchanged'] for r in records),'Passed operator analysis contains bad output')
                rank_hashes=[{(r['rows'],r['kind'],r['repeat']):r['candidate_sha256'] for r in records if r['rank']==rank} for rank in (0,1)]
                require(rank_hashes[0]==rank_hashes[1],'Operator rank outputs differ')
                require(all(f'{prefix}/results/rank{rank}-DONE.json' in data for rank in (0,1)),'Operator rank completion absent')
        operators.append({'stage':stage,'status':state['status'],'error':state.get('error'),'stop_confirmed':state.get('stop_confirmed'),'gpu_fault_receipt_present':prefix+'/GPU-FAULT.json' in data,'quality_records_with_raw_bits_verified':len(records),'all_recorded_outputs_exact':bool(records) and all(r['raw_candidate_equals_xccl'] and r['input_unchanged'] for r in records),'quality_records':records,'recorded_analysis':analysis,'replayed_timings':timing_replay,'analysis_replay_scope':'Raw output bytes stream-hashed; equality, byte lengths and completed quality coverage verified; present paired timings recomputed from raw rank measurements.'})
    return {'schema':'neural.download.mtp-transfer-evidence-summary.v1','frozen_reference':{'strict':frozen_strict,'context':frozen_context},'client_status':{'status':'not-run' if campaign.get('not_run') else ('completed' if campaign.get('passed') is True else 'aborted'),'passed':campaign.get('passed') is True,'error':campaign.get('error'),'promoted':False,'fresh_server_confirmation':False},'strict_attempts':strict,'context_attempts':contexts,'native_rpc_receipts':native,'rpc_receipt_count':len(rpc),'completed_client_replay':client_replay,'operators':operators,'closure':selection['closure'],'running_logs':selection['running_logs'],'interpretation':'Recorded completed and failed stages; exact output qualification and speed promotion remain separate. Single-process metadata screen is not independent-process confirmation.'}


def build_archives(packet,data,objects):
    sources={**data,**objects};members={};parts=[];groups=[];group=[];size=0
    for name,value in sorted(sources.items()):
        count=len(value) if isinstance(value,bytes) else value.stat().st_size
        if group and size+count>PART_LIMIT:groups.append(group);group=[];size=0
        group.append((name,value,count));size+=count
    if group:groups.append(group)
    for index,group in enumerate(groups,1):
        filename=f'evidence-{index:02d}.tar.gz';target=packet/(filename+'.tmp')
        with target.open('wb') as output:
            with gzip.GzipFile(fileobj=output,mode='wb',mtime=0,filename='') as gz:
                with tarfile.open(fileobj=gz,mode='w|') as archive:
                    for name,value,size in group:
                        info=tarfile.TarInfo(name);info.size=size;info.mode=0o644;info.mtime=0
                        if isinstance(value,bytes):archive.addfile(info,io.BytesIO(value));digest=sha(value)
                        else:
                            digest,before_size=hash_file(value);require(before_size==size,'Operator binary changed size')
                            with value.open('rb') as stream:archive.addfile(info,stream)
                        members[name]={'archive':filename,'bytes':size,'sha256':digest}
        digest,count=hash_file(target);require(count<95*1024*1024,'Archive part exceeds Git size budget')
        parts.append({'name':filename,'bytes':count,'sha256':digest})
    return parts,members


def read_archives(packet,manifest,temporary=False):
    expected=manifest['members'];seen=set();data={};binary={}
    for part in manifest['archives']:
        safe_relative(part['name']);path=packet/(part['name']+('.tmp' if temporary else ''))
        digest,count=hash_file(path);require(digest==part['sha256'] and count==part['bytes'],'Archive identity mismatch')
        with tarfile.open(path,'r|gz') as archive:
            for member in archive:
                safe_relative(member.name);require(member.isfile() and member.name not in seen,'Unsafe or duplicate tar member')
                require(member.name in expected,'Unexpected tar member');pin=expected[member.name]
                require(pin['archive']==part['name'] and member.size==pin['bytes'],'Tar coverage/size mismatch')
                stream=archive.extractfile(member);h=hashlib.sha256();chunks=[]
                is_binary=member.name.startswith('operator-output-bits/')
                require(member.size <= (MAX_BINARY_FILE if is_binary else MAX_TEXT_FILE),'Oversized tar member')
                for chunk in iter(lambda:stream.read(1024*1024),b''):
                    h.update(chunk)
                    if not is_binary:chunks.append(chunk)
                require(h.hexdigest()==pin['sha256'],'Tar member hash mismatch')
                if is_binary:binary[member.name]=pin
                else:
                    raw=b''.join(chunks);legacy.secret_check(member.name,raw);data[member.name]=raw
                seen.add(member.name)
    require(seen==set(expected),'Archive member coverage incomplete')
    return data,binary


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',type=Path,default=DEFAULT_ROOT)
    ap.add_argument('--packet',type=Path,default=DEFAULT_PACKET)
    ap.add_argument('--client-dir',default='client-campaign')
    ap.add_argument('--server-dir',default='research-server')
    ap.add_argument('--final-receipt',default='campaign-completion.json')
    ap.add_argument('--operator-stage',action='append',default=[])
    ap.add_argument('--frozen-root',type=Path,default=Path('/mnt/fast-ai/bench-results/amd-transfer-fp8-20260914'))
    ap.add_argument('--running-log-snapshot-label')
    ap.add_argument('--verify',action='store_true',help='Verify existing packet only; raw paths are not read')
    args=ap.parse_args()
    for value in (args.client_dir,args.server_dir,args.final_receipt):safe_relative(value)
    if args.verify:
        manifest=json.loads((args.packet/'manifest.json').read_text())
        require(sha(Path(__file__).read_bytes())==manifest['collector_sha256'],'Collector source drift; replay with packet-matched script')
        data,binary=read_archives(args.packet,manifest)
        summary=summarize(data,binary)
        raw=(args.packet/'summary.json').read_bytes()
        require(sha(raw)==manifest['summary_sha256'] and json.loads(raw)==summary,'Summary replay mismatch')
        print(json.dumps({'passed':True,'archives':len(manifest['archives']),'members':len(manifest['members']),'mode':'verify-only'}));return
    require(not (args.packet/'manifest.json').exists(),'Existing packet is frozen; choose a new packet directory')
    data,objects=select(args)
    args.packet.mkdir(parents=True,exist_ok=True)
    parts,members=build_archives(args.packet,data,objects)
    manifest={'schema':'neural.download.mtp-transfer-evidence-manifest.v1','collector_sha256':sha(Path(__file__).read_bytes()),'collector_repository_path':str(Path(__file__).resolve().relative_to(REPO)),'archives':parts,'members':members,'selection':'Explicit completed-stage allowlists; raw operator outputs content-deduplicated without losing any output bytes; archive parts bounded to64MiB uncompressed payload.'}
    replay_data,binary=read_archives(args.packet,manifest,temporary=True)
    summary=summarize(replay_data,binary);raw=encoded(summary);manifest['summary_sha256']=sha(raw)
    manifest['verification']={'archive_hashes_and_members_verified':True,'strict_intervals_and_context_sse_histograms_replayed':True,'operator_output_bits_stream_hashed':True,'credential_scan_passed':True}
    for part in parts:(args.packet/(part['name']+'.tmp')).replace(args.packet/part['name'])
    (args.packet/'summary.json').write_bytes(raw)
    (args.packet/'manifest.json').write_bytes(encoded(manifest))
    print(json.dumps({'passed':True,'archives':len(parts),'members':len(members),'archive_bytes':sum(p['bytes'] for p in parts),'client_passed':summary['client_status']['passed']}))

if __name__=='__main__':main()
