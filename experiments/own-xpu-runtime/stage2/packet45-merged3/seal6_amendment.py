"""Pinned fix-6 and SPEED1 evidence reuse; no general production-change waiver."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
RULE='packet45.fix6.device-oracle-authority.2026-10-15'
OLD_MAIN='7e8bb826de6463ca5cb48fa62be891f78cbcf71eba9011a2d5a79ab3f6a47296'
NEW_MAIN='1263d055aae92ccb78e541fabbf583e5d1737a5597ad9517213fecf875d2a53f'
BASELINE='7e0317b026d15fafe0e223040a0760bc81c6cb5b4db45574448e69ff0e5f110e'
QUALIFICATION_SOURCES=('seal6_amendment.py','seal_context.py','seal45.py','fixture_delta.py','draft_window.py','copy_adoption_gate.py','audit6.py','test_fixture_delta.py','test_seal6_amendment.py','../../../../scripts/promotion_evidence.py','plan_group_gate.py','speed1_qualification.py','speed1_plan_gate.py','speed1_snapshot_gate.py','speed1_snapshot_inventory.py')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def baseline():
 p=P/'evidence/fix6/before-build-receipt.json'
 assert sha(p)==BASELINE,'seal6 baseline changed'
 return json.loads(p.read_text())
def record():return json.loads((P/'seal6-amendment.json').read_text())
def verify():
 from build import compiled_sources
 from plan_group_gate import verify as plan_verify
 old=baseline();now=compiled_sources();key=str((P/'main.cpp').relative_to(ROOT))
 assert sha(P/'evidence/fix6/before-main.cpp.txt')==OLD_MAIN and now[key]==NEW_MAIN,'outside fixture/fix6 repair'
 from speed1_qualification import verify as speed_verify,PINS
 speed=speed_verify()
 assert {k for k in now if old['sources'].get(k)!=now[k]}=={key,*[str((P/n).relative_to(ROOT)) for n in PINS]},'outside fixture/fix6 repair'
 gate=plan_verify();r=record()
 assert r['rule']==RULE and r['directive_date']=='2026-10-15'
 assert r['plan_dispatch_rows']==48 and r['plan_gate_sha256']==sha(P/'fix6-plan-gates.json')
 assert r['production_changed_files']==['main.cpp','p39_plan.hpp','strict_snapshot.hpp']
 assert r['speed1_extension']==speed,'SPEED1 amendment evidence changed'
 assert set(r['qualification_sources_sha256'])==set(QUALIFICATION_SOURCES),'amendment change set differs'
 for n,h in r['qualification_sources_sha256'].items():assert sha(P/n)==h,'amendment source changed '+n
 assert r['required_device_windows']==['W2m','WS','WSs','WS128x']
 return r
def source_matches(path,digest):
 """Accept only pinned historical provenance; callers still validate outputs."""
 path=Path(path)
 if sha(path)==digest:return True
 if path==P/'main.cpp':return digest==OLD_MAIN and sha(path)==NEW_MAIN
 from speed1_qualification import source_allowed,before
 if source_allowed(path,digest):return True
 r=record();key=str(path.relative_to(ROOT))
 return (path.parent==P and path.name in r['qualification_sources_sha256']
         and digest in {baseline()['sources'].get(key),before()['sources'].get(key)}
         and sha(path)==r['qualification_sources_sha256'][path.name])
def maps_match(old,current):
 return set(old)==set(current) and all(old[k]==current[k] or source_matches(ROOT/k,old[k]) for k in old)
def fixture_identity(old,current):
 a=dict(old);b=dict(current)
 x=a.pop('compiled_sources_and_headers_sha256');y=b.pop('compiled_sources_and_headers_sha256')
 if a!=b or set(x)!=set(y):return False
 for k in x:
  if x[k]==y[k]:continue
  from speed1_qualification import mirror_allowed
  if mirror_allowed(k,x[k],y[k]):continue
  # The generated checked main differs only by the pinned grouping repair.
  if not k.endswith('/build/checked/'+str(P.relative_to(ROOT))+'/main.cpp'):return False
  if x[k]!='11afd06931951be3f9c5d2ffe3c077960ce1bd430962391c70c8e729fc2daa1b':return False
  if sha(P/'main.cpp')!=NEW_MAIN or y[k]!=sha(ROOT/k) or y[k]!='60cab241e95a4d2798b3149032198210fcf8040d5cf1f2e541341f2a8e1c181a':return False
 return True
def gate_unchanged(name):
 assert sha(P/name)==baseline()['gate_receipts'][name],'historical gate changed '+name
def publication_evidence(receipts,artifacts):
 """Publication callers must supply actual passing, same-build device windows."""
 found=set()
 for r in receipts:
  assert r.get('passed') is True and r.get('device_executed') is True
  assert not r.get('diagnostic_unsealed') and r.get('qualifying',True) is not False
  assert r['artifacts_sha256']==artifacts
  found.add(r['window'])
 assert set(record()['required_device_windows'])<=found,'passing device suite windows required for publication'
