"""Bind the proposal only after fresh mini/plan/admission receipts pass."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parent;E=P/'evidence/speed5'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 program="import unittest,json; s=unittest.defaultTestLoader.loadTestsFromName('test_speed5'); r=unittest.TextTestRunner(verbosity=2).run(s); print(json.dumps(dict(passed=r.wasSuccessful(),checks=r.testsRun,failures=len(r.failures),errors=len(r.errors)))); raise SystemExit(not r.wasSuccessful())"
 with (E/'admission.log').open('w') as out:r=subprocess.run([sys.executable,'-B','-c',program],cwd=P,stdout=out,stderr=subprocess.STDOUT)
 assert r.returncode==0,'SPEED5 admission tests failed'
 row=json.loads((E/'admission.log').read_text().splitlines()[-1]);row.update(device_executed=False,memory_plan_sha256=sha(P/'memory-plan.json'),source_sha256={n:sha(P/n) for n in ('test_speed5.py','memory_plan.py','memory_gate.py','window.py','pipeline.py','coordinator_windows.sh')})
 (P/'speed5-admission-gates.json').write_text(json.dumps(row,indent=2)+'\n')
 import speed5_qualification as s5,seal6_amendment as amendment
 row=json.loads((P/'seal6-amendment.json').read_text());row['speed5_extension']=s5.verify()
 row['speed5_files']=['test_seal45_bindings.py',*s5.PINS,*[p.name for p in sorted(P.glob('speed5_*.py'))],'test_speed5.py','speed5-plan-gates.json','speed5-snapshot-gates.json','speed5-admission-gates.json','evidence/speed5/']
 clause=' SPEED5 extends this exact amendment only to split23 and its proved allocation margins, with fresh metadata/mini/admission gates. No arithmetic, kernel selection or SPEED4 restore change.'
 if clause not in row['justification']:row['justification']+=clause
 row['qualification_sources_sha256']={n:sha(P/n) for n in amendment.QUALIFICATION_SOURCES}
 (P/'seal6-amendment.json').write_text(json.dumps(row,indent=2)+'\n');amendment.verify()
 # Existing short source-binding tests need receipts for the new qualification source.
 import speed4_finalize as prior
 prior.E=E;prior.tests()
 print('SPEED5 amendment bound; run build.py seal and detached admission next')
if __name__=='__main__':main()
