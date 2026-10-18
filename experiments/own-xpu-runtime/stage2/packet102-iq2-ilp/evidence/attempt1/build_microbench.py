"""CPU-only standalone build: ship micro proposal before engine gates."""
import json,subprocess,resource,shlex
from pathlib import Path
from build_engine import P,ROOT,B,limits,sha,save
from compile_turn import turn
def main():
 limits();(B/'tmp').mkdir(exist_ok=True)
 from kernel_gate import mirror
 mapping=mirror()
 source=B/'microbench.cpp';source.write_text((P/'microbench.cpp').read_text().replace('\"p102_expert.hpp\"',json.dumps(str(mapping[P/'p102_expert.hpp']))))
 prior=json.loads((P.parent/'packet97-record-bundle/engine-commands.json').read_text())
 cmd=next(r['command'] for r in prior if r['name']=='device-entry-main');cmd=cmd[:cmd.index('-o')]
 cmd=[x.replace(str(P.parent/'packet97-record-bundle'),str(P)) if x.startswith('-I') else x for x in cmd]
 cmd += ['-I'+str(P),'-MMD','-MF',str(B/'microbench.d'),str(source),'-o',str(B/'microbench')]
 with turn(),(B/'microbench-build.log').open('w') as f:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=600)
 deps=shlex.split((B/'microbench.d').read_text().replace('\\\n',' ').split(':',1)[1])
 sources={str(Path(n).resolve().relative_to(ROOT)):sha(n) for n in deps if Path(n).is_file() and Path(n).resolve().is_relative_to(ROOT)}
 for leaf in ('build_microbench.py','run_micro.py','micro_gate.py','shared-wrapper-pin.json'):sources[str((P/leaf).relative_to(ROOT))]=sha(P/leaf)
 save(P/'evidence/microbench-build.json',dict(passed=True,device_executed=False,command=cmd,sources=sources,artifacts={'build/microbench':sha(B/'microbench')},max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
 print('microbench compile PASS; no device run',flush=True)
if __name__=='__main__':main()
