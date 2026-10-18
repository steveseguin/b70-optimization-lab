"""Bind the narrow SPEED3 amendment and run only short seal admission tests."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parent;E=P/'evidence/speed3'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def bind():
 import seal6_amendment as amendment
 import speed1_qualification as s1,speed2_qualification as s2,speed3_qualification as s3
 row=json.loads((P/'seal6-amendment.json').read_text())
 row['speed1_extension']=s1.verify();row['speed2_extension']=s2.verify();row['speed3_extension']=s3.verify()
 row['production_changed_files']=['main.cpp','mtp.hpp','p39_plan.hpp','rank.hpp','strict_snapshot.hpp']
 row['justification']='Owner SEAL6 and SPEED REPAIR 1/2/3 directives, 2026-10-15. Preserve prior pinned repairs; add only single-pass draft event profiling with lifetime/error/duration checks and an explicit 24/24 rank0-draft split admitted at 4096 only. Fresh 72-plan metadata sweep, 63 mini executions (54 checks including six required-extent omissions), 16 event-accounting checks and ten admission checks. No real-model CPU suite or compiler matrix. Device W2m/WS/WSs/WS128x with immutable arithmetic-v2-detmath oracle remain real-model exactness authority.'
 row['publication_rule']='Speed publication must cite hash-bound passing device suite window receipts for the current artifact identity. Historical CPU cases are not SPEED3 real-model exactness evidence.'
 row['speed3_files']=['main.cpp','rank.hpp','mtp.hpp',*[p.name for p in sorted(P.glob('speed3_*.py'))],'test_speed3.py','pipeline.py','window.py','coordinator_windows.sh','cpu_merged_gate.py','memory_gate.py','memory_plan.py','memory-plan.json','speed3-plan-gates.json','speed3-snapshot-gates.json','speed3-event-gates.json','speed3-admission-gates.json','SPEED3-CLOSEOUT.md','evidence/speed3/']
 row['qualification_sources_sha256']={n:sha(P/n) for n in amendment.QUALIFICATION_SOURCES}
 (P/'seal6-amendment.json').write_text(json.dumps(row,indent=2)+'\n')
 amendment.verify();print('SPEED3 amendment bound',flush=True)
def tests():
 tests=(('test_fixture_delta','fixture-delta-tests.json',('fixture_delta.py','test_fixture_delta.py','speed3_qualification.py')),
        ('test_seal6_amendment','seal6-amendment-tests.json',('seal6_amendment.py','test_seal6_amendment.py','speed1_qualification.py','speed3_qualification.py')),
        ('test_audit6','audit6-tests.json',('audit6.py','test_audit6.py','speed3_qualification.py')),
        ('test_seal45_bindings','seal45-binding-tests.json',('seal45.py','test_seal45_bindings.py')))
 for module,dest,sources in tests:
  program="import unittest,json; s=unittest.defaultTestLoader.loadTestsFromName("+repr(module)+"); r=unittest.TextTestRunner(verbosity=2).run(s); print(json.dumps(dict(passed=r.wasSuccessful(),checks=r.testsRun,failures=len(r.failures),errors=len(r.errors)))); raise SystemExit(not r.wasSuccessful())"
  with (E/(module+'.log')).open('w') as out:r=subprocess.run([sys.executable,'-B','-c',program],cwd=P,stdout=out,stderr=subprocess.STDOUT)
  if r.returncode:raise RuntimeError(module+' failed; see evidence/speed3/'+module+'.log')
  row=json.loads((E/(module+'.log')).read_text().splitlines()[-1]);row.update(device_executed=False,source_sha256={n:sha(P/n) for n in sources})
  (P/dest).write_text(json.dumps(row,indent=2)+'\n');print(module,row['checks'],'PASS',flush=True)
def admission():
 program="import unittest,json; r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName('test_speed3')); print(json.dumps(dict(passed=r.wasSuccessful(),checks=r.testsRun))); raise SystemExit(not r.wasSuccessful())"
 with (E/'admission.log').open('w') as out:r=subprocess.run([sys.executable,'-B','-c',program],cwd=P,stdout=out,stderr=subprocess.STDOUT)
 if r.returncode:raise RuntimeError('admission failed: evidence/speed3/admission.log')
 row=json.loads((E/'admission.log').read_text().splitlines()[-1]);row.update(device_executed=False,source_sha256={n:sha(P/n) for n in ('test_speed3.py','memory_gate.py','memory_plan.py','window.py','pipeline.py','coordinator_windows.sh')})
 (P/'speed3-admission-gates.json').write_text(json.dumps(row,indent=2)+'\n')
if __name__=='__main__':
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 admission();bind();tests()
