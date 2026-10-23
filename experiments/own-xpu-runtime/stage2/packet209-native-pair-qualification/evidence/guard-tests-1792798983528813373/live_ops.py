"""P209 passive checks plus explicit single-child operations, used only by --run.
No service start/stop/restart or queue/latch changes. The unit is root-launched.
"""
from pathlib import Path
import ast,gzip,hashlib,importlib.util,json,os,re,resource,shutil,signal,stat,subprocess,sys,time
import runner as R
QUEUE=R.ROOT/'experiments/own-xpu-runtime/ops/lane-queue'
COORD=Path('/home/steve/own-xpu-runtime-results/coordination/chain-lanes-v1')
BFDS={'0000:23:00.0','0000:27:00.0','0000:43:00.0','0000:47:00.0'}
PROPS=['ActiveState','SubState','MainPID','ExecMainStartTimestampMonotonic','ControlGroup','Restart','SendSIGKILL','KillMode','TimeoutStopUSec','ExitType','UMask']

def run(argv,timeout=10):
    cp=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=timeout)
    R.require(cp.returncode==0 and not cp.stderr.strip(),'passive command failed: '+argv[0])
    return cp.stdout

def unit(name):
    R.require(re.fullmatch(r'[A-Za-z0-9_.@:-]+',name) is not None,'unit name')
    text=run(['/usr/bin/systemctl','--user','show',name,*['--property='+x for x in PROPS]])
    return dict(line.split('=',1) for line in text.splitlines() if '=' in line)

def process_identity(pid):
    try:fields=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
    except (FileNotFoundError,ProcessLookupError):return None
    return None if fields[0]=='Z' else int(fields[19])

def topology():
    rows={}
    for p in sorted(Path('/sys/class/drm').iterdir()):
        if not re.fullmatch(r'card\d+|renderD\d+',p.name):continue
        if (p/'device/vendor').read_text().strip()!='0x8086':continue
        bdf=(p/'device').resolve(strict=True).name;driver=(p/'device/driver').resolve(strict=True).name
        major,minor=map(int,(p/'dev').read_text().strip().split(':'));node=Path('/dev/dri')/p.name;info=node.stat()
        R.require(driver=='xe' and bdf in BFDS and stat.S_ISCHR(info.st_mode) and info.st_rdev==os.makedev(major,minor),'DRM sysfs/node identity')
        rows[str(node)]={'bdf':bdf,'dev':f'{major}:{minor}','sys_device':str((p/'device').resolve()),'driver':driver}
    R.require(len(rows)==8 and {r['bdf'] for r in rows.values()}==BFDS,'four-card Intel topology')
    for bdf in BFDS:
        names=[Path(k).name for k,v in rows.items() if v['bdf']==bdf]
        R.require(len(names)==2 and sum(n.startswith('card') for n in names)==1 and sum(n.startswith('renderD') for n in names)==1,'card/render aliases')
    return rows

def inventory(m,child=None):
    before=topology()
    with Path('/home/steve/SUDOPASSWORD.txt').open('rb') as secret:
        cp=subprocess.run(['/usr/bin/sudo','-S','-p','','--','/usr/bin/python3','-B',str(R.HELPER)],stdin=secret,capture_output=True,text=True,timeout=30)
    R.require(cp.returncode in (0,1) and not cp.stderr.strip(),'privileged metadata scan failed')
    R.require(len(cp.stdout)<=8*1024*1024,'inventory bound')
    raw=json.loads(cp.stdout,object_pairs_hook=R.no_duplicates)
    R.require(topology()==before,'DRM mapping changed during scan')
    expected={v['dev']:Path(k).name for k,v in before.items()}
    R.require(raw.get('nodes')==expected and raw.get('intel_devices')==sorted({v['sys_device'] for v in before.values()}),'helper/sysfs census mismatch')
    R.require(cp.returncode==(0 if raw.get('passed') else 1),'helper exit/result mismatch')
    ids={h['pid']:process_identity(h['pid']) for h in m['allowed_holders']}
    for h in raw.get('holders',[]):ids[h['pid']]=process_identity(h['pid'])
    try:result=R.classify_inventory(raw,m['target_nodes'],m['allowed_holders'],ids,child)
    except BaseException as error:
        error.passive_evidence={'kind':'DRM-holder-refusal','raw':raw,'topology':before,'identities':ids}
        raise
    return result,raw

def faults_clear(m):
    review=R.read_json(m['fault_review']);R.require(R.sha(m['fault_review'])==m['fault_review_sha256'],'fault receipt changed')
    source=R.P181/'lineage/window_driver.py';patterns={}
    for n in ast.parse(source.read_text()).body:
        if isinstance(n,ast.Assign) and isinstance(n.value,ast.Call):
            for target in n.targets:
                if isinstance(target,ast.Name) and target.id in ('FAULT','DELETED'):patterns[target.id]=re.compile(ast.literal_eval(n.value.args[0]),re.I)
    R.require(set(patterns)=={'FAULT','DELETED'} and review['driver_sha256']==R.sha(source),'fault source binding')
    original=gzip.decompress(Path(review['kernel_capture']).read_bytes()).decode()
    R.require(hashlib.sha256(original.encode()).hexdigest()==review['journal_sha256'],'review full journal binding')
    current=run(['/usr/bin/journalctl','-k','-b','-o','json','--no-pager'])
    rows=[json.loads(line) for line in current.splitlines() if line]
    R.require(rows and all(r.get('_BOOT_ID')==m['boot_id'].replace('-','') for r in rows),'journal boot identity')
    bad=[r for r in rows if patterns['FAULT'].search(str(r.get('MESSAGE',''))) and not patterns['DELETED'].search(str(r.get('MESSAGE','')))]
    oldrows=[json.loads(line) for line in original.splitlines() if line]
    oldbad=[r for r in oldrows if patterns['FAULT'].search(str(r.get('MESSAGE',''))) and not patterns['DELETED'].search(str(r.get('MESSAGE','')))]
    if not (len(bad)==2 and bad==oldbad==review['faults'] and review['boot_id']==m['boot_id']):
        error=RuntimeError('P209: new/unreviewed kernel fault')
        retained=[];used=0
        for row in bad[:32]:
            encoded=json.dumps(row,sort_keys=True).encode()
            if used+len(encoded)>256*1024:break
            retained.append(row);used+=len(encoded)
        error.passive_evidence={'kind':'kernel-fault-refusal','journal_sha256':hashlib.sha256(current.encode()).hexdigest(),'fault_count':len(bad),'faults':retained,'truncated':len(retained)!=len(bad),'review_sha256':m['fault_review_sha256']}
        raise error
    return True

def durable(path,row,exclusive=True):
    data=json.dumps(row,sort_keys=True,indent=2,allow_nan=False)+'\n'
    with path.open('x' if exclusive else 'w') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
    fd=os.open(path.parent,os.O_DIRECTORY|os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)

class LiveOps:
    def __init__(self,m,digest):
        self.m=m;self.digest=digest;self.control=Path(m['output']+'.control');self.child=None;self.child_identity=None;self.spawn_uncertain=False;self.log=None;self.count=0;self.initial_limits={k:resource.getrlimit(getattr(resource,k)) for k in dir(resource) if k.startswith('RLIMIT_')};self.identity_ack=False
        # Frozen imports provide only the established flock/marker protocol.
        sys.path.insert(0,str(R.P181))
        from lane_admission import Reservation
        from drain_gate import DrainPermit
        self.Reservation=Reservation;self.DrainPermit=DrainPermit
        for module in ('lane_admission','drain_gate','chain_devices'):
            R.require(Path(sys.modules[module].__file__).resolve()==(R.P181/(module+'.py')).resolve(),'wrong imported helper origin')
    def snapshot(self,m):
        topo=topology();protected={name:unit(name) for name in m['protected_units']}
        for name,row in protected.items():R.require(row['ActiveState']=='active' and process_identity(int(row['MainPID'])) is not None,'protected application inactive')
        current=unit(R.UNIT)
        mem=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
        return {'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'now_unix':time.time(),
          'pause_sha256':{l:R.sha(QUEUE/f'PAUSE-{l}') for l in ('A','B')},'queue_sha256':{l:R.sha(QUEUE/f'queue-{l}.txt') for l in ('A','B')},
          'queues_empty':all(not (QUEUE/f'queue-{l}.txt').read_text().strip() for l in ('A','B')),
          'stop_present':any(R.present(QUEUE/f'STOP-{l}') or R.present(QUEUE/f'inflight-{l}.json') for l in ('A','B')) or R.present(self.control/'STOP'),
          'competitors_inactive':all(unit(name)['ActiveState'] in ('inactive','failed') for name in m['competitor_units']),
          'protected_units':protected,'target_bdf':R.BDF,'topology':topo,'target_nodes':sorted(k for k,v in topo.items() if v['bdf']==R.BDF),
          'faults_clear':faults_clear(m),'free_bytes':shutil.disk_usage(R.ROOT).free,'mem_available_bytes':int(mem['MemAvailable'].split()[0])*1024,
          'unit_properties':{k:current[k] for k in R.SAFE_UNIT}}
    def preflight(self,m):
        R.require(Path('/proc/sys/kernel/random/boot_id').read_text().strip()==m['boot_id'],'boot mismatch')
        R.require(R.sha(R.MANIFEST)==self.digest and R.sha(R.BINARY)==m['binary_sha256'],'manifest/binary changed')
        R.require(m['source_sha256']==R.source_closure(),'exact reviewed source closure')
        for p,digest in m['source_sha256'].items():
            path=R.ROOT/p;R.require(not Path(p).is_absolute() and path.resolve().is_relative_to(R.ROOT) and R.sha(path)==digest,'source closure '+p)
        R.require(not R.present(R.OUTPUT) and not R.present(self.control),'fresh output/control required')
        R.require(not any(R.present(COORD/f'active-lane-{l}.json') for l in ('A','B')) and not R.present(COORD/'hold-lane-B'),'outstanding coordinator work')
        R.require(resource.getrlimit(resource.RLIMIT_AS)==(resource.RLIM_INFINITY,resource.RLIM_INFINITY),'unlimited native AS required')
        R.require(os.getpriority(os.PRIO_PROCESS,0)==0 and set(os.sched_getaffinity(0))==R.CPUS,'native unit priority/affinity')
        R.require(os.environ.get('HOME')=='/home/steve','HOME unchanged')
        R.require(not R.present(Path('/home/steve/igdrcl.config')) and not R.present(R.ROOT/'igdrcl.config'),'unreviewed driver debug config')
        R.validate_snapshot(m,self.snapshot(m));state,_=inventory(m);R.require(state['target_empty'],'target descriptor holder before launch')
        self.control.mkdir(mode=0o700)
        (self.control/'cache').mkdir(mode=0o700)
        for name in ('sycl','neo','xdg'):(self.control/'cache'/name).mkdir(mode=0o700)
        durable(self.control/'admission.json',{'manifest_sha256':self.digest,'snapshot':self.snapshot(m)})
        self.heartbeat()
    def check(self,m):
        R.require(R.sha(R.MANIFEST)==self.digest,'manifest changed')
        R.require(self.initial_limits=={k:resource.getrlimit(getattr(resource,k)) for k in self.initial_limits},'resource limits changed')
        R.validate_snapshot(m,self.snapshot(m))
        self.heartbeat()
    def heartbeat(self):
        temporary=self.control/'heartbeat.next'
        with temporary.open('w') as stream:stream.write(self.digest+' '+str(time.monotonic()+90)+'\n');stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,self.control/'heartbeat')
    def reservation(self,m):return self.Reservation('A',window='screen',timing_claim=False,check=lambda:self.check(m))
    def drain(self,m,reservation):return self.DrainPermit(R.OUTPUT,check=lambda:self.check(m),reservation=reservation.record)
    def launch(self,m):
        self.log=(self.control/'native.log').open('xb')
        self.spawn_uncertain=True
        self.child=subprocess.Popen([str(R.BINARY),'--authorized-device-window','--manifest',str(R.MANIFEST),'--manifest-sha256',self.digest],cwd=R.ROOT,env=m['environment'],stdin=subprocess.DEVNULL,stdout=self.log,stderr=subprocess.STDOUT)
        self.spawn_uncertain=False
        return self.child
    def observe(self,m,child):
        if self.child_identity is None:
            ticks=process_identity(child.pid);R.require(ticks is not None,'child vanished before identification')
            self.child_identity={'pid':child.pid,'start_ticks':ticks}
        R.require(self.child_identity and process_identity(child.pid) in (self.child_identity['start_ticks'],None),'child PID reused')
        state,raw=inventory(m,self.child_identity)
        return state
    def ack(self,m,child):
        if self.identity_ack:return
        path=self.control/'identity.json'
        if not path.exists():return
        identity=R.read_json(path)
        node=next(n for n in m['target_nodes'] if Path(n).name.startswith('renderD'))
        R.require(identity==dict(self.child_identity,bdf=R.BDF,visible_devices=1,manifest_sha256=self.digest,admission_node=node,admission_dev=m['topology'][node]['dev'],observation_scope='admission-descriptor'),'native identity event')
        fd=os.open(self.control/'ACK',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        try:os.write(fd,(self.digest+'\n').encode());os.fsync(fd)
        finally:os.close(fd)
        self.identity_ack=True
    def result(self,m):
        entry=R.read_json(self.control/'entry-result.json')
        R.require(entry=={'returncode':0,'device_enumerated':True,'fixture_called':True} and self.identity_ack,'entry did not qualify')
        return R.read_json(R.OUTPUT/'result.json')
    def stop(self,m):
        path=self.control/'STOP'
        if not R.present(path):durable(path,{'incident':True,'no_new_native_work':True})
    def diagnose(self,m,child):
        # No admission or fault guard here: passive failure evidence must remain
        # available after STOP/new faults. Never sends further native requests.
        known=child if child is not None else self.child
        if known is None:return {'child_exited':False,'owner_safe':False,'target_empty':False,'spawn_uncertain':self.spawn_uncertain}
        exited=known.poll() is not None
        state,_=inventory(m,None if exited else self.child_identity)
        safe=False
        if exited:
            path=R.OUTPUT/'result.json'
            if path.exists():
                result=R.read_json(path);owner=result.get('teardown')
                safe=result.get('safe_to_exit') is True and isinstance(owner,dict) and owner.get('safe_to_exit') is True and owner.get('in_flight')==0 and owner.get('live_bytes')==0
            elif not R.present(R.OUTPUT) and (self.control/'entry-refusal.json').is_file():
                refusal=R.read_json(self.control/'entry-refusal.json')
                safe=(refusal.get('pid')==known.pid and self.child_identity is not None and refusal.get('start_ticks')==self.child_identity['start_ticks'] and refusal.get('manifest_sha256')==self.digest and refusal.get('fixture_entered') is False and refusal.get('safe_no_owner') is True)
        return {'child_exited':exited,'owner_safe':safe,'target_empty':state['target_empty']}
    def receipt(self,row):
        self.count+=1;durable(self.control/f'coordinator-{self.count:04d}.json',row)
    def secondary(self,error):
        payload=getattr(error,'passive_evidence',None)
        path=self.control/'incident-passive.json'
        if payload is not None and not R.present(path):durable(path,payload)
    def sleep(self,seconds):time.sleep(seconds)
