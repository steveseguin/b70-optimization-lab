"""Compile the actual p33 and p93 operation bodies; never enumerate devices."""
import json,subprocess,resource,shlex
from build_engine import P,ROOT,B,limits,sha,save
from compile_turn import turn
def main():
 limits()
 build=P/'build-device-receipt.json'
 if not build.is_file():raise ValueError('finish build_engine.py before building the microbenchmark')
 identity=sha(build);receipt=json.loads(build.read_text())
 assert receipt['passed'] and not receipt['device_executed']
 for name,digest in receipt['sources'].items():assert sha(ROOT/name)==digest,name
 for name,digest in receipt['artifacts'].items():assert sha(P/name)==digest,name
 mirror=B/'checked'/P.relative_to(ROOT)
 source=B/'microbench.cpp';source.write_text((P/'microbench.cpp').read_text().replace('\"p100_down.hpp\"',json.dumps(str(mirror/'p100_down.hpp'))))
 cmd=next(r['command'] for r in json.loads((P/'engine-commands.json').read_text()) if r['name']=='device-entry-main');cmd=cmd[:cmd.index('-o')]
 cmd += ['-I'+str(P),'-MMD','-MF',str(B/'microbench.d'),str(source),'-o',str(B/'microbench')]
 with turn(),(B/'microbench-build.log').open('w') as f:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=600)
 assert sha(build)==identity,'engine build changed during microbenchmark compile'
 deps=shlex.split((B/'microbench.d').read_text().replace('\\\n',' ').split(':',1)[1])
 sources={str(Path(n).resolve().relative_to(ROOT)):sha(n) for n in deps if Path(n).is_file() and Path(n).resolve().is_relative_to(ROOT)}
 for f in (P/'build_microbench.py',P/'p100_down.hpp',P/'microbench.cpp',P/'run_micro.py',P/'micro_gate.py',P/'route_inputs.py',P/'shared-wrapper-pin.json',P/'build-device-receipt.json'):sources[str(f.relative_to(ROOT))]=sha(f)
 save(P/'evidence/microbench-build.json',dict(passed=True,device_executed=False,command=cmd,sources=sources,artifacts={'build/microbench':sha(B/'microbench')},binary_sha256=sha(B/'microbench'),max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
 print('microbench compile PASS; no device run')
from pathlib import Path
if __name__=='__main__':main()
