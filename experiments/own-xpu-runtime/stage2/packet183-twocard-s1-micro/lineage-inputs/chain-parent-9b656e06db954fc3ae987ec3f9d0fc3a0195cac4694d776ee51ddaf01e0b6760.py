"""Pinned SPEED4 redo-only bank restore reduction; prior evidence stays historical."""
import hashlib,json,gzip
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
RULE='packet45.speed4.confirmed-redo-spare-bank-overwrite.2026-10-15'
BEFORE='8460585fe53879223066a5d54799c9f105c73002adfc09fc9a743ceaee7e3fa8'
PINS={'strict_snapshot.hpp': 'f3df4371d04b49121064a0215febd0a48806443642dfb54784b3d4429fe98a2c', 'rank.hpp': '80754bb682e89ff9be6c3dc66328f91ef73147cecf562a473040882654c9dabc', 'native_controller.hpp': '5f04a87a9bd7dbdd482f75b4fcb3c3157f61130b4ce1535d2ef0267c4155b67a', 'pipeline.py': 'd059aca9a446a9d66e01ae8f7d11eff91585a3edb82d9cba780922d15bb7528f'}
COMPILED=('strict_snapshot.hpp','rank.hpp','native_controller.hpp')
MIRRORS={'strict_snapshot.hpp': {'old': ['42a26f4aa254eab1b52edc2ea115d9082770d2a691d0b8eb0ac1e342d98ee885', '60957654a6a418782f7b1cd7930d4e3bc499784f157d25a64d02f5220c078ad7', '78820f2338872bf5f0d17f44885a66d47e0448e3ede7739fdf02090630319018'], 'new': '29a395575648247848372d056479f26f5252502e9ce1550d4a0dfd05699656d0'}, 'rank.hpp': {'old': ['c24f08a558840b32831785d47e2514c7df03e2ce75775e5a848aa13e38d87136', '4eef587666b52f9f8d2e8dfcbfef3228e0d4633efc53b76b42b82dab5c127c10'], 'new': 'c85dc64000c23352d991c8eb2965fa7d2e7fc99ef305f6a4f58f7676baeccabf'}, 'native_controller.hpp': {'old': ['8934b23f9fee65be3b85e47864533326ec555b3c31b51054e5a81e00c4401cb1'], 'new': '2317075b562df4e0f5159cbc2113d6b9a3d4f392d6670a2b32a90edb6ac0110f'}}
def sha(p):return __import__('speed5_qualification').prior_sha(p)
def before():
 p=P/'evidence/speed4/before-build-receipt.json';assert sha(p)==BEFORE,'SPEED4 baseline changed';return json.loads(p.read_text())
def historical_compiled_sources(current):
 current=__import__('speed5_qualification').historical_compiled_sources(current)
 old=before()['sources'];expected={str((P/n).relative_to(ROOT)) for n in COMPILED}
 assert all(k in old for k in current),'compiled source closure changed'
 assert {k for k in current if current[k]!=old[k]}==expected,'outside fixture/SPEED4 repair'
 assert all(current[str((P/n).relative_to(ROOT))]==PINS[n] for n in COMPILED),'outside fixture/SPEED4 repair'
 return {k:old[k] for k in current}
def source_allowed(path,old):
 path=Path(path)
 return path.parent==P and path.name in PINS and old==before()['sources'].get(str(path.relative_to(ROOT))) and sha(path)==PINS[path.name]
def prior_sha(path):
 path=Path(path);actual=sha(path)
 if path.parent==P and path.name in PINS and actual==PINS[path.name]:return before()['sources'][str(path.relative_to(ROOT))]
 return actual

def mirror_allowed(path,old,new):
 path=Path(path);n=path.name
 return n in MIRRORS and str(path)==str((P/'build/checked'/P.relative_to(ROOT)/n).relative_to(ROOT)) and old in MIRRORS[n]['old'] and new==MIRRORS[n]['new']==sha(ROOT/path) and sha(P/n)==PINS[n]
def verify():
 from build import compiled_sources
 current=compiled_sources();historical_compiled_sources(current);current=__import__('speed5_qualification').historical_compiled_sources(current)
 assert all(sha(P/n)==h for n,h in PINS.items()),'SPEED4 runtime source changed'
 gates={n:json.loads((P/n).read_text()) for n in ('speed4-plan-gates.json','speed4-snapshot-gates.json','speed4-snapshot-inventory.json')}
 for name,row in gates.items():
  assert row['passed'] and row['device_executed'] is False,name
  for field in ('source_sha256','sources_sha256'):
   for n,h in row.get(field,{}).items():assert sha(P/n)==h,'SPEED4 gate source changed '+n
 plan=gates['speed4-plan-gates.json'];mini=gates['speed4-snapshot-gates.json'];inventory=gates['speed4-snapshot-inventory.json']
 expected={(c,dr,s,kind,r,d) for c in (4096,32768) for dr,s in ((0,0),(1,0),(0,24)) for kind,r in [('target',0),('target',1),('KD',1),('draft',dr)] for d in ('dr0','dr1','forced')}
 assert plan['plan_dispatch_rows']==len(plan['rows'])==72 and {(r['context'],r['draft_rank'],r['target_split'],r['plan'],r['rank'],r['dispatch']) for r in plan['rows']}==expected
 assert plan['removed_target_commands']==192 and all(r['result']['passed'] for r in plan['rows'])
 assert sha(P/'build/speed4-plan/after')==plan['binary_sha256'] and sha(P/'build/speed4-plan/after.cpp')==plan['generated_sha256']
 for r in plan['rows']:
  assert sha(P/('evidence/fix6/dispatch-'+r['dispatch']+'.json'))==r['dispatch_sha256']
  assert all(b['full_byte_coverage'] and b['inputs_use_distinct_active_bank'] and b['bytes']>0 for b in r['write_set']['redo_banks'])
  if r['plan']=='target' and r['rank']==0:assert r['write_set']['redo_banks']
 assert mini['cases']==93 and mini['gate_count']==78 and len(mini['negative_controls'])==6
 assert mini['build']['compiled_sources_sha256']==current and mini['build']['binary_sha256']==__import__('speed5_qualification').before()['artifacts_sha256']['gnu-host/own-rt-iq3']
 assert all(r['full_state_equal'] for r in mini['rows']) and all(r['rejected'] for r in mini['negative_controls'])
 from seal45 import archive_bound
 for row in mini['owners']:archive_bound(row['archive'])
 cases=json.loads((P/'evidence/speed4/mini-cases.json').read_text());assert cases['passed'] and cases['completed'] and cases['cases']==51
 from cpu_merged_gate import target_equal
 by_name={r['name']:r for r in cases['rows']}
 for row in cases['rows']:archive_bound(row['scratch_archive'])
 for dr,split in ((0,0),(1,0),(0,24)):
  key=f'r{dr}s{split}';reference=by_name[key+'-control']['signature']
  for controller in ('native','python'):
   for kind in ('hit','miss','mtp','mtp-wrong'):target_equal(by_name[f'{key}-{controller}-{kind}']['signature'],reference)
   assert by_name[f'{key}-{controller}-mtp']['signature']['draft_state']==by_name[f'{key}-{controller}-mtp-wrong']['signature']['draft_state']
   boundary=by_name[f'{key}-{controller}-boundary-reference']['signature']
   partial=[r for n,r in by_name.items() if n.startswith(f'{key}-{controller}-partial-redo-')]
   assert len(partial)==3
   for row in partial:target_equal(row['signature'],boundary)
   owners=[r for r in mini['owners'] if r['draft_rank']==dr and r['target_split']==split and r['controller']==controller]
   base=next(r for r in owners if r['cancel_launch']==-1 and not r['omit_required_extent'] and not r['abandoned_redo'])
   for row in owners:
    if row['omit_required_extent']:assert row['state']!=base['state']
    else:assert row['state']==base['state'] and row['tokens']==base['tokens']
    if row['abandoned_redo']:assert row['snapshot']['redo_fallbacks']==1
 from speed2_snapshot_inventory import schedule
 proof=inventory['writer_proof'];assert sha(P/proof['path'])==proof['sha256']
 details=json.loads(gzip.decompress((P/proof['path']).read_bytes()));assert len(details)==len(inventory['rows'])==18
 assert inventory['plan_gate_sha256']==sha(P/'speed4-plan-gates.json')
 for r,w in zip(inventory['rows'],details):
  assert all(r[k]==w[k] for k in ('context','draft_rank','target_split','position'))
  plans=[v for v in plan['rows'] if v['plan']=='target' and v['rank']==0 and all(v[k]==r[k] for k in ('context','draft_rank','target_split'))]
  assert len(plans)==3
  banks={v['name']:(v['first_writer'],v['bytes']) for v in plans[0]['write_set']['redo_banks']}
  assert all({v['name']:(v['first_writer'],v['bytes']) for v in p['write_set']['redo_banks']}==banks for p in plans)
  assert r['capture_bytes']==r['restore_bytes']==sum(e['captured_bytes'] for e in w['extents'])
  assert r['redo_restore_bytes']==sum(e['captured_bytes'] for e in w['extents'] if not e['redo_overwritten'])
  assert r['redo_omitted_bytes']==r['capture_bytes']-r['redo_restore_bytes']>0
  assert r['redo_restore_submissions']==len(schedule([e['captured_bytes'] for e in w['extents'] if not e['redo_overwritten'] and e['captured_bytes']]))
  for e in w['extents']:
   if e['redo_overwritten']:
    assert e['redo_first_writer'] and e['redo_covered_bytes']==e['captured_bytes']==e['allocation_bytes'] and e['offset']==0
    assert banks[e['name']]==(e['redo_first_writer'],e['redo_covered_bytes'])
 return dict(rule=RULE,directive_date='2026-10-15',production_changed_files=list(COMPILED),runtime_sources_sha256=PINS,
  plan_dispatch_rows=72,mini_cases=93,mini_checks=78,required_extent_negative_controls=6,
  gate_receipts_sha256={n:sha(P/n) for n in gates},full_state_end_state_contract_unchanged=True,
  terminal_rollback_full_write_set=True,abandoned_redo_restores_before_observation=True,
  real_model_cpu_rerun=False,compiler_matrix_rerun=False,
  reuse_justification='Owner SPEED REPAIR 4 extends seal-6 for exactly pinned confirmed-redo spare-bank overwrite proof and guarded full fallback. Arithmetic, dispatch and snapshot capture unchanged. Fresh plan/coverage mutations and mini complete-state cases; coordinator device W2m/WS/WSs/WS128x remain real-model exactness authority.')
