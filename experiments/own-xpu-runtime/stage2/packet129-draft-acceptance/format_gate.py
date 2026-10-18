"""GNU and Intel CPU bytes for the actual new FP8 kernel, twice per compiler."""
import json,subprocess,resource
from build_engine import P,B,ROOT,sha,save,limits
from compile_turn import turn
def main():
 limits();out=B/'format';out.mkdir(exist_ok=True)
 prior=json.loads((P/'engine-commands.json').read_text())
 base=next(r['command'] for r in prior if r['name']=='gnu-host-entry-main')
 flags=[x for x in base[1:base.index('-o')] if x!='-fopenmp']
 compilers=[('GNU','/usr/bin/g++'),('Intel','/opt/intel/oneapi/compiler/latest/bin/icpx')]
 rows=[];expected=None
 for label,compiler in compilers:
  command=[compiler,*flags,'-o',str(out/label),str(P/'format_fixture.cpp')]
  with turn(),(out/(label+'-compile.log')).open('w') as log:subprocess.run(command,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
  links=subprocess.check_output(['readelf','-d',str(out/label)],text=True).lower()
  assert not any(n in links for n in ('libsycl','libze_loader','libur_loader','libopencl'))
  for repeat in (1,2):
   dest=P/'evidence'/f'format-{label}-{repeat}.bin'
   result=subprocess.run([str(out/label),str(dest)],stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True,timeout=60)
   if expected is None:expected=dest.read_bytes()
   assert dest.read_bytes()==expected
   rows.append(dict(compiler=label,repeat=repeat,sha256=sha(dest),bytes=dest.stat().st_size,stdout=result.stdout))
  print(label,'exact FP8 arithmetic PASS',flush=True)
 save(P/'evidence/format-gate.json',dict(passed=True,device_executed=False,rows=rows,sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('p129_fp8.hpp','format_fixture.cpp','format_gate.py')}))
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3));main()
