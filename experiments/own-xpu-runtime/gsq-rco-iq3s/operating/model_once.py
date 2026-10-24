#!/usr/bin/env python3
"""One explicit real-model comparison. No service changes, retries or hard kills."""
import argparse, hashlib, importlib.util, json, os, resource, signal, stat, time
from pathlib import Path
P=Path(__file__).resolve().parent;L=P.parent;R=P.parents[3]
CONTROL=Path('/home/steve/own-xpu-runtime-results/gsq-model-a.control')
EVIDENCE=Path('/mnt/usb-models/own-xpu-runtime-results/gsq-model-a')
UNIT='gsq-model-a.service';BDFS=('0000:23:00.0','0000:47:00.0')
VISION=(3487303,63453537);VISION_BDFS={'0000:27:00.0','0000:43:00.0'}
PROMPT=P/'first-model-prompt.json';BASELINE=P/'host-after-model-stop.json'
COORD=Path('/home/steve/own-xpu-runtime-results/coordination/chain-lanes-v1')
MARKERS=tuple(COORD/n for n in ('active-lane-A.json','active-lane-B.json','hold-lane-B'))
STOP=[]
def require(ok,message):
    if not ok:raise RuntimeError(message)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':')).encode()
def load(p,name):
    s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def read_json(p):
    p=Path(p);require(p.is_file() and not p.is_symlink() and p.stat().st_size<=2*1024**2,'bounded regular JSON required')
    return json.loads(p.read_text())
OBS=load(P/'observe.py','gsq_model_observer')
ADAPTER=load(L/'serving/adapter.py','gsq_model_adapter')
def record(name,value,exclusive=False):
    raw=json.dumps(value,indent=2).encode()+b'\n';require(len(raw)<=2*1024**2,'bounded coordinator record')
    target=CONTROL/name;temporary=CONTROL/(name+'.tmp')
    if exclusive:require(not target.exists(),'one-shot evidence already exists')
    fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        os.replace(temporary,target)
        d=os.open(CONTROL,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(d)
        finally:os.close(d)
    except BaseException:
        # Keep interrupted bytes; no retry or silent overwrite.
        raise

def pause_pins():
    q=R/'experiments/own-xpu-runtime/ops/lane-queue'
    return {str(q/f'PAUSE-{lane}'):sha(q/f'PAUSE-{lane}') for lane in ('A','B')}
def prompt_tokens(obj):
    tokens=obj.get('tokens',obj.get('token_ids'))
    require(type(tokens)is list and tokens and all(type(t)is int and 0<=t<248320 for t in tokens),'prompt token IDs')
    require(obj.get('max_new',obj.get('max_new_tokens'))==32 and len(tokens)+32<=4096,'fixed 32-token request bound')
    return tokens

def coordination_clear():
    require(not any(os.path.lexists(p) for p in MARKERS),'coordination ownership/hold marker remains')

def build_plan():
    coordination_clear()
    require(CONTROL.is_dir() and not CONTROL.is_symlink() and CONTROL.resolve()==CONTROL,'canonical control parent')
    st=CONTROL.stat();require(st.st_uid==os.getuid() and stat.S_IMODE(st.st_mode)==0o700,'private owned control parent')
    require(not (CONTROL/'admission.json').exists() and not (CONTROL/'terminal.json').exists(),'fresh one-shot control parent')
    baseline=read_json(BASELINE);prompt=read_json(PROMPT);tokens=prompt_tokens(prompt)
    require(baseline['known_fault_baseline_matches'] and not baseline['identity_races'],'reviewed complete baseline')
    require(baseline['holders'][str(VISION[0])]['start_ticks']==VISION[1],'fixed vision identity')
    for lane in ('A','B'):
        q=baseline['queue'][lane];require(q['queue']=='' and q['STOP'] is None and q['inflight'] is None,'empty queue baseline')
    adapter=ADAPTER.build_plan(CONTROL/'ranks',mini=False,max_new=32,seconds=7200,evidence_output=EVIDENCE)
    ledger=read_json(L/'memory/engine-accounting.json')
    need=sum(x['device_logical_bytes'] for x in ledger['scenarios']['split24-24_mtp-rank0']['ranks'])+ledger['host_file_backing_bytes']+8*1024**3
    files=[Path(__file__),P/'observe.py',BASELINE,PROMPT,L/'serving/adapter.py',L/'serving/evidence/host-pair.json',L/'memory/engine-accounting.json',P/'host-before-stop.json',R/'experiments/own-xpu-runtime/ops/packet196-window/passive_device_holders.py',R/'experiments/own-xpu-runtime/stage1/packet4-prep/driver/window_driver.py']
    return dict(schema='ownrt.gsq.model-once-plan.v1',unit=UNIT,adapter=adapter,prompt=tokens,max_new=32,requests=2,source_sha256={str(f):sha(f) for f in files},pause_sha256=pause_pins(),baseline_sha256=sha(BASELINE),expected_vision=list(VISION),target_bdfs=list(BDFS),control_identity=[st.st_dev,st.st_ino,st.st_uid,st.st_mode],initial_mem_available_required=need,continuous_mem_available_required=8*1024**3,root_floor_bytes=27000000000,unit_properties={'Restart':'no','SendSIGKILL':'no','KillMode':'process','TimeoutStopUSec':'infinity','LimitAS':'infinity','LimitCORE':'0'},nice=19,affinity=[0,1,2,3,16,17,18,19],native_admitted=False,storage_mode='monitored forecast; not hard quota',no_retry=True,no_service_changes=True)

def unit_status(plan):
    fields=['MainPID','ActiveState',*plan['unit_properties']]
    text=OBS.command(['systemctl','--user','show',UNIT,'--property='+','.join(fields)])
    row=dict(line.split('=',1) for line in text.splitlines() if '=' in line)
    require(row.get('MainPID')==str(os.getpid()) and row.get('ActiveState')=='active','coordinator unit/PID identity')
    for k,v in plan['unit_properties'].items():require(row.get(k)==v,'unsafe coordinator unit property '+k)
    return row

class Monitor:
    def __init__(self,plan):
        self.plan=plan;self.before=read_json(BASELINE);self.started=time.monotonic();self.last=0.;self.identities=[];self.contacts=[False,False];self.first=None;self.latest=None;self.samples=0;self.unit=None
        self.target={b:OBS.target_nodes(self.before,b) for b in BDFS}
        self.vision_nodes={h['node'] for h in self.before['inventory']['holders'] if h['pid']==VISION[0]}
        require(self.vision_nodes,'vision baseline contact')
    def latch(self,error):
        if self.first is None:self.first=error
    def register(self,pid):
        require(len(self.identities)<2,'only two owner launches')
        identity=OBS.process_identity(pid);require(identity is not None,'new rank identity unavailable')
        self.identities.append((pid,identity['start_ticks']));self.last=0
        record('registered-ranks.json',dict(identities=self.identities,expected_bdfs=BDFS))
    def validate(self,s,initial=False):
        coordination_clear()
        require(not s['identity_races'] and not s['inventory']['errors'],'complete passive process inventory')
        require(s['boot']==self.before['boot'] and s['kernel']['faults']==self.before['kernel']['faults'] and s['known_fault_baseline_matches'],'boot/kernel fault baseline changed')
        require(s['drm']==self.before['drm'],'DRM alias/topology changed')
        require(s['queue']==self.before['queue'],'queue/PAUSE/STOP/inflight changed')
        for f,h in self.plan['pause_sha256'].items():require(sha(f)==h,'PAUSE bytes changed')
        require(s['units']['qwen38-27b-vision']==self.before['units']['qwen38-27b-vision'],'preserved vision unit changed')
        v=OBS.process_identity(VISION[0]);require(v is not None and v['start_ticks']==VISION[1] and v['state']!='Z','vision PID/start ticks changed')
        for name in ('qwen38-27b-fp8','qwen38-27b-fp8-tp1-test'):
            u=s['units'][name];require(u['ActiveState']=='inactive' and u['MainPID']=='0','stopped text unit became active')
        require(s['root_free_bytes']>=self.plan['root_floor_bytes'],'root floor crossed')
        require(s['memory']['MemAvailable']>=self.plan['initial_mem_available_required'] if initial else s['memory']['MemAvailable']>=self.plan['continuous_mem_available_required'],'available memory admission/floor')
        vision=set()
        for h in s['inventory']['holders']:
            identity=s['holders'][str(h['pid'])];require(identity is not None,'holder identity unavailable')
            key=(h['pid'],identity['start_ticks']);node=h['node'];require(node in s['drm'],'unclassified DRM holder')
            if key==VISION:
                require(s['drm'][node]['bdf'] in VISION_BDFS,'vision contacted target device');vision.add(node)
            elif key in self.identities:
                rank=self.identities.index(key);require(node in self.target[BDFS[rank]],'rank contacted unexpected physical device');self.contacts[rank]=True
            else:raise RuntimeError('foreign DRM holder: '+str(key)+' '+node)
        require(vision==self.vision_nodes,'preserved vision descriptor set changed')
        for pid,ticks in self.identities:
            now=OBS.process_identity(pid)
            if now is not None:require(now['start_ticks']==ticks,'rank PID reused')
        if initial:require(not self.identities,'initial gate after owner launch')
    def sample(self,initial=False,force=False,draining=False):
        if not force and time.monotonic()-self.last<1:
            if self.first is not None and not draining:raise self.first
            return self.latest
        self.last=time.monotonic();s=None
        try:
            s=OBS.observe();self.latest=s;self.samples+=1
            self.validate(s,initial)
            self.unit=unit_status(self.plan)
            if STOP:raise RuntimeError('coordinator cooperative signal '+str(STOP[0]))
            if time.monotonic()-self.started>self.plan['adapter']['seconds']:raise RuntimeError('coordinator lifetime exceeded')
            if len(self.identities)==2 and all((EVIDENCE/f'rank{r}/census.json').exists() for r in (0,1)):
                require(all(self.contacts),'both native target contacts must be observed before requests')
        except BaseException as error:self.latch(error)
        try:
            record('monitor.json',dict(samples=self.samples,elapsed=time.monotonic()-self.started,latest=s,first_error=repr(self.first) if self.first else None,registered=self.identities,observed_target_contact=self.contacts,unit=self.unit))
        except BaseException as error:self.latch(error)
        if self.first is not None and not draining:raise self.first
        return s
    def check(self):self.sample()
    def drained(self,s,transport=None):
        # Poll every known child before /proc checks: an exited retained child
        # otherwise remains a zombie and cannot satisfy disappearance.
        if transport is not None:
            known_exited=True
            for child in getattr(transport,'children',[]):
                try:known_exited &= child.poll() is not None
                except BaseException:known_exited=False
            if not known_exited or getattr(transport,'spawn_uncertain',False):return False
        if s is None or s['identity_races'] or s['inventory']['errors'] or s['drm']!=self.before['drm']:return False
        targets=set().union(*[set(x) for x in self.target.values()])
        if any(h['node'] in targets for h in s['inventory']['holders']):return False
        if any((i:=OBS.process_identity(pid)) is not None and i['start_ticks']==ticks for pid,ticks in self.identities):return False
        return True

def run(path):
    plan=read_json(path);require(plan==build_plan(),'reviewed plan/source/parent binding changed');ADAPTER.validate_plan(plan['adapter'])
    require(resource.getrlimit(resource.RLIMIT_AS)==(resource.RLIM_INFINITY,resource.RLIM_INFINITY),'unlimited native address space required')
    require(os.getpriority(os.PRIO_PROCESS,0)==plan['nice'] and sorted(os.sched_getaffinity(0))==plan['affinity'],'coordinator priority/affinity')
    require(not (Path('/home/steve')/'igdrcl.config').exists() and not (R/'igdrcl.config').exists(),'unadmitted driver config')
    monitor=Monitor(plan);result=None;retained=None;original=None
    for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,lambda s,f:STOP.append(s) if not STOP else None)
    # Durable initial record and actual host checks precede the sole adapter call.
    monitor.sample(initial=True,force=True);ADAPTER.storage_guard(plan['adapter'])
    record('admission.json',dict(plan=plan,plan_sha256=sha(path),canonical_plan_sha256=hashlib.sha256(canonical(plan)).hexdigest(),before=monitor.latest,unit=monitor.unit),exclusive=True)
    try:
        result=ADAPTER.qualification(plan['adapter'],plan['prompt'],32,admit=lambda p:require(p==plan['adapter'],'adapter admission mismatch'),check=monitor.check,launch_hook=monitor.register)
    except ADAPTER.RetainedOwner as error:
        original=error.original;retained=error.transport;monitor.latch(original)
    except BaseException as error:original=error;monitor.latch(error)
    # Adapter owns the single cooperative stop pipe. Never issue a second signal,
    # retry, release its uncertain handles, or abandon physical-drain monitoring.
    while True:
        s=monitor.sample(force=True,draining=True)
        if monitor.drained(s,retained):
            passed=bool(result and result.get('passed') and monitor.first is None and len(monitor.identities)==2 and all(monitor.contacts))
            terminal=dict(passed=passed,result=result,first_error=repr(monitor.first) if monitor.first else None,original_error=repr(original) if original else None,rank_identities=monitor.identities,observed_target_contact=monitor.contacts,children_exited=True,target_descriptors_empty=True,after=s,elapsed=time.monotonic()-monitor.started,service_changes=0,retries=0,hard_kills=0,speed_claim=False,plan_sha256=sha(path))
            try:record('terminal.json',terminal,exclusive=True)
            except BaseException as error:monitor.latch(error);time.sleep(1);continue
            print(json.dumps({'passed':passed,'terminal':str(CONTROL/'terminal.json')}),flush=True);return 0 if passed else 1
        try:time.sleep(1)
        except BaseException as error:monitor.latch(error)

def main():
    ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--plan',action='store_true');g.add_argument('--run',type=Path);a=ap.parse_args()
    if a.plan:print(json.dumps(build_plan(),indent=2));return 0
    return run(a.run)
if __name__=='__main__':raise SystemExit(main())
