"""Compile only, under packet94's shared serial compiler turn."""
import json,os,resource,shlex,subprocess,time
from build_engine import P,ROOT,B,limits,sha,save
from compile_turn import turn
def main():
    limits();(B/'tmp').mkdir(parents=True,exist_ok=True)
    os.environ['TMPDIR']=str(B/'tmp')
    from kernel_gate import mirror
    from math_gate import check,closure
    from route_inputs import require_ready
    routes=require_ready()
    paths=closure(['microbench.cpp','prepared_submission.hpp','owner_api.hpp'])
    math=check(paths);mapping=mirror(paths)
    cmd=json.loads((P/'compiler.snapshot.json').read_text())
    cmd+=['-MMD','-MF',str(B/'microbench.d'),str(mapping[P/'microbench.cpp']),'-o',str(B/'microbench')]
    with turn(),(B/'microbench-build.log').open('x') as log:
        started=time.monotonic()
        result=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=1200)
    if result.returncode:
        save(P/'evidence/build-failure.json',dict(passed=False,device_executed=False,command=cmd,returncode=result.returncode,log_sha256=sha(B/'microbench-build.log')))
        raise SystemExit(result.returncode)
    deps=shlex.split((B/'microbench.d').read_text().replace('\\\n',' ').split(':',1)[1])
    sources={str(q.resolve().relative_to(ROOT)):sha(q) for n in deps if (q:=__import__('pathlib').Path(n)).is_file() and q.resolve().is_relative_to(ROOT)}
    for src,dst in mapping.items():
        if str(dst.relative_to(ROOT)) in sources:sources[str(src.relative_to(ROOT))]=sha(src)
    for q in P.iterdir():
        if q.is_file() and q.suffix in ('.py','.hpp','.cpp','.json') and q.name not in ('compiler.snapshot.json',):sources[str(q.relative_to(ROOT))]=sha(q)
    for name in ('compiler.snapshot.json','evidence/route-inputs.json.gz','evidence/routes.bin'):
        sources[str((P/name).relative_to(ROOT))]=sha(P/name)
    size=sum(p.stat().st_size for p in B.rglob('*') if p.is_file());assert size<=300_000_000,size
    save(P/'evidence/microbench-build.json',dict(passed=True,device_executed=False,command=cmd,sources=sources,artifacts={'build/microbench':sha(B/'microbench')},binary_sha256=sha(B/'microbench'),build_logical_bytes=size,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,wall_seconds=time.monotonic()-started,math_check=math,route_bytes_sha256=routes['route_bytes_sha256']))
    print('Micro compile PASS; no device run; build bytes',size,flush=True)
if __name__=='__main__':main()
