"""Exact SPEED3 source/evidence amendment; no general reuse of production changes."""
import hashlib,json,gzip
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
RULE='packet45.speed3.single-profile-and-explicit-target-split.2026-10-15'
BEFORE='9e0b3ce4ff13f20c2ec55e2580ae2716bdf6c8ab09aec1297534f9a9cb2aa29e'
PINS={'main.cpp': '6861b569fcff10e8515d1ead9ec2fd4176f273ff00a07e6fc699ac804007738c', 'rank.hpp': '821a0c74403df98de7b6608cac9e9556e257b84ac29e68451482ebbe4e9b2f9b', 'mtp.hpp': 'e9587829d78c599270983ce450755c9fe1aae0b7e98c2ba25a6a5b897a69fd0b', 'pipeline.py': 'b331b810f0ce4025510760c61458b1e0b05551126ab312c4e69d6bc5e019c08b', 'window.py': '6446b7e6abb35f333f8354de35fab6f4ebc66af1703d43bbe1779fd6bf828545', 'memory_gate.py': '76910a7670dcc7db81ba9dea5a2fb717b05e8b5fc945ec852bd7229fab55b07b', 'memory_plan.py': '59305e748f848bdba02d61385c54e95426c752c07ef0a6b1e9dcfe325976318f', 'coordinator_windows.sh': '15e4ca0cb27de2539ee494b18c22c537bdd6618aa1efb997f291f08bb1c37a33', 'cpu_merged_gate.py': '08198b2dd77c2fcd63ed1fdc09576dbf96e1a528da56953f966dcfa0026a029b', 'memory-plan.json': '8c30ff3787b0fe9473d021aff18e70465b6452a5f6b65524d4b8f63336a8de9a', 'plan_group_gate.py': '3f0828e218e6085e190ad1387c29f30a4cfd6919297b305cee4d9c3acb1bff2b'}
COMPILED=('main.cpp','rank.hpp','mtp.hpp')
MIRRORS={'main.cpp': {'old': ['11afd06931951be3f9c5d2ffe3c077960ce1bd430962391c70c8e729fc2daa1b'], 'new': '4ffe0ee8ec6442bed197458dd1ce0da804645227396da9323b44b12dc7ce7859'}, 'rank.hpp': {'old': ['c24f08a558840b32831785d47e2514c7df03e2ce75775e5a848aa13e38d87136'], 'new': '4eef587666b52f9f8d2e8dfcbfef3228e0d4633efc53b76b42b82dab5c127c10'}, 'mtp.hpp': {'old': ['3a87e739de35c7f2e69b5e1393a8e7445097c6a8096bf651219b20daf8959515'], 'new': 'a00b881301da407d85472e6829f2e6493f6585cb504ea58a6de3edb2adca5184'}}
def sha(p):return __import__('speed4_qualification').prior_sha(p)
def before():
 p=P/'evidence/speed3/before-build-receipt.json';assert sha(p)==BEFORE,'SPEED3 baseline changed';return json.loads(p.read_text())
def historical_compiled_sources(current):
 current=__import__('speed4_qualification').historical_compiled_sources(current)
 old=before()['sources'];expected={str((P/n).relative_to(ROOT)) for n in COMPILED}
 assert all(k in old for k in current),'compiled source closure changed'
 assert {k for k in current if current[k]!=old[k]}==expected,'outside fixture/SPEED3 repair'
 assert all(current[str((P/n).relative_to(ROOT))]==PINS[n] for n in COMPILED),'outside fixture/SPEED3 repair'
 return {k:old[k] for k in current}
def source_allowed(path,old):
 path=Path(path)
 if path.parent!=P or path.name not in PINS:return False
 return old==before()['sources'].get(str(path.relative_to(ROOT))) and sha(path)==PINS[path.name]
def effective_sha(path):
 path=Path(path)
 if path.parent==P and path.name in PINS and sha(path)==PINS[path.name]:return before()['sources'][str(path.relative_to(ROOT))]
 return sha(path)
def mirror_allowed(path,old,new):
 path=Path(path);n=path.name
 return n in MIRRORS and str(path)==str((P/'build/checked'/P.relative_to(ROOT)/n).relative_to(ROOT)) and old in MIRRORS[n]['old'] and new==MIRRORS[n]['new']==sha(ROOT/path) and sha(P/n)==PINS[n]
def verify():
 from build import compiled_sources
 current=compiled_sources();historical_compiled_sources(current);current=__import__('speed4_qualification').historical_compiled_sources(current)
 assert all(sha(P/n)==h for n,h in PINS.items()),'SPEED3 runtime source changed'
 gates={n:json.loads((P/n).read_text()) for n in ('speed3-plan-gates.json','speed3-snapshot-gates.json','speed3-event-gates.json','speed3-admission-gates.json')}
 for name,row in gates.items():
  assert row['passed'] and row['device_executed'] is False,name
  for field in ('source_sha256','sources_sha256'):
   for n,h in row.get(field,{}).items():assert sha(P/n)==h,'SPEED3 gate source changed '+n
 plan=gates['speed3-plan-gates.json'];mini=gates['speed3-snapshot-gates.json'];event=gates['speed3-event-gates.json']
 expected={(c,dr,s,kind,r,d) for c in (4096,32768) for dr,s in ((0,0),(1,0),(0,24)) for kind,r in [('target',0),('target',1),('KD',1),('draft',dr)] for d in ('dr0','dr1','forced')}
 assert plan['plan_dispatch_rows']==len(plan['rows'])==72 and {(r['context'],r['draft_rank'],r['target_split'],r['plan'],r['rank'],r['dispatch']) for r in plan['rows']}==expected
 assert plan['removed_target_commands']==192 and all(r['result']['passed'] for r in plan['rows'])
 for r in plan['rows']:
  assert sha(P/('evidence/fix6/dispatch-'+r['dispatch']+'.json'))==r['dispatch_sha256']
  if r['plan']=='target':assert r['group_census']['shared']==0 and r['group_census']['ffn']==((24 if r['target_split'] or r['draft_rank'] else 22) if r['rank']==0 else (24 if r['target_split'] or r['draft_rank'] else 26))
 assert sha(P/'build/speed3-plan/after')==plan['binary_sha256'] and sha(P/'build/speed3-plan/after.cpp')==plan['generated_sha256']
 detail=plan['writer_sites'];assert sha(P/detail['path'])==detail['sha256']
 sites=json.loads(gzip.decompress((P/detail['path']).read_bytes()));assert len(sites)==72
 for row,site in zip(plan['rows'],sites):
  assert row['write_set']['sites_count']==len(site['sites'])
  assert row['write_set']['sites_sha256']==hashlib.sha256(json.dumps(site['sites'],sort_keys=True).encode()).hexdigest()
 assert mini['cases']==63 and mini['gate_count']==54 and len(mini['negative_controls'])==6
 assert mini['build']['compiled_sources_sha256']==current and mini['build']['binary_sha256']==__import__('speed4_qualification').before()['artifacts_sha256']['gnu-host/own-rt-iq3']
 assert all(r['full_state_equal'] for r in mini['rows']) and all(r['rejected'] for r in mini['negative_controls'])
 from seal45 import archive_bound
 for row in mini['owners']:archive_bound(row['archive'])
 cases=json.loads((P/'evidence/speed3/mini-cases.json').read_text());assert cases['passed'] and cases['completed'] and cases['cases']==27
 from cpu_merged_gate import target_equal
 by_name={r['name']:r for r in cases['rows']}
 for row in cases['rows']:archive_bound(row['scratch_archive'])
 for dr,split in ((0,0),(1,0),(0,24)):
  key=f'r{dr}s{split}'
  reference=by_name[key+'-control']['signature']
  for controller in ('native','python'):
   for kind in ('hit','miss','mtp','mtp-wrong'):target_equal(by_name[f'{key}-{controller}-{kind}']['signature'],reference)
   assert by_name[f'{key}-{controller}-mtp']['signature']['draft_state']==by_name[f'{key}-{controller}-mtp-wrong']['signature']['draft_state']
   owners=[r for r in mini['owners'] if r['draft_rank']==dr and r['target_split']==split and r['controller']==controller]
   base=next(r for r in owners if r['cancel_launch']==-1 and not r['omit_required_extent'])
   for row in owners:
    if row['omit_required_extent']:assert row['state']!=base['state']
    else:assert row['state']==base['state'] and row['tokens']==base['tokens']
 assert event['checks']==16 and event['publication_timing_queries']==0 and event['profile_queries_per_three_events']==3
 assert event['budget_negative_controls']==event['sticky_error_checks']==2
 assert sha(P/'build/speed3-events/gate')==event['binary_sha256'] and sha(P/'build/speed3-events/gate.cpp')==event['generated_sha256']
 assert gates['speed3-admission-gates.json']['checks']==10
 from memory_gate import configuration
 # Preserve the historical ledger proof; SPEED6 verifies the current arena ledger separately.
 memory=__import__('speed6_qualification').before()['memory_plan'];old=json.loads((P/'evidence/speed3/before-memory-plan.json').read_text())
 assert all(memory['placements'][key]==old['placements'][key] for key in ('0','1'))
 assert configuration(memory,4096,0,24)['ranks'][0]['free_with_mtp_bytes']==2316749746
 try:configuration(memory,32768,0,24)
 except ValueError:pass
 else:raise AssertionError('32K split admitted')
 return dict(rule=RULE,directive_date='2026-10-15',production_changed_files=list(COMPILED),runtime_sources_sha256=PINS,
  plan_dispatch_rows=72,mini_cases=63,mini_checks=54,event_checks=16,admission_checks=10,
  gate_receipts_sha256={n:sha(P/n) for n in gates},full_state_contract_unchanged=True,
  real_model_cpu_rerun=False,compiler_matrix_rerun=False,
  reuse_justification='Owner SPEED REPAIR 3 extends seal-6 for exactly pinned single-pass draft profiling and admitted explicit 24/24-dr0 at 4K. Fresh metadata, mini full-state, event-lifetime/budget and admission gates; coordinator device oracle windows remain real-model exactness authority.')
