"""Narrow SPEED2 write-set extension; retained evidence keeps its old identity."""
import gzip,hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
RULE='packet45.speed2.parallel-write-set-union.2026-10-15'
BEFORE='a199dffa53d9f31e30c1b805ffa251694829bc0beb57d7f7322dc998eccc8c28'
PINS={'strict_snapshot.hpp':'a199ce9ce73004e408a474d63c3c3d22da25b5c5d498e293e0e3fe4a7f874c04'}
MIRROR='78820f2338872bf5f0d17f44885a66d47e0448e3ede7739fdf02090630319018'
def sha(p):return __import__('speed4_qualification').prior_sha(p)
def before():
 p=P/'evidence/speed2/before-build-receipt.json';assert sha(p)==BEFORE,'SPEED2 baseline changed';return json.loads(p.read_text())
def source_allowed(path,old):
 path=Path(path);key=str(path.relative_to(ROOT))
 return path.parent==P and path.name in PINS and old==before()['sources'][key] and sha(path)==PINS[path.name]
def mirror_allowed(path,old,new):
 p=Path(path)
 return str(p)==str((P/'build/checked'/P.relative_to(ROOT)/'strict_snapshot.hpp').relative_to(ROOT)) and old in ('42a26f4aa254eab1b52edc2ea115d9082770d2a691d0b8eb0ac1e342d98ee885','60957654a6a418782f7b1cd7930d4e3bc499784f157d25a64d02f5220c078ad7') and new==MIRROR and sha(P/'strict_snapshot.hpp')==PINS['strict_snapshot.hpp'] and sha(ROOT/p)==new

def verify():
 from build import compiled_sources
 from speed3_qualification import historical_compiled_sources
 old=before();now=historical_compiled_sources(compiled_sources())
 expected={str((P/n).relative_to(ROOT)) for n in PINS}
 assert {k for k in now if old['sources'].get(k)!=now[k]}==expected,'outside fixture/SPEED2 repair'
 assert all(now[str((P/n).relative_to(ROOT))]==h for n,h in PINS.items()),'outside fixture/SPEED2 repair'
 plan=json.loads((P/'speed2-plan-gates.json').read_text());mini=json.loads((P/'speed2-snapshot-gates.json').read_text());inventory=json.loads((P/'speed2-snapshot-inventory.json').read_text())
 for row in (plan,mini,inventory):
  assert row['passed'] and row['device_executed'] is False
  for field in ('sources_sha256','source_sha256'):
   for n,h in row.get(field,{}).items():assert sha(P/n)==h or __import__('speed3_qualification').source_allowed(P/n,h),'SPEED2 source changed '+n
 assert plan['plan_dispatch_rows']==len(plan['rows'])==48 and plan['removed_target_commands']==192
 assert sha(P/'build/speed2-plan/after')==plan['binary_sha256'] and sha(P/'build/speed2-plan/after.cpp')==plan['generated_sha256']
 assert sha(P/'build/input/plan.tsv')==plan['metadata_sha256']
 detail=plan['writer_sites'];assert sha(P/detail['path'])==detail['sha256']
 sites=json.loads(gzip.decompress((P/detail['path']).read_bytes()));assert len(sites)==48
 for r,d in zip(plan['rows'],sites):
  assert all(r[k]==d[k] for k in ('plan','context','draft_rank','rank','dispatch'))
  assert r['write_set']['sites_count']==len(d['sites'])
  assert r['write_set']['sites_sha256']==hashlib.sha256(json.dumps(d['sites'],sort_keys=True).encode()).hexdigest()
  assert r['write_set']['scratch_bound']==max(x['scratch_bytes'] for x in d['sites'])
  assert r['result']['passed'] and sha(P/('evidence/fix6/dispatch-'+r['dispatch']+'.json'))==r['dispatch_sha256']
  if r['plan']!='draft':assert r['group_census']['shared']==0 and r['group_census']['ffn']>0
 assert mini['cases']==42 and mini['gate_count']==36 and len(mini['negative_controls'])==4
 assert mini['build']['binary_sha256']==__import__('speed3_qualification').before()['artifacts_sha256']['gnu-host/own-rt-iq3']
 assert mini['build']['compiled_sources_sha256']==now
 historical=json.loads((P/'speed1-snapshot-gates.json').read_text())
 assert len(mini['owners'])==len(historical['owners'])
 for new,old_owner in zip(mini['owners'],historical['owners']):
  assert all(new[k]==old_owner[k] for k in ('draft_rank','controller','cancel_launch','omit_required_extent'))
  assert new['snapshot']['capacity_bytes']==old_owner['snapshot']['capacity_bytes']
  if new['snapshot']['captures']:assert new['snapshot']['snapshot_payload_bytes']<old_owner['snapshot']['snapshot_payload_bytes'],'write-set reduction not exercised'
 assert all(r['full_state_equal'] for r in mini['rows']) and all(r['rejected'] for r in mini['negative_controls'])
 from seal45 import archive_bound
 for r in mini['owners']:archive_bound(r['archive'])
 cases=json.loads((P/'evidence/speed2/mini-cases.json').read_text());assert cases['passed'] and cases['completed'] and cases['cases']==18
 for r in cases['rows']:archive_bound(r['scratch_archive'])
 by_name={r['name']:r for r in cases['rows']}
 from cpu_merged_gate import target_equal
 for rank in (0,1):
  reference=by_name[f'r{rank}-control']['signature']
  for controller in ('native','python'):
   for kind in ('hit','miss','mtp','mtp-wrong'):target_equal(by_name[f'r{rank}-{controller}-{kind}']['signature'],reference)
   assert by_name[f'r{rank}-{controller}-mtp']['signature']['draft_state']==by_name[f'r{rank}-{controller}-mtp-wrong']['signature']['draft_state'],'draft confirmed state changed'
   owners=[r for r in mini['owners'] if r['draft_rank']==rank and r['controller']==controller]
   reference=next(r for r in owners if r['cancel_launch']==-1 and not r['omit_required_extent'])
   for r in owners:
    if r['omit_required_extent']:assert r['state']!=reference['state'],'excluded extent escaped full-state check'
    else:
     assert r['state']==reference['state'] and r['tokens']==reference['tokens'],'terminal full-state difference'
     if r['cancel_launch']>=0:
      speculative=[t for t in r['timings'] if t['speculative']]
      assert len(speculative)==1 and speculative[0]['position']==32 and speculative[0]['launch_extent']==64,'terminal gate missed 32-to-64 crossing'
   reference=by_name[f'r{rank}-control']['signature']
 from speed2_snapshot_inventory import schedule
 proof=inventory['writer_proof'];assert sha(P/proof['path'])==proof['sha256']
 writer_rows=json.loads(gzip.decompress((P/proof['path']).read_bytes()));assert len(writer_rows)==proof['extents']==12
 assert inventory['plan_gate_sha256']==sha(P/'speed2-plan-gates.json')
 for n,h in inventory['input_sha256'].items():assert sha(P/n)==h
 for r,w in zip(inventory['rows'],writer_rows):
  assert (r['draft_rank'],r['context'],r['position'])==(w['draft_rank'],w['context'],w['position'])
  extents=w['extents'];assert all(0<=x['offset']<=x['allocation_bytes'] and 0<=x['captured_bytes']<=x['allocation_bytes']-x['offset'] for x in extents)
  assert r['capture_bytes']==r['restore_bytes']==sum(map(sum,r['batches']))==sum(x['captured_bytes'] for x in extents)
  assert r['capture_submissions']==r['restore_submissions']==len(r['batches'])
  assert r['batches']==schedule([x['captured_bytes'] for x in extents if x['captured_bytes']])
  matching=[x for x in plan['rows'] if (x['plan'],x['rank'],x['context'],x['draft_rank'])==('target',0,r['context'],r['draft_rank'])]
  assert len(matching)==3 and all(x['write_set']['scratch_bound']==r['scratch_bound'] for x in matching)
  qsa={x['name']:x for x in matching[0]['write_set']['qsa_rows']}
  for x in extents:
   if x['name']=='card0:operator-scratch':assert x['captured_bytes']==r['scratch_bound']
   elif x['name'] in qsa:
    q=qsa[x['name']];assert x['captured_bytes']==q['row_bytes'] and x['allocation_bytes']==q['allocation_bytes']
    assert x['offset']==(r['position']//4 if q['pooled'] else r['position'])*q['row_bytes']
   else:assert x['offset']==0 and x['captured_bytes']==x['allocation_bytes'],'unproved exclusion'
 return dict(rule=RULE,directive_date='2026-10-15',production_changed_files=sorted(PINS),
  production_sources_sha256=PINS,plan_dispatch_rows=48,mini_cases=42,mini_checks=36,
  gate_receipts_sha256={n:sha(P/n) for n in ('speed2-plan-gates.json','speed2-snapshot-gates.json','speed2-snapshot-inventory.json')},
  full_state_contract_unchanged=True,write_set='Checked conservative union: parallel scratch prefix and current QSA rows; every other prior extent retained; unknown/reference fallback is full allocation.',
  reuse_justification='Owner SPEED REPAIR 2 extends seal-6 on 2026-10-15. Historical real-model/compiler/fixture evidence retains its original identity. Fresh mini full-state, required-extent negative controls and metadata writer-bound sweep cover this pinned change; passing coordinator device oracle windows remain exactness authority.')
