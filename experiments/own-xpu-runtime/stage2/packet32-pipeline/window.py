#!/usr/bin/env python3
"""Coordinator-only device windows. Preparation never executes this entry."""
import argparse,json,math,os,re,signal,subprocess,time
from pathlib import Path
import pipeline as pp
from pipeline import P,save,sha,require,Transport,CANARY,SLOT
from window_safety import environment_gate,memory_snapshot
from fixture_support import journal,ldd_preflight,oracle_gate,fixture_receipt_gate,k1_gate
from k2_summary import summarize
from merge_dispatch import validate
B=P/'build';ROOT=P.parents[3]
CONFIG={'K0':(30,600),'K1a':(1800,10800),'K1b':(1800,10800),'K2':(1800,10800),'W0p':(30,600),
        'W2s':(1900,10800),'W2n':(1900,10800),'W2d':(1900,10800),'W2c':(1900,10800)}
FAULT=re.compile(r'Fault response|Engine memory CAT error|engine reset|timed[- ]out job|devcoredump|GPU.*coredump',re.I)
def watchdog(name,seconds=None):
    expected,default=CONFIG[name];seconds=seconds or default
    require(max(300,math.ceil(4*(expected+17)))<=seconds<=10800,'watchdog below four times estimate/300s or above 10800s')
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
        self.out=out;self.boot=boot;self.end=time.monotonic()+seconds;self.last=0.;self.cancelled=[]
        text,self.cursor=journal();(out/'kernel-preflight.txt').write_text(text)
    def latch(self,reason):
        save(B/'FAULT.json',dict(boot_id=self.boot,reason=str(reason),window=str(self.out)))
    def check(self):
        require(not self.cancelled,'coordinator stop requested')
        require(time.monotonic()<self.end,'window watchdog')
        if time.monotonic()-self.last<.25:return
        text,self.cursor=journal(self.cursor);self.last=time.monotonic()
        with (self.out/'kernel-window.txt').open('a') as f:f.write(text)
        if FAULT.search(text):self.latch('GPU fault signature');raise ValueError('GPU fault signature')
    def postflight(self):
        end=time.monotonic()+5
        while time.monotonic()<end:self.check();time.sleep(.25)

def prerequisites(path,name,identity):
    require(path is not None,'missing prerequisite '+name)
    row=json.loads(path.read_text());require(row.get('passed') is True and row.get('window')==name,'failed prerequisite '+name)
    for field in ('boot_id','artifacts_sha256','environment','card'):
        require(row.get(field)==identity.get(field),'prerequisite identity changed: '+name+' '+field)
    for filename,digest in row.get('receipts',{}).items():require(sha(path.parent/filename)==digest,'prerequisite receipt changed')
    return row

def run_fixtures(a,out,env,watch):
    # Kernel JIT uses one single-device process per card; fixture processes keep
    # the packet29 harness and receive only a cooperative stop pipe.
    names=['jit-smoke']*2 if a.window=='K0' else ['k2-fixtures' if a.window=='K2' else 'nongemv-fixtures']
    receipts={};children=[];logs=[];stop_r,stop_w=os.pipe();sent=False
    try:
        for rank,name in enumerate(names):
            watch.check();binary=B/'device'/name;ldd_preflight(binary)
            dest=out/f'run{rank}';log=(out/f'rank{rank}.log').open('w');logs.append(log)
            cmd=[str(binary),'--authorized-device-window','--card',str(a.card+rank),'--output',str(dest)]
            if a.window=='K0':cmd+=['--cards','1']
            else:cmd+=['--stop-fd',str(stop_r)]
            if a.window=='K2':cmd+=['--repetitions','200']
            if a.dispatch and a.window!='K0':cmd+=['--dispatch',str(a.dispatch)]
            children.append(subprocess.Popen(['ionice','-c','3']+cmd,stdout=log,stderr=subprocess.STDOUT,env=env,pass_fds=(stop_r,)))
        save(out/'children.json',dict(pids=[p.pid for p in children],signals_sent=0))
        while any(p.poll() is None for p in children):
            watch.check();require(all(p.poll() in (None,0) for p in children),'fixture rank failure');time.sleep(.1)
        for rank,p in enumerate(children):
            require(p.returncode==0,'fixture exit failure');r=json.loads((out/f'run{rank}/receipt.json').read_text());require(r.get('passed') is True,'fixture native failure')
            receipts[f'run{rank}/receipt.json']=sha(out/f'run{rank}/receipt.json')
        return receipts
    except Exception as error:
        watch.latch(error);save(out/'failure-before-teardown.json',dict(error=str(error),pids=[p.pid for p in children]))
        os.write(stop_w,b'!');sent=True
        end=time.monotonic()+65
        while any(p.poll() is None for p in children) and time.monotonic()<end:time.sleep(.1)
        save(out/'retained.json',dict(pids=[p.pid for p in children if p.poll() is None],signals_sent=0,stop_requested=True))
        raise
    finally:
        # K0 cannot interrupt an in-progress JIT; report and retain it, never signal.
        for log in logs:log.close()
        os.close(stop_w);os.close(stop_r)

def concurrency_canary(args,out,env,watch):
    args.canary=True;args.mini=True;args.output=out/'run';args.output.mkdir()
    t=Transport.__new__(Transport);result=dict(passed=False,device_executed=True)
    try:
        t.__init__(args,args.output,env,watch.check);t.failure_hook=watch.latch;overlaps=0;pids=[p.pid for p in t.children]
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
        save(args.output/'receipt.json',dict(result,error=str(error)));watch.latch(error)
        if hasattr(t,'stop_write'):t.stop(error);t.close(False)
        raise
    save(args.output/'receipt.json',result);return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--authorized-device-window',action='store_true',required=True)
    p.add_argument('--window',choices=CONFIG,required=True);p.add_argument('--card',type=int,required=True);p.add_argument('--prompt-overlap',choices=('on','off'),default='on');p.add_argument('--seconds',type=int)
    for name in ('output','input','oracle','dispatch','k0','k1a','k1b','k2','w0p'):p.add_argument('--'+name,type=Path,required=name=='output')
    a=p.parse_args();require(0<=a.card<=2,'--card is first of adjacent pair')
    environment=environment_gate();require(os.environ.get('OMP_NUM_THREADS')=='2','OMP_NUM_THREADS=2')
    nice=0 if a.window.startswith('W') else 19;require(os.getpriority(os.PRIO_PROCESS,0)==nice,'W windows need a nice-0 parent; K windows nice19')
    seconds=watchdog(a.window,a.seconds);out=a.output.resolve();require(B.resolve() in out.parents and not out.exists(),'new output beneath packet32/build required')
    build=json.loads((P/'build-receipt.json').read_text());require(build.get('passed') is True,'CPU/build gates incomplete')
    for name,digest in build['sources'].items():require(sha(ROOT/name)==digest,'source changed '+name)
    artifacts=build['artifacts_sha256']
    for name,digest in artifacts.items():require(sha(B/name)==digest,'binary changed '+name)
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if (B/'FAULT.json').exists():require(json.loads((B/'FAULT.json').read_text()).get('boot_id')!=boot,'boot fault latch requires coordinator recovery')
    identity=dict(schema='packet32.window.v1',window=a.window,card=a.card,boot_id=boot,artifacts_sha256=artifacts,environment=environment)
    record=dict(identity,prompt_overlap=a.prompt_overlap,passed=False,device_executed=False,expected_seconds=CONFIG[a.window][0]+17,expectation_enforced=False,watchdog_seconds=seconds)
    if a.window!='K0':prerequisites(a.k0,'K0',identity)
    if a.window=='K1b':prerequisites(a.k1a,'K1a',identity)
    if a.window in ('K2','W2s','W2n','W2d','W2c'):
        ka=prerequisites(a.k1a,'K1a',identity);kb=prerequisites(a.k1b,'K1b',identity)
        require(ka.get('candidate_dispatch_sha256')==kb.get('candidate_dispatch_sha256'),'K1 dispatch mismatch')
        require(ka.get('pids')!=kb.get('pids'),'K1 fresh process required')
        if a.window=='K2':require(ka.get('candidate_dispatch_sha256')==(sha(a.dispatch) if a.dispatch else None),'K2 candidate differs from K1')
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
    if a.dispatch:validate(json.loads(a.dispatch.read_text()))
    record['foreign_engine_admission']=foreign_engines();out.mkdir(parents=True);save(out/'window.json',record)
    watch=Watch(out,boot,seconds);old={s:signal.signal(s,lambda n,f:watch.cancelled.append(n)) for s in (signal.SIGTERM,signal.SIGINT)}
    try:
        record['device_executed']=True;save(out/'window.json',record)
        if a.window.startswith('K'):
            record['receipts']=run_fixtures(a,out,environment['native'],watch)
            record['pids']=json.loads((out/'children.json').read_text())['pids']
            if a.window=='K0':
                for rank in (0,1):
                    r=json.loads((out/f'run{rank}/receipt.json').read_text());require(r['cards']==1 and r['kernel_execution'] is False and r['explicit_allocations']==0 and r['kernels_per_device']>0,'K0 coverage')
            elif a.window in ('K1a','K1b'):
                fixture_receipt_gate(out/'run0',build);record['candidate_dispatch_sha256']=sha(a.dispatch) if a.dispatch else None
            else:
                summary=summarize(out/'run0',identity);require(summary['passed'],'K2 exact/timing gate')
                record.update(dispatch_sha256=sha(out/'run0/dispatch-measured.json'),summary_sha256=sha(out/'run0/summary.json'))
                for name in ('dispatch-measured.json','events.jsonl','summary.json'):record['receipts']['run0/'+name]=sha(out/'run0'/name)
        else:
            args=pp.parser().parse_args(['--output',str(out/'run')]);args.binary=B/'device/own-rt-iq3';args.device=True;args.native_nice=0
            args.prompt_overlap=a.prompt_overlap;args.card=a.card;args.seconds=seconds;args.wait_seconds=600;args.context=256;args.tokens=64;args.input=a.input;args.oracle=a.oracle;args.dispatch=a.dispatch;args.timing='class' if a.window=='W2c' else 'token'
            record['ldd_preflight']=ldd_preflight(args.binary)
            if a.window=='W0p':concurrency_canary(args,out,environment['native'],watch)
            else:
                args.draft={'W2s':'none','W2n':'ngram','W2d':'script','W2c':'ngram'}[a.window]
                if a.window=='W2d':args.script=out/'DIAGNOSTIC-oracle-guesses.txt';args.script.write_text(' '.join(map(str,expected[:63])))
                r=pp.run(args,environment['native'],watch.check,watch.latch);require(r['tokens']==expected,'64-token oracle mismatch')
                observed={}
                for rank in (0,1):
                    for f in (out/f'run/rank{rank}').glob('step*/layer-*.bf16'):observed[str(f.relative_to(out/f'run/rank{rank}'))]=sha(f)
                require(observed==hashes,'384 retained fixtures differ/missing');record.update(token_matches=64,layer_matches=384,diagnostic=r['diagnostic'],decode_tok_s=r['decode_tok_s'])
            record['receipts']={str(f.relative_to(out)):sha(f) for f in (out/'run').rglob('receipt.json')}
        watch.postflight();record['passed']=True
    except Exception as error:
        watch.latch(error);record.update(error=str(error),passed=False)
    finally:
        for s,handler in old.items():signal.signal(s,handler)
    save(out/'window.json',record);return 0 if record['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
