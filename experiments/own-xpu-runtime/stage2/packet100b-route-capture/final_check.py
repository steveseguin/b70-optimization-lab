"""Read-only final CPU verification; no device discovery or live queue writes."""
import json,subprocess,sys
from build_engine import P,ROOT,B,sha,save,limits
def main():
 limits()
 from capture_identity import verify
 seal=verify()
 for name in ('capture-cpu.json','full-shape.json','python-tests.json','queue-plans.json'):
  row=json.loads((P/'evidence'/name).read_text());assert row['passed'] and not row['device_executed']
 plans=json.loads((P/'evidence/queue-plans.json').read_text())
 assert len(plans['plans'])==6 and not plans['live_queue_modified']
 for row in plans['plans']:assert sha(ROOT/row['proposal'])==row['sha256']
 size=sum(f.stat().st_size for f in B.rglob('*') if f.is_file());assert size<=300_000_000
 assert not (P/'evidence/capture-B').exists() and not (P/'evidence/micro-B').exists()
 from capture_inputs import require_ready
 from qualification import require_qualified
 refused=[]
 for gate in (require_ready,require_qualified):
  try:gate()
  except ValueError as e:assert 'pending' in str(e);refused.append(str(e))
  else:raise AssertionError('device gate passed without evidence')
 save(P/'evidence/final-verification.json',dict(passed=True,device_executed=False,
  packet_seal_sha256=sha(P/'packet-seal.json'),build_bytes=size,build_limit_bytes=300_000_000,
  capture_output_limit_bytes=50_000_000,queue_plans=6,python_checks=23,
  pending_gates_refused=refused,parents_resealed=False,live_queue_modified=False,
  compile_turn='packet94-hc-norm-fusion/compile_turn.py'))
 print('final CPU verification PASS; capture and speed gates correctly pending')
if __name__=='__main__':main()
