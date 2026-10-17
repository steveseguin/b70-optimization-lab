#!/usr/bin/env python3
"""Coordinator-only device windows. Preparation never executes this entry."""
import argparse,gzip,hashlib,json,math,os,re,signal,subprocess,time
from pathlib import Path
import pipeline as pp
from pipeline import P,save,sha,require,Transport,CANARY,SLOT
from window_safety import environment_gate,memory_snapshot
from fixture_support import journal,ldd_preflight,oracle_gate,fixture_receipt_gate,k1_gate,sequential_teardown
from k2_summary import summarize, estimated_seconds
from merge_dispatch import validate
from storage import admit, projected_write_bytes
from diagnostic_mode import actual_artifacts, label_outputs, MARKERS
from suite_metrics import admit_cap
B=P/'build';ROOT=P.parents[3]
CONFIG={'K0':(30,600),'K1a':(120,10800),'K1b':(120,10800),'K2':(1800,14400),'W0p':(30,600),
        'W2s':(1900,10800),'W2n':(1900,10800),'W2x':(1900,10800),'W2d':(1900,10800),'W2c':(1900,10800),'KD':(1800,10800),'W2m':(2100,10800),'W2mc':(2100,10800),'WS':(7200,30000),'WSs':(7200,30000),'W2m-speed':(2100,10800),'W2m-exact':(2100,10800),'WS64':(7200,30000),'WS64x':(7200,30000),'WS128':(14400,60000),'WS128x':(14400,60000)}
FAULT= re.compile(r'Fault response|CAT error|engine.*reset|reset.*engine|devcoredump|device coredump|GPU.*coredump|GuC.*(?:hang|lockup)|timed.out.*(?:job|fence)|job.*timed.out', re.I)
SUITE_WINDOWS={'WS','WSs','WS64','WS64x','WS128','WS128x'}
MTP_WINDOWS={'W2m','W2mc','W2m-speed','W2m-exact','WS','WS64','WS64x','WS128','WS128x'}
SPEED_WINDOWS={'W2m-speed':'W2m-exact','WS64':'WS64x','WS128':'WS128x','WSs':'WSs'}

def watchdog(name,seconds=None,context=256):
    expected,default=CONFIG[name];expected=estimated_seconds(context) if name=='K2' else expected;seconds=default if seconds is None else seconds
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
        self.out=out;self.boot=boot;self.end=time.monotonic()+seconds;self.last=0.;self.cancelled=[];self.launched=[];self.cpu_children=[];self.new_gpu_fault=False
        text,self.cursor=journal();(out/'kernel-preflight.txt').write_text(text)
    def mark_launched(self,pid):
        self.launched.append(int(pid))
    def mark_cpu_child(self,child):
        # Keep the actual process handle: poll distinguishes exit from PID reuse.
        # CPU ownership never counts as device contact for the fault latch.
        self.cpu_children.append(child)
    def latch(self,reason):
        # Admission/loader/argument refusals before any child exists cannot poison a boot.
        owner_failure = False
        if getattr(reason, 'device_owner_failed', False) and not self.cancelled:
            directory = Path(reason.owner_output)
            try:
                contact = json.loads((directory/'device-contact.json').read_text()).get('device_contact') is True
            except (OSError, ValueError):
                contact = False
            native_error = ''
            try:
                native_error = str(json.loads((directory/'receipt.json').read_text()).get('error', ''))
            except (OSError, ValueError):
                pass
            storage_or_stop = re.search(r'no space|ENOSPC|disk full|write |storage|coordinator stop|stop requested|cancel', str(reason)+' '+native_error, re.I)
            owner_failure = contact and not storage_or_stop
        if not self.launched or not (self.new_gpu_fault or owner_failure):return
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

def live_owner_pids(watch):
    device=[pid for pid in watch.launched if Path(f'/proc/{pid}').exists()]
    cpu=[child.pid for child in watch.cpu_children if child.poll() is None]
    return sorted(set(device+cpu))

def output_path(path,*,cpu_rehearsal=False):
    out=Path(path).resolve();boundary=B.resolve()
    require(boundary in out.parents and not out.exists(),'new output beneath packet40 required')
    return out

def admit_output(root,extra):
    destination=Path(root).resolve()
    return admit(extra,build_extra=extra if destination==B.resolve() or B.resolve() in destination.parents else 0)

def evidence_path(root,name):
    rel=Path(name)
    require(not rel.is_absolute() and '..' not in rel.parts,'unsafe retained evidence path')
    path=(root/rel).resolve()
    require(root.resolve() in path.parents,'retained evidence escapes window')
    return path

def fixture_disposition(root,name,item,record):
    require(Path(name).name=='output.bin' and item.get('uncompressed_bytes',0)>20_000_000,'hash-only retention is oversized fixture only')
    receipt=evidence_path(root,item['native_receipt_path']);children=evidence_path(root,item['children_path'])
    require(sha(receipt)==item['native_receipt_sha256'] and sha(children)==item['children_sha256'],'fixture provenance changed')
    native=json.loads(receipt.read_text());launches=json.loads(children.read_text())['entries'];entry=item['launch_entry']
    require(native.get('passed') is True and native.get('schema') in ('packet26.fixtures.v1','packet37.p33-linked-fixtures.v1'),'fixture native receipt not qualified')
    require(entry in launches and entry['directory']==str(Path(name).parent),'fixture launch provenance differs')
    require(entry['binary_sha256'] in record.get('artifacts_sha256',{}).values(),'fixture binary outside sealed artifacts')
    require(native.get('output_sha256')==item['uncompressed_sha256'],'fixture native digest differs')
    argv=entry['argv']
    if '--dispatch' in argv:
        dispatch=Path(argv[argv.index('--dispatch')+1]).resolve();bound=item.get('restoration_dispatch',{})
        require(P.resolve() in dispatch.parents or B.resolve() in dispatch.parents,'fixture restoration dispatch outside packet')
        require(bound.get('path')==str(dispatch) and bound.get('sha256')==sha(dispatch),'fixture restoration dispatch changed')
    require(receipt.parent==evidence_path(root,name).parent,'fixture receipt directory differs')
    return native['output_sha256']

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
            children=root/'children.json';launches=json.loads(children.read_text())['entries']
            relative=str(source.relative_to(root));entries=[entry for entry in launches if entry['directory']==str(Path(relative).parent)]
            require(len(entries)==1,'oversized fixture needs exactly one authenticated launcher')
            item=dict(disposition='sha256-only',uncompressed_sha256=digest,uncompressed_bytes=size,
                native_receipt_path=str((source.parent/'receipt.json').relative_to(root)),native_receipt_sha256=sha(source.parent/'receipt.json'),
                children_path='children.json',children_sha256=sha(children),launch_entry=entries[0],
                restoration='Rerun the sealed fixture binary with children.json argv, a fresh output and newly allocated stop descriptor; same binary, dispatch and inputs. Device execution requires coordinator authorization.')
            argv=entries[0]['argv']
            if '--dispatch' in argv:
                dispatch=Path(argv[argv.index('--dispatch')+1]).resolve()
                require(P.resolve() in dispatch.parents or B.resolve() in dispatch.parents,'fixture restoration dispatch outside packet')
                item['restoration_dispatch']=dict(path=str(dispatch),sha256=sha(dispatch))
            fixture_disposition(root,relative,item,record)
            retained[relative]=item;save(root/'retention.json',retained);source.unlink();continue
        # Logs retain their exact bytes; gzip worst-case coexistence is admitted.
        admit_output(root,size+size//1000+2_000_000)
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
    path=evidence_path(root,name)
    if path.is_file():return stream_hash(path)
    item=record.get('retained_artifacts',{}).get(name)
    require(isinstance(item,dict),'prerequisite artifact missing: '+name)
    if item.get('disposition')=='sha256-only':return fixture_disposition(root,name,item,record)
    target=evidence_path(root,item['path'])
    require(root.resolve() in target.parents and stream_hash(target)==item['sha256'],'compressed prerequisite changed')
    digest=stream_hash(target,True)
    require(digest==item['uncompressed_sha256'],'compressed prerequisite bytes changed')
    return digest

def prerequisites(path,name,identity,*,cpu_rehearsal=False):
    require(path is not None,'missing prerequisite '+name)
    row=json.loads(path.read_text());require(row.get('device_executed') is True or (cpu_rehearsal and row.get('cpu_rehearsal') is True),'CPU rehearsal cannot authorize device work');require(row.get('passed') is True and row.get('window')==name,'failed prerequisite '+name)
    diagnostic=bool(identity.get('diagnostic_unsealed'))
    require(bool(row.get('diagnostic_unsealed'))==diagnostic,'diagnostic prerequisite mode differs')
    require(row.get('qualifying') is False if diagnostic else row.get('qualifying') is not False,'prerequisite qualification mode differs')
    fields=('boot_id','artifacts_sha256','environment','card','context','draft_rank','target_split')
    if not diagnostic:fields+=('build_receipt_sha256',)
    for field in fields:
        require(row.get(field)==identity.get(field),'prerequisite identity changed: '+name+' '+field)
    if name in ('K1a','K1b'):
        qsa=row.get('qsa_split32',{})
        require(qsa.get('checks')==88 and qsa.get('binary_sha256')==identity['artifacts_sha256'].get(('gnu-host' if cpu_rehearsal else 'device')+'/p49-qsa-fixtures') and qsa.get('card')==identity.get('card'),'K1 split32 bridge evidence missing')
        require({'qsa/receipt.json','qsa/output.bin'}<=set(row.get('receipts',{})),'K1 split32 evidence missing')
        linked=row.get('linked_p33',{})
        require(linked.get('checks')==216 and linked.get('split_instantiations')==36 and linked.get('binary_sha256')==identity['artifacts_sha256'].get(('gnu-host' if cpu_rehearsal else 'device')+'/p33-linked-fixtures') and linked.get('card')==identity.get('card'),'K1 linked fixture prerequisite coverage/identity changed')
        require({'linked/receipt.json','linked/output.bin'}<=set(row.get('receipts',{})),'K1 linked fixture evidence missing')
    for filename,digest in row.get('receipts',{}).items():require(retained_hash(path.parent,filename,row)==digest,'prerequisite receipt changed')
    return row

def qsa_fixture_gate(root,build,card,*,cpu_rehearsal=False):
    row=json.loads((root/'receipt.json').read_text())
    require(row.get('schema')=='packet49.qsa-fixtures.v1' and row.get('passed') is True and row.get('reference_exact') is True and row.get('checks')==88,'split32 fixture coverage')
    require(row.get('device_executed') is (not cpu_rehearsal) and row.get('card')==card,'split32 fixture execution/card')
    t=row.get('teardown',{});require(t.get('safe_to_exit') is True and t.get('exit_code')==0 and t.get('live_bytes')==t.get('in_flight')==0,'split32 fixture unsafe teardown')
    digest=sha(root/'output.bin');require(digest==row.get('output_sha256')==build.get('p49_qsa_fixture_host_sha256'),'split32 fixture bytes differ')
    return dict(checks=88,output_sha256=digest,binary_sha256=build['artifacts_sha256'][('gnu-host' if cpu_rehearsal else 'device')+'/p49-qsa-fixtures'],card=card)

def linked_fixture_gate(root,build,card,*,cpu_rehearsal=False):
    row=json.loads((root/'receipt.json').read_text())
    require(row.get('schema')=='packet37.p33-linked-fixtures.v1' and row.get('passed') is True and row.get('device_executed') is (not cpu_rehearsal) and row.get('reference_exact') is True,'linked p33 device/exactness receipt failed')
    for key,value in (('checks',216),('type_k_families',18),('split_instantiations',36),('modes_per_instantiation',6),('output_rows',1512),('argument_limit_bytes',1024),('owner_cards',1)):
        require(type(row.get(key)) is int and row[key]==value,'linked p33 coverage incomplete: '+key)
    require(type(row.get('card')) is int and row['card']==card,'linked p33 fixture card differs from admitted first card')
    teardown=row.get('teardown',{})
    require(isinstance(teardown,dict) and teardown.get('safe_to_exit') is True and type(teardown.get('exit_code')) is int and teardown['exit_code']==0 and type(teardown.get('live_bytes')) is int and teardown['live_bytes']==0 and type(teardown.get('in_flight')) is int and teardown['in_flight']==0,'linked p33 owner teardown incomplete')
    digest=sha(root/'output.bin')
    require(digest==row.get('output_sha256')==build.get('p33_linked_fixture_host_sha256'),'linked p33 bytes differ from sealed host fixture')
    return dict(checks=row['checks'],split_instantiations=row['split_instantiations'],output_sha256=digest,binary_sha256=build['artifacts_sha256'][('gnu-host' if cpu_rehearsal else 'device')+'/p33-linked-fixtures'],card=card)

def fresh_k1_owners(first,second):
    left,right=first.get('pids'),second.get('pids')
    require(isinstance(left,list) and isinstance(right,list) and len(left)==len(right)==3,'K1 requires three fixture processes')
    require(all(type(pid) is int and pid>0 for pid in left+right) and len(set(left+right))==6,'K1 requires distinct fresh fixture owner processes')

def run_fixtures(a,out,env,watch):
    # K0 remains two simultaneous single-device JIT owners. K1 runs its two
    # fixture programs sequentially on the first card; no same-card overlap.
    if a.window=='K0':jobs=[('jit-smoke',a.card,'run0'),('jit-smoke',a.card+1,'run1')]
    elif a.window in ('K1a','K1b'):jobs=[('nongemv-fixtures',a.card,'run0'),('p33-linked-fixtures',a.card,'linked'),('p49-qsa-fixtures',a.card,'qsa')]
    else:jobs=[('k2-fixtures',a.card,'run0')]
    cpu_rehearsal=getattr(a,'cpu_rehearsal',False)
    if cpu_rehearsal and a.window=='K0':
        # No host equivalent to a SYCL JIT bundle build: structural receipt only.
        for rank in (0,1):
            dest=out/f'run{rank}';dest.mkdir();save(dest/'receipt.json',dict(passed=True,cpu_rehearsal=True,device_executed=False,cards=1,kernel_execution=False,explicit_allocations=0,kernels_per_device=1,scope='STRUCTURAL SHIM ONLY: no JIT executed'))
        save(out/'children.json',dict(pids=[],entries=[],signals_sent=0))
        return {f'run{rank}/receipt.json':sha(out/f'run{rank}/receipt.json') for rank in (0,1)}
    binary_group='gnu-host' if cpu_rehearsal else 'device'
    admit_output(out,projected_write_bytes(a.window,context=a.context))
    receipts={};children=[];entries=[];logs=[];stop_r,stop_w=os.pipe()
    def check_child_failures():
        for entry, child in zip(entries, children):
            if child.poll() not in (None, 0):
                raise pp.DeviceOwnerFailure('fixture rank failed with exit '+str(child.returncode), out/entry['directory'])
    def wait_for_children():
        while any(child.poll() is None for child in children):
            watch.check();check_child_failures();time.sleep(.1)
        check_child_failures()
        require(all(child.poll()==0 for child in children),'fixture exit failure')
    try:
        # All loader refusals precede the first device owner, including the
        # second sequential K1 program and the second K0 card process.
        for name,_,_ in jobs:watch.check();ldd_preflight(B/binary_group/name)
        for index,(name,card,directory) in enumerate(jobs):
            watch.check();admit_output(out,projected_write_bytes('K2',context=a.context) if a.window=='K2' else 550_000_000 if a.window!='K0' else 16_000_000);binary=B/binary_group/name
            dest=out/directory;log=(out/f'fixture{index}.log').open('w');logs.append(log)
            cmd=[str(binary),*([] if cpu_rehearsal else ['--authorized-device-window']),'--card',str(card),'--output',str(dest)]
            if name in ('nongemv-fixtures','k2-fixtures'):cmd+=['--context',str(a.context)]
            if cpu_rehearsal and name in ('nongemv-fixtures','k2-fixtures'):cmd+=['--validate-only','--fixtures',str(B/'fusion-fixtures')]
            if a.window=='K0':cmd+=['--cards','1']
            else:cmd+=['--stop-fd',str(stop_r)]
            if name in ('p33-linked-fixtures','p49-qsa-fixtures'):cmd+=['--seconds',str(watchdog(a.window,a.seconds,a.context))]
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
            if entry['binary'] in ('p33-linked-fixtures','p49-qsa-fixtures'):receipts[directory+'/output.bin']=sha(out/directory/'output.bin')
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
    admit_output(out,projected_write_bytes('W0p'))
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

def selected_oracle(a,inp,retained_steps):
    require(len(inp['tokens'])+a.max_new<=a.context,'prompt plus --max-new exceeds context capacity')
    _,expected=oracle_gate(a.oracle,inp['tokens'],0,a.max_new)
    hashes={f'step{step}/layer-{layer:02}.bf16':sha(a.oracle/f'step{step}/layer-{layer:02}.bf16') for step in retained_steps for layer in range(48)}
    return hashes,expected

def admit_oracle(a,*,cpu_rehearsal=False):
    if cpu_rehearsal or not (a.window=='KD' or a.window.startswith('W2') or a.window in SUITE_WINDOWS):return
    from oracle.oracle_job import status as oracle_status
    require(oracle_status(True)==0,'packet49 complete full-model oracle required before this window')
    if a.window.startswith('W2'):
        require(a.oracle is not None and a.oracle.resolve()==(P/'oracle/results/incident-retrospective').resolve(),'packet49 incident oracle authority required')
    if a.window in SUITE_WINDOWS:
        require(a.suite_manifest is not None and a.suite_manifest.resolve()==(P/'oracle/results/suite-manifest.json').resolve(),'packet49 completed suite authority required')

def main(*,cpu_rehearsal=False):
    # Internal test seam only: no CLI switch can authorize or select this path.
    from functools import partial
    prerequisite=partial(prerequisites,cpu_rehearsal=cpu_rehearsal)
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--authorized-device-window',action='store_true',required=True);p.add_argument('--diagnostic-unsealed',action='store_true')
    p.add_argument('--target-split',type=int,choices=(0,23,24),default=0);p.add_argument('--context',type=int,choices=(256,4096,32768),required=True);p.add_argument('--draft-rank',type=int,choices=(0,1),default=0);p.add_argument('--window',choices=CONFIG,required=True);p.add_argument('--card',type=int,required=True);p.add_argument('--prompt-overlap',choices=('on','off'),default='on');p.add_argument('--seconds',type=int);p.add_argument('--controller',choices=('python','native'),default='native');p.add_argument('--suite-manifest',type=Path);p.add_argument('--repeat',type=int,default=1)
    p.add_argument('--max-new',type=int);p.add_argument('--retain-steps');p.add_argument('--exactness-window',type=Path)
    for name in ('output','input','oracle','dispatch','k0','k1a','k1b','k2','w0p','kd'):p.add_argument('--'+name,type=Path,required=name=='output')
    a=p.parse_args();a.cpu_rehearsal=cpu_rehearsal
    require(not a.diagnostic_unsealed,'packet49 requires its scoped CPU/build seal');require(a.card==0 and a.context==4096 and a.draft_rank==1 and a.target_split==23,'packet49 sealed scope is cards01 context4096 dr1 split23')
    admit_oracle(a,cpu_rehearsal=cpu_rehearsal)
    from memory_gate import configuration
    configuration(json.loads((P/'memory-plan.json').read_text()),a.context,a.draft_rank,a.target_split)
    if a.window in SUITE_WINDOWS:
        require(a.suite_manifest is not None,'suite manifest required')
        from suite import validate_manifest
        manifest=json.loads(a.suite_manifest.read_text());suite_cap=validate_manifest(manifest,a.context,mini=cpu_rehearsal)
        require(a.max_new is None or a.max_new==suite_cap,'suite window token cap comes from manifest')
        a.max_new=suite_cap
    else:a.max_new=a.max_new if a.max_new is not None else 64
    require(1<=a.max_new<=a.context,'--max-new must fit context capacity')
    require(a.repeat>=1,'--repeat must be positive')
    if a.retain_steps is None:a.retain_steps='none' if a.window in SPEED_WINDOWS else '1-8,97-104' if a.window=='WS128x' else '1-8'
    a.retain_steps=pp.canonical_retention(a.retain_steps,a.max_new)
    retained_steps=pp.retention_steps(a.retain_steps,a.max_new)
    if a.window in SPEED_WINDOWS and a.window!='WSs':require(not retained_steps,'speed windows require --retain-steps none')
    if a.window in ('W2m-exact','WS64x'):require(set(pp.retention_steps('1-8',a.max_new))<=set(retained_steps),'exactness needs available steps1-8')
    if a.window=='WS128x':require(set(pp.retention_steps('1-8,97-104',a.max_new))<=set(retained_steps),'exactness needs available steps1-8,97-104')
    environment=environment_gate();require(environment['native']['OMP_NUM_THREADS']=='2','OMP_NUM_THREADS=2')
    nice=0 if a.window.startswith('W') and not cpu_rehearsal else 19;require(os.getpriority(os.PRIO_PROCESS,0)==nice,'W windows need a nice-0 parent; K windows nice19')
    scale=a.repeat if a.window in SUITE_WINDOWS else 1
    expected=(estimated_seconds(a.context) if a.window=='K2' else CONFIG[a.window][0])*scale+17
    seconds=watchdog(a.window,a.seconds or CONFIG[a.window][1]*scale,a.context)
    require(seconds>=max(300,math.ceil(4*expected)),'repeat watchdog below four times estimate')
    out=output_path(a.output,cpu_rehearsal=cpu_rehearsal)
    from p49_seal import verify as verify_packet49
    build=verify_packet49()
    if a.diagnostic_unsealed:
        # Skip only sealed provenance. All runtime and oracle admissions below run.
        artifacts=actual_artifacts(build,B,sha)
        build=dict(build,artifacts_sha256=artifacts)
    else:
        require(build.get('passed') is True,'CPU/build gates incomplete')
        for name,digest in build['sources'].items():require(sha(ROOT/name)==digest,'source changed '+name)
        require(sha(P/'mtp-manifest.tsv')==build['official_manifest_sha256'],'official draft manifest changed')
        require(json.loads((P/'memory-plan.json').read_text())==build['memory_plan'],'memory plan changed')
        artifacts=build['artifacts_sha256']
        for name,digest in artifacts.items():require(sha(B/name)==digest,'binary changed '+name)
    require((('gnu-host' if cpu_rehearsal else 'device')+'/p33-linked-fixtures') in artifacts and isinstance(build.get('p33_linked_fixture_host_sha256'),str),'linked p33 fixture binary/host gate missing from seal')
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if (B/'FAULT.json').exists():require(json.loads((B/'FAULT.json').read_text()).get('boot_id')!=boot,'boot fault latch requires coordinator recovery')
    identity=dict(diagnostic_unsealed=a.diagnostic_unsealed,qualifying=not a.diagnostic_unsealed,schema='packet49.window.v1',window=a.window,card=a.card,context=a.context,draft_rank=a.draft_rank,target_split=a.target_split,boot_id=boot,artifacts_sha256=artifacts,environment=environment,build_receipt_sha256=sha(P/'build-receipt.json'))
    record=dict(identity,cpu_rehearsal=cpu_rehearsal,prompt_overlap=a.prompt_overlap,controller=a.controller,max_new=a.max_new,retain_steps=a.retain_steps,retained_steps=retained_steps,diagnostic_for_speed=bool(retained_steps) or a.window=='W2mc',passed=False,device_executed=False,expected_seconds=expected,expectation_enforced=True,expectation_policy='prelaunch expected+17s <= watchdog/4; no early runtime stop',watchdog_seconds=seconds,cpu_affinity=sorted(os.sched_getaffinity(0)),load_average=list(os.getloadavg()))
    if a.window!='K0':prerequisite(a.k0,'K0',identity)
    if a.window=='K1b':prerequisite(a.k1a,'K1a',identity)
    if a.window in ({'K2','KD'}|{w for w in CONFIG if w.startswith('W2')}|SUITE_WINDOWS):
        ka=prerequisite(a.k1a,'K1a',identity);kb=prerequisite(a.k1b,'K1b',identity)
        require(ka.get('candidate_dispatch_sha256')==kb.get('candidate_dispatch_sha256'),'K1 dispatch mismatch')
        fresh_k1_owners(ka,kb)
        if a.window=='K2':require(ka.get('candidate_dispatch_sha256')==(sha(a.dispatch) if a.dispatch else None),'K2 candidate differs from K1')
    if a.window in MTP_WINDOWS:
        kd=prerequisite(a.kd,'KD',identity)
        require(a.dispatch and kd.get('dispatch_sha256')==sha(a.dispatch),'KD draft head dispatch changed')
    if a.window=='KD':
        measured=prerequisite(a.k2,'K2',identity)
        require(a.dispatch and sha(a.dispatch)==measured.get('dispatch_sha256'),'KD measured dispatch required')
        record['dispatch_sha256']=sha(a.dispatch)
        require(a.input is not None,'KD target input required')
        require(sha(a.input/'input.json')==build['input_sha256'],'KD target input changed')
        inp=json.loads((a.input/'input.json').read_text())
        for name,digest in inp['files'].items():require(sha(a.input/name)==digest,'KD input artifact changed')
        sample=memory_snapshot();require(sample['MemAvailable']>=16*1024**3,'KD needs16GiB host memory available')
        record['memory_admission']=dict(sample,required_MemAvailable=16*1024**3)
    if a.window.startswith('W2'):
        prerequisite(a.w0p,'W0p',identity);measured=prerequisite(a.k2,'K2',identity)
        require(a.dispatch and sha(a.dispatch)==measured.get('dispatch_sha256'),'measured dispatch required')
        require(a.input and a.oracle,'input and oracle required')
        inp=json.loads((a.input/'input.json').read_text());require(sha(a.input/'input.json')==build['input_sha256'],'input identity changed')
        hashes,expected=selected_oracle(a,inp,retained_steps)
        for name,digest in inp['files'].items():require(sha(a.input/name)==digest,'input artifact changed')
        record.update(oracle_hashes=hashes,expected_tokens=expected,dispatch_sha256=sha(a.dispatch))
        # Conservative pre-admission until measured per-rank shadow receipts exist.
        sample=memory_snapshot();require(sample['MemAvailable']>=97*1024**3,'model window needs 97 GiB available before ranks load')
        record['memory_admission']=dict(sample,required_MemAvailable=97*1024**3,shadow_removal='unmeasured; no assumption')
    if a.window in SUITE_WINDOWS:
        require(a.suite_manifest is not None,'suite manifest required')
        prerequisite(a.w0p,'W0p',identity);measured=prerequisite(a.k2,'K2',identity)
        require(a.dispatch and sha(a.dispatch)==measured.get('dispatch_sha256'),'suite measured dispatch required')
        manifest=json.loads(a.suite_manifest.read_text())
        admit_cap(manifest,a.max_new)
        sample=memory_snapshot();require(sample['MemAvailable']>=97*1024**3,'suite needs97GiB available before ranks load')
        record['memory_admission']=dict(sample,required_MemAvailable=97*1024**3)
        record.update(token_cap=suite_cap,suite_manifest_sha256=sha(a.suite_manifest),controller=a.controller,repeat=a.repeat,dispatch_sha256=sha(a.dispatch))
    if a.window in SPEED_WINDOWS and not retained_steps:
        companion=prerequisite(a.exactness_window,SPEED_WINDOWS[a.window],identity)
        for key in ('controller','max_new','dispatch_sha256','prompt_overlap','context','draft_rank','target_split'):
            require(companion.get(key)==record.get(key),'exactness companion differs: '+key)
        companion_steps=pp.retention_steps(companion.get('retain_steps','none'),a.max_new)
        require(companion.get('retained_steps')==companion_steps,'exactness companion retention metadata differs')
        required=pp.retention_steps('1-8,97-104' if a.window=='WS128' else '1-8',a.max_new)
        require(companion_steps and set(required)<=set(companion_steps) and companion.get('diagnostic_for_speed') is True,'exactness companion has no retained fixture gate')
        if a.window in SUITE_WINDOWS:require(companion.get('suite_manifest_sha256')==record.get('suite_manifest_sha256'),'exactness companion prompt set differs')
        else:require(companion.get('expected_tokens')==record.get('expected_tokens'),'exactness companion tokens differ')
        record['exactness_companion']=dict(path=str(a.exactness_window.resolve()),sha256=sha(a.exactness_window),window=companion['window'],boot_id=boot)
    if a.dispatch:validate(json.loads(a.dispatch.read_text()))
    request_count=(1+len(manifest.get('requests',manifest.get('prompts',[])))*a.repeat) if a.window in SUITE_WINDOWS else 1
    record['storage_admission']=admit_output(out,projected_write_bytes(a.window,request_count,a.context,len(retained_steps)))
    record['foreign_engine_admission']=foreign_engines();out.mkdir(parents=True)
    if a.diagnostic_unsealed:
        record.update(MARKERS,diagnostic=True,diagnostic_for_speed=True)
        save(out/'DIAGNOSTIC-UNSEALED.json',dict(MARKERS,reason='Unsealed diagnostic; never submission, publication or promotion evidence',artifacts_sha256=artifacts))
    save(out/'window.json',record)
    watch=Watch(out,boot,seconds);old={s:signal.signal(s,lambda n,f:watch.cancelled.append(n)) for s in (signal.SIGTERM,signal.SIGINT)}
    try:
        save(out/'window.json',record)
        if a.window=='KD':
            from draft_window import run as run_draft
            record['receipts'],record['pids']=run_draft(a,out,environment['native'],watch,build,cpu_rehearsal=cpu_rehearsal)
        elif a.window.startswith('K'):
            record['receipts']=run_fixtures(a,out,environment['native'],watch)
            record['pids']=json.loads((out/'children.json').read_text())['pids']
            if a.window=='K0':
                for rank in (0,1):
                    r=json.loads((out/f'run{rank}/receipt.json').read_text());require(r['cards']==1 and r['kernel_execution'] is False and r['explicit_allocations']==0 and r['kernels_per_device']>0,'K0 coverage')
            elif a.window in ('K1a','K1b'):
                fixture_receipt_gate(out/'run0',dict(build,nongemv_fixture_host_sha256=build['nongemv_fixture_host_sha256_by_context'][str(a.context)]),cpu_rehearsal=cpu_rehearsal);record['linked_p33']=linked_fixture_gate(out/'linked',build,a.card,cpu_rehearsal=cpu_rehearsal)
                record['qsa_split32']=qsa_fixture_gate(out/'qsa',build,a.card,cpu_rehearsal=cpu_rehearsal)
                record['candidate_dispatch_sha256']=sha(a.dispatch) if a.dispatch else None
                if a.window=='K1b':fresh_k1_owners(json.loads(a.k1a.read_text()),record)
            else:
                require(sequential_teardown(json.loads((out/'run0/receipt.json').read_text())),'K2 unsafe/missing sequential-owner teardown')
                if cpu_rehearsal:
                    from k2_summary import cpu_structure
                    record['cpu_k2_structure']=cpu_structure(out/'run0')
                summary=summarize(out/'run0',identity)
                record['device_timing_qualified']=bool(summary['passed'])
                require(not summary['passed'] if cpu_rehearsal else summary['passed'],'CPU must fail K2 device timing' if cpu_rehearsal else 'K2 exact/timing gate')
                if not cpu_rehearsal:
                    from p49_dispatch import pin_production_dispatch
                    summary,record['production_dispatch_policy']=pin_production_dispatch(out/'run0',summary)
                    for name in ('summary-k2-measured.json','dispatch-k2-recommendation.json'):
                        record['receipts']['run0/'+name]=sha(out/'run0'/name)
                record.update(dispatch_sha256=sha(out/'run0/dispatch-measured.json'),summary_sha256=sha(out/'run0/summary.json'))
                for name in ('dispatch-measured.json','events.jsonl','summary.json'):record['receipts']['run0/'+name]=sha(out/'run0'/name)
                # One-card class measurements determine the common vocabulary for both ranks.
                # These are identical aliases, never a claim that rank1 was timed here.
                record['rank_dispatches']={}
                for rank in (0,1):
                    name=f'dispatch-rank{rank}.json';path=out/'run0'/name
                    path.write_bytes((out/'run0/dispatch-measured.json').read_bytes())
                    record['receipts']['run0/'+name]=sha(path)
                    record['rank_dispatches'][str(rank)]=dict(path='run0/'+name,sha256=sha(path),measurement_card=a.card,rank_card=a.card+rank,scope='SPEED6 pinned non-QSA dispatch with fresh one-card K2 exactness; target QSA overridden by split32')
        else:
            args=pp.parser().parse_args(['--output',str(out/'run')]);args.binary=B/('gnu-host' if cpu_rehearsal else 'device')/'own-rt-iq3';args.device=not cpu_rehearsal;args.native_nice=19 if cpu_rehearsal else 0;args.mini=cpu_rehearsal
            args.controller=a.controller;args.prompt_overlap=a.prompt_overlap;args.card=a.card;args.seconds=seconds;args.wait_seconds=600;args.context=a.context;args.draft_rank=a.draft_rank;args.target_split=a.target_split;args.tokens=a.max_new;args.retain_steps=a.retain_steps;args.input=a.input;args.oracle=None if cpu_rehearsal else a.oracle;args.dispatch=a.dispatch;args.timing='class' if a.window in ('W2c','W2mc') else 'token'
            record['ldd_preflight']=ldd_preflight(args.binary)
            if a.window=='W0p':concurrency_canary(args,out,environment['native'],watch)
            elif a.window in SUITE_WINDOWS:
                args.suite_manifest=a.suite_manifest;args.repeat=a.repeat;args.draft='mtp' if a.window in MTP_WINDOWS else 'none'
                args.controller=a.controller
                r=pp.run(args,environment['native'],watch.check,watch.latch,watch.mark_launched)
                record.update(summary=r,decode_tok_s=r['decode_median_tok_s'],submission_tok_s=r['class_balanced_tok_s_1_100_intervals_after_ttft']['median'])
                require(r['passed'],'one or more suite requests failed exactness')
            else:
                args.draft={'W2s':'none','W2n':'ngram','W2d':'script','W2x':'script','W2c':'ngram','W2m':'mtp','W2mc':'mtp','W2m-speed':'mtp','W2m-exact':'mtp'}[a.window]
                if a.window in ('W2d','W2x'):
                    args.script=out/'DIAGNOSTIC-oracle-guesses.txt';args.script.write_text(' '.join(map(str,expected[:63] if a.window=='W2d' else [(token+1)%248320 for token in expected[:63]])))
                r=pp.run(args,environment['native'],watch.check,watch.latch,watch.mark_launched);require(r['tokens']==expected,'every-token oracle mismatch')
                if a.window in ('W2d','W2x'):
                    require(r['stats']['guesses']==len(r['tokens'])-1 and r['stats']['hits']==(len(r['tokens'])-1 if a.window=='W2d' else 0),'diagnostic all-hit/all-miss pattern mismatch')
                observed={}
                for rank in (0,1):
                    for f in (out/f'run/rank{rank}').glob('step*/layer-*.bf16'):observed[str(f.relative_to(out/f'run/rank{rank}'))]=sha(f)
                require(observed==hashes,'retained fixtures differ/missing');record.update(token_matches=len(expected),layer_matches=len(hashes),diagnostic=r['diagnostic'],decode_tok_s=r['decode_tok_s'])
            record['receipts']={str(f.relative_to(out)):sha(f) for f in (out/'run').rglob('receipt.json')}
        watch.postflight();record['passed']=True
    except Exception as error:
        record.update(error=str(error),passed=False)
        pp.failure_attempt('window fault latch',lambda:watch.latch(error),record.setdefault('diagnostic_errors',[]))
    finally:
        for s,handler in old.items():signal.signal(s,handler)
    record['device_executed']=bool(watch.launched) and not cpu_rehearsal;record['launched_pids']=watch.launched
    # Only completed owners may have their logs compacted. Preserve any retained owner.
    alive=live_owner_pids(watch)
    record['cpu_owned_pids']=[child.pid for child in watch.cpu_children]
    record['retained_owner_pids']=alive
    if not alive:
        if a.diagnostic_unsealed:
            try:label_outputs(out,record,sha)
            except Exception as error:record.update(passed=False,diagnostic_label_error=str(error))
        try:compress_evidence(out,record)
        except Exception as error:record.update(retention_error=str(error),raw_evidence_retained=True)
    if a.diagnostic_unsealed:record.update(MARKERS,diagnostic=True,diagnostic_for_speed=True)
    save(out/'window.json',record);return 0 if record['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
