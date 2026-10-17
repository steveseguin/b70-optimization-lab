#!/usr/bin/env python3
"""Production route and split32 CPU entry points absent from the mini engine."""
import json,subprocess,time
from pathlib import Path
import build
from p59c_cpu_gate import constraints
from p59c_selection import P,sha,save
B=P/'build';E=P/'cpu-evidence/operators'
def main():
 constraints();start=time.monotonic();E.mkdir(parents=True,exist_ok=False)
 cmd=['/usr/bin/g++','-std=c++20','-O2','-g0','-fopenmp','-fno-fast-math','-ffp-contract=off','-ffunction-sections','-fdata-sections','-Wl,--gc-sections','-DOWN_RT_HOST_ONLY','-I'+str(P),'-I'+str(P.parent.parent/'stage1/packet3-prep/src'),'-I'+str(P.parent/'packet2/kernels'),'-I'+str(P.parent/'packet2/loader'),str(P/'p59c_route_fixture.cpp')]
 objects=sorted((B/'gnu-host/CMakeFiles/programs.dir').rglob('*.o'))
 assert objects
 cmd+=list(map(str,objects))+['-lcrypto','-o',str(B/'p59c-route-fixture')]
 with (B/'p59c-route-compile.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
 subprocess.run(['cmake','--build',str(B/'gnu-host'),'--target','p49-qsa-fixtures','-j1'],check=True,stdout=(B/'p59c-qsa-compile.log').open('w'),stderr=subprocess.STDOUT,timeout=180)
 build.record_mode_build('gnu-host')
 dense=['/usr/bin/g++','-std=c++20','-O2','-g0','-fno-fast-math','-ffp-contract=off','-ffunction-sections','-fdata-sections','-Wl,--gc-sections','-DOWN_RT_HOST_ONLY','-I'+str(P),'-I'+str(P.parent.parent/'stage1/packet3-prep/src'),'-I'+str(P.parent/'packet2/kernels'),'-I'+str(P.parent/'packet2/loader'),str(P/'p59c_dense_fixture.cpp'),'-o',str(B/'p59c-dense-fixture')]
 with (B/'p59c-dense-compile.log').open('w') as f:subprocess.run(dense,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
 for suffix in ('a','b'):subprocess.run([str(B/'p59c-dense-fixture'),str(E/('dense-'+suffix+'.bin'))],check=True,timeout=60)
 assert sha(E/'dense-a.bin')==sha(E/'dense-b.bin')
 rows={}
 for name,binary in [('route',B/'p59c-route-fixture'),('qsa',B/'gnu-host/p49-qsa-fixtures')]:
  for suffix in ('a','b'):
   dest=E/(name+'-'+suffix)
   argv=[str(binary),str(dest)] if name=='route' else [str(binary),'--output',str(dest)]
   subprocess.run(argv,check=True,timeout=120)
   row=json.loads((dest/'receipt.json').read_text());assert row['passed'] and not row['device_executed']
  assert sha(E/(name+'-a/output.bin'))==sha(E/(name+'-b/output.bin'))
  rows[name]={'binary_sha256':sha(binary),'checks_per_run':row['checks'],'output_sha256':sha(E/(name+'-a/output.bin'))}
 save(P/'operator-gates.json',{'schema':'packet59c.operator-cpu.v1','passed':True,'device_executed':False,'rows':rows,'compiled_sources':build.compiled_sources(),'sources':{n:sha(P/n) for n in ('p59c_route_fixture.cpp','p59c_operator_gate.py','p59c_dense_fixture.cpp','p59_fixture.cpp')},'dense_binary_sha256':sha(B/'p59c-dense-fixture'),'dense_output_sha256':sha(E/'dense-a.bin'),'dense_compile_command':dense,'compile_command':cmd,'seconds':time.monotonic()-start})
 print(json.dumps(rows))
if __name__=='__main__':main()
