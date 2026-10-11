"""Compile old functors, never execute; measure sizeof(F) from ELF symbol sizes."""
import subprocess,json,hashlib,re,concurrent.futures,resource
from pathlib import Path
from kernel_gate import mirror,HERE,ROOT,BASELINE
B=HERE/'build';IC='/opt/intel/oneapi/compiler/2026.0/bin/icpx'
def sizes(path):
 text=subprocess.check_output(['nm','-S','-C',str(path)],text=True)
 out={}
 for line in text.splitlines():
  if 'packet23::capture_size<' not in line:continue
  parts=line.split(None,3)
  if len(parts)==4:out[parts[3]]=int(parts[1],16)
 return out
def main():
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 probe=B/'oversized-capture.cpp';probe.write_text('#include "'+str(HERE/'kernel_guard.hpp')+'"\n#include <array>\nvoid test(){packet23::checked(std::array<char,1025>{});}\n')
 result=subprocess.run([IC,'-std=c++20','-fsycl','-fsyntax-only',str(probe)],capture_output=True,text=True)
 assert result.returncode!=0 and 'device kernel capture exceeds 1024 bytes' in result.stderr
 (HERE/'oversized-capture.log').write_text(result.stderr)
 guard=(HERE/'kernel_guard.hpp').read_text().replace('sizeof(F)<=1024','sizeof(F)<=8192')
 (B/'kernel_guard_before.hpp').write_text(guard)
 mapping=mirror(True);old= B/'capture-before';old.mkdir(exist_ok=True)
 sources=[x for x in mapping if x.suffix=='.cpp' and (re.search(r'\.(parallel_for|single_task)',x.read_text()) or x.name=='main.cpp')]
 def compile(src):
  obj=old/(str(src.relative_to(ROOT)).replace('/','__')+'.o');log=obj.with_suffix('.log')
  cmd=[IC,'-std=c++20','-O2','-fsycl','-fno-fast-math','-ffp-contract=off','-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt','-I'+str(HERE),'-I'+str(HERE.parent.parent/'stage1/packet3-prep/src'),'-I'+str(HERE.parent/'packet2/kernels'),'-I'+str(HERE.parent/'packet2/loader'),'-c',str(mapping[src]),'-o',str(obj)]
  with log.open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
  return sizes(obj)
 before={}
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
  for row in pool.map(compile,sources):before.update(row)
 after=sizes(B/'device/jit-smoke')
 assert before.keys()==after.keys(),(before.keys()-after.keys(),after.keys()-before.keys())
 rows=[dict(kernel=k,before=before[k],after=v) for k,v in sorted(after.items())]
 assert rows and max(after.values())<=1024
 (HERE/'kernel-sizes.json').write_text(json.dumps(dict(passed=True,device_executed=False,baseline_commit=BASELINE,measurement='sizeof(F) from compiler-emitted capture_size<F> ELF object symbol size; device ABI packing may differ',kernel_classes=len(rows),max_after=max(after.values()),rows=rows),indent=2)+'\n')
 print('CAPTURES',len(rows),'max',max(after.values()))
if __name__=='__main__':main()
