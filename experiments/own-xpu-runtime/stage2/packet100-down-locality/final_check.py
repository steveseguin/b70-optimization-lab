"""Re-read CPU evidence and seals; report the device boundary honestly."""
import json
from build_engine import P,ROOT,B,sha,save,limits,provenance
from chain_seal import check_map

def main():
 limits();provenance()
 for name in ('cpu-byte-identity.json','full-shape.json','python-tests.json','microbench-build.json'):
  row=json.loads((P/'evidence'/name).read_text());assert row['passed'] and not row['device_executed'];check_map(ROOT,row['sources'])
  if 'artifacts' in row:check_map(P,row['artifacts'])
 for name in ('production','down-interleave','down-tile16'):
  p=P/'selections'/name;row=json.loads((p/'screen-seal.json').read_text());check_map(ROOT,row['sources'])
  for key in ('artifacts','gates','fixture_files'):check_map(p,row[key])
  assert row['qualification']=='screen only; no full-chain qualification'
 from screen_jobs import verify
 verify()
 plans=json.loads((P/'evidence/queue-plans.json').read_text());assert plans['passed'] and not plans['live_queue_modified'];assert len(plans['plans'])==5
 for r in plans['plans']:assert sha(ROOT/r['proposal'])==r['sha256']
 shape=json.loads((P/'evidence/full-shape.json').read_text());routes=json.loads((P/'evidence/route-inputs.json').read_text())
 assert not (B/'full-shape/scratch').exists()
 assert not any((B/'cpu').glob('*/*/*/expected.bin'))
 size=sum(p.stat().st_size for p in B.rglob('*') if p.is_file());assert size<500_000_000,size
 report=dict(passed=True,device_executed=False,cpu_preparation=True,build_logical_bytes=size,sealed_views=3,startup_checks=len(shape['runs']),negative_allocations=len(shape['negative_allocations']),unsupported_modes_rejected=shape['unsupported_modes_rejected'],minimum_arena_headroom_bytes=min(r['arena_headroom_bytes'] for r in shape['runs']),real_routes_ready=routes['ready'],real_routes_missing=routes['missing_rows'],micro_qualified=False,screen_qualified=False,record_ready=False,record_lane='A',sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('final_check.py','screen-jobs-seal.json','evidence/queue-plans.json','evidence/route-inputs.json')})
 save(P/'evidence/final-verification.json',report);print(json.dumps(report,indent=2))
if __name__=='__main__':main()
