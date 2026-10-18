"""CPU preparation and evidence reading only; never launches or submits."""
import argparse,json,os,subprocess,sys
from pathlib import Path
from source_decision import O,P,ROOT,save,sha

def test_sources():
 return {str(f.relative_to(ROOT)):sha(f) for f in [*O.glob('*.py'),*P.glob('v5/*.py'),P/'bundle_selection.py',P/'compare.py',P/'draft_identity.py',P/'packet56_submission.py',P/'test_packet124.py',P/'test_drain_fix.py',P/'drain_gate.py',ROOT/'scripts/check_drain_fix.py']}

def verify_tests():
 row=json.loads((O/'cpu-tests.json').read_text())
 assert row['passed'] and row['device_executed'] is False
 assert row['sources']==test_sources(),'CPU preparation tests stale'
 assert sha(O/'tests.log')==row['log_sha256']
 return row

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--evidence-only',action='store_true');a=ap.parse_args()
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 if not a.evidence_only:
  python='/home/steve/.venvs/deepseek-v4-xpu/bin/python3'
  cmd=[python,'-B','-m','pytest','-q','-p','no:cacheprovider',str(O/'test_policy.py'),str(O/'test_submission.py'),str(O/'test_argument_gate.py'),str(P/'test_packet124.py'),str(P/'test_drain_fix.py'),str(P/'test_resume_chain.py'),str(P/'test_prepare_resume.py')]
  env=dict(os.environ,PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',OMP_NUM_THREADS='2',PYTHONPATH=str(O)+':'+str(P))
  with (O/'tests.log').open('w') as log:r=subprocess.run(cmd,cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=600)
  save(O/'cpu-tests.json',dict(passed=r.returncode==0,device_executed=False,command=cmd,log_sha256=sha(O/'tests.log'),sources=test_sources()))
  assert r.returncode==0,'CPU tests failed; see tests.log'
 verify_tests()
 from verify_ready import evaluate
 row=evaluate();save(O/'ready.json',row)
 print(json.dumps(row,indent=2))
if __name__=='__main__':main()
