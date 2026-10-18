"""CPU-only Python lifecycle tests, source-bound evidence."""
import json,subprocess,sys
from build131 import P,ROOT,sha,save,cpu_main
def main():
 cmd=[sys.executable,'-B','-m','unittest','-v','test131','test_drain_fix']
 cp=subprocess.run(cmd,cwd=P,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=180)
 (P/'evidence/python131.log').write_text(cp.stdout+cp.stderr);assert cp.returncode==0,cp.stdout+cp.stderr
 sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'python131.py',P/'test131.py',P/'test_drain_fix.py',P/'smoke_worker.py',P/'grid_worker.py',P/'teardown.py',P/'drain_gate.py',P/'compare131.py']}
 save(P/'evidence/python131.json',dict(passed=True,device_executed=False,command=cmd,sources=sources));print(cp.stderr)
if __name__=='__main__':cpu_main();main()
