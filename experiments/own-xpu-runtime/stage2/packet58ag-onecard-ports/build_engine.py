"""Rebuild only the entry, owner and exact packet60 port; CPU compilation only."""
import hashlib,importlib.util,json,os,resource,shlex,shutil,subprocess,time
from pathlib import Path
from native_source import P,ROOT,BASE,generate
from frozen_inputs import FROZEN
B=P/'build'
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n')
def limits():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
    assert shutil.disk_usage('/').free>=25_000_000_000,'root below 25 GB'
    assert sum(f.stat().st_size for f in B.rglob('*') if f.is_file())<=300_000_000,'build above 300 MB'
def compiler_turn():
    path=P.parents[1]/'ops/compile_turn.py';s=importlib.util.spec_from_file_location('p58ag_packet58ab_compile_turn',path)
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m.turn()
def translate(arg):
    old=str(P.parent/'packet58x-cache-capacity')
    arg=arg.replace(old,str(P))
    root=str(ROOT)+'/experiments/'
    if root in arg and str(P) not in arg:arg=arg.replace(root,str(FROZEN)+'/experiments/')
    return arg

def main():
    from frozen_inputs import restore
    assert not (P/"READY-FOR-DEVICE.json").exists() and not (P/"evidence/card0-ports-a").exists(),"sealed or started packet"
    restore();limits();native=generate();commands=[];sources={};artifacts={}
    previous=json.loads((P/'evidence/build.json').read_text()) if (P/'evidence/build.json').exists() else {}
    checked=BASE/'build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port'
    # p60 uses exactly this line's arithmetic headers; no packet56 mutable include.
    from hc_source import prepare
    prepare()
    original=json.loads((P/'lineage/base-commands.json').read_text())
    for mode in ('gnu-host','device'):
        dest=B/mode;dest.mkdir(parents=True,exist_ok=True)
        jobs=[dict(name=r['name'],command=[translate(a) for a in r['command']]) for r in original if r['name'].startswith(mode)]
        compile_cmd=jobs[0]['command'];includes=['-I'+str(checked),'-I'+str(checked.parents[2]/'stage1/packet3-prep/src')]
        for job in jobs:
            cmd=job['command']
            if '-c' in cmd:
                cmd[1:1]=includes
            else:
                cmd.insert(cmd.index('-o'),str(dest/'p60_submit.o'));cmd.insert(cmd.index('-o'),str(dest/'p58ag_submit.o'))
        p60=compile_cmd.copy();p60[p60.index('-o')+1]=str(dest/'p60_submit.o');p60[p60.index('-c')+1]=str(native/'p60_submit.cpp')
        p60[p60.index('-MF')+1]=str(dest/'p60_submit.d')
        extra=p60.copy();extra[extra.index('-o')+1]=str(dest/'p58ag_submit.o');extra[extra.index('-c')+1]=str(native/'p58ag_submit.cpp');extra[extra.index('-MF')+1]=str(dest/'p58ag_submit.d')
        jobs.insert(0,dict(name=mode+'-p58ag_submit',command=extra))
        jobs.insert(0,dict(name=mode+'-p60_submit',command=p60))
        for job in jobs:
            name,cmd=job['name'],job['command'];limits();start=time.monotonic()
            reused=False
            if '-c' in cmd and '-MF' in cmd:
                dep=Path(cmd[cmd.index('-MF')+1]);obj=Path(cmd[cmd.index('-o')+1])
                if dep.exists() and obj.exists() and any(r['name']==name and r['command']==cmd for r in previous.get('commands',[])):
                    paths=[Path(n).resolve() for n in shlex.split(dep.read_text().replace('\\\n',' '))[1:]]+[obj]
                    reused=all(p.is_relative_to(ROOT) and previous.get('sources',{}).get(str(p.relative_to(ROOT)))==sha(p) for p in paths)
            if not reused:
                with compiler_turn(),(B/(name+'.log')).open('w') as log:
                    subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1200)
            commands.append(dict(name=name,command=cmd,seconds=time.monotonic()-start,reused_verified_object=reused));save(B/'commands-progress.json',commands)
            print(name,'verified reuse' if reused else 'PASS',flush=True)
            if '-c' not in cmd:artifacts[str(Path(cmd[cmd.index('-o')+1]).relative_to(P))]=sha(cmd[cmd.index('-o')+1])
        for dep in dest.glob('*.d'):
            for name in shlex.split(dep.read_text().replace('\\\n',' '))[1:]:
                path=Path(name).resolve()
                if path.is_relative_to(ROOT):sources[str(path.relative_to(ROOT))]=sha(path)
        for cmd in [j['command'] for j in jobs]:
            for a in cmd:
                if a.endswith('.o') and Path(a).exists():sources[str(Path(a).resolve().relative_to(ROOT))]=sha(a)
    for mode in ('gnu-host','device'):
        src=BASE/'build'/mode/'p58-cache-fixtures';out=B/mode/'p58-cache-fixtures'
        shutil.copy2(src,out);artifacts[str(out.relative_to(P))]=sha(out)
    for f in [*native.glob('*'),*P.glob('native/*'),*P.glob('sources/*'),P/'build_engine.py',P/'native_source.py']:
        if f.is_file():sources[str(f.relative_to(ROOT))]=sha(f)
    limits();save(P/'evidence/build.json',dict(passed=True,device_executed=False,sources=sources,artifacts=artifacts,commands=commands,
        parent_relinks=[],max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
