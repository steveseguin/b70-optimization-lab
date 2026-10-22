import json,resource,subprocess
from p185_v5_build_engine import P,LOCAL,ROOT,B,CHECKED,sha,save,run,limits

def main():
 limits();rows=[];sources=[P/'native/controller_probe_test.cpp',CHECKED/'native_controller.hpp',CHECKED/'host_spin.hpp',P/'controller_gate.py']
 for mode,compiler in [('GNU','g++'),('Intel','/opt/intel/oneapi/compiler/latest/bin/icpx')]:
  binary=B/('controller-'+mode)
  run([compiler,'-std=c++20','-DOWN_RT_HOST_ONLY','-O2','-pthread','-I'+str(CHECKED),P/'native/controller_probe_test.cpp','-o',binary],'controller-'+mode)
  for repeat in (1,2):
   result=subprocess.run([str(binary)],stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True,timeout=60)
   row=json.loads(result.stdout);assert row['passed'] and row['cases']==12 and row['miss_commands']>0
   rows.append(dict(row,compiler=mode,repeat=repeat,binary=str(binary.relative_to(ROOT)),binary_sha256=sha(binary)))
 save(P/'evidence/controller.json',dict(passed=True,device_executed=False,rows=rows,sources={str(f.relative_to(ROOT)):sha(f) for f in sources}))
 print('Controller: GNU/Intel, two repeats each; all-hit/miss/mixed/native-draft exact mock tokens and state PASS')
if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
