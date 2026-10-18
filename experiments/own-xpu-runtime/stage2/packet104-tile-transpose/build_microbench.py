"""Compile first; do not run any device binary or long CPU qualification."""
import os,resource,shlex,subprocess,json
from pathlib import Path
from build_engine import P,ROOT,B,limits,sha,save
from compile_turn import turn
def main():
 limits();(B/'tmp').mkdir(exist_ok=True);os.environ['TMPDIR']=str(B/'tmp')
 from kernel_gate import mirror
 from math_gate import check,closure
 paths=closure(['microbench.cpp','prepared_submission.hpp']);check(paths);mapping=mirror(paths)
 cmd=json.loads((P/'compiler.snapshot.json').read_text())
 cmd += ['-MMD','-MF',str(B/'microbench.d'),str(mapping[P/'microbench.cpp']),'-o',str(B/'microbench')]
 with turn(),(B/'microbench-build.log').open('w') as log:
  subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1200)
 deps=shlex.split((B/'microbench.d').read_text().replace('\\\n',' ').split(':',1)[1])
 sources={str(Path(n).resolve().relative_to(ROOT)):sha(n) for n in deps if Path(n).is_file() and Path(n).resolve().is_relative_to(ROOT)}
 for src,dst in mapping.items():
  if str(dst.relative_to(ROOT)) in sources:sources[str(src.relative_to(ROOT))]=sha(src)
 for name in ('build_microbench.py','build_engine.py','compile_turn.py','compiler.snapshot.json','source-origin.json','derive.py','derive_small.py','microbench.cpp','run_micro.py','micro_gate.py','qualification.py','route_inputs.py','shared-wrapper-pin.json','kernel_gate.py','math_gate.py','kernel_overlay.py','submission_overlay.py','baseline-selection.json','baseline-dispatch-speed6.json','evidence/route-inputs.json.gz','evidence/routes.bin'):
  sources[str((P/name).relative_to(ROOT))]=sha(P/name)
 size=sum(p.stat().st_size for p in B.rglob('*') if p.is_file());assert size<=300_000_000,size
 save(P/'evidence/microbench-build.json',dict(passed=True,device_executed=False,command=cmd,sources=sources,artifacts={'build/microbench':sha(B/'microbench')},binary_sha256=sha(B/'microbench'),build_logical_bytes=size,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
 print('microbench compile PASS; no device run; build bytes',size,flush=True)
if __name__=='__main__':main()
