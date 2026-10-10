#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""CPU read-only source replay for the chosen quiet grace; no live operations."""
import hashlib
import json
from pathlib import Path
from statistics import median

here = Path(__file__).resolve().parent
source = here / 'continuation128-overlap-evidence.json'
evidence = json.loads(source.read_bytes())
rows = []
for name, pin in evidence['sources'].items():
    if '/receipt-stream126-s' not in name:
        continue
    raw = Path(name).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == pin['sha256'], name
    receipt = json.loads(raw)
    marks = (receipt.get('turnaround') or {}).get('marks_ns', {})
    t = receipt['timing_ns']
    if not all(marks.get(k) for k in ('commit_written', 'first_served', 'executor_exit')) or not t.get('queued'):
        continue
    if marks['first_served'] - marks['commit_written'] >= 150_000_000:
        continue
    rows.append({'receipt': name, 'receipt_sha256': pin['sha256'],
                 'successor_queue_minus_executor_exit_s': (t['queued'] - marks['executor_exit'])/1e9})
values = sorted(r['successor_queue_minus_executor_exit_s'] for r in rows)
result = {'schema': 'ltx.stream128.quiet-grace-evidence.v1',
          'scope': 'all captured126 receipt pairs with complete queue/exit marks and handoff below150ms; includes boundary receipts',
          'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
          'count': len(values), 'median_s': median(values), 'p90_nearest_rank_s': values[int(len(values)*.9)],
          'max_s': max(values), 'below100ms': sum(v < .1 for v in values),
          'below250ms': sum(v < .25 for v in values), 'rows': rows}
(here / 'continuation128-handoff-grace.json').write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n')
print({k: v for k, v in result.items() if k != 'rows'})
