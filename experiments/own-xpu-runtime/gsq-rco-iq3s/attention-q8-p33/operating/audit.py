#!/usr/bin/env python3
"""Closed-run auditor. --run requires explicit completion authorization from root.
No import of the suite's metric/summary implementation; no model/runtime API.
"""
import argparse,gzip,hashlib,json,math,os,resource,stat,statistics,time
from pathlib import Path
P=Path(__file__).resolve().parent;L=P.parent.parent;R=L.parents[2]
PARENT_AUDITOR=L/'baseline/audit.py'
PARENT_AUDITOR_SHA='43154e5b8101fb879eb08bbbebc29714443dd083cb90df6fbbb7e269d522d0ab'
CONTROL=Path('/home/steve/own-xpu-runtime-results/gsq-attention-p33-a.control')
EVIDENCE=Path('/mnt/usb-models/own-xpu-runtime-results/gsq-attention-p33-a')
EOS=(248044,248046)

def require(v,msg):
    if not v:raise ValueError(msg)
def read(p):return json.loads(Path(p).read_text())
def sha(p):
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        a=os.fstat(fd);require(stat.S_ISREG(a.st_mode),'regular retained artifact required')
        h=hashlib.sha256()
        while b:=os.read(fd,256*1024):h.update(b)
        z=os.fstat(fd);require((a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns)==(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns),'artifact changed during readback')
        return h.hexdigest()
    finally:os.close(fd)
def near(a,b,label,absolute=.001,relative=1e-8):
    require(type(a) in (int,float) and type(b) in (int,float) and math.isfinite(a) and math.isfinite(b),label+' nonfinite')
    require(abs(a-b)<=max(absolute,abs(b)*relative),label+' mismatch')
def confirmed_inputs(result,prompt):
    tokens=result['tokens'];expected=list(enumerate(prompt+tokens[:-1]))
    trace=result['rank_trace'];r1=sorted([x for x in trace if x['rank']==1 and x['op']==1],key=lambda x:x['position'])
    require([(x['position'],x['token']) for x in r1]==expected,'rank1 consumed prompt/token history')
    pending=None;accepted=[]
    for row in sorted((x for x in trace if x['rank']==0),key=lambda x:x['rank_received']):
        if row['op']==1:pending=row
        elif row['op']==3:pending=None
        elif row['op']==2:
            require(pending is not None,'ACCEPT without pending HALF');accepted.append((pending['position'],pending['token']));pending=None
    require(accepted==expected,'rank0 accepted prompt/token history')
    # An EOS stop can leave a resolved speculative candidate; require no
    # unaccepted HALF remains after the retained rollback/accept trace.
    require(pending is None,'unresolved final candidate')
    return len(expected)

def timing(result,cap,eos=True):
    tokens=result['tokens'];events=result['timing_rows'];require(0<len(tokens)<=cap and len(events)==len(tokens),'complete emitted events')
    require(all(type(t)is int and 0<=t<248320 for t in tokens),'token vocabulary')
    require(eos or len(tokens)==cap,'excluded warmup incomplete')
    if len(tokens)<cap:require(eos and tokens[-1] in EOS,'unexplained short output')
    times=[]
    for i,event in enumerate(events):
        require(event['generated_index']==i+1 and event['token_id']==tokens[i],'timing token identity')
        x=event['completed_monotonic'];require(type(x) in (int,float) and math.isfinite(x),'completion time');times.append(x)
    require(all(a<b for a,b in zip(times,times[1:])),'completion ordering')
    intervals=len(tokens)-1;elapsed=(times[-1]-times[0])*1000 if intervals else 0
    require(result['decode_intervals']==intervals and result['decode_numerator']==intervals,'interval numerator')
    near(result['decode_wall_ms'],elapsed,'raw elapsed')
    require(math.isfinite(result['prompt_wall_ms']) and result['prompt_wall_ms']>=0,'prompt time')
    return dict(output_tokens=len(tokens),decode_intervals=intervals,decode_wall_ms=elapsed,decode_tok_s=intervals*1000/elapsed if intervals else None,prompt_wall_ms=result['prompt_wall_ms'],termination='eos' if tokens[-1] in EOS else 'cap')

def guess_outcomes(result,prompt,cap):
    stats=result['stats'];rows=result['guess_rows'];tokens=result['tokens']
    require(all(type(stats[k])is int and stats[k]>=0 for k in ('guesses','hits','misses')),'guess counters')
    for g in rows:
        i=g['position']-len(prompt)
        require(0<=i<len(tokens) and g['actual']==tokens[i] and g['hit']==(g['guess']==g['actual']),'resolved guess identity')
    require(sum(g['hit'] for g in rows)==stats['hits'] and len(rows)-stats['hits']==stats['misses'],'resolved guess outcomes')
    cancelled=stats['guesses']-len(rows)
    # Native controller counts a speculative next-input launch before receiving
    # EOS, then rolls it back without accepting/rejecting that unused proposal.
    require(cancelled==0 or (cancelled==1 and len(tokens)<cap and tokens[-1] in EOS),'unexplained unresolved guess')
    return cancelled

def aggregate(pairs):
    groups={}
    for first in ('all','none','mtp'):
        chosen=[p for p in pairs if first=='all' or p['order'][0]==first];arms={}
        for mode in ('none','mtp'):
            rows=[next(a for a in p['arms'] if a['mode']==mode) for p in chosen]
            rates=[a['timing']['decode_tok_s'] for a in rows if a['timing']['decode_tok_s'] is not None]
            n=sum(a['timing']['decode_intervals'] for a in rows);ms=sum(a['timing']['decode_wall_ms'] for a in rows)
            arms[mode]=dict(prompts=len(rows),zero_interval_prompts=len(rows)-len(rates),total_output_tokens=sum(a['timing']['output_tokens'] for a in rows),decode_intervals=n,decode_wall_ms=ms,interval_weighted_tok_s=n*1000/ms if n else None,median_prompt_tok_s=statistics.median(rates) if rates else None,prompt_wall_ms_sum=sum(a['timing']['prompt_wall_ms'] for a in rows),guesses=sum(a['stats']['guesses'] for a in rows),hits=sum(a['stats']['hits'] for a in rows),misses=sum(a['stats']['misses'] for a in rows))
        groups[first]=dict(first_arm=first,arms=arms)
    return groups

def compare_summary(actual,stored):
    require(set(actual)==set(stored),'summary groups')
    for group,row in actual.items():
        require(stored[group]['first_arm']==group,'order label')
        for mode,arm in row['arms'].items():
            for key,value in arm.items():
                other=stored[group]['arms'][mode][key]
                if value is None:require(other is None,'zero interval rate')
                elif isinstance(value,int):require(other==value,'aggregate integer '+key)
                else:near(other,value,'aggregate '+key,absolute=.03,relative=1e-7)

def validate_passive(before,after,terminal):
    require(terminal['passed'] and terminal['first_error'] is None and terminal['original_error'] is None,'terminal failure')
    require(terminal['children_exited'] and terminal['target_descriptors_empty'] and terminal['observed_target_contact']==[True,True],'owner/contact terminal')
    require(terminal['retries']==terminal['hard_kills']==terminal['service_changes']==0,'unexpected action')
    require(before['boot']==after['boot'] and before['kernel']['faults']==after['kernel']['faults'] and after['known_fault_baseline_matches'],'fault baseline')
    require(before['drm']==after['drm'] and before['queue']==after['queue'],'topology/queue changed')
    require(before['units']['qwen38-27b-vision']==after['units']['qwen38-27b-vision'],'vision unit changed')
    require(after['holders']['3487303']['start_ticks']==63453537,'vision identity')
    require(not after['identity_races'] and not after['inventory']['errors'],'incomplete passive inventory')
    for h in after['inventory']['holders']:require(h['pid']==3487303 and after['drm'][h['node']]['bdf'] in ('0000:27:00.0','0000:43:00.0'),'remaining foreign/target holder')
    require({h['node'] for h in before['inventory']['holders']}=={h['node'] for h in after['inventory']['holders']},'vision descriptor set')

def run():
    require(os.getpriority(os.PRIO_PROCESS,0)==19,'nice19');require(os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32)),'helper affinity')
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
    dest=P/'evidence/independent-a';dest.mkdir(parents=True,exist_ok=False)
    started=time.monotonic();receipt={'schema':'ownrt.gsq.attention-candidate-independent.v1','passed':False,'device_executed_by_reviewer':False,'scope':'candidate vs independently audited original baseline exact tokens/full target state on all12 pairs; separate-process timings descriptive only, no speed promotion'}
    try:
        require(sha(PARENT_AUDITOR)==PARENT_AUDITOR_SHA,'frozen parent auditor changed')
        baseline_review=L/'baseline/evidence/independent-a/review.json'
        require(sha(baseline_review)=='f662fcecf93c92f90006c09c05d4a4c02e71e84ae9d8c82dbff3fdfc39ebb5bb','independent baseline review authority')
        prior_audit=read(baseline_review);require(prior_audit['passed'] and prior_audit['all12_exact'] and prior_audit['source_and_binary_pins_verified'],'baseline authority incomplete')
        baseline_path=Path('/mnt/usb-models/own-xpu-runtime-results/gsq-baseline-a/resident-suite.json')
        require(sha(baseline_path)==prior_audit['full_result_sha256'],'audited original full result')
        baseline=read(baseline_path);require(baseline['passed'] and len(baseline['prompts'])==12,'baseline corpus')
        references={arm['name']:arm for pair in baseline['prompts'] for arm in pair['arms']};require(len(references)==24,'baseline unique arms')
        plan=read(CONTROL/'plan.json');admission=read(CONTROL/'admission.json');terminal=read(CONTROL/'terminal.json');manifest=read(L/'baseline/manifest.json')
        require(terminal['plan_sha256']==admission['plan_sha256']==sha(CONTROL/'plan.json'),'plan binding')
        require(admission['plan']==plan,'admitted plan')
        for key,value in plan['unit_properties'].items():require(admission['unit'][key]==value,'coordinator safe unit property')
        require(hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(',',':')).encode()).hexdigest()==admission['canonical_plan_sha256'],'canonical plan')
        validate_passive(admission['before'],terminal['after'],terminal)
        full_path=Path(terminal['result']['full_result_path']);require(full_path==EVIDENCE/'resident-suite.json','fixed full result')
        require(sha(full_path)==terminal['result']['full_result_sha256'],'full result hash');full=read(full_path)
        require(plan['suite']['baseline_review_sha256']==sha(baseline_review) and plan['suite']['baseline_result_sha256']==sha(baseline_path),'candidate baseline plan binding')
        require(full['passed'] and full['requests']==26 and full['measured_requests']==24,'complete fixed suite')
        require(full['manifest_sha256']==sha(L/'baseline/manifest.json')==plan['suite']['manifest_sha256'],'manifest')
        require(full['rank_pids']==[x[0] for x in terminal['rank_identities']],'same ranks')
        require(len(full['warmup'])==2 and len(full['prompts'])==12,'complete corpus')
        corpus=read(R/'experiments/own-xpu-runtime/stage2/suite-inputs-20261012-cap128/suite-manifest.json')['prompts']
        require(len(corpus)==12 and [x['prompt_id'] for x in manifest['prompts']]==[x['prompt_id'] for x in corpus],'original complete corpus')
        for selected,original in zip(manifest['prompts'],corpus):require(selected['tokens']==list(map(int,(R/original['input_bundle']/'tokens.txt').read_text().split())),'original corpus tokens')
        for f,h in plan['source_sha256'].items():require(sha(f)==h,'source '+f)
        for f,h in plan['suite']['source_sha256'].items():require(sha(f)==h,'suite source '+f)
        for f,h in plan['adapter']['source_sha256'].items():require(sha(R/f)==h,'adapter source '+f)
        native=read(plan['adapter']['build_receipt']);require(native['passed'] and native['mode']=='native','native build')
        require(sha(plan['adapter']['build_receipt'])==plan['adapter']['build_receipt_sha256'],'build receipt')
        require(sha(plan['adapter']['binary'])==native['binary_sha256']==plan['adapter']['binary_sha256'],'native binary')
        for f,h in native['source_sha256'].items():require(sha(R/f)==h,'native source '+f)
        for f,h in native['object_sha256'].items():require(sha(f)==h,'native object')
        for f,h in manifest['source_pins'].items():require(sha(R/f)==h,'corpus input')
        # One bounded readback of every retained file. Streaming gzip index keeps
        # >50k per-file records compact; no multi-GB state copying into Git.
        digests={};sizes={};count=0;total=0
        with (dest/'artifact-index.jsonl.gz').open('xb') as raw,gzip.GzipFile(fileobj=raw,mode='wb',filename='',mtime=0) as zipped:
            for label,root in [('control',CONTROL),('evidence',EVIDENCE)]:
                for f in sorted(root.rglob('*')):
                    require(not f.is_symlink(),'retained symlink')
                    if not f.is_file():continue
                    h=sha(f);n=f.stat().st_size;digests[str(f)]=h;sizes[str(f)]=n;count+=1;total+=n
                    zipped.write((json.dumps(dict(root=label,path=str(f.relative_to(root)),bytes=n,sha256=h),separators=(',',':'))+'\n').encode())
                    require(total<=8*1024**3 and count<=100000,'closed audit byte/file bound')
        def states(base,expected):
            answer={};raw_bytes=0
            for rank in (0,1):
                directory=base/f'rank{rank}/state-2147483647'
                rows={str(f.relative_to(directory)):digests[str(f)] for f in sorted(directory.rglob('*')) if f.is_file()}
                require(rows==expected[str(rank)] and rows,'retained target state mismatch')
                own=read(directory/'state.json')
                for name,h in own['buffers'].items():
                    name=('alternate-'+name.split(':',1)[1] if name.startswith('alternate:') else name)+'.bin'
                    require(rows[name]==h,'native state manifest digest')
                raw_bytes+=sum(sizes[str(f)] for f in directory.glob('*.bin'));answer[str(rank)]=rows
            require(raw_bytes==221743168,'full target state extent');return answer
        checked=[];number=0
        for w,definition in zip(full['warmup'],manifest['warmup']):
            number+=1;require(w['request']==number and w['mode']==definition['mode'] and not w['measured'],'warmup schedule')
            require(w['prompt_tokens']==definition['tokens'] and w['requested_max_new']==8,'warmup identity')
            timing(w['result'],8,False);confirmed_inputs(w['result'],w['prompt_tokens'])
            for rank in (0,1):require(read(EVIDENCE/w['name']/f'rank{rank}/reset.json')['allocation_ids_preserved'],'warmup reset')
        for i,(pair,prompt) in enumerate(zip(full['prompts'],manifest['prompts'])):
            require(pair['prompt_id']==prompt['prompt_id'] and pair['order']==prompt['order'],'all12 original order')
            require(prompt['order']==(['none','mtp'] if i%2==0 else ['mtp','none']),'balanced order')
            require(pair['exact_tokens'] and pair['exact_final_target_state'],'pair gate')
            arms=[];pair_states=[]
            for arm,mode in zip(pair['arms'],prompt['order']):
                number+=1;require(arm['request']==number and arm['mode']==mode and arm['measured'],'arm schedule')
                require(arm['prompt_tokens']==prompt['tokens'] and arm['requested_max_new']==128,'unchanged prompt/cap')
                base=EVIDENCE/arm['name'];require(read(base/'suite-request.json')==arm,'raw request copy')
                reference=references[arm['name']]
                require(reference['mode']==mode and reference['prompt_tokens']==arm['prompt_tokens'] and reference['requested_max_new']==128,'corresponding original baseline arm')
                require(arm['result']['tokens']==reference['result']['tokens'],'candidate tokens differ from original baseline')
                require(arm['state_sha256']==reference['state_sha256'],'candidate target state map differs from original baseline')
                exact=read(base/'baseline-exact.json');require(exact['passed'] and exact['reference_sha256']==sha(baseline_path),'per-arm live exact gate receipt')
                metric=timing(arm['result'],128);consumed=confirmed_inputs(arm['result'],arm['prompt_tokens'])
                for key in ('output_tokens','decode_intervals','termination'):require(metric[key]==arm['metric'][key],'metric identity')
                near(arm['metric']['decode_wall_ms'],metric['decode_wall_ms'],'stored metric elapsed')
                for rank in (0,1):
                    reset=read(base/f'rank{rank}/reset.json');require(reset['passed'] and reset['allocation_ids_preserved'],'full reset')
                pair_states.append(states(base,arm['state_sha256']))
                stats=arm['result']['stats'];guesses=arm['result']['guess_rows']
                if mode=='none':require(stats['guesses']==stats['hits']==stats['misses']==0,'target-only guess statistics')
                else:guess_outcomes(arm['result'],arm['prompt_tokens'],128)
                arms.append(dict(mode=mode,tokens=arm['result']['tokens'],timing=metric,stats=stats,consumed_positions=consumed,cancelled_unverified_guesses=stats['guesses']-len(guesses)))
            require(arms[0]['tokens']==arms[1]['tokens'] and pair_states[0]==pair_states[1],'independent pair equality')
            checked.append(dict(prompt_id=prompt['prompt_id'],order=prompt['order'],arms=arms))
        require(number==26,'all26 verified')
        derived=aggregate(checked);compare_summary(derived,full['summary']['order_groups']);compare_summary(derived,terminal['result']['summary']['order_groups'])
        ledger=read(P/'candidate-ledger.json')['scenarios']['split24-24_mtp-rank0']['ranks'];owners=[];memory=[]
        for rank in (0,1):
            owner=read(EVIDENCE/f'rank{rank}/receipt.json');require(owner['passed'] and owner['rank']==rank and owner['error']=='','rank receipt')
            require(len(owner['teardown'])==1,'teardown count');t=owner['teardown'][0]
            require(t['safe_to_exit'] and t['in_flight']==t['live_bytes']==t['exit_code']==0,'owner safe close');owners.append({k:t[k] for k in ('backend','status','safe_to_exit','in_flight','live_bytes','exit_code')})
            census=read(EVIDENCE/f'rank{rank}/census.json');actual=sum(a['bytes'] for a in census['allocations'] if a['live'] and a['memory']=='device')
            require(actual==census['totals']['device']==ledger[rank]['device_logical_bytes'],'memory forecast exact');memory.append(actual)
        ownership=read(EVIDENCE/'ownership.json');require(ownership['returncodes']==[0,0] and ownership['retained_pids']==[] and ownership['signals_sent']==0 and not ownership['stop_requested'],'process cleanup')
        receipt.update(candidate_vs_original_baseline_exact=True,baseline_review_sha256=sha(baseline_review),baseline_result_sha256=sha(baseline_path),no_speed_promotion=True,code_identity='attention Q8 p33 variant6 split1 only48 projections; candidate native build and per-rank expanded memory ledger',passed=True,requests=26,measured_requests=24,warmups_excluded=2,all12_exact=True,rank_pids=full['rank_pids'],prompts=checked,recomputed_order_groups=derived,owners=owners,ownership=ownership,actual_device_bytes=memory,passive_drain_scope='retained complete afterinventory shows only unchanged vision27/43; no fresh process/kernel/service query',kernel_fault_baseline_unchanged=True,source_and_binary_pins_verified=True,native_binary_sha256=native['binary_sha256'],full_result_sha256=sha(full_path),artifact_count=count,indexed_bytes=total,index_sha256=sha(dest/'artifact-index.jsonl.gz'),roots=dict(control=str(CONTROL),evidence=str(EVIDENCE)),originals_retained=True,limitations=['Same-engine target/MTP exactness, not external-engine or broad semantic quality','Short fixed60-90token prompts with cap128; allEOS/short outputs retained','Separate candidate process versus prior baseline; timing descriptive, no speed promotion; first-use/order effects may remain','No cold-start, long-context or old-model record claim','Physicaldrain based on retained observations, not fresh reviewer host/device operations'])
    except BaseException as error:
        receipt['error']=type(error).__name__+': '+str(error);raise
    finally:
        receipt.update(auditor_sha256=sha(__file__),parent_auditor_sha256=sha(PARENT_AUDITOR),elapsed_seconds=time.monotonic()-started)
        with (dest/'review.json').open('x') as f:json.dump(receipt,f,indent=2);f.write('\n')
    print(json.dumps({'passed':True,'review':str(dest/'review.json'),'sha256':sha(dest/'review.json')}))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',action='store_true',required=True);p.parse_args();run()
if __name__=='__main__':main()
