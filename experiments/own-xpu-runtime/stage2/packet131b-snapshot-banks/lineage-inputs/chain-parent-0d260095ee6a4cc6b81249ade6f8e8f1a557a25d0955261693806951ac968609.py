"""Bind the narrow SPEED2 amendment and run only short seal admission tests."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parent;E=P/'evidence/speed2'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def bind():
 f=P/'speed2_qualification.py';s=f.read_text();s=s.replace("MIRROR='MIRROR_PIN'","MIRROR="+repr(sha(P/'build/checked'/P.relative_to(P.parents[3])/'strict_snapshot.hpp')));f.write_text(s)
 import seal6_amendment as amendment
 import speed1_qualification as s1,speed2_qualification as s2
 row=json.loads((P/'seal6-amendment.json').read_text())
 row['speed1_extension']=s1.verify();row['speed2_extension']=s2.verify()
 row['justification']='Owner SEAL6, SPEED REPAIR 1 and SPEED REPAIR 2 directives, 2026-10-15. Retain the pinned fix6 grouping and SPEED1 full-state batching/small-FFN repair; add only a checked conservative speculative write union. Fresh 48-plan metadata sweep and 42 mini executions (36 checks including four rejected required-extent omissions). No pre-device real-model CPU suite or compiler matrix. GNU/device/ASAN rebuilt from current sources; device suite windows retain exactness authority.'
 row['publication_rule']='Speed publication must cite hash-bound passing device suite window receipts for the new artifact identity. Historical CPU cases are not fix6/SPEED1/SPEED2 real-model exactness evidence.'
 row['speed2_files']=['strict_snapshot.hpp',*[p.name for p in sorted(P.glob('speed2_*.py'))],'speed2-plan-gates.json','speed2-snapshot-gates.json','speed2-snapshot-inventory.json','SPEED2-CLOSEOUT.md','evidence/speed2/']
 row['qualification_sources_sha256']={n:sha(P/n) for n in amendment.QUALIFICATION_SOURCES}
 (P/'seal6-amendment.json').write_text(json.dumps(row,indent=2)+'\n')
 amendment.verify();print('SPEED2 amendment bound',flush=True)
def tests():
 tests=(('test_fixture_delta','fixture-delta-tests.json',('fixture_delta.py','test_fixture_delta.py','speed2_qualification.py')),
        ('test_seal6_amendment','seal6-amendment-tests.json',('seal6_amendment.py','test_seal6_amendment.py','speed1_qualification.py','speed2_qualification.py')),
        ('test_audit6','audit6-tests.json',('audit6.py','test_audit6.py','speed2_qualification.py')),
        ('test_seal45_bindings','seal45-binding-tests.json',('seal45.py','test_seal45_bindings.py')))
 for module,dest,sources in tests:
  program="import unittest,json; s=unittest.defaultTestLoader.loadTestsFromName("+repr(module)+"); r=unittest.TextTestRunner(verbosity=2).run(s); print(json.dumps(dict(passed=r.wasSuccessful(),checks=r.testsRun,failures=len(r.failures),errors=len(r.errors)))); raise SystemExit(not r.wasSuccessful())"
  with (E/(module+'.log')).open('w') as out:r=subprocess.run([sys.executable,'-B','-c',program],cwd=P,stdout=out,stderr=subprocess.STDOUT)
  if r.returncode:raise RuntimeError(module+' failed; see evidence/speed2/'+module+'.log')
  row=json.loads((E/(module+'.log')).read_text().splitlines()[-1]);row.update(device_executed=False,source_sha256={n:sha(P/n) for n in sources})
  (P/dest).write_text(json.dumps(row,indent=2)+'\n');print(module,row['checks'],'PASS',flush=True)
if __name__=='__main__':
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 bind();tests()
