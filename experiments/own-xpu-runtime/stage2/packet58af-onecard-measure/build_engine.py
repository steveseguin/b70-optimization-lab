"""CPU-only compile through ops/compile_turn; never run a device entry."""
import hashlib,importlib.util,json,os,resource,shlex,shutil,subprocess,time
from pathlib import Path
from measure_source import P,ROOT,X,generate
B=P/'build'
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,row):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(row,indent=2)+'\n')
def limits():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
    assert shutil.disk_usage('/').free>=25_000_000_000
    assert sum(f.stat().st_size for f in B.rglob('*') if f.is_file())<=200_000_000

def turn():
    path=P.parents[1]/'ops/compile_turn.py';spec=importlib.util.spec_from_file_location('p58af_compile_turn',path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m.turn()
def main():
    limits();generate()
    original=json.loads((P/'lineage/snapshot/gates/evidence/build.json').read_text())
    pins={};commands=[];artifacts={};relinks=[]
    # Reproduce BOTH frozen executables before linking new sources to their objects.
    for mode in ('gnu-host','device'):
        dest=B/mode;dest.mkdir(exist_ok=True)
        source_jobs=[r for r in original['commands'] if r['name'].startswith(mode)]
        link=next(r['command'] for r in source_jobs if r['name']==mode+'-own-rt-iq3').copy()
        for a in link:
            if a.endswith('.o'):pins[str(Path(a).relative_to(ROOT))]=sha(a)
        relink=link.copy();relink[relink.index('-o')+1]=str(dest/'parent-relink')
        with turn(),(B/(mode+'-parent-relink.log')).open('w') as log:
            subprocess.run(relink,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
        expected=json.loads((P/'lineage/vendor58z/copy-manifest.json').read_text())['native_artifacts'][f'build/{mode}/own-rt-iq3']
        assert sha(dest/'parent-relink')==expected,'frozen object relink mismatch'
        relinks.append(dict(mode=mode,passed=True,sha256=expected));(dest/'parent-relink').unlink()
        for stem in ('entry-main','expert')+(('single_device',) if mode=='device' else ()):
            job=next(r for r in source_jobs if r['name']==mode+'-'+('entry-main' if stem=='expert' else stem))
            if stem=='expert':job=dict(name=mode+'-expert',command=[a.replace('entry-main','expert') for a in job['command']])
            cmd=[a.replace(str(X),str(P)) for a in job['command']]
            # Eliminate mutable source/include dependencies. Frozen object inputs
            # remain separately hash-bound, proven by the exact parent relink.
            for i,a in enumerate(cmd):
                if a.startswith('-I') and str(ROOT) in a and not str(P) in a:
                    cmd[i]='-I'+str(P/'frozen-inputs/repo'/Path(a[2:]).relative_to(ROOT))
            start=time.monotonic()
            with turn(),(B/(job['name']+'.log')).open('w') as log:
                subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
            commands.append(dict(name=job['name'],command=cmd,seconds=time.monotonic()-start))
            for name in shlex.split((dest/(stem+'.d')).read_text().replace('\\\n',' '))[1:]:
                f=Path(name).resolve()
                if f.is_relative_to(ROOT):pins[str(f.relative_to(ROOT))]=sha(f)
            print(job['name'],'PASS',flush=True)
        for i,a in enumerate(link):
            if a.endswith('/p49d_expert_submit.cpp.o'):link[i]=str(dest/'expert.o')
            if a==str(X/'build'/mode/'entry-main.o') or (mode=='device' and a==str(X/'build'/mode/'single_device.o')):link[i]=a.replace(str(X),str(P))
        assert link.count(str(dest/'expert.o'))==1 and not any(a.endswith('/p49d_expert_submit.cpp.o') for a in link)
        assert link.count(str(dest/'entry-main.o'))==1
        if mode=='device':assert link.count(str(dest/'single_device.o'))==1
        link[link.index('-o')+1]=str(dest/'own-rt-iq3')
        with turn(),(B/(mode+'-link.log')).open('w') as log:
            subprocess.run(link,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
        if mode=='gnu-host':
            full=next(r['command'] for r in source_jobs if r['name']=='gnu-host-fullshape-submit').copy()
            for i,a in enumerate(full):
                if a==str(X/'build'/mode/'entry-main.o'):full[i]=str(dest/'entry-main.o')
                if a.endswith('/p49d_expert_submit.cpp.o'):full[i]=str(dest/'expert.o')
            full[full.index('-o')+1]=str(dest/'fullshape-submit')
            with turn(),(B/'fullshape-link.log').open('w') as log:subprocess.run(full,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
            artifacts['build/gnu-host/fullshape-submit']=sha(dest/'fullshape-submit')
        commands.append(dict(name=mode+'-link',command=link));artifacts[f'build/{mode}/own-rt-iq3']=sha(dest/'own-rt-iq3')
        for leaf in ('p58-cache-fixtures',):
            shutil.copy2(P.parent/'packet58z-onecard-record/build'/mode/leaf,dest/leaf)
            artifacts[f'build/{mode}/{leaf}']=sha(dest/leaf)
        print(mode,'linked',flush=True)
    limits();save(P/'evidence/build-measure.json',dict(passed=True,device_executed=False,sources=pins,artifacts=artifacts,commands=commands,parent_relinks=relinks,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
