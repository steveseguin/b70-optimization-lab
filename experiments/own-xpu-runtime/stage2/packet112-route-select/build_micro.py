"""Compile standalone route micro with frozen production header dependencies."""
import argparse, os, shlex, subprocess, resource, time
from pathlib import Path
from build_engine import P, ROOT, B, BASE, limits, sha, save
from compile_turn import turn
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['gnu','intel','device'],required=True);args=ap.parse_args()
    limits();B.mkdir(exist_ok=True);(B/'tmp').mkdir(exist_ok=True);os.environ['TMPDIR']=str(B/'tmp')
    compiler='/usr/bin/g++' if args.mode=='gnu' else '/opt/intel/oneapi/compiler/2026.0/bin/icpx'
    cmd=[compiler,'-std=gnu++20','-O2','-fno-fast-math','-ffp-contract=off','-Werror=return-type']
    if args.mode=='device':cmd+=['-fsycl','-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt']
    else:cmd+=['-DOWN_RT_HOST_ONLY']
    if args.mode=='intel':cmd+=['-fdenormal-fp-math=ieee']
    # Match the parent's owner API override without modifying the frozen tree.
    hook=P.parents[1]/'stage1/packet3-prep/src/sycl_operation.hpp'
    include=B/'include';include.mkdir(exist_ok=True)
    (include/'sycl_operation.hpp').write_text(hook.read_text().replace('#include "owner.hpp"','#include "'+str(BASE/'owner_api.hpp')+'"'))
    cmd+=['-I'+str(x) for x in [include,BASE, P.parents[1]/'stage1/packet3-prep/src',P.parent/'packet2/kernels',P.parent/'packet2/loader']]
    binary=B/('micro-'+args.mode);dep=B/('micro-'+args.mode+'.d');log=B/('micro-'+args.mode+'.log')
    cmd+=['-MMD','-MF',str(dep),str(P/'microbench.cpp'),'-o',str(binary),'-lcrypto']
    started=time.monotonic()
    with turn(),log.open('w') as out:
        subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,check=True,timeout=900)
    deps=shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1])
    sources={str(q.relative_to(ROOT)):sha(q) for n in deps if (q:=Path(n).resolve()).is_relative_to(ROOT)}
    sources[str(hook.relative_to(ROOT))]=sha(hook)
    size=sum(x.stat().st_size for x in B.rglob('*') if x.is_file());assert size<=200_000_000,size
    save(P/'evidence'/('build-'+args.mode+'.json'),dict(passed=True,device_executed=False,mode=args.mode,command=cmd,sources=sources,artifacts={str(binary.relative_to(P)):sha(binary)},build_bytes=size,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,wall_seconds=time.monotonic()-started))
    print(args.mode,'compile PASS; build bytes',size,flush=True)
if __name__=='__main__':main()
