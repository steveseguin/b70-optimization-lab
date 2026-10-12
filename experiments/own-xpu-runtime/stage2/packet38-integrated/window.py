#!/usr/bin/env python3
"""Coordinator-only device windows. Preparation never executes this entry."""
import argparse,gzip,hashlib,json,math,os,re,signal,subprocess,time
from pathlib import Path
import pipeline as pp
from pipeline import P,save,sha,require,Transport,CANARY,SLOT
from window_safety import environment_gate,memory_snapshot
from fixture_support import journal,ldd_preflight,oracle_gate,fixture_receipt_gate,k1_gate
from k2_summary import summarize
from merge_dispatch import validate
from storage import admit
B=P/'build';ROOT=P.parents[3]
CONFIG={'K0':(30,600),'K1a':(120,10800),'K1b':(120,10800),'K2':(1596,10800),'W0p':(30,600),
        'W2s':(1900,10800),'W2n':(1900,10800),'W2x':(1900,10800),'W2d':(1900,10800),'W2c':(1900,10800),'KD':(1800,10800),'W2m':(2100,10800),'W2mc':(2100,10800),'WS':(7200,30000),'WSs':(7200,30000)}
FAULT=re.compile(r'Fault response|Engine memory CAT error|engine reset|timed[- ]out job|devcoredump|GPU.*coredump',re.I)
def watchdog(name,seconds=None):
    expected,default=CONFIG[name];seconds=default if seconds is None else seconds
    require(math.isfinite(expected) and expected>=0 and expected+17<=seconds/4,'expected duration exceeds a quarter of watchdog')
    require(max(300,math.ceil(4*(expected+17)))<=seconds<=172800,'watchdog below four times estimate/300s or above 172800s')
    return seconds

def foreign_engines(proc=Path('/proc')):
    """Read-only fdinfo samples, no DRM device opens/discovery.

    Conservatively reserve the whole host: any visible foreign engine growth
    blocks admission, even outside the chosen adjacent pair. Record unreadable
    process counts; this cannot inspect private clients of another UID.
    """
    def sample():
        values={};unreadable=0
        for pid in proc.iterdir():
            if not pid.name.isdigit():continue
            try:paths=list((pid/'fdinfo').iterdir())
            except (PermissionError,FileNotFoundError):unreadable+=1;continue
            for f in paths:
                try:text=f.read_text()
                except (PermissionError,FileNotFoundError,ProcessLookupError):continue
                lines=dict(line.split(':',1) for line in text.splitlines() if ':' in line)
                pci=lines.get('drm-pdev','').strip();client=lines.get('drm-client-id',f.name).strip()
                for key,value in lines.items():
                    if key.startswith('drm-engine-') and not key.startswith(('drm-engine-capacity','drm-engine-cycles')):
                        try:values[(pid.name,pci,client,key)]=int(value.split()[0])
                        except (ValueError,IndexError):raise ValueError('unparsed DRM engine counter')
        return values,unreadable
    before,u0=sample();time.sleep(.25);after,u1=sample()
    active=[dict(pid=k[0],pci=k[1],engine=k[3],delta_ns=v-before.get(k,0)) for k,v in after.items() if v>before.get(k,0)]
    require(not active,'foreign engine activity: '+str(active))
    return dict(active=active,scope='whole-host conservative',unreadable_processes=max(u0,u1),sample_seconds=.25)
class Watch:
    def __init__(self,out,boot,seconds):
        self.out=out;self.boot=boot;self.end=time.monotonic()+seconds;self.last=0.;self.cancelled=[];self.launched=[];self.new_gpu_fault=False
        text,self.cursor=journal();(out/'kernel-preflight.txt').write_text(text)
    def mark_launched(self,pid):
        self.launched.append(int(pid))
    def latch(self,reason):
        # Admission/loader/argument refusals before any child exists cannot poison a boot.
        if not self.launched or not self.new_gpu_fault:return
        save(B/'FAULT.json',dict(boot_id=self.boot,reason=str(reason),window=str(self.out)))
    def poll_kernel(self):
        if time.monotonic()-self.last<.25:return
        text,self.cursor=journal(self.cursor);self.last=time.monotonic()
        fault=bool(FAULT.search(text))
        if fault:self.new_gpu_fault=True
        # Remember the fresh signature even if saving its text runs out of space.
        try:
            with (self.out/'kernel-window.txt').open('a') as f:f.write(text)
        finally:
            if fault:self.latch('GPU fault signature')
        if fault:raise ValueError('GPU fault signature')
    def check(self):
        self.poll_kernel()
        require(not self.cancelled,'coordinator stop requested')
        require(time.monotonic()<self.end,'window watchdog')
    def postflight(self):
        end=time.monotonic()+5
        while time.monotonic()<end:self.check();time.sleep(.25)

def compress_evidence(root,record):
    """Stream, verify, then unlink raw logs and oversized fixture bytes."""
    retained=record.setdefault('retained_artifacts',{})
    for source in sorted(root.rglob('*')):
        if not source.is_file() or source.suffix=='.gz':continue
        is_log=source.suffix=='.log' or (source.suffix=='.jsonl' and any(word in source.name for word in ('event','trace')))
        is_fixture=source.name=='output.bin' and source.stat().st_size>20_000_000
        if not (is_log or is_fixture):continue
        size=source.stat().st_size
        digest=stream_hash(source)
        if is_fixture:
            native=json.loads((source.parent/'receipt.json').read_text())
            require(native.get('output_sha256')==digest,'fixture retention hash differs from native receipt')
        # gzip worst-case overhead plus one streaming block; both files coexist.
        admit(size+size//1000+2_000_000)
        target=source.with_name(source.name+'.gz')
        require(not target.exists(),'compressed evidence already exists')
        with source.open('rb') as inp,target.open('wb') as raw:
            with gzip.GzipFile(fileobj=raw,mode='wb',mtime=0) as compressed:
                for chunk in iter(lambda:inp.read(1024*1024),b''):compressed.write(chunk)
        require(stream_hash(target,True)==digest,'compressed evidence byte mismatch')
        name=str(source.relative_to(root))
        retained[name]=dict(path=str(target.relative_to(root)),sha256=stream_hash(target),uncompressed_sha256=digest,uncompressed_bytes=size)
        # Persist mapping before unlink so interrupted retention is recoverable.
        save(root/'retention.json',retained)
        source.unlink()
    return retained

def stream_hash(path,compressed=False):
    h=hashlib.sha256()
    with (gzip.open(path,'rb') if compressed else path.open('rb')) as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def retained_hash(root,name,record):
    path=root/name
    if path.is_file():return stream_hash(path)
    item=record.get('retained_artifacts',{}).get(name)
    require(isinstance(item,dict),'prerequisite artifact missing: '+name)
    target=(root/item['path']).resolve()
    require(root.resolve() in target.parents and stream_hash(target)==item['sha256'],'compressed prerequisite changed')
    digest=stream_hash(target,True)
    require(digest==item['uncompressed_sha256'],'compressed prerequisite bytes changed')
    return digest

def projected_write_bytes(name,requests=1):
    # Sealed fixture gate peaks below 500MB; include compression coexistence.
    # Model requests retain 384 20KB layer fixtures plus hashes, timing and logs.
    if name in ('K1a','K1b','K2'):return 1_100_000_000
    if name in ('K0','W0p'):return 32_000_000
    return 550_000_000+requests*16_000_000

def prerequisites(path,name,identity):
    require(path is not None,'missing prerequisite '+name)
    row=json.loads(path.read_text());require(row.get('passed') is True and row.get('window')==name,'failed prerequisite '+name)
    for field in ('boot_id','artifacts_sha256','environment','card','build_receipt_sha256'):
        require(row.get(field)==identity.get(field),'prerequisite identity changed: '+name+' '+field)
    if name in ('K1a','K1b'):
        linked=row.get('linked_p33',{})
        require(linked.get('checks')==216 and linked.get('split_instantiations')==36 and linked.get('binary_sha256')==identity['artifacts_sha256'].get('device/p33-linked-fixtures') and linked.get('card')==identity.get('card'),'K1 linked fixture prerequisite coverage/identity changed')
        require({'linked/receipt.json','linked/output.bin'}<=set(row.get('receipts',{})),'K1 linked fixture evidence missing')
    for filename,digest in row.get('receipts',{}).items():require(retained_hash(path.parent,filename,row)==digest,'prerequisite receipt changed')
    return row

def linked_fixture_gate(root,build,card):
    row=json.loads((root/'receipt.json').read_text())
    require(row.get('schema')=='packet37.p33-linked-fixtures.v1' and row.get('passed') is True and row.get('device_executed') is True and row.get('reference_exact') is True,'linked p33 device/exactness receipt failed')
    for key,value in (('checks',216),('type_k_families',18),('split_instantiations',36),('modes_per_instantiation',6),('output_rows',1512),('argument_limit_bytes',1024),('owner_cards',1)):
        require(type(row.get(key)) is int and row[key]==value,'linked p33 coverage incomplete: '+key)
    require(type(row.get('card')) is int and row['card']==card,'linked p33 fixture card differs from admitted first card')
    teardown=row.get('teardown',{})
    require(isinstance(teardown,dict) and teardown.get('safe_to_exit') is True and type(teardown.get('exit_code')) is int and teardown['exit_code']==0 and type(teardown.get('live_bytes')) is int and teardown['live_bytes']==0 and type(teardown.get('in_flight')) is int and teardown['in_flight']==0,'linked p33 owner teardown incomplete')
    digest=sha(root/'output.bin')
    require(digest==row.get('output_sha256')==build.get('p33_linked_fixture_host_sha256'),'linked p33 bytes differ from sealed host fixture')
    return dict(checks=row['checks'],split_instantiations=row['split_instantiations'],output_sha256=digest,binary_sha256=build['artifacts_sha256']['device/p33-linked-fixtures'],card=card)

def fresh_k1_owners(first,second):
    left,right=first.get('pids'),second.get('pids')
    require(isinstance(left,list) and isinstance(right,list) and len(left)==len(right)==2,'K1 requires both fixture processes')
    require(all(type(pid) is int and pid>0 for pid in left+right) and len(set(left+right))==4,'K1 requires distinct fresh fixture owner processes')

def run_fixtures(a,out,env,watch):
    # K0 remains two simultaneous single-device JIT owners. K1 runs its two
    # fixture programs sequentially on the first card; no same-card overlap.
    if a.window=='K0':jobs=[('jit-smoke',a.card,'run0'),('jit-smoke',a.card+1,'run1')]
    elif a.window in ('K1a','K1b'):jobs=[('nongemv-fixtures',a.card,'run0'),('p33-linked-fixtures',a.card,'linked')]
    else:jobs=[('k2-fixtures',a.card,'run0')]
    admit(projected_write_bytes(a.window))
    receipts={};children=[];entries=[];logs=[];stop_r,stop_w=os.pipe()
    def wait_for_children():
        while any(child.poll() is None for child in children):
            watch.check();require(all(child.poll() in (None,0) for child in children),'fixture rank failure');time.sleep(.1)
        require(all(child.poll()==0 for child in children),'fixture exit failure')
    try:
        # All loader refusals precede the first device owner, including the
        # second sequential K1 program and the second K0 card process.
        for name,_,_ in jobs:watch.check();ldd_preflight(B/'device'/name)
        for index,(name,card,directory) in enumerate(jobs):
            watch.check();admit(550_000_000 if a.window!='K0' else 16_000_000);binary=B/'device'/name
            dest=out/directory;log=(out/f'fixture{index}.log').open('w');logs.append(log)
            cmd=[str(binary),'--authorized-device-window','--card',str(card),'--output',str(dest)]
            if a.window=='K0':cmd+=['--cards','1']
            else:cmd+=['--stop-fd',str(stop_r)]
            if name=='p33-linked-fixtures':cmd+=['--seconds',str(watchdog(a.window,a.seconds))]
            if a.window=='K2':cmd+=['--repetitions','200']
            if a.dispatch and name in ('nongemv-fixtures','k2-fixtures'):cmd+=['--dispatch',str(a.dispatch)]
            child=subprocess.Popen(['ionice','-c','3']+cmd,stdout=log,stderr=subprocess.STDOUT,env=env,pass_fds=(stop_r,))
            children.append(child);watch.mark_launched(child.pid)
            entries.append(dict(binary=name,binary_sha256=sha(binary),card=card,directory=directory,pid=child.pid,argv=cmd))
            save(out/'children.json',dict(pids=[child.pid for child in children],entries=entries,signals_sent=0))
            if a.window in ('K1a','K1b'):
                wait_for_children()
                receipt=json.loads((dest/'receipt.json').read_text());require(receipt.get('passed') is True,'fixture native failure')
        wait_for_children()
        for entry,child in zip(entries,children):
            require(child.returncode==0,'fixture exit failure');directory=entry['directory']
            receipt=json.loads((out/directory/'receipt.json').read_text());require(receipt.get('passed') is True,'fixture native failure')
            receipts[directory+'/receipt.json']=sha(out/directory/'receipt.json')
            if entry['binary']=='p33-linked-fixtures':receipts[directory+'/output.bin']=sha(out/directory/'output.bin')
        return receipts
    except Exception as error:
        errors=[]
        pp.failure_attempt('fixture fault latch',lambda:watch.latch(error),errors)
        pp.failure_attempt('fixture failure receipt',lambda:save(out/'failure-before-teardown.json',dict(error=str(error),pids=[child.pid for child in children])),errors)
        try:os.write(stop_w,b'!')
        except OSError:
            os.close(stop_w);stop_w=-1
        end=time.monotonic()+65
        while any(child.poll() is None for child in children) and time.monotonic()<end:
            try:watch.check()
            except Exception:pass # retain original failure; new fault is already latched by Watch
            time.sleep(.1)
        pp.failure_attempt('fixture retained receipt',lambda:save(out/'retained.json',dict(pids=[child.pid for child in children if child.poll() is None],signals_sent=0,stop_requested=True,diagnostic_errors=errors)),errors)
        raise
    finally:
        # K0 cannot interrupt an in-progress JIT; report and retain it, never signal.
        for log in logs:log.close()
        if stop_w>=0:os.close(stop_w)
        os.close(stop_r)

def concurrency_canary(args,out,env,watch):
    admit(projected_write_bytes('W0p'))
    args.canary=True;args.mini=True;args.output=out/'run';args.output.mkdir()
    t=Transport.__new__(Transport);result=dict(passed=False,device_executed=args.device)
    try:
        t.__init__(args,args.output,env,watch.check,watch.mark_launched);t.failure_hook=watch.latch;overlaps=0;pids=[p.pid for p in t.children]
        for i in range(1000):
            for rank in (0,1):
                t.mapping[rank*SLOT:rank*SLOT+256]=pp.struct.pack('<64I',*([i]*64))
                t.start(rank,CANARY,position=i)
            require(all(p.poll() is None for p in t.children),'canary ranks not simultaneously alive')
            t.wait(0);t.wait(1)
            for rank in (0,1):require(t.mapping[rank*SLOT:rank*SLOT+256]==pp.struct.pack('<64I',*([i+1]*64)),'shared handover bytes')
            left,right=t.trace[-2:]
            overlaps+=max(left['rank_received'],right['rank_received'])<min(left['rank_completed'],right['rank_completed'])
        require(overlaps>0,'no observed overlap of outstanding work')
        t.close(True);result.update(passed=True,handovers=1000,kernels_per_rank=1000,pids=pids,both_alive_checks=1000,overlapping_host_work_intervals=overlaps,
            overlap_definition='rank command receive through local drain; device clocks not compared',metrics=t.metrics)
    except Exception as error:
        errors=[]
        pp.failure_attempt('canary failure receipt',lambda:save(args.output/'receipt.json',dict(result,error=str(error))),errors)
        pp.failure_attempt('canary fault latch',lambda:watch.latch(error),errors)
        if hasattr(t,'stop_write'):
            try:t.stop(error)
            finally:pp.failure_attempt('canary bounded drain',lambda:t.close(False),errors)
        raise
    save(args.output/'receipt.json',result);return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--authorized-device-window',action='store_true',required=True)
    p.add_argument('--window',choices=CONFIG,required=True);p.add_argument('--card',type=int,required=True);p.add_argument('--prompt-overlap',choices=('on','off'),default='on');p.add_argument('--seconds',type=int);p.add_argument('--controller',choices=('python','native'),default='python');p.add_argument('--suite-manifest',type=Path);p.add_argument('--repeat',type=int,default=2)
    for name in ('output','input','oracle','dispatch','k0','k1a','k1b','k2','w0p','kd'):p.add_argument('--'+name,type=Path,required=name=='output')
    a=p.parse_args();require(0<=a.card<=2,'--card is first of adjacent pair')
    environment=environment_gate();require(os.environ.get('OMP_NUM_THREADS')=='2','OMP_NUM_THREADS=2')
    nice=0 if a.window.startswith('W') else 19;require(os.getpriority(os.PRIO_PROCESS,0)==nice,'W windows need a nice-0 parent; K windows nice19')
    seconds=watchdog(a.window,a.seconds);out=a.output.resolve();require(B.resolve() in out.parents and not out.exists(),'new output beneath packet38/build required')
    build=json.loads((P/'build-receipt.json').read_text());require(build.get('passed') is True,'CPU/build gates incomplete')
    for name,digest in build['sources'].items():require(sha(ROOT/name)==digest,'source changed '+name)
    require(sha(P/'mtp-manifest.tsv')==build['official_manifest_sha256'],'official draft manifest changed')
    require(json.loads((P/'memory-plan.json').read_text())==build['memory_plan'],'memory plan changed')
    artifacts=build['artifacts_sha256']
    require('device/p33-linked-fixtures' in artifacts and isinstance(build.get('p33_linked_fixture_host_sha256'),str),'linked p33 fixture binary/host gate missing from seal')
    for name,digest in artifacts.items():require(sha(B/name)==digest,'binary changed '+name)
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if (B/'FAULT.json').exists():require(json.loads((B/'FAULT.json').read_text()).get('boot_id')!=boot,'boot fault latch requires coordinator recovery')
    identity=dict(schema='packet38.window.v1',window=a.window,card=a.card,boot_id=boot,artifacts_sha256=artifacts,environment=environment,build_receipt_sha256=sha(P/'build-receipt.json'))
    record=dict(identity,prompt_overlap=a.prompt_overlap,passed=False,device_executed=False,expected_seconds=CONFIG[a.window][0]+17,expectation_enforced=True,expectation_policy='prelaunch expected+17s <= watchdog/4; no early runtime stop',watchdog_seconds=seconds,cpu_affinity=sorted(os.sched_getaffinity(0)),load_average=list(os.getloadavg()))
    if a.window!='K0':prerequisites(a.k0,'K0',identity)
    if a.window=='K1b':prerequisites(a.k1a,'K1a',identity)
    if a.window in ('K2','KD','W2s','W2n','W2x','W2d','W2c','W2m','W2mc','WS','WSs'):
        ka=prerequisites(a.k1a,'K1a',identity);kb=prerequisites(a.k1b,'K1b',identity)
        require(ka.get('candidate_dispatch_sha256')==kb.get('candidate_dispatch_sha256'),'K1 dispatch mismatch')
        fresh_k1_owners(ka,kb)
        if a.window=='K2':require(ka.get('candidate_dispatch_sha256')==(sha(a.dispatch) if a.dispatch else None),'K2 candidate differs from K1')
    if a.window in ('W2m','W2mc','WS'):
        kd=prerequisites(a.kd,'KD',identity)
        require(a.dispatch and kd.get('dispatch_sha256')==sha(a.dispatch),'KD draft head dispatch changed')
    if a.window=='KD':
        measured=prerequisites(a.k2,'K2',identity)
        require(a.dispatch and sha(a.dispatch)==measured.get('dispatch_sha256'),'KD measured dispatch required')
        record['dispatch_sha256']=sha(a.dispatch)
        require(a.input is not None,'KD target input required')
        require(sha(a.input/'input.json')==build['input_sha256'],'KD target input changed')
        inp=json.loads((a.input/'input.json').read_text())
        for name,digest in inp['files'].items():require(sha(a.input/name)==digest,'KD input artifact changed')
        sample=memory_snapshot();require(sample['MemAvailable']>=16*1024**3,'KD needs16GiB host memory available')
        record['memory_admission']=dict(sample,required_MemAvailable=16*1024**3)
    if a.window.startswith('W2'):
        prerequisites(a.w0p,'W0p',identity);measured=prerequisites(a.k2,'K2',identity)
        require(a.dispatch and sha(a.dispatch)==measured.get('dispatch_sha256'),'measured dispatch required')
        require(a.input and a.oracle,'input and oracle required')
        inp=json.loads((a.input/'input.json').read_text());require(sha(a.input/'input.json')==build['input_sha256'],'input identity changed')
        hashes,expected=oracle_gate(a.oracle,inp['tokens'],8,64)
        for name,digest in inp['files'].items():require(sha(a.input/name)==digest,'input artifact changed')
        record.update(oracle_hashes=hashes,expected_tokens=expected,dispatch_sha256=sha(a.dispatch))
        # Conservative pre-admission until measured per-rank shadow receipts exist.
        sample=memory_snapshot();require(sample['MemAvailable']>=97*1024**3,'model window needs 97 GiB available before ranks load')
        record['memory_admission']=dict(sample,required_MemAvailable=97*1024**3,shadow_removal='unmeasured; no assumption')
    if a.window in ('WS','WSs'):
        require(a.suite_manifest is not None,'suite manifest required')
        prerequisites(a.w0p,'W0p',identity);measured=prerequisites(a.k2,'K2',identity)
        require(a.dispatch and sha(a.dispatch)==measured.get('dispatch_sha256'),'suite measured dispatch required')
        manifest=json.loads(a.suite_manifest.read_text())
        require(manifest.get('arithmetic')=='iq3-p17-detmath-v2' and manifest.get('token_cap')==64,'suite identity')
        sample=memory_snapshot();require(sample['MemAvailable']>=97*1024**3,'suite needs97GiB available before ranks load')
        record['memory_admission']=dict(sample,required_MemAvailable=97*1024**3)
        record.update(suite_manifest_sha256=sha(a.suite_manifest),controller=a.controller,repeat=a.repeat,dispatch_sha256=sha(a.dispatch))
    if a.dispatch:validate(json.loads(a.dispatch.read_text()))
    request_count=(1+len(manifest.get('requests',manifest.get('prompts',[])))*a.repeat) if a.window in ('WS','WSs') else 1
    record['storage_admission']=admit(projected_write_bytes(a.window,request_count))
    record['foreign_engine_admission']=foreign_engines();out.mkdir(parents=True);save(out/'window.json',record)
    watch=Watch(out,boot,seconds);old={s:signal.signal(s,lambda n,f:watch.cancelled.append(n)) for s in (signal.SIGTERM,signal.SIGINT)}
    try:
        save(out/'window.json',record)
        if a.window=='KD':
            from draft_window import run as run_draft
            record['receipts'],record['pids']=run_draft(a,out,environment['native'],watch,build)
        elif a.window.startswith('K'):
            record['receipts']=run_fixtures(a,out,environment['native'],watch)
            record['pids']=json.loads((out/'children.json').read_text())['pids']
            if a.window=='K0':
                for rank in (0,1):
                    r=json.loads((out/f'run{rank}/receipt.json').read_text());require(r['cards']==1 and r['kernel_execution'] is False and r['explicit_allocations']==0 and r['kernels_per_device']>0,'K0 coverage')
            elif a.window in ('K1a','K1b'):
                fixture_receipt_gate(out/'run0',build);record['linked_p33']=linked_fixture_gate(out/'linked',build,a.card)
                record['candidate_dispatch_sha256']=sha(a.dispatch) if a.dispatch else None
                if a.window=='K1b':fresh_k1_owners(json.loads(a.k1a.read_text()),record)
            else:
                summary=summarize(out/'run0',identity);require(summary['passed'],'K2 exact/timing gate')
                record.update(dispatch_sha256=sha(out/'run0/dispatch-measured.json'),summary_sha256=sha(out/'run0/summary.json'))
                for name in ('dispatch-measured.json','events.jsonl','summary.json'):record['receipts']['run0/'+name]=sha(out/'run0'/name)
                # One-card class measurements determine the common vocabulary for both ranks.
                # These are identical aliases, never a claim that rank1 was timed here.
                record['rank_dispatches']={}
                for rank in (0,1):
                    name=f'dispatch-rank{rank}.json';path=out/'run0'/name
                    path.write_bytes((out/'run0/dispatch-measured.json').read_bytes())
                    record['receipts']['run0/'+name]=sha(path)
                    record['rank_dispatches'][str(rank)]=dict(path='run0/'+name,sha256=sha(path),measurement_card=a.card,rank_card=a.card+rank,scope='one-card measured dispatch applied to both ranks')
        else:
            args=pp.parser().parse_args(['--output',str(out/'run')]);args.binary=B/'device/own-rt-iq3';args.device=True;args.native_nice=0
            args.controller=a.controller;args.prompt_overlap=a.prompt_overlap;args.card=a.card;args.seconds=seconds;args.wait_seconds=600;args.context=256;args.tokens=64;args.input=a.input;args.oracle=a.oracle;args.dispatch=a.dispatch;args.timing='class' if a.window in ('W2c','W2mc') else 'token'
            record['ldd_preflight']=ldd_preflight(args.binary)
            if a.window=='W0p':concurrency_canary(args,out,environment['native'],watch)
            elif a.window in ('WS','WSs'):
                args.suite_manifest=a.suite_manifest;args.repeat=a.repeat;args.draft='mtp' if a.window=='WS' else 'none'
                args.controller=a.controller
                r=pp.run(args,environment['native'],watch.check,watch.latch,watch.mark_launched)
                record.update(summary=r,decode_tok_s=r['decode_median_tok_s'])
                require(r['passed'],'one or more suite requests failed exactness')
            else:
                args.draft={'W2s':'none','W2n':'ngram','W2d':'script','W2x':'script','W2c':'ngram','W2m':'mtp','W2mc':'mtp'}[a.window]
                if a.window in ('W2d','W2x'):
                    args.script=out/'DIAGNOSTIC-oracle-guesses.txt';args.script.write_text(' '.join(map(str,expected[:63] if a.window=='W2d' else [(token+1)%248320 for token in expected[:63]])))
                r=pp.run(args,environment['native'],watch.check,watch.latch,watch.mark_launched);require(r['tokens']==expected,'64-token oracle mismatch')
                if a.window in ('W2d','W2x'):
                    require(r['stats']['guesses']==len(r['tokens'])-1 and r['stats']['hits']==(len(r['tokens'])-1 if a.window=='W2d' else 0),'diagnostic all-hit/all-miss pattern mismatch')
                observed={}
                for rank in (0,1):
                    for f in (out/f'run/rank{rank}').glob('step*/layer-*.bf16'):observed[str(f.relative_to(out/f'run/rank{rank}'))]=sha(f)
                require(observed==hashes,'384 retained fixtures differ/missing');record.update(token_matches=64,layer_matches=384,diagnostic=r['diagnostic'],decode_tok_s=r['decode_tok_s'])
            record['receipts']={str(f.relative_to(out)):sha(f) for f in (out/'run').rglob('receipt.json')}
        watch.postflight();record['passed']=True
    except Exception as error:
        record.update(error=str(error),passed=False)
        pp.failure_attempt('window fault latch',lambda:watch.latch(error),record.setdefault('diagnostic_errors',[]))
    finally:
        for s,handler in old.items():signal.signal(s,handler)
    record['device_executed']=bool(watch.launched);record['launched_pids']=watch.launched
    # Only completed owners may have their logs compacted. Preserve any retained owner.
    alive=[pid for pid in watch.launched if Path(f'/proc/{pid}').exists()]
    if not alive:
        try:compress_evidence(out,record)
        except Exception as error:record.update(passed=False,retention_error=str(error))
    save(out/'window.json',record);return 0 if record['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
