"""Pinned fix-6 and SPEED1 evidence reuse; no general production-change waiver."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
RULE='packet45.fix6.device-oracle-authority.2026-10-15'
OLD_MAIN='7e8bb826de6463ca5cb48fa62be891f78cbcf71eba9011a2d5a79ab3f6a47296'
NEW_MAIN='1263d055aae92ccb78e541fabbf583e5d1737a5597ad9517213fecf875d2a53f'
BASELINE='7e0317b026d15fafe0e223040a0760bc81c6cb5b4db45574448e69ff0e5f110e'
QUALIFICATION_SOURCES=('speed7_qualification.py','speed7_rebuild.py','speed7_finalize.py','speed7_plan_gate.py','speed7_snapshot_gate.py','speed7_memory_gate.py','speed7_copy_gate.py','speed6_qualification.py','speed6_rebuild.py','speed6_finalize.py','speed6_plan_gate.py','speed6_snapshot_gate.py','speed6_memory_gate.py','test_speed6.py','test_seal45_bindings.py','speed5_qualification.py','speed5_prepare.py','speed5_finalize.py','speed5_rebuild.py','speed5_plan_gate.py','speed5_snapshot_gate.py','test_speed5.py','speed4_qualification.py','speed4_rebuild.py','speed4_plan_gate.py','speed4_snapshot_gate.py','speed4_snapshot_inventory.py','speed4_attribution.py','speed4_finalize.py','seal6_amendment.py','seal_context.py','seal45.py','fixture_delta.py','draft_window.py','copy_adoption_gate.py','audit6.py','test_fixture_delta.py','test_seal6_amendment.py','../../../../scripts/promotion_evidence.py','plan_group_gate.py','speed1_qualification.py','speed1_plan_gate.py','speed1_snapshot_gate.py','speed1_snapshot_inventory.py','speed2_qualification.py','speed2_plan_gate.py','speed2_snapshot_gate.py','speed2_snapshot_inventory.py','speed2_rebuild.py','speed2_attribution.py','speed2_finalize.py','speed3_qualification.py','speed3_rebuild.py','speed3_plan_gate.py','speed3_snapshot_gate.py','speed3_event_gate.py','test_speed3.py','speed3_finalize.py','memory_gate.py','memory_plan.py','pipeline.py','window.py','cpu_merged_gate.py','coordinator_windows.sh','test_window_seal_admission.py')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def baseline():
 p=P/'evidence/fix6/before-build-receipt.json'
 assert sha(p)==BASELINE,'seal6 baseline changed'
 return json.loads(p.read_text())
def record():return json.loads((P/'seal6-amendment.json').read_text())
def verify():
 from build import compiled_sources
 from plan_group_gate import verify as plan_verify
 from speed3_qualification import historical_compiled_sources,verify as speed3_verify
 old=baseline();now=historical_compiled_sources(compiled_sources());key=str((P/'main.cpp').relative_to(ROOT))
 assert sha(P/'evidence/fix6/before-main.cpp.txt')==OLD_MAIN and now[key]==NEW_MAIN,'outside fixture/fix6 repair'
 from speed1_qualification import verify as speed_verify,PINS
 speed=speed_verify()
 from speed2_qualification import verify as speed2_verify
 speed2=speed2_verify()
 assert {k for k in now if old['sources'].get(k)!=now[k]}=={key,*[str((P/n).relative_to(ROOT)) for n in PINS]},'outside fixture/fix6 repair'
 gate=plan_verify();r=record()
 assert r['rule']==RULE and r['directive_date']=='2026-10-15'
 assert r['plan_dispatch_rows']==48 and r['plan_gate_sha256']==sha(P/'fix6-plan-gates.json')
 assert r['production_changed_files']==['main.cpp','mtp.hpp','native_controller.hpp','p39_plan.hpp','rank.hpp','strict_snapshot.hpp']
 assert r['speed7_extension']==__import__('speed7_qualification').verify(),'SPEED7 amendment evidence changed'
 assert r['speed6_extension']==__import__('speed6_qualification').verify(),'SPEED6 amendment evidence changed'
 assert r['speed5_extension']==__import__('speed5_qualification').verify(),'SPEED5 amendment evidence changed'
 assert r['speed4_extension']==__import__('speed4_qualification').verify(),'SPEED4 amendment evidence changed'
 assert r['speed3_extension']==speed3_verify(),'SPEED3 amendment evidence changed'
 assert r['speed1_extension']==speed,'SPEED1 amendment evidence changed'
 assert r['speed2_extension']==speed2,'SPEED2 amendment evidence changed'
 assert set(r['qualification_sources_sha256'])==set(QUALIFICATION_SOURCES),'amendment change set differs'
 for n,h in r['qualification_sources_sha256'].items():assert sha(P/n)==h,'amendment source changed '+n
 assert r['required_device_windows']==['W2m','WS','WSs','WS128x']
 return r
def source_matches(path,digest):
 """Accept only pinned historical provenance; callers still validate outputs."""
 path=Path(path)
 if sha(path)==digest:return True
 if __import__('speed7_qualification').source_allowed(path,digest):return True
 if __import__('speed6_qualification').source_allowed(path,digest):return True
 if __import__('speed5_qualification').source_allowed(path,digest):return True
 if __import__('speed4_qualification').source_allowed(path,digest):return True
 from speed3_qualification import source_allowed as speed3_source,effective_sha
 if speed3_source(path,digest):return True
 if path==P/'main.cpp':return digest==OLD_MAIN and effective_sha(path)==NEW_MAIN
 from speed1_qualification import source_allowed,before
 if source_allowed(path,digest):return True
 from speed2_qualification import source_allowed as speed2_source,before as speed2_before
 if speed2_source(path,digest):return True
 r=record();key=str(path.relative_to(ROOT))
 return (path.parent==P and path.name in r['qualification_sources_sha256']
         and digest in {baseline()['sources'].get(key),before()['sources'].get(key),speed2_before()['sources'].get(key),__import__('speed3_qualification').before()['sources'].get(key),__import__('speed4_qualification').before()['sources'].get(key),__import__('speed5_qualification').before()['sources'].get(key),__import__('speed6_qualification').before()['sources'].get(key),__import__('speed7_qualification').before()['sources'].get(key)}
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
  from speed3_qualification import mirror_allowed as speed3_mirror
  if __import__('speed7_qualification').mirror_allowed(k,x[k],y[k]):continue
  if __import__('speed6_qualification').mirror_allowed(k,x[k],y[k]):continue
  if __import__('speed5_qualification').mirror_allowed(k,x[k],y[k]):continue
  if __import__('speed4_qualification').mirror_allowed(k,x[k],y[k]):continue
  if speed3_mirror(k,x[k],y[k]) or mirror_allowed(k,x[k],y[k]):continue
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
