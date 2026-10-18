"""Explicit CPU test entry; no device work."""
import subprocess,sys,json
from build_engine import P,ROOT,sha,save,limits

def main():
 limits();cmd=[sys.executable,'-B','-m','unittest','-v','test_packet127','test_drain_fix']
 log=P/'evidence/protocol-tests.log'
 with log.open('w') as out:r=subprocess.run(cmd,cwd=P,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT)
 paths=[P/n for n in ('test_gates.py','test_packet127.py','test_drain_fix.py','memory_gate.py','memory_plans.py','bracket_report.py','screen_job.py','screen_jobs.py','chain_pipeline.py','memory_observation.py','bootstrap.py','conditions.py','drain_gate.py','run_micro.py','runtime_worker.py')]
 save(P/'evidence/protocol-tests.json',dict(passed=r.returncode==0,device_executed=False,command=cmd,log_sha256=sha(log),sources={str(f.relative_to(ROOT)):sha(f) for f in paths}))
 assert r.returncode==0,'see protocol-tests.log'
if __name__=='__main__':main()
