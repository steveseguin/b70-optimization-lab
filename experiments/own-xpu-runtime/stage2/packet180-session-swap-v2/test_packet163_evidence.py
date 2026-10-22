"""Re-anchor packet163 real full512 replay; raw per-request receipts were retention-cleaned.

packet165's replay receipt was derived from packet163's real device evidence
while its per-request receipts still existed; only the bracket summaries
survive in the frozen packet163 tree. This gate re-verifies packet165's replay
medians and cold-prefill fields against those surviving real summaries and the
one-card analyzer module, fail-closed. No new measurement.
"""
import json,math,sys
from pathlib import Path
P=Path(__file__).resolve().parent;p=P/'one-card';sys.path.insert(0,str(p))
import measurement as M
read=lambda f:json.loads(f.read_text())
source=P.parent/'packet163-full-gate/two-card/evidence'
parent_receipt=read(P.parent/'packet165-warm-prefill/evidence/packet163-replay.json')
assert parent_receipt['passed'] and parent_receipt['device_executed'] is False
assert parent_receipt['source_is_real_device_evidence'] and parent_receipt['new_measurement'] is False
key='class_balanced_tok_s_1_100_intervals_after_ttft';results=[]
for row in parent_receipt['results']:
    attempt=row['attempt'];old=source/f'device-full512-B-{attempt}'
    assert row['source']==str(old.relative_to(P.parents[3]))
    summary=read(old/'bracket-summary.json')
    assert math.isclose(row['primary_decode_tok_s'],summary[key]['median'],rel_tol=1e-12)
    prefill=row['prefill']
    assert prefill['warmup'] is None and prefill['cached_tokens']==0
    assert 'cold' in prefill['measurement_temperature']
    assert prefill['prefill_phase_device_ms'] is None
    results.append(dict(attempt=attempt,source=row['source'],
        primary_decode_tok_s=row['primary_decode_tok_s'],prefill=prefill,real_evidence=True))
(P/'evidence/packet163-replay.json').write_text(json.dumps(dict(passed=True,device_executed=False,
    source_is_real_device_evidence=True,new_measurement=False,results=results,
    raw_per_request_receipts='retention-cleaned from frozen packet163; medians re-verified against surviving real bracket-summary.json and packet165 replay receipt',
    parent_replay_sha256=__import__('hashlib').sha256((P.parent/'packet165-warm-prefill/evidence/packet163-replay.json').read_bytes()).hexdigest()),indent=2)+'\n')
print('packet163 real full512 replay anchor PASS',[(r['attempt'],r['primary_decode_tok_s']) for r in results])
