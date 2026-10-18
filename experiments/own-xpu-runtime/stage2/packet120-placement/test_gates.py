"""CPU entry for packet120 admission, decision, imports and drain regressions."""
import subprocess,sys,json
from build_engine import P,ROOT,sha,save,limits

def main():
 limits();cmd=[sys.executable,'-B','-m','unittest','-v','test_packet120']
 log=P/'evidence/protocol-tests.log'
 with log.open('w') as out:r=subprocess.run(cmd,cwd=P,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT)
 save(P/'evidence/protocol-tests.json',dict(passed=r.returncode==0,device_executed=False,command=cmd,log_sha256=sha(log),sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('test_gates.py','test_packet120.py','memory_gate.py','memory_plans.py','bracket_report.py','timing_accounting.py','screen_job.py','chain_pipeline.py','memory_observation.py')}))
 assert r.returncode==0,'see protocol-tests.log'
if __name__=='__main__':main()
