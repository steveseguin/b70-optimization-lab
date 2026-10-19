import json,resource,subprocess
from p153_v5_build_engine import P,LOCAL,ROOT,B,CHECKED,sha,save,run,limits

def main():
 limits();rows=[];sources=[P/'native/transport_probe_test.cpp',P/'native/probe_exchange.hpp',CHECKED/'host_spin.hpp',P/'transport_gate.py']
 for mode,compiler in [('GNU','g++'),('Intel','/opt/intel/oneapi/compiler/latest/bin/icpx')]:
  binary=B/('transport-'+mode)
  run([compiler,'-std=c++20','-DOWN_RT_HOST_ONLY','-O2','-pthread','-I'+str(CHECKED),P/'native/transport_probe_test.cpp','-o',binary],'transport-'+mode)
  for repeat in (1,2):
   result=subprocess.run([str(binary)],stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True,timeout=60)
   row=json.loads(result.stdout);assert row['passed'] and row['exchanges']==96 and row['model_buffers_unchanged']
   rows.append(dict(row,compiler=mode,repeat=repeat,binary=str(binary.relative_to(ROOT)),binary_sha256=sha(binary)))
 save(P/'evidence/transport.json',dict(passed=True,device_executed=False,rows=rows,sources={str(f.relative_to(ROOT)):sha(f) for f in sources}))
 print('Transport: GNU/Intel, two repeats; actual probe methods, 96 exchanges, byte sizes, bounds, event waits and untouched model buffers PASS')
if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
