"""Compile serially and execute the actual native controller with mock rank owners."""
import json,subprocess
from build_engine import P,B,ROOT,limits,sha,save

def main():
 limits();out=B/'protocol';out.mkdir(exist_ok=True);runs=[]
 for compiler,cxx in [('GNU','/usr/bin/g++'),('Intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  binary=out/compiler;cmd=[cxx,'-std=c++20','-O2','-pthread','-DP56X_SLEEP20=0','-fno-fast-math','-ffp-contract=off',str(P/'protocol_mock.cpp'),str(P/'host_wait_mode.cpp'),'-o',str(binary)]
  with (out/(compiler+'-compile.log')).open('w') as f:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True)
  for repeat in (1,2):
   r=subprocess.run([str(binary)],stdin=subprocess.DEVNULL,capture_output=True,text=True)
   (out/f'{compiler}-{repeat}.log').write_text(r.stdout+r.stderr)
   assert r.returncode==0,r.stderr
   v=json.loads(r.stdout);assert v['passed'] and v['cases']==20
   runs.append(dict(compiler=compiler,repeat=repeat,binary_sha256=sha(binary),**v));print(compiler,repeat,'PASS',flush=True)
 sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('protocol_gate.py','protocol_mock.cpp','native_controller.hpp','host_spin.hpp','host_wait_mode.cpp')}
 save(P/'evidence/protocol.json',dict(passed=True,device_executed=False,runs=runs,sources=sources,scope='Actual controller accept/miss/rollback/EOS with mock ranks and callback-driven publication; actual reverse memcpy covered by miniature engines.'))
if __name__=='__main__':main()
