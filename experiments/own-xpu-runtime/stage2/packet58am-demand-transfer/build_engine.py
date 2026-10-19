"""One compiler at a time, private checked 58ah closure, no device access."""
import importlib.util,json,os,resource,shutil,subprocess,time,shlex
from pathlib import Path
from prepare import P, ROOT, AG, sha, save, destination
B=P/'build'
def limits():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
    assert shutil.disk_usage('/').free>=27_000_000_000,'CPU preparation root floor 27 GB'
    assert sum(f.stat().st_size for f in P.rglob('*') if f.is_file())<300_000_000,'300 MB total preparation budget'
def compiler_turn():
    spec=importlib.util.spec_from_file_location('compile_turn',P.parents[1]/'ops/compile_turn.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m.turn()
def translate(arg):
    # Resolve symlinked object inputs against the BEFORE manifest, then use a
    # private byte copy. Text includes already point into the private closure.
    prefix='-I' if arg.startswith('-I') else ''
    value=arg[len(prefix):]
    if value.startswith(str(ROOT)+'/'):
        p=Path(value)
        if str(p).startswith(str(AG/'build')) and (p.suffix in ('.o','.d') or p.name in ('own-rt-iq3','fullshape-submit')):
            return prefix+str(B/p.relative_to(AG/'build'))
        dst=destination(p)
        if not dst.exists() and p.exists():dst=destination(p.resolve())
        return prefix+str(dst)
    return arg
def run(cmd,name):
    limits();start=time.monotonic();log=B/(name+'.log');log.parent.mkdir(parents=True,exist_ok=True)
    with compiler_turn(),log.open('w') as f:
        subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,
          preexec_fn=lambda:resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3)))
    print(name,'PASS',round(time.monotonic()-start,2),flush=True)
    return dict(name=name,command=cmd,seconds=time.monotonic()-start)
def main():
    from generate import generate
    generate();commands=[]
    original=json.loads((P/'lineage/parent-build-commands.json').read_text())
    for mode in ('gnu-host','device'):
        (B/mode).mkdir(parents=True,exist_ok=True)
        for row in original:
            name=row['name']
            if not name.startswith(mode+'-') or name.endswith('fullshape-submit'):continue
            cmd=[translate(a) for a in row['command']]
            if '-c' in cmd:
                source=Path(cmd[cmd.index('-c')+1]);local=B/'native'/source.name
                cmd[cmd.index('-c')+1]=str(local)
            commands.append(run(cmd,name))
            save(P/'evidence/build-progress.json',commands)
    sources={}
    for dep in B.glob('*/*.d'):
        for item in shlex.split(dep.read_text().replace('\\\n',' '))[1:]:
            path=Path(item).resolve()
            if path.is_relative_to(ROOT):
                assert path.is_relative_to(P),'mutable sibling compile dependency: '+str(path)
                sources[str(path.relative_to(P))]=sha(path)
    for path in list((P/'native').glob('*'))+list(P.glob('*.py')):
        if path.is_file():sources[str(path.relative_to(P))]=sha(path)
    save(P/'evidence/build.json',dict(passed=True,commands=commands,device_executed=False,sources=sources,
         max_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024,
         artifacts={str(f.relative_to(P)):sha(f) for f in B.glob('*/own-rt-iq3')}))
if __name__=='__main__':main()
