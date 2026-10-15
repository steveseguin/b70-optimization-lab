"""Exact SPEED7 size-aware snapshot batching amendment, with fresh bounded CPU proof."""
import gzip,hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
RULE='packet45.speed7.size-aware-snapshot-batches.2026-10-15'
BEFORE='9b6fa7f397151c380a25f79dc3cf08abca1c70853300d7159febbf9456b35fbf'
PINS={'strict_snapshot.hpp': 'af6ddbd8bf57e50b2c5d75c93b20d0c3d9bf8d692e020a728ca662d7b1d6e226'}
COMPILED=('strict_snapshot.hpp',)
MIRRORS={'strict_snapshot.hpp': {'old': ['42a26f4aa254eab1b52edc2ea115d9082770d2a691d0b8eb0ac1e342d98ee885', '60957654a6a418782f7b1cd7930d4e3bc499784f157d25a64d02f5220c078ad7', '78820f2338872bf5f0d17f44885a66d47e0448e3ede7739fdf02090630319018', '29a395575648247848372d056479f26f5252502e9ce1550d4a0dfd05699656d0'], 'new': '3f188b5ff668854d3f6ca45ac08f807750d03261a8f3cdaab7d60c61e0a30646'}}
def sha(p):
 p=Path(p)
 if not p.exists():
  for name in ('results-f912fdaf6','results-65c5eb22b','results-9b91d3270'):
   root=P/'build'/name
   if p.is_relative_to(root):p=Path('/home/steve/own-xpu-runtime-results/packet45')/name/p.relative_to(root);break
 return hashlib.sha256(p.read_bytes()).hexdigest()
def before():
 p=P/'evidence/speed7/before-build-receipt.json';assert sha(p)==BEFORE,'SPEED7 baseline changed';return json.loads(p.read_text())
def historical_compiled_sources(current):
 old=before()['sources'];keys={str((P/n).relative_to(ROOT)) for n in COMPILED}
 assert all(n in old for n in current),'compiled source closure changed'
 assert {n for n in current if current[n]!=old[n]}==keys,'outside fixture/SPEED7 repair'
 assert all(current[str((P/n).relative_to(ROOT))]==PINS[n] for n in COMPILED),'outside fixture/SPEED7 repair'
 return {n:old[n] for n in current}
def prior_sha(path):
 path=Path(path);actual=sha(path)
 if path.parent==P and path.name in PINS and actual==PINS[path.name]:return before()['sources'][str(path.relative_to(ROOT))]
 return actual
def source_allowed(path,old):
 path=Path(path)
 return path.parent==P and path.name in PINS and sha(path)==PINS[path.name] and old==before()['sources'].get(str(path.relative_to(ROOT)))
def mirror_allowed(path,old,new):
 path=Path(path);n=path.name
 return n in MIRRORS and str(path)==str((P/'build/checked'/P.relative_to(ROOT)/n).relative_to(ROOT)) and old in MIRRORS[n]['old'] and new==MIRRORS[n]['new']==sha(ROOT/path) and sha(P/n)==PINS[n]
def verify():
 from build import compiled_sources
 current=compiled_sources();historical_compiled_sources(current)
 assert all(sha(P/n)==h for n,h in PINS.items()),'SPEED7 runtime/admission source changed'
 gates={n:json.loads((P/n).read_text()) for n in ('speed7-plan-gates.json','speed7-snapshot-gates.json','speed7-memory-gates.json','speed7-copy-gates.json')}
 for name,row in gates.items():
  assert row['passed'] and row['device_executed'] is False,name
  for field in ('source_sha256','sources_sha256'):
   for n,h in row.get(field,{}).items():assert sha(P/n)==h,'stale SPEED7 source '+n
 plan=gates['speed7-plan-gates.json'];mini=gates['speed7-snapshot-gates.json'];admit=gates['speed7-memory-gates.json']
 expected={(c,dr,s,k,r,d) for c in (4096,32768) for dr,s in ((0,0),(1,0),(0,24),(1,24),(0,23),(1,23)) for k,r in [('target',0),('target',1),('KD',1),('draft',dr)] for d in ('dr0','dr1','forced')}
 assert plan['plan_dispatch_rows']==len(plan['rows'])==144
 assert {(r['context'],r['draft_rank'],r['target_split'],r['plan'],r['rank'],r['dispatch']) for r in plan['rows']}==expected
 assert plan['removed_target_commands']==192 and all(r['result']['passed'] for r in plan['rows'])
 assert plan['weight_bytes_read']==0 and plan['metadata_sha256']==sha(P/'build/input/plan.tsv')
 details=plan['writer_sites'];assert sha(P/details['path'])==details['sha256']
 writers=json.loads(gzip.decompress((P/details['path']).read_bytes()));assert len(writers)==details['rows']==144
 for r,w in zip(plan['rows'],writers):
  assert all(r[k]==w[k] for k in ('context','draft_rank','target_split','plan','rank','dispatch'))
  assert r['write_set']['sites_count']==len(w['sites']) and r['write_set']['sites_sha256']==hashlib.sha256(json.dumps(w['sites'],sort_keys=True).encode()).hexdigest()
  assert all(v['full_byte_coverage'] and v['inputs_use_distinct_active_bank'] and v['bytes']>0 for v in r['write_set']['redo_banks'])
  allocation=r['scratch_allocation']
  reduced=(r['context'],r['draft_rank'],r['target_split'])==(4096,1,23) and r['plan']!='draft'
  assert allocation['reduced']==reduced and allocation['bytes']==(8 if reduced or r['plan']=='draft' else 256)*1024**2
  assert allocation['kernel_read_write_requirements_checked'] and allocation['reference_preserved']
  assert r['write_set']['scratch_bound']<=allocation['bytes']
  sparse=r['sparse_workspace'];assert sparse['passed'] and sparse['owner_checks']>0 and sparse['negative_controls']==3
  assert sparse['workspace_peak_bytes']<=8*1024**2 and sparse['scratch_peak_bytes']==r['write_set']['scratch_bound']
  assert sparse['maximum_copy']<=134217728 and sparse['device_executed'] is False
  assert sha(P/('evidence/fix6/dispatch-'+r['dispatch']+'.json'))==r['dispatch_sha256']
 assert plan['temporary_probe_removed']
 for name,key in (('after','binary_sha256'),('after.cpp','generated_sha256')):
  archive=plan['probe_archives'][name];assert sha(P/archive['path'])==archive['sha256']
  assert hashlib.sha256(gzip.decompress((P/archive['path']).read_bytes())).hexdigest()==plan[key]
 from seal45 import archive_bound
 from cpu_merged_gate import target_equal
 assert mini['cases']==93 and mini['gate_count']==78 and len(mini['negative_controls'])==6
 assert mini['build']['compiled_sources_sha256']==current and mini['build']['binary_sha256']==sha(P/'build/gnu-host/own-rt-iq3')
 assert all(r['full_state_equal'] for r in mini['rows']) and all(r['rejected'] for r in mini['negative_controls'])
 cases=json.loads((P/'evidence/speed7/mini-cases.json').read_text());assert cases['passed'] and cases['completed'] and cases['cases']==51
 by_name={r['name']:r for r in cases['rows']}
 for r in cases['rows']:archive_bound(r['scratch_archive'])
 for r in mini['owners']:
  archive_bound(r['archive'])
  assert r['operator_scratch_bytes']==[(8 if r['draft_rank']==1 and r['target_split']==23 else 256)*1024**2]*2
 for dr,split in ((1,23),(0,24),(1,24)):
  key=f'r{dr}s{split}';reference=by_name[key+'-control']['signature']
  for controller in ('native','python'):
   for kind in ('hit','miss','mtp','mtp-wrong'):target_equal(by_name[f'{key}-{controller}-{kind}']['signature'],reference)
   assert by_name[f'{key}-{controller}-mtp']['signature']['draft_state']==by_name[f'{key}-{controller}-mtp-wrong']['signature']['draft_state']
   boundary=by_name[f'{key}-{controller}-boundary-reference']['signature']
   partial=[r for n,r in by_name.items() if n.startswith(f'{key}-{controller}-partial-redo-')];assert len(partial)==3
   for r in partial:target_equal(r['signature'],boundary)
   owners=[r for r in mini['owners'] if r['draft_rank']==dr and r['target_split']==split and r['controller']==controller]
   base=next(r for r in owners if r['cancel_launch']==-1 and not r['omit_required_extent'] and not r['abandoned_redo'])
   for r in owners:
    if r['omit_required_extent']:assert r['state']!=base['state']
    else:assert r['state']==base['state'] and r['tokens']==base['tokens']
    if r['abandoned_redo']:assert r['snapshot']['redo_fallbacks']==1
 from speed7_copy_gate import verify as copy_verify
 copy_proof=copy_verify()
 from memory_plan import plan as memory_plan
 from memory_gate import configuration,arena_bytes,ARENA_LIMIT_BYTES
 memory=json.loads((P/'memory-plan.json').read_text());assert memory==memory_plan()==before()['memory_plan']
 for c,dr,s in ((c,dr,s) for c in (4096,32768) for dr,s in ((0,0),(1,0),(0,23))):configuration(memory,c,dr,s)
 configuration(memory,4096,0,24)
 new=configuration(memory,4096,1,23)
 assert [ARENA_LIMIT_BYTES-arena_bytes(r) for r in new['ranks']]==[6172740440,89364320]
 for dr,s in ((0,24),(1,23)):
  try:configuration(memory,32768,dr,s)
  except ValueError:pass
  else:raise AssertionError('infeasible 32K placement admitted')
 assert admit['checks']==23 and admit['errors']==admit['failures']==0 and admit['memory_plan_sha256']==sha(P/'memory-plan.json')
 return dict(rule=RULE,directive_date='2026-10-15',production_changed_files=list(COMPILED),runtime_sources_sha256=PINS,
  plan_dispatch_rows=144,sparse_production_rows=144,mini_cases=93,mini_checks=78,required_extent_negative_controls=6,admission_checks=23,
  gate_receipts_sha256={n:sha(P/n) for n in gates},real_model_cpu_rerun=False,compiler_matrix_rerun=False,
  full_state_contract_unchanged=True,copy_production_rows=copy_proof['production_rows'],copy_phases=copy_proof['copy_phases'],copy_negative_controls=copy_proof['negative_controls'],additional_device_allocation_bytes=0,device_suite_required=['W2m','WS','WSs','WS128x'],
  reuse_justification='Only the maximum-to-minimum snapshot batch extent ratio changes, to eight. Byte sets, allocation sizes, admission and all guards are unchanged. Fresh production-geometry sparse checks and mini full-state proof bind the rebuilt artifacts; device oracle remains real-model exactness authority.')
