#!/usr/bin/env python3
"""Bounded GSQ rank adapter. CLI is plan-only; operational admission is external."""
import argparse, copy, fcntl, hashlib, importlib.util, json, mmap, os, shutil, socket, struct, subprocess, time
from pathlib import Path

P=Path(__file__).resolve().parent
LANE=Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s')
ROOT=Path('/home/steve/llm-optimizations')
CANDIDATE=LANE/'recurrent-f32'
SERVICE_BUILD=Path(os.environ.get('SC117_ENGINE_RECEIPT',str(ROOT/'experiments/own-xpu-runtime/engine/receipts/32654dfb2fde.json')))  # engine/src builds with typed activations
ACTIVATIONS=os.environ.get('SC117_ACTIVATIONS','bf16')
if ACTIVATIONS not in ('bf16','f32'):raise ValueError('SC117_ACTIVATIONS must be bf16 or f32')
SERVICE_FLAGS=['--reset-dump','none','--finish-dump','none','--token-stream','jsonl','--draft-experts','fp8','--activations',ACTIVATIONS]
# Batched prefill (engine --prefill-rows): rows per chunk, 0 = off. Requires the F32 exact engine. The rows travel
# through prefill.bin next to shared.bin (engine prefill_wire.hpp layout: header page, forward[2], reverse[2]).
PREFILL_ROWS=int(os.environ.get('SC117_PREFILL_ROWS','0'))
TARGET_SPLIT=int(os.environ.get('SC117_TARGET_SPLIT','24'))  # layers on rank 0 (draft on rank 0); the rest on rank 1
DISPATCH=os.environ.get('SC117_DISPATCH','')  # non-GEMV kernel choices (packet26.dispatch.v1); empty = engine defaults
if not 0<=PREFILL_ROWS<=64:raise ValueError('SC117_PREFILL_ROWS must be 0..64')
if PREFILL_ROWS and ACTIVATIONS!='f32':raise ValueError('batched prefill requires SC117_ACTIVATIONS=f32')
PREFILL_STREAM=4*2560*4  # four F32 HC streams of width 2560
PREFILL_HEADER=4096
def prefill_bytes(rows):return PREFILL_HEADER+4*rows*PREFILL_STREAM
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
    return {str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p):sha(p) for p in files}  # absolute key: relocated (lab) copy

def environments(output,mini):
    base=load(ENV_SOURCE,'gsq_launch_env').environment();base['HOME']=os.environ['HOME']
    envs=[]
    for rank,bdf in enumerate(BDFS):
        e=dict(base)
        if not mini:e.update(NEOReadDebugKeys='1',FilterBdfPath=bdf,ZE_ENABLE_PCI_ID_DEVICE_ORDER='1',ZE_AFFINITY_MASK='0',ONEAPI_DEVICE_SELECTOR='level_zero:0')
        for key,sub in [('SYCL_CACHE_DIR','sycl'),('NEO_CACHE_DIR','neo'),('XDG_CACHE_HOME','xdg')]:e[key]=str(output/'cache'/str(rank)/sub)
        for key in ('OWNRT_PREFILL_PROFILE','OWNRT_PREFILL_NATIVE','OWNRT_PREFILL_TILED','OWNRT_PREFILL_REUSE','OWNRT_PREFILL_SMALLTILE','OWNRT_DECODE_PROFILE','OWNRT_DECODE_FUSE','OWNRT_ROUTE_GROUP','OWNRT_KOPT_BLOCK_ROWS','OWNRT_ROUTE_FAST','OWNRT_IQ4NL_ROWS','OWNRT_SMALLK_ROWS','OWNRT_DRAFT_PREFIX_ROWS','OWNRT_DRAFT_HEAD_Q4','OWNRT_ARGMAX_FAST','OWNRT_MISS','OWNRT_SNAPSHOT_HOST','OWNRT_EARLY_RANK1','OWNRT_DRAFT_KERNELS','OWNRT_MERGE_CHECKS','OWNRT_ATTN_GQA','OWNRT_SELECT_SG','OWNRT_ADMIT_FAST','OWNRT_ATTN_PIPELINE','OWNRT_PREFILL_LEAN_ROWS','OWNRT_ATTN_WIDE','OWNRT_LOOKUP_COPY','OWNRT_GSQ_FUSE_NORM','OWNRT_FUSE_MIX','OWNRT_DRAFT_DEPTH_PROBE','OWNRT_DRAFT_DEPTH_VERIFY','OWNRT_SELECT_TOPK'):  # prefill diagnostics: per-site wall times; native rows off
            if key in os.environ:e[key]=os.environ[key]
        envs.append(e)
    return envs

def command(plan,rank,channel,stop_fd):
    o=Path(plan['output']);e=Path(plan['evidence_output']);cmd=['ionice','-c','3',plan['binary'],'--gsq-packed','--rank',str(rank),'--channel',str(channel),'--stop-fd',str(stop_fd),'--shared',str(o/'shared.bin'),'--cards','1','--card','0','--output',str(e/f'rank{rank}'),'--memory','resident','--context',str(plan['context']),'--seconds',str(plan['seconds']),'--native-nice','19','--timing','token','--max-new',str(plan['max_new']),'--retain-steps','none','--draft-rank','0','--target-split',str(TARGET_SPLIT),'--host-path','prepared']
    if plan['mini']:cmd+=['--mini','--pipeline-mini']
    else:cmd+=['--plan',str(LANE/'loader/placement.tsv'),'--identity',str(LANE/'loader/shard-auth.tsv'),'--model-dir',str(MODEL),'--authorized-device-window']
    if rank==0:
        cmd+=['--draft-mtp','--draft-fault','none']
        if not plan['mini']:cmd+=['--draft-manifest',str(LANE/'mtp/draft-manifest.tsv'),'--draft-model',str(DRAFT_MODEL)]
    cmd.extend(['--attention-q8-p33','--qkv-q6-p33','--expert-iq3xxs-block','--dense-q6-p33','--dense-packed-block','--recurrent-f32'])
    cmd.extend(plan.get('service_flags',[]))
    if PREFILL_ROWS:cmd+=['--prefill-rows',str(PREFILL_ROWS),'--prefill-shared',str(o/'prefill.bin')]
    if DISPATCH:cmd+=['--dispatch',DISPATCH]
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
    receipt=SERVICE_BUILD
    build=json.loads(receipt.read_text()) if receipt.exists() else None
    ready=bool(build and build.get('passed') is True and build.get('schema')=='ownrt.engine.build.v1' and build.get('root_binary_sha256')=='5926a24746c62c6b0ecdc5c3e4895f310145e0f9d74a90a5d657035b9a8151f4')
    if build:require(ready,'successful matching build required')
    plan=dict(schema='ownrt.gsq.rank-adapter-plan.v1',output=str(output),output_parent_identity=[parent.st_dev,parent.st_ino],evidence_output=str(evidence),evidence_parent_identity=[ep.st_dev,ep.st_ino,ep.st_uid,ep.st_gid,ep.st_mode],mini=mini,context=64 if mini else int(os.environ.get('SC117_CONTEXT','4096')),max_new=max_new,seconds=seconds,wait_seconds=min(seconds,900)*max(1,int(os.environ.get('SC117_CONTEXT','4096'))//4096),binary=build['binary'] if ready else '<pending-full-native-build>' if not mini else '<pending-full-host-build>',binary_sha256=build.get('binary_sha256') if ready else None,build_receipt=str(receipt),build_receipt_sha256=sha(receipt) if ready else None,build_ready=ready,native_admitted=False,source_sha256=source_pins(),environment=environments(output,mini),candidate_bdfs=list(BDFS),request_cap=None,service_retention='each RESET dump (and its request directory) is removed by the service once the next request has run; per-request summaries live in the control requests.jsonl',shared_bytes=BASE.SHARED,device_execution_requested=False)
    scale=1 if mini else int(os.environ.get('SC117_CONTEXT','4096'))//4096 # context-sized buffers: an upper bound at 32768
    raw_state=0 if mini else (310364224+9699332)*scale # one transient RESET dump; removed after it is written
    plan['storage']={'target_state_per_request_bytes':0 if mini else 310364224*scale,'draft_state_per_request_bytes':0 if mini else 9699332*scale,'request_count':None,'raw_state_bytes':raw_state,'evidence_forecast_bytes':raw_state+128*1024**2,'control_cache_forecast_bytes':128*1024**2,'root_floor_bytes':27000000000,'external_floor_bytes':2*1024**3,'hard_bound':False,'scope':'service: one transient RESET dump at a time plus monitored metadata; previous request dumps removed by explicit service retention policy'}
    plan['service_flags']=list(SERVICE_FLAGS)
    plan['storage']['target_state_per_request_bytes']=plan['storage']['draft_state_per_request_bytes']=plan['storage']['raw_state_bytes']=0
    plan['storage']['evidence_forecast_bytes']=128*1024**2
    plan['storage']['scope']='service build: --reset-dump none/--finish-dump none; no per-request state dumps'
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

# Rank 0 copies the embedding and PLE lookup tables into anonymous memory (engine Weights::copy_lookups, 2026-10-25):
# the exact size it reported for this model. The sealed base bounds both ranks' anonymous memory at 8 GiB.
LOOKUP_COPY_BYTES=29_137_853_440

class Transport(BASE.Transport):
    """Constructor differs; the anonymous-memory bound also admits rank 0's lookup-table copy. Caller owns admission,
    leases and physical drain."""
    def check_alive(self):
        self.check()
        require(time.monotonic()-self.start_time<self.a.seconds,"pipeline total deadline")
        for rank,proc in enumerate(self.children):
            code=proc.poll()
            if code is not None and rank not in self.finishing:
                if code != 0 and not self.stop_sent:
                    raise BASE.DeviceOwnerFailure("rank failed with exit "+str(code), self.out/f"rank{rank}")
                raise ValueError("rank closed unexpectedly")
        allowance=0 if os.environ.get('OWNRT_LOOKUP_COPY')=='0' else LOOKUP_COPY_BYTES
        receipt=self.out/'rank0'/'lookup-residency.json'
        if allowance and receipt.exists():
            r=json.loads(receipt.read_text());require(r.get('enabled') and r.get('bytes')==LOOKUP_COPY_BYTES,'lookup copy size differs from the admitted bound')
        anonymous=0
        for proc in self.children:
            try:
                for line in Path(f"/proc/{proc.pid}/status").read_text().splitlines():
                    if line.startswith("RssAnon:"):anonymous+=int(line.split()[1])*1024
            except FileNotFoundError:pass
        require(anonymous<8*1024**3+allowance,"aggregate rank anonymous memory exceeded 8 GiB plus the lookup copy")
    def __init__(self,plan,*,admit,check,launch_hook):
        # These trusted coordinator hooks are mandatory, including for CPU tests.
        require(all(callable(x) for x in (admit,check,launch_hook)),'coordinator hooks required')
        self.plan=copy.deepcopy(plan);self.failure_hook=lambda reason:None
        self.children=[];self.sockets=[];self.logs=[];self.spawn_uncertain=False;self.launch_attempts=0
        self.closed=False;self.retained=[];self.stop_sent=False;self.check=check
        validate_plan(plan);admit(copy.deepcopy(plan));check()
        args=BASE.parser().parse_args(['--output',plan['output'],'--binary',plan['binary'],'--draft','mtp','--draft-rank','0','--target-split','24','--context',str(plan['context']),'--tokens',str(plan['max_new']),'--seconds',str(plan['seconds']),'--wait-seconds',str(plan['wait_seconds']),'--native-nice','19','--retain-steps','none','--controller','native']+(['--mini'] if plan['mini'] else ['--device']))
        args.target_split=TARGET_SPLIT  # the sealed base parser admits only 0/23/24; this adapter launches its own ranks
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
        if PREFILL_ROWS:
            import struct
            fd=os.open(self.control_output/'prefill.bin',os.O_RDWR|os.O_CREAT|os.O_EXCL,0o600)
            try:
                os.ftruncate(fd,prefill_bytes(PREFILL_ROWS))
                os.pwrite(fd,struct.pack('<4I',0x31465050,1,PREFILL_ROWS,PREFILL_STREAM),0)
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
                require(actual<=(ledger[rank]['device_logical_bytes'] if ACTIVATIONS=='bf16' else 30*1024**3),'native allocations exceed source forecast')  # F32 mode: hard 30 GiB cap; actual census recorded
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

def redirect(transport,destination):
    """Conversation continuation boundary (rank command 16): the next request continues the current state; only each
    rank's output directory moves. The shared region is reset except the draft's first-step inputs."""
    require(not any(transport.pending),'redirect while busy')
    destination=Path(destination).absolute();require(not destination.exists(),'fresh request destination')
    require(destination.parent==transport.out,'fixed request child')
    destination.mkdir(mode=0o700)
    for rank in (0,1):
        metadata=transport.out/f'rank{rank}'/f'redirect-{transport.seq[rank]+1}.txt'
        dest=destination/f'rank{rank}';require('\n' not in str(dest),'redirect path newline')
        with metadata.open('x') as f:f.write(str(dest)+'\n')
        transport.call(rank,16)
    transport.request_output=destination
    # Same shared region as after a reset, except the two inputs of the draft's first continuation step (rank.hpp
    # layout): reverse_ready at 2*slot+192 and rank 1's final hidden row at reverse_offset. Turn 1's verification
    # slot, draft publication and mailbox must not survive: a fresh request never sees them.
    slot=65536;ready=2*slot+192;reverse=2*slot+4096;require(BASE.SHARED==reverse+2*slot+64,'shared layout')
    keep_ready=bytes(transport.mapping[ready:ready+4]);keep_row=bytes(transport.mapping[reverse:reverse+slot])
    transport.mapping[:BASE.SHARED]=bytes(BASE.SHARED)
    transport.mapping[ready:ready+4]=keep_ready;transport.mapping[reverse:reverse+slot]=keep_row
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

class NativeController(BASE.NativeController):
    """BASE.NativeController plus the optional "prefill <rows>" and "start <position>" request trailers (engine
    native_controller.hpp). start>0 continues a conversation: prompt[:start] is already in the ranks' state."""
    def __init__(self,backend,draft,overlap=True,dumps=False,prefill=None,start=0):
        super().__init__(backend,draft,overlap,dumps);self.prefill=PREFILL_ROWS if prefill is None else prefill;self.start=start
        require(0<=self.prefill<=PREFILL_ROWS,'request prefill rows exceed the engine allocation')
        require(start>=0,'continuation start')
    def run(self,prompt,count,eos=()):
        if not self.prefill and not self.start:return super().run(prompt,count,eos)
        require(self.start+2<=len(prompt),'continuation needs at least two new prompt tokens')
        # BASE.NativeController.run with the trailer; everything after the request write is the parent's code path.
        b=self.b;mode={"none":0,"ngram":1,"script":2,"mtp":3}[self.draft.mode]
        values=[mode,count,int(self.overlap),int(self.dumps),len(prompt),len(self.draft.script),len(eos),*prompt,*self.draft.script,*eos]
        if self.prefill:values+=['prefill',self.prefill]
        if self.start:values+=['start',self.start]
        (b.shared_path.parent/"native-request.txt").write_text(" ".join(map(str,values))+"\n")
        trace_start=len(b.trace)
        b.start(1,BASE.NATIVE);b.start(0,BASE.NATIVE)
        b.wait(0);b.wait(1)
        r=json.loads((b.shared_path.parent/"native-result.json").read_text())
        b.trace[trace_start:]=r["rank_trace"]
        b.work_start=r["work_start"];b.work_end=r["work_end"]
        b.metrics=[dict(busy_ms=0.,handover_ms=0.,calls=0,gpu_ms=0.) for _ in range(2)]
        for row in b.trace:
            m=b.metrics[row["rank"]];m["busy_ms"]+=row.get("busy_ms",0);m["gpu_ms"]+=row.get("gpu_ms",0);m["calls"]+=1
        r.update(diagnostic=False,prompt_overlap=self.overlap,prefill_rows=self.prefill,acceptance=r["stats"]["hits"]/r["stats"]["guesses"] if r["stats"]["guesses"] else None,
                 decode_tok_s=(r["decode_intervals"]*1000/r["decode_wall_ms"] if r["decode_wall_ms"] else None) if b.device else None)
        return r

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

# ---------------------------------------------------------------- session parking (opt-in; service SC117_SESSIONS=1)
# Two-rank save/restore of a conversation's engine state, coordinated here exactly like reset()/redirect(): between
# requests both ranks sit in their command loops and take rank commands over their own channels (the native
# controller runs only inside op 10). Rank ops (engine session_checkpoint.hpp): 17 STAGE, 18 VERIFY (only directly
# after op 11), 19 APPLY (only directly after a successful VERIFY). A refusal replies status 2 / error = op, writes
# checkpoint-refused-<seq>.json into the rank's request output and leaves that rank's engine state unchanged.
# Layout under the parking root:  <id>/manifest.json (authoritative, written last, published by one directory rename),
# <id>/rank0/ and <id>/rank1/ (sealed rank bundles), <id>/reverse.bin (shared-map reverse slot); lock: sibling <id>.lock
# (flock, non-blocking: shared for restore/inspect, exclusive for save/delete). <id> = first 32 hex of tokens_sha256.
SESSION_SCHEMA='sc117.session.v1'
STAGE_OP,VERIFY_OP,APPLY_OP=17,18,19
SESSION_SLOT=65536;SESSION_READY=2*SESSION_SLOT+192;SESSION_REVERSE=2*SESSION_SLOT+4096  # rank.hpp shared layout
PENDING_CONVENTION=('the ranks hold positions [0, position) = tokens; pending_token is the last target output, not yet '
                    'stepped; the draft has consumed confirmed positions up to position-1 and the reverse slot holds rank '
                    "1's final row of position-1 with reverse_ready = position. A restore continues exactly like the "
                    'in-memory continuation (native start = position): the next prompt must be tokens + [pending_token] '
                    '+ at least one more token.')

class SessionRefused(RuntimeError):
    """A session operation refused. engine: 'untouched' (no rank command sent), 'fresh' (both ranks at a fresh request
    reset, nothing applied), 'partial' (some rank applied: the caller must RESET again), 'unchanged' (save: live state
    intact)."""
    def __init__(self,message,engine='untouched'):
        super().__init__(message);self.engine=engine

def tokens_sha256(tokens):return hashlib.sha256(struct.pack(f'<{len(tokens)}i',*tokens)).hexdigest()
def session_id(tokens):return tokens_sha256(tokens)[:32]

def session_identity(t):
    """What a parked session must match to be restored into this engine (the ranks check their own identity again)."""
    plan=t.plan
    env=[{k:v for k,v in e.items() if k not in ('SYCL_CACHE_DIR','NEO_CACHE_DIR','XDG_CACHE_HOME')} for e in plan['environment']]
    return dict(binary_sha256=plan['binary_sha256'],build_receipt_sha256=plan['build_receipt_sha256'],target_split=TARGET_SPLIT,
                context=plan['context'],prefill_rows=PREFILL_ROWS,activations=ACTIVATIONS,dispatch_sha256=sha(DISPATCH) if DISPATCH else None,
                service_flags=list(plan['service_flags']),rank_environment_sha256=hashlib.sha256(json.dumps(env,sort_keys=True).encode()).hexdigest())

class SessionLock:
    def __init__(self,root,sid,exclusive):self.path=Path(root)/f'{sid}.lock';self.exclusive=exclusive;self.fd=None
    def __enter__(self):
        fd=os.open(self.path,os.O_RDWR|os.O_CREAT|os.O_CLOEXEC|os.O_NOFOLLOW,0o600)
        try:fcntl.flock(fd,(fcntl.LOCK_EX if self.exclusive else fcntl.LOCK_SH)|fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd);raise SessionRefused('session locked by another holder: '+self.path.name)
        self.fd=fd;return self
    def __exit__(self,*exc):
        fcntl.flock(self.fd,fcntl.LOCK_UN);os.close(self.fd);self.fd=None

def _durable(path,data):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_CLOEXEC|os.O_NOFOLLOW,0o600)
    try:
        view=memoryview(data)
        while view:view=view[os.write(fd,view):]
        os.fsync(fd)
    finally:os.close(fd)

def _fsync_dir(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
    try:os.fsync(fd)
    finally:os.close(fd)

def _tree_bytes(path):return sum(f.stat().st_size for f in Path(path).rglob('*') if f.is_file())

def _checkpoint_ops(t,op,per_rank):
    """One checkpoint op on the given ranks, issued to both before either reply is read. per_rank: {rank: dict(position,
    token, fixture, metadata=[lines] or None)}. Returns {rank: dict(ok, ...)}; a rank that fails (not a refusal) raises."""
    require(not any(t.pending),'checkpoint op while a rank is busy')
    for rank,a in per_rank.items():
        if a.get('metadata') is not None:
            text=''.join(line+'\n' for line in a['metadata']);require(text.count('\n')==len(a['metadata']),'checkpoint metadata newline')
            with (t.out/f'rank{rank}'/f'checkpoint-{t.seq[rank]+1}.txt').open('x') as f:f.write(text)
        t.start(rank,op,a.get('token',0),a['position'],a.get('fixture',0))
    replies={}
    for rank in per_rank:
        # The sealed base receive() admits only status 0 and a slot-sized payload; checkpoint replies carry byte counts.
        values=BASE.REPLY.unpack(t.io(rank));t.pending[rank]=False
        require(values[4]==t.seq[rank] and values[5]==rank,'checkpoint reply sequence/identity')
        if values[0]==0 and values[2]==0:
            replies[rank]=dict(ok=True,token=values[1],bytes=values[3],blobs=values[6],checked=values[7],busy_ms=values[8])
            continue
        require(values[0]==2 and values[2]==op,f'rank {rank} failed checkpoint op {op} (status {values[0]}, error {values[2]})')
        receipt=t.request_output/f'rank{rank}'/f'checkpoint-refused-{t.seq[rank]}.json'
        replies[rank]=dict(ok=False,reason=json.loads(receipt.read_text()).get('reason') if receipt.exists() else 'refusal receipt missing')
    return replies

def _refusals(replies):return {r:x['reason'] for r,x in replies.items() if not x['ok']}

def session_inspect(path,lock=True):
    """Manifest of a published session after cheap integrity checks (manifest/token binding, reverse slot hash, both rank
    bundle seals). The ranks verify every payload byte again at VERIFY. Raises SessionRefused."""
    path=Path(path);sid=path.name
    ctx=SessionLock(path.parent,sid,False) if lock else None
    if ctx:ctx.__enter__()
    try:
        try:m=json.loads((path/'manifest.json').read_text())
        except (OSError,ValueError) as e:raise SessionRefused(f'session manifest unreadable: {e}')
        ok=(m.get('schema')==SESSION_SCHEMA and m.get('id')==sid and type(m.get('tokens')) is list and len(m['tokens'])==m.get('position')
            and tokens_sha256(m['tokens'])==m.get('tokens_sha256') and session_id(m['tokens'])==sid)
        if not ok:raise SessionRefused('session manifest/token binding')
        rev=m['reverse']
        try:row=(path/rev['file']).read_bytes()
        except OSError as e:raise SessionRefused(f'session reverse slot unreadable: {e}')
        if len(row)!=SESSION_SLOT or hashlib.sha256(row).hexdigest()!=rev['sha256'] or rev['ready']!=m['position']:raise SessionRefused('session reverse slot')
        for r in ('0','1'):
            try:seal=(path/m['ranks'][r]['directory']/'state-seal.txt').read_bytes()
            except (OSError,KeyError) as e:raise SessionRefused(f'session rank {r} bundle: {e!r}')
            if hashlib.sha256(seal).hexdigest()!=m['ranks'][r]['seal_sha256']:raise SessionRefused(f'session rank {r} seal differs from the manifest')
        return m
    finally:
        if ctx:ctx.__exit__(None,None,None)

def session_list(root):
    """[(path, manifest or None, error or None)] for every published session under root (staging directories skipped)."""
    out=[]
    for p in sorted(Path(root).iterdir()):
        if p.name.startswith('.') or not p.is_dir():continue
        try:out.append((p,session_inspect(p),None))
        except SessionRefused as e:out.append((p,None,str(e)))
    return out

def session_save(t,root,tokens,pending):
    """Park the live state (positions [0, N) = tokens, pending token not yet stepped) as root/<id>. Phase 1: STAGE both
    ranks into a private staging directory and copy the shared-map reverse slot; phase 2: manifest.json last, then one
    rename publishes. The live engine state is never changed (STAGE only reads). Raises SessionRefused(engine='unchanged')."""
    root=Path(root);tokens=[int(x) for x in tokens];N=len(tokens)
    require(1<=N<t.plan['context'] and all(0<=x<248320 for x in tokens) and type(pending) is int and 0<=pending<248320,'session token state bounds')
    require(not any(t.pending),'session save while a rank is busy')
    ready=struct.unpack_from('<I',t.mapping,SESSION_READY)[0]
    if ready!=N:raise SessionRefused(f'reverse_ready {ready} != position {N}: not at a request boundary',engine='unchanged')
    identity=session_identity(t);sid=session_id(tokens);final=root/sid;digest=tokens_sha256(tokens)
    try:lock=SessionLock(root,sid,True).__enter__()
    except SessionRefused as e:e.engine='unchanged';raise
    try:
        if final.exists():
            try:
                m=session_inspect(final,lock=False)
                if m['identity']==identity and m['tokens']==tokens and m['pending_token']==pending:os.utime(final);return m
            except SessionRefused:pass
            shutil.rmtree(final)  # broken, or another engine identity: replace
        staging=root/f'.{sid}.staging'
        if staging.exists():shutil.rmtree(staging)
        staging.mkdir(mode=0o700)
        try:
            tag='sc117.'+digest;started=time.monotonic()
            replies=_checkpoint_ops(t,STAGE_OP,{0:dict(position=N,token=pending,fixture=0,metadata=[str(staging/'rank0'),tag]),
                                                1:dict(position=N,token=pending,fixture=1,metadata=[str(staging/'rank1'),tag])})
            if _refusals(replies):raise SessionRefused('stage refused: '+json.dumps(_refusals(replies)),engine='unchanged')
            stage_ms=(time.monotonic()-started)*1000
            row=bytes(t.mapping[SESSION_REVERSE:SESSION_REVERSE+SESSION_SLOT]);_durable(staging/'reverse.bin',row)
            receipt=t.request_output/'rank0'/f'checkpoint-stage-{t.seq[0]}.json'
            draft_position=json.loads(receipt.read_text()).get('draft_position') if receipt.exists() else None
            ranks={str(r):dict(directory=f'rank{r}',seal_sha256=hashlib.sha256((staging/f'rank{r}'/'state-seal.txt').read_bytes()).hexdigest(),
                               bundle_bytes=_tree_bytes(staging/f'rank{r}'),saved_bytes=replies[r]['bytes'],saved_blobs=replies[r]['blobs'],
                               stage_ms=replies[r]['busy_ms']) for r in (0,1)}
            m=dict(schema=SESSION_SCHEMA,id=sid,created_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),identity=identity,position=N,
                   tokens=tokens,tokens_sha256=digest,pending_token=pending,pending_convention=PENDING_CONVENTION,draft_position=draft_position,
                   reverse=dict(file='reverse.bin',bytes=SESSION_SLOT,sha256=hashlib.sha256(row).hexdigest(),ready=N),ranks=ranks,
                   bytes=_tree_bytes(staging)+len(json.dumps(tokens)),stage_wall_ms=stage_ms)
            _durable(staging/'manifest.json',(json.dumps(m,indent=1)+'\n').encode())
            _fsync_dir(staging);os.rename(staging,final);_fsync_dir(root)
            return m
        except BaseException:
            shutil.rmtree(staging,ignore_errors=True);raise
    finally:lock.__exit__(None,None,None)

def session_restore(t,path,destination,readback=False):
    """Restore a parked session into both ranks: inspect (shared lock held throughout), RESET into `destination`, VERIFY
    both, APPLY both only if both verified, then the shared map exactly as redirect() leaves it (reverse_ready and the
    reverse slot; everything else zero). Returns dict(position, pending_token, tokens, id, ...). The next request must
    run the native continuation with start = position. Raises SessionRefused with engine 'untouched'/'fresh'/'partial'."""
    path=Path(path);sid=path.name
    with SessionLock(path.parent,sid,False):
        m=session_inspect(path,lock=False)
        if m['identity']!=session_identity(t):raise SessionRefused('session identity differs from this engine')
        N=m['position']
        if not 1<=N<t.plan['context']:raise SessionRefused('session position outside this engine context')
        row=(path/'reverse.bin').read_bytes()
        if hashlib.sha256(row).hexdigest()!=m['reverse']['sha256']:raise SessionRefused('session reverse slot changed')
        if any(t.pending):raise SessionRefused('a rank is busy')
        reset(t,destination)  # op 11 on both ranks, fresh shared map: from here on the engine is at a fresh request
        tag='sc117.'+m['tokens_sha256'];started=time.monotonic()
        v=_checkpoint_ops(t,VERIFY_OP,{r:dict(position=N,token=m['pending_token'],metadata=[str(path/m['ranks'][str(r)]['directory']),tag]) for r in (0,1)})
        if _refusals(v):raise SessionRefused('verify refused: '+json.dumps(_refusals(v)),engine='fresh')
        verify_ms=(time.monotonic()-started)*1000;started=time.monotonic()
        a=_checkpoint_ops(t,APPLY_OP,{r:dict(position=N,fixture=1 if readback else 0) for r in (0,1)})
        if _refusals(a):raise SessionRefused('apply refused: '+json.dumps(_refusals(a)),engine='partial' if any(x['ok'] for x in a.values()) else 'fresh')
        apply_ms=(time.monotonic()-started)*1000
        require(not any(t.mapping[SESSION_READY:SESSION_READY+4]) and not any(t.mapping[SESSION_REVERSE:SESSION_REVERSE+SESSION_SLOT]),'shared map not fresh after reset')
        t.mapping[SESSION_REVERSE:SESSION_REVERSE+SESSION_SLOT]=row;struct.pack_into('<I',t.mapping,SESSION_READY,N)
        os.utime(path)  # LRU recency
        return dict(id=sid,position=N,pending_token=m['pending_token'],tokens=m['tokens'],verify_ms=verify_ms,apply_ms=apply_ms,
                    held_bytes=sum(x['bytes'] for x in v.values()),uploaded_bytes=sum(x['bytes'] for x in a.values()),readback=readback)

def session_delete(path):
    """Remove a parked session under its exclusive lock. False if another holder has it locked."""
    path=Path(path);sid=path.name
    try:lock=SessionLock(path.parent,sid,True).__enter__()
    except SessionRefused:return False
    try:
        if path.exists():shutil.rmtree(path)
        (path.parent/f'{sid}.lock').unlink(missing_ok=True)
        return True
    finally:lock.__exit__(None,None,None)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--plan',action='store_true',required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--mini',action='store_true');ap.add_argument('--evidence-output',type=Path);ap.add_argument('--max-new',type=int,default=4);ap.add_argument('--seconds',type=int,default=1800)
    a=ap.parse_args();print(json.dumps(build_plan(a.output,mini=a.mini,max_new=a.max_new,seconds=a.seconds,evidence_output=a.evidence_output),indent=2))
if __name__=='__main__':main()
