import json,resource,subprocess
from p194_v5_build_engine import P,LOCAL,ROOT,B,CHECKED,sha,save,run,limits

TESTS=(('probe','native/controller_probe_test.cpp',lambda row:row['cases']==12 and row['miss_commands']>0),
       # packet186: run_v3 (boundary after every rank-0 accept) against run() on the mailbox mock
       ('v3','native/v3_controller_test.cpp',lambda row:row['cases']>=60 and row['boundaries']>0 and row['hits']>0 and row['misses']>0 and row['no_guess']>0))

def main():
 limits();rows=[];sources=[P/'native/controller_probe_test.cpp',P/'native/v3_controller_test.cpp',P/'native/v3_controller.hpp',CHECKED/'native_controller.hpp',CHECKED/'host_spin.hpp',P/'controller_gate.py']
 for name,source,check in TESTS:
  for mode,compiler in [('GNU','g++'),('Intel','/opt/intel/oneapi/compiler/latest/bin/icpx')]:
   binary=B/('controller-'+name+'-'+mode)
   run([compiler,'-std=c++20','-DOWN_RT_HOST_ONLY','-O2','-pthread','-I'+str(CHECKED),P/source,'-o',binary],'controller-'+name+'-'+mode)
   for repeat in (1,2):
    result=subprocess.run([str(binary)],stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True,timeout=120)
    row=json.loads(result.stdout);assert row['passed'] and check(row),row
    rows.append(dict(row,test=name,compiler=mode,repeat=repeat,binary=str(binary.relative_to(ROOT)),binary_sha256=sha(binary)))
 save(P/'evidence/controller.json',dict(passed=True,device_executed=False,rows=rows,sources={str(f.relative_to(ROOT)):sha(f) for f in sources}))
 print('Controller: GNU/Intel, two repeats each; packet185 probe mock and packet186 run_v3 vs run (unchanged in packet188/189: the boundary command is independent of its layer count, of the trims and of the export path) (all-hit/miss/mixed/no-guess/native-draft/EOS, overlap on/off): tokens, proposals and all three states PASS')
if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
