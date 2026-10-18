"""Linked AOT register/spill inspection; no GPU or binary execution."""
import gzip,json,os,re,resource,subprocess,shlex
from pathlib import Path
from build_engine import P,limits
from build_layer import sha
from compile_turn import turn
from mirror import prepare
ROOT=P.parents[3]
def main():
 limits();b=P/'build';e=P/'evidence';out=b/('igc-'+sha(P/'hc_gate.hpp')[:16]);out.mkdir(exist_ok=True)
 flags=['-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt','-fsycl','-fsycl-targets=spir64_gen','-fsycl-device-code-split=per_source','-fPIC','-shared','-Xs','-device bmg-g31 -options "-ze-fp32-correctly-rounded-divide-sqrt -ze-opt-print-spill"']
 with turn(),(e/'image-compile.log').open('w') as log:
  source=prepare(P/'image.cpp');cmd=['/opt/intel/oneapi/compiler/2026.0/bin/icpx',*flags,'-MMD','-MF',str(b/'image.d'),str(source),'-o',str(b/'hc-image.so')]
  env={**os.environ,'TMPDIR':str(b/'tmp'),'OMP_NUM_THREADS':'1','OMP_THREAD_LIMIT':'1','IGC_ShaderDumpEnable':'1','IGC_DumpToCustomDir':str(out)}
  subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,env=env,check=True,timeout=600)
 sources={}
 for name in shlex.split((b/'image.d').read_text().replace('\\\n',' ').split(':',1)[1]):
  f=Path(name).resolve()
  if f.is_relative_to(ROOT):
   sources[str(f.relative_to(ROOT))]=sha(f)
   if f.is_relative_to(b/'checked'):
    original=ROOT/f.relative_to(b/'checked');sources[str(original.relative_to(ROOT))]=sha(original)
 rows=[]
 for f in sorted(out.glob('*.asm')):
  s=f.read_text();grf=re.search(r'numGRF=(\d+)',s)
  if not grf:continue
  spill=[l for l in s.splitlines() if l.startswith('//.spill')]
  scratch=[l for l in s.splitlines() if not l.lstrip().startswith('//') and any(x in l.lower() for x in ('scratch','spill to','fill from'))]
  saved=e/(f.stem+'.asm.gz');saved.write_bytes(gzip.compress(f.read_bytes(),mtime=0))
  rows.append(dict(name=s.splitlines()[0],grf=int(grf[1]),spill_metadata=spill,scratch_messages=len(scratch),assembly=str(saved.relative_to(P)),sha256=sha(saved)))
 ze=[]
 for f in sorted(out.glob('*.zeinfo')):
  saved=e/(f.name+'.gz');saved.write_bytes(gzip.compress(f.read_bytes(),mtime=0));ze.append(dict(path=str(saved.relative_to(P)),sha256=sha(saved)))
 report=dict(schema='packet117.linked-aot-inspection.v1',passed=bool(rows),sources=sources,device_executed=False,command=cmd,kernels=rows,zeinfo=ze,artifact_sha256=sha(b/'hc-image.so'),max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
 (e/'registers.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(rows,indent=2));limits()
if __name__=='__main__':main()
