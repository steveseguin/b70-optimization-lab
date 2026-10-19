"""Compile only the changed entry, reusing hash-bound 58ah composition objects."""
import hashlib,importlib.util,json,os,resource,shutil,subprocess,time
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];B=P/'build'
BASE=P/'frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port'
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n')
def limits():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
    assert shutil.disk_usage('/').free>=30_000_000_000,'STOP: root below 30 GB'
    assert sum(f.stat().st_size for f in B.rglob('*') if f.is_file())<=300_000_000,'build above 300 MB'
def compiler_turn():
    s=importlib.util.spec_from_file_location('p58aj_compile_turn',P.parents[1]/'ops/compile_turn.py')
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m.turn()
def wait_predecessors():
    # Owner priority: the two-card packet preparations get their compiler turns
    # first. Waiting itself has no wall deadline that can count frozen time.
    packets=('packet151-sibling-cost','packet153-snapshot-host')
    last=None
    while True:
        missing=[n for n in packets if not (P.parent/n/'READY-FOR-DEVICE.json').is_file()]
        if not missing:return
        if missing!=last:print('Waiting for two-card preparation markers:',missing,flush=True);last=missing
        time.sleep(5)
def main():
    wait_predecessors();limits()
    old=str(P.parent/'packet58ag-onecard-ports');commands=[]
    original=json.loads((P/'lineage/58ag-build-commands.json').read_text())
    for mode in ('gnu-host','device'):
        for row in original:
            if row['name'] not in (mode+'-entry-main',mode+'-own-rt-iq3'):continue
            cmd=[a.replace(old,str(P)) for a in row['command']]
            with compiler_turn(),(B/(row['name']+'-resident.log')).open('w') as log:
                limits();subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True)
            commands.append(dict(name=row['name'],command=cmd));print(row['name'],'PASS',flush=True)
    artifacts={str(f.relative_to(P)):sha(f) for mode in ('gnu-host','device') for f in (B/mode).glob('*') if f.name in ('own-rt-iq3','fullshape-submit','p58-cache-fixtures')}
    save(P/'evidence/build.json',dict(passed=True,device_executed=False,commands=commands,artifacts=artifacts,peak_child_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024))
    limits()
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
