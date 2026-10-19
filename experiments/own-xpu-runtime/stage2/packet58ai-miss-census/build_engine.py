"""CPU-only compile of the current record entry, backend and diagnostic expert TU."""
import hashlib,importlib.util,json,os,resource,shutil,subprocess,time
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
B=P/'build'
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,row):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(row,indent=2)+'\n')
def limits():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
    assert shutil.disk_usage('/').free>=27_000_000_000,'root below 27 GB'
    assert sum(p.stat().st_size for p in B.rglob('*') if p.is_file())<=300_000_000,'build exceeds 300 MB'
def turn():
    spec=importlib.util.spec_from_file_location('p58ai_compile_turn',P.parents[1]/'ops/compile_turn.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m.turn()
def main():
    limits();mapping={k:Path(v) for k,v in json.loads((P/'lineage/source-map.json').read_text()).items()}
    def get(name):return next(v for k,v in mapping.items() if Path(k).name==name)
    original=json.loads((P/'lineage/58ab-commands.json').read_text());commands=[];inputs={};artifacts={}
    for mode in ('gnu-host','device'):
        dest=B/mode;dest.mkdir(parents=True,exist_ok=True)
        jobs=[]
        entry=next(r['command'] for r in original if r['name']==mode+'-entry-main')
        for name in ['entry-main','expert']+(['single_device'] if mode=='device' else []):
            cmd=entry.copy()
            # Includes are absolute and closed in the source snapshot; no mutable sibling includes.
            cmd=[x for x in cmd if not x.startswith('-I')]
            cmd[cmd.index('-c')+1]=str(get({'entry-main':'entry-main.cpp','expert':'p49d_expert_submit.cpp','single_device':'single_device.cpp'}[name]))
            cmd[cmd.index('-o')+1]=str(dest/(name+'.o'))
            cmd[cmd.index('-MF')+1]=str(dest/(name+'.d'))
            jobs.append((name,cmd))
        link=next(r['command'] for r in original if r['name']==mode+'-own-rt-iq3').copy()
        link[link.index('-o')+1]=str(dest/'own-rt-iq3')
        for i,x in enumerate(link):
            if x.endswith('/entry-main.o'):link[i]=str(dest/'entry-main.o')
            elif x.endswith('/p49d_expert_submit.cpp.o'):link[i]=str(dest/'expert.o')
            elif mode=='device' and x.endswith('/single_device.o'):link[i]=str(dest/'single_device.o')
            elif x.endswith('.o'):
                assert Path(x).is_file(),x
                inputs[str(Path(x).resolve().relative_to(ROOT))]=sha(x)
                link[i]=str(Path(x).resolve())
        jobs.append(('own-rt-iq3',link))
        for name,cmd in jobs:
            limits();start=time.monotonic()
            with turn(),(B/(mode+'-'+name+'.log')).open('w') as log:
                cp=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=900)
            commands.append(dict(name=mode+'-'+name,command=cmd,returncode=cp.returncode,seconds=time.monotonic()-start))
            save(B/'commands-progress.json',commands)
            if cp.returncode:raise RuntimeError('compile failed: '+name)
            print(mode,name,'PASS',flush=True)
        artifacts[str((dest/'own-rt-iq3').relative_to(P))]=sha(dest/'own-rt-iq3')
        src=P.parent/'packet58ad-onecard-record/build'/mode/'p58-cache-fixtures'
        shutil.copy2(src,dest/'p58-cache-fixtures');artifacts[str((dest/'p58-cache-fixtures').relative_to(P))]=sha(dest/'p58-cache-fixtures')
    save(P/'evidence/build.json',dict(passed=True,device_executed=False,commands=commands,artifacts=artifacts,immutable_binary_inputs=inputs,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
