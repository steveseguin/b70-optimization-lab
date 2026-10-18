"""Focused CPU-only regressions; retain command, output and source identities."""
import json,subprocess,sys
from build_engine import P,ROOT,sha,save,limits

def main():
 limits();tests=['test_analysis','test_worker','test_drain_fix','test_post_report']
 command=[sys.executable,'-B','-m','unittest','-v',*tests]
 result=subprocess.run(command,cwd=P,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=180)
 (P/'evidence/python-tests.log').write_text(result.stdout+result.stderr)
 assert result.returncode==0,result.stdout+result.stderr
 save(P/'evidence/python-tests.json',dict(passed=True,device_executed=False,command=command,
  sources={str(f.relative_to(ROOT)):sha(f) for f in [*(P/(t+'.py') for t in tests),P/'analyze.py',P/'run_screen.py',P/'worker.py',P/'teardown.py',P/'drain_gate.py']}))
 print(result.stderr.strip())
if __name__=='__main__':
 import resource
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3));main()
