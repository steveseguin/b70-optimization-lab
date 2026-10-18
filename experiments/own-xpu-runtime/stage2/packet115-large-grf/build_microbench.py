"""CPU-only micro link and final source seal; never execute the device program."""
import json,os,resource,shlex,subprocess,sys
from pathlib import Path
from build_engine import P,limits
from build_images import sha
from mirror import prepare
from compile_turn import turn
ROOT=P.parents[3]
def main():
 limits();b=P/'build';e=P/'evidence'
 if '--seal-only' not in sys.argv:
  source=prepare(P/'microbench.cpp')
  cmd=['/opt/intel/oneapi/compiler/2026.0/bin/icpx','-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt','-fsycl','-Werror=deprecated-this-capture','-MMD','-MF',str(b/'microbench.d'),str(source),str(b/'libp115_normal.so'),str(b/'libp115_large.so'),'-Wl,-rpath,'+str(b),'-o',str(b/'microbench')]
  env={**os.environ,'TMPDIR':str(b/'tmp'),'OMP_NUM_THREADS':'1','OMP_THREAD_LIMIT':'1'}
  with turn(),(e/'build-micro.log').open('w') as log:
   subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,env=env,check=True,timeout=600)
  deps=shlex.split((b/'microbench.d').read_text().replace('\\\n',' ').split(':',1)[1])
  sources={str(Path(p).resolve().relative_to(ROOT)):sha(p) for p in deps if Path(p).resolve().is_relative_to(ROOT)}
  for path in list(sources):
   f=ROOT/path
   if f.is_relative_to(b/'checked'):
    original=ROOT/f.relative_to(b/'checked');sources[str(original.relative_to(ROOT))]=sha(original)
  row=dict(command=cmd,sources=sources,artifact_sha256=sha(b/'microbench'),max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
  (e/'micro-compile.json').write_text(json.dumps(row,indent=2)+'\n')
 compile=json.loads((e/'micro-compile.json').read_text());assert sha(b/'microbench')==compile['artifact_sha256']
 for path,h in compile['sources'].items():assert sha(ROOT/path)==h,path
 images=json.loads((e/'images.json').read_text());assert images['passed'],'zero-spill gate1 incomplete'
 sources=dict(compile['sources']);artifacts={'build/microbench':sha(b/'microbench')}
 for row in images['images']:sources.update(row['sources']);artifacts.update(row['artifact'])
 for name in ('build_microbench.py','run_micro.py','micro_gate.py','route_inputs.py','shared-wrapper-pin.json','evidence/images.json','evidence/cpu-byte-identity.json','evidence/route-inputs.json','evidence/routes.bin'):
  f=P/name;sources[str(f.relative_to(ROOT))]=sha(f)
 receipt=dict(schema='packet115.micro-build.v1',passed=True,device_executed=False,sources=sources,artifacts=artifacts,command=compile['command'],max_rss_kib=compile['max_rss_kib'],expert_images='separate default128 and module-wideLARGE256 AOT DSOs; harness has no expert entry kernels')
 (e/'microbench-build.json').write_text(json.dumps(receipt,indent=2)+'\n');print('micro compiled/sealed; device not executed')
if __name__=='__main__':main()
