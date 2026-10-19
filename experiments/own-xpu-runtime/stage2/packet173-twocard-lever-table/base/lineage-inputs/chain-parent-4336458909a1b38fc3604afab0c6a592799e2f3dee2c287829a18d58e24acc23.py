"""Bind the narrow SPEED4 amendment and run only short seal admission tests."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parent;E=P/'evidence/speed4'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def bind():
 import seal6_amendment as amendment
 import speed1_qualification as s1,speed2_qualification as s2,speed3_qualification as s3,speed4_qualification as s4
 row=json.loads((P/'seal6-amendment.json').read_text())
 row['speed1_extension']=s1.verify();row['speed2_extension']=s2.verify();row['speed3_extension']=s3.verify();row['speed4_extension']=s4.verify()
 row['production_changed_files']=['main.cpp','mtp.hpp','native_controller.hpp','p39_plan.hpp','rank.hpp','strict_snapshot.hpp']
 row['justification']='Owner SEAL6 and SPEED REPAIR 1/2/3/4 directives, 2026-10-15. Preserve all prior pinned repairs. SPEED4 skips restoration only for physically distinct spare recurrent/conv banks proved completely overwritten by a same-position confirmed redo. Every other extent is restored; abandoned redo restores deferred banks before any other command. Full-state mini comparisons cover both controllers, placements and admitted split families, partial cancellation, terminal/boundary paths, and deliberate omitted-extent failures. Arithmetic and dispatch unchanged. No real-model CPU suite or compiler matrix. Device W2m/WS/WSs/WS128x with immutable arithmetic-v2-detmath oracle remain real-model exactness authority.'
 row['publication_rule']='Speed publication must cite hash-bound passing device suite window receipts for the current artifact identity. Historical CPU cases are not SPEED4 real-model exactness evidence.'
 row['speed4_files']=['strict_snapshot.hpp','rank.hpp','native_controller.hpp','pipeline.py',*[p.name for p in sorted(P.glob('speed4_*.py'))],'speed4-plan-gates.json','speed4-snapshot-gates.json','speed4-snapshot-inventory.json','SPEED4-CLOSEOUT.md','evidence/speed4/']
 row['qualification_sources_sha256']={n:sha(P/n) for n in amendment.QUALIFICATION_SOURCES}
 (P/'seal6-amendment.json').write_text(json.dumps(row,indent=2)+'\n')
 amendment.verify();print('SPEED4 amendment bound',flush=True)
def tests():
 tests=(('test_fixture_delta','fixture-delta-tests.json',('fixture_delta.py','test_fixture_delta.py','speed4_qualification.py')),
        ('test_seal6_amendment','seal6-amendment-tests.json',('seal6_amendment.py','test_seal6_amendment.py','speed1_qualification.py','speed4_qualification.py')),
        ('test_audit6','audit6-tests.json',('audit6.py','test_audit6.py','speed4_qualification.py')),
        ('test_seal45_bindings','seal45-binding-tests.json',('seal45.py','test_seal45_bindings.py')))
 for module,dest,sources in tests:
  program="import unittest,json; s=unittest.defaultTestLoader.loadTestsFromName("+repr(module)+"); r=unittest.TextTestRunner(verbosity=2).run(s); print(json.dumps(dict(passed=r.wasSuccessful(),checks=r.testsRun,failures=len(r.failures),errors=len(r.errors)))); raise SystemExit(not r.wasSuccessful())"
  with (E/(module+'.log')).open('w') as out:r=subprocess.run([sys.executable,'-B','-c',program],cwd=P,stdout=out,stderr=subprocess.STDOUT)
  if r.returncode:raise RuntimeError(module+' failed; see evidence/speed4/'+module+'.log')
  row=json.loads((E/(module+'.log')).read_text().splitlines()[-1]);row.update(device_executed=False,source_sha256={n:sha(P/n) for n in sources})
  (P/dest).write_text(json.dumps(row,indent=2)+'\n');print(module,row['checks'],'PASS',flush=True)
if __name__=='__main__':
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 bind();tests()
