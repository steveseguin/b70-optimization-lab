"""Incremental entry-only compilation using hash-bound frozen kernel objects."""
import hashlib,importlib.util,json,os,resource,shlex,shutil,subprocess,time
from pathlib import Path
from native_source import P,ROOT,BASE,generate
B=P/'build'

def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def save(path,row):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(row,indent=2)+'\n')

def limits():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
    assert shutil.disk_usage('/').free>=25_000_000_000,'root below 25 GB'
    assert sum(f.stat().st_size for f in B.rglob('*') if f.is_file())<=200_000_000,'build above 200 MB'

def compiler_turn():
    path=P.parent/'packet94-hc-norm-fusion/compile_turn.py'
    spec=importlib.util.spec_from_file_location('packet94_compile_turn',path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod.turn()

def main():
    limits();native=generate();commands=[];sources={};artifacts={};parent_relinks=[]
    # Source closure is verified against the frozen parent receipt before reuse.
    parent=json.loads((BASE/'build-receipt.json').read_text())
    sources[str((BASE/'build-receipt.json').relative_to(ROOT))]=sha(BASE/'build-receipt.json')
    for name,digest in parent['sources'].items():
        assert sha(ROOT/name)==digest,name
        sources[name]=digest
    for mode in ('gnu-host','device'):
        base=BASE/'build'/mode;dest=B/mode;dest.mkdir(exist_ok=True)
        flags=dict(line.split(' = ',1) for line in (base/'CMakeFiles/programs.dir/flags.make').read_text().splitlines() if ' = ' in line)
        # Reproduce the frozen binary with the exact objects we will reuse.
        # A current object hash alone does not establish parent provenance.
        link_file=base/'CMakeFiles/own-rt-iq3.dir/link.txt'
        frozen=base/'own-rt-iq3';expected=parent['artifacts'][f'build/{mode}/own-rt-iq3']
        assert sha(frozen)==expected,'frozen parent binary changed'
        sources[str(frozen.relative_to(ROOT))]=expected
        sources[str(link_file.relative_to(ROOT))]=sha(link_file)
        relink=shlex.split(link_file.read_text())
        for i,arg in enumerate(relink):
            if arg.endswith('.o'):
                obj=base/arg;relink[i]=str(obj);sources[str(obj.relative_to(ROOT))]=sha(obj)
        reproduced=dest/'parent-relink'
        relink[relink.index('-o')+1]=str(reproduced)
        with compiler_turn(),(B/(mode+'-parent-relink.log')).open('w') as log:
            subprocess.run(relink,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1200)
        actual=sha(reproduced)
        assert actual==expected,'reused objects did not reproduce frozen parent '+mode
        parent_relinks.append(dict(mode=mode,passed=True,command=relink,binary_sha256=actual))
        reproduced.unlink();print(mode,'parent-relink PASS',flush=True)
        compiler='/usr/bin/g++' if mode=='gnu-host' else '/opt/intel/oneapi/compiler/2026.0/bin/icpx'
        compile_cmd=[compiler,*shlex.split(flags['CXX_DEFINES']+' '+flags['CXX_INCLUDES']+' '+flags['CXX_FLAGS']),
            '-MMD','-MF',str(dest/'entry-main.d'),'-o',str(dest/'entry-main.o'),'-c',str(native/'entry-main.cpp')]
        jobs=[(mode+'-entry-main',compile_cmd)]
        for target in (('own-rt-iq3','fullshape-submit') if mode=='gnu-host' else ('own-rt-iq3',)):
            link=shlex.split((base/f'CMakeFiles/{target}.dir/link.txt').read_text())
            for i,arg in enumerate(link):
                if arg.endswith('.o'):
                    src=base/arg
                    if arg.endswith('/entry-main.cpp.o'):link[i]=str(dest/'entry-main.o')
                    else:link[i]=str(src);sources[str(src.relative_to(ROOT))]=sha(src)
            link[link.index('-o')+1]=str(dest/target)
            jobs.append((mode+'-'+target,link))
        for name,cmd in jobs:
            limits();start=time.monotonic()
            with compiler_turn(),(B/(name+'.log')).open('w') as log:
                subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1200)
            commands.append(dict(name=name,command=cmd,seconds=time.monotonic()-start));print(name,'PASS',flush=True)
        for target in (('own-rt-iq3','fullshape-submit') if mode=='gnu-host' else ('own-rt-iq3',)):
            artifacts[str((dest/target).relative_to(P))]=sha(dest/target)
        # Bind the actual checked include bytes consumed by this compiler,
        # including ignored generated headers, not only their source generators.
        dependencies=shlex.split((dest/'entry-main.d').read_text().replace('\\\n',' '))[1:]
        for name in dependencies:
            path=Path(name).resolve()
            if path.is_relative_to(ROOT):sources[str(path.relative_to(ROOT))]=sha(path)
    for f in [*native.glob('*'),*P.glob('native/*'),*P.glob('sources/*'),P/'build_engine.py',P/'native_source.py']:
        sources[str(f.relative_to(ROOT))]=sha(f)
    limits();save(P/'evidence/build.json',dict(passed=True,device_executed=False,sources=sources,artifacts=artifacts,commands=commands,
        parent_relinks=parent_relinks,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))

if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
    main()
