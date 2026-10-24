#!/usr/bin/env python3
"""Bounded GSQ rank adapter. CLI is plan-only; operational admission is external."""
import argparse, copy, hashlib, importlib.util, json, mmap, os, shutil, socket, subprocess, time
from pathlib import Path

P=Path(__file__).resolve().parent
LANE=Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s')
ROOT=Path('/home/steve/llm-optimizations')
CANDIDATE=LANE/'recurrent-f32'
LEDGER=LANE/'recurrent-f32/operating/candidate-ledger.json'
PARENT=ROOT/'experiments/own-xpu-runtime/stage2/packet195-record-bundle-diet/pipeline.py'
PARENT_SHA='4abadf40aa7bdab9400707f0dc9bbb13b104c1278f56b126bf767716459b63e3'
ENV_SOURCE=ROOT/'experiments/own-xpu-runtime/stage2/packet181-session-swap-v3/one-card/launch_env.py'
MODEL=Path('/mnt/usb-models/llm-models/SC117-Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_S-eec4e10a')
DRAFT_MODEL=Path('/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8')
BDFS=('0000:23:00.0','0000:47:00.0')
RETAINED=[]

def require(v,msg):
    if not v:raise ValueError(msg)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,obj):
    with Path(p).open('x') as f:json.dump(obj,f,indent=2);f.write('\n')
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
require(sha(PARENT)==PARENT_SHA,'P195 pipeline source changed')
BASE=load(PARENT,'gsq_p195_pipeline')
BUNDLE=load(Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/state-bundle/reader.py'),'gsq_state_bundle_reader')

def source_pins():
    files=[Path(__file__).resolve(),LANE/'recurrent-f32/operating/prefix-replay-a/generated/adapter.py',LANE/'recurrent-f32/operating/prefix-replay-a/source-preparation.json',Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/state-bundle/reader.py'),PARENT,ENV_SOURCE,LANE/'loader/bound.hpp',LANE/'loader/bound-authority.json',LANE/'loader/placement.tsv',LANE/'loader/shard-auth.tsv',LANE/'mtp/draft-manifest.tsv',LANE/'mtp/target-bindings.json',LEDGER]
    history=LANE/'integration/evidence/host-retained-source-map.json'
    if history.exists():files.append(history)
    return {str(p.relative_to(ROOT)):sha(p) for p in files}

def environments(output,mini):
    base=load(ENV_SOURCE,'gsq_launch_env').environment();base['HOME']=os.environ['HOME']
    envs=[]
    for rank,bdf in enumerate(BDFS):
        e=dict(base)
        if not mini:e.update(NEOReadDebugKeys='1',FilterBdfPath=bdf,ZE_ENABLE_PCI_ID_DEVICE_ORDER='1',ZE_AFFINITY_MASK='0',ONEAPI_DEVICE_SELECTOR='level_zero:0')
        for key,sub in [('SYCL_CACHE_DIR','sycl'),('NEO_CACHE_DIR','neo'),('XDG_CACHE_HOME','xdg')]:e[key]=str(output/'cache'/str(rank)/sub)
        envs.append(e)
    return envs

def command(plan,rank,channel,stop_fd):
    o=Path(plan['output']);e=Path(plan['evidence_output']);cmd=['ionice','-c','3',plan['binary'],'--gsq-packed','--rank',str(rank),'--channel',str(channel),'--stop-fd',str(stop_fd),'--shared',str(o/'shared.bin'),'--cards','1','--card','0','--output',str(e/f'rank{rank}'),'--memory','resident','--context',str(plan['context']),'--seconds',str(plan['seconds']),'--native-nice','19','--timing','token','--max-new',str(plan['max_new']),'--retain-steps','none','--draft-rank','0','--target-split','24','--host-path','prepared']
    if plan['mini']:cmd+=['--mini','--pipeline-mini']
    else:cmd+=['--plan',str(LANE/'loader/placement.tsv'),'--identity',str(LANE/'loader/shard-auth.tsv'),'--model-dir',str(MODEL),'--authorized-device-window']
    if rank==0:
        cmd+=['--draft-mtp','--draft-fault','none']
        if not plan['mini']:cmd+=['--draft-manifest',str(LANE/'mtp/draft-manifest.tsv'),'--draft-model',str(DRAFT_MODEL)]
    cmd.extend(['--attention-q8-p33','--qkv-q6-p33','--expert-iq3xxs-block','--dense-q6-p33','--dense-packed-block','--recurrent-f32'])
    return cmd

def build_plan(output,*,mini=False,max_new=4,seconds=1800,evidence_output=None):
    output=Path(output).absolute()
    require(not output.exists() and not output.is_symlink(),'fresh output required')
    require(output.parent.is_dir() and not output.parent.is_symlink(),'existing output parent required')
    parent=output.parent.stat();require(parent.st_uid==os.getuid() and parent.st_mode&0o077==0,'private owned output parent required')
    evidence=Path(evidence_output).absolute() if evidence_output is not None else output
    require(not evidence.exists() and not evidence.is_symlink(),'fresh evidence output required')
    require(evidence.parent.is_dir() and evidence.parent.resolve()==evidence.parent,'canonical evidence parent required')
    ep=evidence.parent.stat()
    require(type(max_new)is int and 1<=max_new<=512,'bounded max_new')
    require(type(seconds)is int and 30<=seconds<=172800,'bounded lifetime (native maximum 172800 s)')
    require(not mini,'candidate adapter is native-only; no synthetic override')
    receipt=CANDIDATE/'evidence/native-build.json'
    build=json.loads(receipt.read_text()) if receipt.exists() else None
    ready=bool(build and build.get('passed') is True and build.get('objects_rebuilt')==21 and build.get('objects_reused')==19)
    if build:require(ready,'successful matching build required')
    plan=dict(schema='ownrt.gsq.rank-adapter-plan.v1',output=str(output),output_parent_identity=[parent.st_dev,parent.st_ino],evidence_output=str(evidence),evidence_parent_identity=[ep.st_dev,ep.st_ino,ep.st_uid,ep.st_gid,ep.st_mode],mini=mini,context=64 if mini else 4096,max_new=max_new,seconds=seconds,wait_seconds=min(seconds,900),binary=build['binary'] if ready else '<pending-full-native-build>' if not mini else '<pending-full-host-build>',binary_sha256=build.get('binary_sha256') if ready else None,build_receipt=str(receipt),build_receipt_sha256=sha(receipt) if ready else None,build_ready=ready,native_admitted=False,source_sha256=source_pins(),environment=environments(output,mini),candidate_bdfs=list(BDFS),request_cap=None,service_retention='each RESET dump (and its request directory) is removed by the service once the next request has run; per-request summaries live in the control requests.jsonl',shared_bytes=BASE.SHARED,device_execution_requested=False)
    raw_state=0 if mini else 310364224+9699332 # one transient RESET dump; removed after it is written
    plan['storage']={'target_state_per_request_bytes':0 if mini else 310364224,'draft_state_per_request_bytes':0 if mini else 9699332,'request_count':None,'raw_state_bytes':raw_state,'evidence_forecast_bytes':raw_state+128*1024**2,'control_cache_forecast_bytes':128*1024**2,'root_floor_bytes':27000000000,'external_floor_bytes':2*1024**3,'hard_bound':False,'scope':'service: one transient RESET dump at a time plus monitored metadata; previous request dumps removed by explicit service retention policy'}
    plan['rank_argv']=[command(plan,r,'<channel-fd>','<stop-fd>') for r in range(2)]
    plan['command_sha256']=hashlib.sha256(json.dumps({'argv':plan['rank_argv'],'environment':plan['environment']},sort_keys=True).encode()).hexdigest()
    return plan

def validate_plan(plan):
    current=build_plan(plan['output'],mini=plan['mini'],max_new=plan['max_new'],seconds=plan['seconds'],evidence_output=plan['evidence_output'])
    require(plan==current,'plan/source/command/parent changed')
    require(plan['build_ready'],'compiled binary required')
    build=json.loads(Path(plan['build_receipt']).read_text())
    require(sha(plan['binary'])==plan['binary_sha256'],'binary changed')
    history={}
    if plan['mini']:
        path=LANE/'integration/evidence/host-retained-source-map.json'
        if path.exists():
            historic=json.loads(path.read_text());require(historic['build_receipt_sha256']==plan['build_receipt_sha256'],'historical build binding')
            history=historic['source_relocations']
    for f,h in build['source_sha256'].items():
        candidate=ROOT/f
        if f in history:
            require(history[f]['sha256']==h,'historical source digest mismatch');candidate=ROOT/history[f]['retained_path']
        require(sha(candidate)==h,'compiled source changed: '+f)
    for f,h in build.get('objects',{}).items():require(sha(f)==h,'compiled object changed')
    return build

def storage_guard(plan,started=False):
    # Forecast admission, not an enforced native writer quota. Called before
    # startup and each request; trusted continuous guard also monitors growth.
    if plan['mini']:return
    c=Path(plan['output']);e=Path(plan['evidence_output']);b=plan['storage']
    cp=c if started else c.parent;ep=e if started else e.parent
    same=cp.stat().st_dev==ep.stat().st_dev
    need=b['root_floor_bytes']+b['control_cache_forecast_bytes']+(b['evidence_forecast_bytes'] if same else 0)
    require(shutil.disk_usage(cp).free>=need,'root storage forecast/floor')
    if not same:require(shutil.disk_usage(ep).free>=b['external_floor_bytes']+b['evidence_forecast_bytes'],'external evidence forecast/floor')

class Transport(BASE.Transport):
    """Only constructor differs. Caller owns admission, leases and physical drain."""
    def __init__(self,plan,*,admit,check,launch_hook):
        # These trusted coordinator hooks are mandatory, including for CPU tests.
        require(all(callable(x) for x in (admit,check,launch_hook)),'coordinator hooks required')
        self.plan=copy.deepcopy(plan);self.failure_hook=lambda reason:None
        self.children=[];self.sockets=[];self.logs=[];self.spawn_uncertain=False;self.launch_attempts=0
        self.closed=False;self.retained=[];self.stop_sent=False;self.check=check
        validate_plan(plan);admit(copy.deepcopy(plan));check()
        args=BASE.parser().parse_args(['--output',plan['output'],'--binary',plan['binary'],'--draft','mtp','--draft-rank','0','--target-split','24','--context',str(plan['context']),'--tokens',str(plan['max_new']),'--seconds',str(plan['seconds']),'--wait-seconds',str(plan['wait_seconds']),'--native-nice','19','--retain-steps','none','--controller','native']+(['--mini'] if plan['mini'] else ['--device']))
        self.a=args;self.control_output=Path(plan['output']);self.out=Path(plan['evidence_output']);self.device=args.device
        self.seq=[0,0];self.pending=[False,False];self.started=[0.,0.];self.commands=[{},{}]
        self.metrics=[dict(busy_ms=0.,handover_ms=0.,calls=0,gpu_ms=0.) for _ in range(2)]
        self.trace=[];self.finishing=set();self.last_complete=[0.,0.]
        storage_guard(plan)
        self.control_output.mkdir(mode=0o700)
        if self.out!=self.control_output:self.out.mkdir(mode=0o700)
        self.shared_path=self.control_output/'shared.bin'
        fd=os.open(self.shared_path,os.O_RDWR|os.O_CREAT|os.O_EXCL,0o600)
        try:os.ftruncate(fd,BASE.SHARED);self.mapping=mmap.mmap(fd,BASE.SHARED)
        finally:os.close(fd)
        self.stop_read,self.stop_write=os.pipe();self.start_time=time.monotonic()
        save(self.control_output/'admission-plan.json',plan)
        for rank in range(2):
            check()
            for key in ('SYCL_CACHE_DIR','NEO_CACHE_DIR','XDG_CACHE_HOME'):Path(plan['environment'][rank][key]).mkdir(parents=True,mode=0o700,exist_ok=True)
            parent,child=socket.socketpair();parent.setblocking(False);self.sockets.append(parent)
            log=(self.control_output/f'rank{rank}.log').open('x');self.logs.append(log)
            cmd=command(plan,rank,child.fileno(),self.stop_read)
            self.spawn_uncertain=True;self.launch_attempts+=1
            try:
                proc=subprocess.Popen(cmd,pass_fds=(child.fileno(),self.stop_read),stdout=log,stderr=subprocess.STDOUT,env=plan['environment'][rank])
                self.children.append(proc);self.spawn_uncertain=False
            finally:child.close()
            launch_hook(proc.pid);check()
            save(self.control_output/f'rank{rank}-launch.json',dict(argv=cmd,pid=proc.pid,environment=plan['environment'][rank]))
        for rank in range(2):self.receive(rank,args.seconds,ready=True)
        check()
        # This census verifies logical allocations only. External admission must
        # separately establish physical availability before either process starts.
        if not plan['mini']:
            ledger=json.loads((LEDGER).read_text())['scenarios']['split24-24_mtp-rank0']['ranks']
            rows=[]
            for rank in range(2):
                c=json.loads((self.out/f'rank{rank}/census.json').read_text())
                actual=sum(a['bytes'] for a in c['allocations'] if a['live'] and a['memory']=='device')
                require(actual==c['totals']['device'] and 0<actual<=30*1024**3,'native census extent/cap')
                require(actual<=ledger[rank]['device_logical_bytes'],'native allocations exceed source forecast')
                rows.append(dict(rank=rank,bytes=actual))
            save(self.out/'logical-memory.json',dict(passed=True,ranks=rows,physical_fit_claimed=False))

class RetainedOwner(RuntimeError):
    def __init__(self,original,transport,secondary):
        super().__init__('owner retained; coordinator must remain alive and retain admission resources')
        self.original=original;self.transport=transport;self.secondary=secondary

def cleanup_failure(transport,error):
    """Never replace primary failure; uncertain owners remain caller-owned."""
    secondary=[]
    if getattr(transport,'spawn_uncertain',False):
        if hasattr(transport,'stop_write'):
            try:transport.stop(error)
            except BaseException as e:secondary.append('stop: '+repr(e))
        RETAINED.append(transport)
        raise RetainedOwner(error,transport,secondary) from error
    if hasattr(transport,'stop_write'):
        for name,action in [('stop',lambda:transport.stop(error)),('close',lambda:transport.close(False))]:
            try:action()
            except BaseException as e:secondary.append(name+': '+repr(e))
    uncertain=getattr(transport,'spawn_uncertain',False)
    for child in getattr(transport,'children',[]):
        try:uncertain |= child.poll() is None
        except BaseException as e:uncertain=True;secondary.append('poll: '+repr(e))
    if uncertain:
        RETAINED.append(transport)
        raise RetainedOwner(error,transport,secondary) from error
    return secondary

def state_hashes(transport):
    result={}
    for rank in (0,1):
        transport.call(rank,BASE.DUMP,position=2147483647)
        path=transport.request_output/f'rank{rank}/state-2147483647'
        result[str(rank)]=BUNDLE.read_state(path)
    return result

def reset(transport,destination):
    require(not any(transport.pending),'reset while busy')
    destination=Path(destination).absolute();require(not destination.exists(),'fresh request destination')
    require(destination.parent==transport.out,'fixed request child')
    destination.mkdir(mode=0o700)
    for rank in (0,1):
        metadata=transport.out/f'rank{rank}'/f'reset-{transport.seq[rank]+1}.txt'
        dest=destination/f'rank{rank}';require('\n' not in str(dest),'reset path newline')
        with metadata.open('x') as f:f.write(str(dest)+'\n\n')
        transport.call(rank,11)
    transport.request_output=destination
    transport.mapping[:BASE.SHARED]=bytes(BASE.SHARED)
    transport.trace=[];transport.metrics=[dict(busy_ms=0.,handover_ms=0.,calls=0,gpu_ms=0.) for _ in range(2)];transport.last_complete=[0.,0.]

def compare_attached(transport,prompt,count):
    """Two serialized requests, same pair. Leaves normal close to caller."""
    require(type(prompt)is list and prompt and all(type(t)is int and 0<=t<(16 if transport.a.mini else 248320) for t in prompt),'prompt token IDs')
    require(type(count)is int and 0<count<=transport.a.tokens and len(prompt)+count<=transport.a.context,'request token bound')
    require(not getattr(transport,'sequence_started',False),'qualification sequence already used')
    transport.sequence_started=True;transport.request_output=transport.out
    rows=[]
    for mode in ('none','mtp'):
        transport.check_alive();storage_guard(transport.plan,started=True)
        if rows:reset(transport,transport.out/'mtp-request')
        result=BASE.NativeController(transport,BASE.Draft(mode),True,False).run(prompt,count,() if transport.a.mini else (248044,248046))
        # Historical evidence_label presumes its old qualified arithmetic. Replace
        # that label, retain raw protocol result and make no speed/quality claim.
        result.update(evidence_label='GSQ experimental target/MTP comparison; not independently qualified',decode_tok_s=None)
        save(transport.out/f'{mode}-result.json',result)
        rows.append(dict(mode=mode,tokens=result['tokens'],state=state_hashes(transport)))
    require(rows[0]['tokens']==rows[1]['tokens'],'MTP confirmed token mismatch')
    require(rows[0]['state']==rows[1]['state'],'MTP final target state mismatch')
    return dict(passed=True,same_rank_processes=True,rank_pids=[p.pid for p in transport.children],requests=2,rows=rows,no_speed_claim=True)

def qualification(plan,prompt,count,*,admit,check,launch_hook):
    """Trusted coordinator API, not a CLI. Keeps uncertain owner handle reachable."""
    t=Transport.__new__(Transport)
    try:
        t.__init__(plan,admit=admit,check=check,launch_hook=launch_hook)
        result=compare_attached(t,prompt,count)
        t.close(True);save(t.out/'qualification.json',result);return result
    except BaseException as error:
        secondary=cleanup_failure(t,error)
        if hasattr(t,'out') and t.out.exists():
            try:save(t.out/'incident.json',dict(error=repr(error),secondary=secondary,passed=False))
            except BaseException:pass
        raise

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--plan',action='store_true',required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--mini',action='store_true');ap.add_argument('--evidence-output',type=Path);ap.add_argument('--max-new',type=int,default=4);ap.add_argument('--seconds',type=int,default=1800)
    a=ap.parse_args();print(json.dumps(build_plan(a.output,mini=a.mini,max_new=a.max_new,seconds=a.seconds,evidence_output=a.evidence_output),indent=2))
if __name__=='__main__':main()
