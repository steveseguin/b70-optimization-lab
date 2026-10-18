"""CPU-only packet contracts, closed worker imports, real lane predicate."""
import json,os,subprocess,sys
from build_engine import P,ROOT,sha,save,limits

def main():
 limits()
 command=[sys.executable,'-B','-m','unittest','discover','-s',str(P),'-p','test_packet100.py','-v']
 with (P/'evidence/python-tests.log').open('w') as log:subprocess.run(command,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
 from bootstrap import install
 install()
 from common import W
 env=W.closed_environment({'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2','LD_LIBRARY_PATH':'/opt/intel/oneapi/compiler/2026.0/lib:/usr/lib/x86_64-linux-gnu'})
 command2=[sys.executable,'-B',str(P/'worker.py'),'--help']
 result=subprocess.run(command2,env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True,timeout=120)
 (P/'evidence/worker-closed-help.log').write_text(result.stdout+result.stderr)
 from lane_admission import admission_scope
 scopes={lane:admission_scope(lane,'screen') for lane in ('A','B')}
 assert scopes=={'A':'lane-A','B':'lane-B'},scopes
 names=('test_packet100.py','micro_gate.py','route_inputs.py','screen_jobs.py','compare.py','bundle_selection.py','prepare_chain.py','selection_gate.py','merge_dispatch.py','packet56_submission.py','k2_summary.py','bootstrap.py','worker.py','python_gate.py','evidence/full-shape.json')
 save(P/'evidence/python-tests.json',dict(passed=True,device_executed=False,tests=15,commands=[command,command2],closed_worker_import=True,lane_admission=scopes,sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in names}))
 print('15 packet tests, closed worker imports, both real lane predicates PASS')
if __name__=='__main__':main()
