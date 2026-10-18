#!/usr/bin/env python3
"""Check deterministic discarded proposals across the two fresh CPU fixtures."""
import json
from pathlib import Path
P=Path(__file__).resolve().parent
def main():
 runs=[]
 for arm in ('on1','on2'):
  rows=[]
  for request in ('','request2'):
   path=P/'fixture'/arm/request/'depth2-probe.jsonl'
   records=[json.loads(line) for line in path.read_text().splitlines()]
   assert len(records)==34
   for r in records:
    assert r['discarded'] is True and r['rank']==1 and r['d2']>=0 and r['snapshot_bytes']<=32*1024**2
    assert r['d2_position']==r['d1_position']+1
   rows.extend([(request,r['d1_position'],r['d1'],r['d2'],r['snapshot_bytes']) for r in records])
  runs.append(rows)
 assert runs[0]==runs[1]
 result=dict(passed=True,device_executed=False,fresh_runs=2,matching_discarded_proposals=68,request_reset_checked=True,scope='tiny synthetic draft, not model acceptance')
 (P/'evidence/proposal-repeat.json').write_text(json.dumps(result,indent=2)+'\n');print(result)
if __name__=='__main__':main()
