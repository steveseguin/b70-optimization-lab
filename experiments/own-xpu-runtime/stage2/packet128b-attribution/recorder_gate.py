"""CPU-only boundary tests for the actual C++ recorder."""
import subprocess
from compile_turn import turn
from build_engine import P,B,ROOT,limits,sha,save

def main():
 limits();binary=B/'recorder-test'
 command=['/usr/bin/g++','-std=c++20','-O2',str(P/'recorder_test.cpp'),'-o',str(binary)]
 with turn():subprocess.run(command,stdin=subprocess.DEVNULL,check=True,timeout=120)
 subprocess.run([str(binary)],stdin=subprocess.DEVNULL,check=True,timeout=30)
 save(P/'evidence/recorder-gate.json',dict(passed=True,device_executed=False,command=command,
  sources={str(f.relative_to(ROOT)):sha(f) for f in (P/'attribution.hpp',P/'recorder_test.cpp',P/'recorder_gate.py')}))
 print('C++ recorder: 9..16 only, all layers and disabled/reset modes PASS')
if __name__=='__main__':
 import resource
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3));main()
