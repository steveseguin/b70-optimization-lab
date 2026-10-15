"""Exact split23 amendment; fresh proof required, no performance qualification."""
import hashlib,json,gzip
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
RULE='packet45.speed5.explicit-split23.2026-10-15'
BEFORE='26038284a7adc5400a0090e6a2ae9b81d5739d24d6a455d198c996d55d512538'
PINS={'main.cpp': '0cbc1c9d620bbb0fd815795dd53fc3837884dff21caa9c9391543b98d8e61278', 'rank.hpp': '0a409244d197d7b703912b56b26a044b5becaa5653761958d454537d0637fe8e', 'pipeline.py': '0fd36f19c0b6cf1b2199080bbf86ab039e215ca011c5906acad7f01067b8ebb0', 'window.py': 'c8f0fef4f55b6ca1a3518e24d7d0d07d1f0e5bd5dfe9d12c94a716d4d0f9e242', 'memory_plan.py': '7103a46cb0025d9c05b10b24dfff1dd0d5934e277ce16b626375a8e6efba8dd8', 'memory_gate.py': '41c93f39eb7046874797b1ae47c4ceadb7680c793c9b5a08d77d3dbcc93704ce', 'memory-plan.json': '2a1458c0ce692ba4edf3b55068d454f8aa2356ee543020d033145599955cb285', 'coordinator_windows.sh': '08d0305716e98063a07737bfeef86e13787f3a555a54f22a3ce7d2fec70e8217', 'test_speed3.py': 'c6d3d26105f8dfa231d85a2905064389ce5d21612fc6025fbd6dc72b03d2a395'}
MIRRORS={'main.cpp': {'old': ['11afd06931951be3f9c5d2ffe3c077960ce1bd430962391c70c8e729fc2daa1b', '4ffe0ee8ec6442bed197458dd1ce0da804645227396da9323b44b12dc7ce7859', '60cab241e95a4d2798b3149032198210fcf8040d5cf1f2e541341f2a8e1c181a'], 'new': 'bb1a84b338eefac6bc57ab81da2f4bedcb1db714b37301f2e9101eec4ed92688'}, 'rank.hpp': {'old': ['4eef587666b52f9f8d2e8dfcbfef3228e0d4633efc53b76b42b82dab5c127c10', 'c24f08a558840b32831785d47e2514c7df03e2ce75775e5a848aa13e38d87136', 'c85dc64000c23352d991c8eb2965fa7d2e7fc99ef305f6a4f58f7676baeccabf'], 'new': '6d1512df4a1483e436c7ae12017008471ff3c5f300004d6dc23e2f77a0f08c9d'}}
COMPILED=('main.cpp','rank.hpp')
def sha(p):
 p=Path(p)
 if not p.exists():
  # Coordinator moved these exact historical result roots on the same filesystem.
  # Every consumer still compares their actual bytes to the retained SHA256.
  for name in ('results-f912fdaf6','results-65c5eb22b','results-9b91d3270'):
   root=P/'build'/name
   if p.is_relative_to(root):
    p=Path('/home/steve/own-xpu-runtime-results/packet45')/name/p.relative_to(root);break
 return hashlib.sha256(p.read_bytes()).hexdigest()
def before():
 p=P/'evidence/speed5/before-build-receipt.json';assert sha(p)==BEFORE,'SPEED5 baseline changed';return json.loads(p.read_text())
def historical_compiled_sources(current):
 old=before()['sources'];keys={str((P/n).relative_to(ROOT)) for n in COMPILED}
 assert all(n in old for n in current),'compiled source closure changed'
 assert {n for n in current if current[n]!=old[n]}==keys,'outside fixture/SPEED5 repair'
 assert all(current[str((P/n).relative_to(ROOT))]==PINS[n] for n in COMPILED),'outside fixture/SPEED5 repair'
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
 assert all(sha(P/n)==h for n,h in PINS.items()),'SPEED5 runtime/admission source changed'
 gates={n:json.loads((P/n).read_text()) for n in ('speed5-plan-gates.json','speed5-snapshot-gates.json','speed5-admission-gates.json')}
 for name,row in gates.items():
  assert row['passed'] and row['device_executed'] is False,name
  for field in ('source_sha256','sources_sha256'):
   for n,h in row.get(field,{}).items():assert sha(P/n)==h,'stale SPEED5 source '+n
 plan=gates['speed5-plan-gates.json'];mini=gates['speed5-snapshot-gates.json'];admit=gates['speed5-admission-gates.json']
 expected={(c,dr,s,k,r,d) for c in (4096,32768) for dr,s in ((0,0),(1,0),(0,24),(0,23),(1,23)) for k,r in [('target',0),('target',1),('KD',1),('draft',dr)] for d in ('dr0','dr1','forced')}
 assert plan['plan_dispatch_rows']==len(plan['rows'])==120
 assert {(r['context'],r['draft_rank'],r['target_split'],r['plan'],r['rank'],r['dispatch']) for r in plan['rows']}==expected
 assert plan['removed_target_commands']==192 and all(r['result']['passed'] for r in plan['rows'])
 assert plan['weight_bytes_read']==0 and plan['metadata_sha256']==sha(P/'build/input/plan.tsv')
 details=plan['writer_sites'];assert sha(P/details['path'])==details['sha256']
 writers=json.loads(gzip.decompress((P/details['path']).read_bytes()));assert len(writers)==details['rows']==120
 for r,w in zip(plan['rows'],writers):
  assert all(r[k]==w[k] for k in ('context','draft_rank','target_split','plan','rank','dispatch'))
  assert r['write_set']['sites_count']==len(w['sites']) and r['write_set']['sites_sha256']==hashlib.sha256(json.dumps(w['sites'],sort_keys=True).encode()).hexdigest()
  assert all(v['full_byte_coverage'] and v['inputs_use_distinct_active_bank'] and v['bytes']>0 for v in r['write_set']['redo_banks'])
 assert sha(P/'build/speed5-plan/after')==plan['binary_sha256'] and sha(P/'build/speed5-plan/after.cpp')==plan['generated_sha256']
 for r in plan['rows']:
  assert sha(P/('evidence/fix6/dispatch-'+r['dispatch']+'.json'))==r['dispatch_sha256']
  if r['plan']!='draft':
   boundary=r['target_split'] or (24 if r['plan']=='KD' or r['draft_rank'] else 22)
   assert r['group_census']['ffn']==(boundary if r['rank']==0 else 48-boundary) and not r['group_census']['shared']
 from seal45 import archive_bound
 from cpu_merged_gate import target_equal
 assert mini['cases']==62 and mini['gate_count']==52 and len(mini['negative_controls'])==4
 assert mini['build']['compiled_sources_sha256']==current and mini['build']['binary_sha256']==sha(P/'build/gnu-host/own-rt-iq3')
 assert all(r['full_state_equal'] for r in mini['rows']) and all(r['rejected'] for r in mini['negative_controls'])
 cases=json.loads((P/'evidence/speed5/mini-cases.json').read_text());assert cases['passed'] and cases['completed'] and cases['cases']==34
 by_name={r['name']:r for r in cases['rows']}
 for r in cases['rows']:archive_bound(r['scratch_archive'])
 for r in mini['owners']:archive_bound(r['archive'])
 for dr in (0,1):
  key=f'r{dr}s23';reference=by_name[key+'-control']['signature']
  for controller in ('native','python'):
   for kind in ('hit','miss','mtp','mtp-wrong'):target_equal(by_name[f'{key}-{controller}-{kind}']['signature'],reference)
   assert by_name[f'{key}-{controller}-mtp']['signature']['draft_state']==by_name[f'{key}-{controller}-mtp-wrong']['signature']['draft_state']
   boundary=by_name[f'{key}-{controller}-boundary-reference']['signature']
   partial=[r for n,r in by_name.items() if n.startswith(f'{key}-{controller}-partial-redo-')];assert len(partial)==3
   for r in partial:target_equal(r['signature'],boundary)
   owners=[r for r in mini['owners'] if r['draft_rank']==dr and r['target_split']==23 and r['controller']==controller]
   base=next(r for r in owners if r['cancel_launch']==-1 and not r['omit_required_extent'] and not r['abandoned_redo'])
   for r in owners:
    if r['omit_required_extent']:assert r['state']!=base['state']
    else:assert r['state']==base['state'] and r['tokens']==base['tokens']
    if r['abandoned_redo']:assert r['snapshot']['redo_fallbacks']==1
 from memory_plan import plan as memory_plan
 from memory_gate import configuration
 memory=json.loads((P/'memory-plan.json').read_text());assert memory==memory_plan()
 assert all(memory['placements'][k]==v for k,v in before()['memory_plan']['placements'].items())
 for c,dr in ((4096,0),(32768,0),(4096,1)):configuration(memory,c,dr,23)
 try:configuration(memory,32768,1,23)
 except ValueError:pass
 else:raise AssertionError('32K rank1 split23 admitted')
 assert admit['checks']==9 and admit['errors']==admit['failures']==0 and admit['memory_plan_sha256']==sha(P/'memory-plan.json')
 return dict(rule=RULE,directive_date='2026-10-15',production_changed_files=list(COMPILED),runtime_sources_sha256=PINS,
  plan_dispatch_rows=120,mini_cases=62,mini_checks=52,required_extent_negative_controls=4,admission_checks=9,
  gate_receipts_sha256={n:sha(P/n) for n in gates},real_model_cpu_rerun=False,compiler_matrix_rerun=False,
  full_state_contract_unchanged=True,device_suite_required=['W2m','WS','WSs','WS128x'],
  reuse_justification='Exact split23 selection and memory arithmetic only; prior controllers, kernels and SPEED4 restore remain pinned. Fresh plan, mini full-state and admission gates bind rebuilt artifacts. No speed claim before coordinator device suites.')
