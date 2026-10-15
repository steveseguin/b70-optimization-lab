"""Exact SPEED1 extension of seal-6; no general source-reuse waiver."""
import gzip,hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
RULE='packet45.speed1.full-state-batched-copy-and-small-ffn.2026-10-15'
BEFORE='85f1100617612698dc73d50162c309605a6ce976faf71ca9f6bb711c458fe585'
PINS={'p39_plan.hpp':'fec70f9aa95dfd71fea8dac927419373ce3172c73e76d4a3510d52b595eb855c',
      'strict_snapshot.hpp':'c0f1d3e795798de4679aa13a6d872306e7bdbb8a916266c2f125995e2cc655ce'}
MIRRORS={'p39_plan.hpp':('13870730098c4b5f515c7e80f82d7a1316d6a12520f4e532f099aa981f74fcda','9f8d2457fb65caad4c47aabf2e02352571a5da2832604047369938d4b4c1b75a'),
 'strict_snapshot.hpp':('42a26f4aa254eab1b52edc2ea115d9082770d2a691d0b8eb0ac1e342d98ee885','60957654a6a418782f7b1cd7930d4e3bc499784f157d25a64d02f5220c078ad7')}
def sha(p):return __import__('speed4_qualification').prior_sha(p)
def before():
 p=P/'evidence/speed1/before-build-receipt.json';assert sha(p)==BEFORE,'SPEED1 baseline changed';return json.loads(p.read_text())
def current_pin(n):
 from speed2_qualification import PINS as current
 return current.get(n,PINS[n])
def source_allowed(path,old):
 path=Path(path);n=path.name;key=str(path.relative_to(ROOT))
 return path.parent==P and n in PINS and old==before()['sources'][key] and sha(path)==current_pin(n)
def mirror_allowed(path,old,new):
 from speed2_qualification import mirror_allowed as later
 if later(path,old,new):return True
 p=Path(path);n=p.name
 return n in MIRRORS and str(p)==str((P/'build/checked'/P.relative_to(ROOT)/n).relative_to(ROOT)) and (old,new)==MIRRORS[n] and sha(P/n)==PINS[n] and sha(ROOT/p)==new

def verify():
 from build import compiled_sources
 from speed3_qualification import historical_compiled_sources
 old=before();now=historical_compiled_sources(compiled_sources())
 expected={str((P/n).relative_to(ROOT)) for n in PINS}
 assert {k for k in now if old['sources'].get(k)!=now[k]}==expected,'outside fixture/SPEED1 repair'
 assert all(now[str((P/n).relative_to(ROOT))]==current_pin(n) for n in PINS),'outside fixture/SPEED1 repair'
 plan=json.loads((P/'speed1-plan-gates.json').read_text());mini=json.loads((P/'speed1-snapshot-gates.json').read_text());inventory=json.loads((P/'speed1-snapshot-inventory.json').read_text())
 for row in (plan,mini,inventory):
  assert row['passed'] and row['device_executed'] is False
  for field in ('sources_sha256','source_sha256'):
   for n,h in row.get(field,{}).items():
    from speed2_qualification import source_allowed as later
    assert sha(P/n)==h or later(P/n,h) or __import__('speed3_qualification').source_allowed(P/n,h),'SPEED1 source changed '+n
 assert plan['plan_dispatch_rows']==len(plan['rows'])==48 and plan['removed_target_commands']==192
 assert sha(P/'build/speed1-plan/after')==plan['binary_sha256'] and sha(P/'build/speed1-plan/after.cpp')==plan['generated_sha256']
 assert sha(P/'build/input/plan.tsv')==plan['metadata_sha256']
 for r in plan['rows']:
  assert r['result']['passed'] and sha(P/('evidence/fix6/dispatch-'+r['dispatch']+'.json'))==r['dispatch_sha256']
  if r['plan']!='draft':assert r['group_census']['shared']==0 and r['group_census']['ffn']>0
 assert mini['cases']==42 and mini['gate_count']==36 and len(mini['negative_controls'])==4
 from speed2_qualification import before as subsequent
 assert mini['build']['binary_sha256']==subsequent()['artifacts_sha256']['gnu-host/own-rt-iq3']
 assert mini['build']['compiled_sources_sha256']=={k:subsequent()['sources'][k] for k in now}
 assert all(r['full_state_equal'] for r in mini['rows']) and all(r['rejected'] for r in mini['negative_controls'])
 from seal45 import archive_bound
 for r in mini['owners']:archive_bound(r['archive'])
 cases=json.loads((P/'evidence/speed1/mini-cases.json').read_text());assert cases['passed'] and cases['completed'] and cases['cases']==18
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
 from speed1_snapshot_inventory import schedule
 proof=inventory['writer_proof'];assert sha(P/proof['path'])==proof['sha256']
 writer_rows=json.loads(gzip.decompress((P/proof['path']).read_bytes()));assert len(writer_rows)==proof['extents']
 assert inventory['excluded_extents']==[] and all(not r['excluded'] and not r['full_write_coverage_proven'] for r in writer_rows)
 for n,h in inventory['input_sha256'].items():assert sha(P/n)==h
 for r in inventory['rows']:
  assert r['capture_bytes']==r['restore_bytes']==sum(map(sum,r['batches']))
  assert r['capture_submissions']==r['restore_submissions']==len(r['batches'])
  assert max(map(sum,r['batches']))<=134217728 and all(len(b)<=32 for b in r['batches'])
  assert r['batches']==schedule([v for b in r['batches'] for v in b])
  assert r['excluded_bytes']==0
 return dict(rule=RULE,directive_date='2026-10-15',production_changed_files=sorted(PINS),
  production_sources_sha256=PINS,plan_dispatch_rows=48,mini_cases=42,mini_checks=36,
  gate_receipts_sha256={n:sha(P/n) for n in ('speed1-plan-gates.json','speed1-snapshot-gates.json','speed1-snapshot-inventory.json')},
  full_state_contract_unchanged=True,writer_exclusion='No exclusions admitted: write-before-read does not prove terminal byte restoration; partial or unknown coverage rejected.',
  reuse_justification='Owner SPEED REPAIR 1 extends named seal-6 amendment. Historical real-model/compiler/fixture evidence retains its original identity; fresh mini full-state and metadata plan gates cover this pinned repair. Coordinator device windows remain the new artifact real-model exactness authority.')

def audit_inventory_allowed(old,new):
 baseline_row=json.loads((P/'audit6-gates.json').read_text())
 assert sha(P/'audit6-gates.json')==before()['gate_receipts']['audit6-gates.json'],'audit6 retained gate changed'
 assert old==baseline_row['copy_sites'],'audit6 copy inventory changed'
 strip=lambda rows:[{k:v for k,v in r.items() if k!='line'} for r in rows if r['source']!='strict_snapshot.hpp']
 assert strip(old)==strip(new),'audit6 copy inventory changed outside snapshot'
 assert sha(P/'strict_snapshot.hpp')==current_pin('strict_snapshot.hpp')
 copies=[r for r in new if r['source']=='strict_snapshot.hpp']
 assert len(copies)==2 and all(r['expressions']==1 and r['largest_n']==r['limit']==134217728 for r in copies)
 return True
