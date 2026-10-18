"""Compile and seal paired micro, with retained IGC dumps; never execute GPU code."""
import importlib.util
import json
import os
from pathlib import Path
import re
import resource
import shlex
import shutil
import subprocess
import sys
from build_engine import P,limits,sha
from compile_turn import turn
ROOT=P.parents[3]
OWNER=P.parents[1]/'stage1/packet3-prep/src'
PARENT=P.parent/'packet58j-onecard-port'
DEST=P/'build/micro-checked'

def mirror(entry):
 seen={}
 def copy(src):
  src=Path(src).resolve()
  if src==OWNER/'owner.hpp' or src.name=='owner_api.hpp':src=P/'owner_api.hpp'
  dest=DEST/src.relative_to(ROOT)
  if src in seen:return dest
  seen[src]=dest;text=src.read_text()
  def include(m):
   options=[src.parent/m[1],P/m[1],PARENT/m[1],OWNER/m[1],P.parent/'packet2/kernels'/m[1],P.parent/'packet2/loader'/m[1]]
   target=next((p for p in options if p.is_file()),None)
   if target is None:raise ValueError(f'unresolved include: {src}: {m[1]}')
   return '#include '+json.dumps(str(copy(target)))
  text=re.sub(r'^\s*#include\s*"([^"\n]+)"',include,text,flags=re.M)
  dest.parent.mkdir(parents=True,exist_ok=True)
  if not dest.exists() or dest.read_text()!=text:dest.write_text(text)
  return dest
 return copy(entry)

def storage():
 assert shutil.disk_usage('/').free>=25_000_000_000,'root free below25GB'
 size=sum(p.stat().st_size for folder in (P/'build',P/'v5/build') for p in folder.rglob('*') if p.is_file() and not p.is_symlink())
 assert size<=200_000_000,('build exceeds200MB',size)
 return size

def main():
 limits();storage();b=P/'build';e=P/'evidence';(b/'tmp').mkdir(parents=True,exist_ok=True);e.mkdir(exist_ok=True)
 if '--seal-only' not in sys.argv:
  source=mirror(P/'microbench.cpp');dump=b/'igc-micro';dump.mkdir(exist_ok=True)
  cmd=['/opt/intel/oneapi/compiler/2026.0/bin/icpx','-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt','-fsycl','-fsycl-targets=spir64_gen','-fsycl-device-code-split=per_source','-Werror=deprecated-this-capture','-Xs','-device bmg-g31 -options "-ze-fp32-correctly-rounded-divide-sqrt -ze-opt-print-spill"','-MMD','-MF',str(b/'microbench.d'),str(source),'-lze_loader','-o',str(b/'microbench')]
  env={**os.environ,'TMPDIR':str(b/'tmp'),'OMP_NUM_THREADS':'1','OMP_THREAD_LIMIT':'1','IGC_ShaderDumpEnable':'1','IGC_DumpToCustomDir':str(dump),'IGC_ShowFullVectorsInShaderDumps':'1'}
  with turn(),(e/'build-micro.log').open('w') as log:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,env=env,check=True,timeout=600)
  deps=shlex.split((b/'microbench.d').read_text().replace('\\\n',' ').split(':',1)[1])
  sources={str(Path(p).resolve().relative_to(ROOT)):sha(p) for p in deps if Path(p).resolve().is_relative_to(ROOT)}
  for path in list(sources):
   f=ROOT/path
   if f.is_relative_to(DEST):
    original=ROOT/f.relative_to(DEST);sources[str(original.relative_to(ROOT))]=sha(original)
  row=dict(command=cmd,sources=sources,artifact_sha256=sha(b/'microbench'),max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
  (e/'micro-compile.json').write_text(json.dumps(row,indent=2)+'\n')
 compile=json.loads((e/'micro-compile.json').read_text());assert sha(b/'microbench')==compile['artifact_sha256']
 for path,h in compile['sources'].items():assert sha(ROOT/path)==h,path
 sources=dict(compile['sources']);artifacts={'build/microbench':sha(b/'microbench')}
 for name in ('build_engine.py','compile_turn.py','build_microbench.py','preregistration.json','run_micro.py','micro_gate.py','route_inputs.py','shared-wrapper-pin.json','drain_gate.py','exec_limits.py','evidence/route-inputs.json','evidence/cases.bin','evidence/all-routes.bin','evidence/cpu-tests.json'):
  f=P/name;sources[str(f.relative_to(ROOT))]=sha(f)
 receipt=dict(schema='packet125.micro-build.v1',passed=True,device_executed=False,sources=sources,artifacts=artifacts,command=compile['command'],max_rss_kib=compile['max_rss_kib'],build_bytes=storage(),arithmetic='frozen 58j production IQ2/IQ3 gate/up, p39 activation, production or p100 down; transport only')
 (e/'microbench-build.json').write_text(json.dumps(receipt,indent=2)+'\n');print('micro compiled/sealed; device not executed')
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 main()
