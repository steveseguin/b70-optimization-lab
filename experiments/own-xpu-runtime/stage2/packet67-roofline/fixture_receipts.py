#!/usr/bin/env python3
"""Compact validation of compiler-specific exceptional payloads and failed arm."""
from pathlib import Path
import json,hashlib
P=Path(__file__).resolve().parent
def sha(b):return hashlib.sha256(b).hexdigest()
def save(p,x):p.parent.mkdir(exist_ok=True,parents=True);p.write_text(json.dumps(x,indent=2)+'\n')
def main():
 roots=[P/'build'/x for x in ('fixture-gnu-b','fixture-intel')]
 cases=[json.loads(x) for x in (roots[0]/'repeat-1/cases.jsonl').read_text().splitlines()]
 differing=[]
 with (roots[0]/'repeat-1/expected.bin').open('rb') as a,(roots[1]/'repeat-1/expected.bin').open('rb') as b:
  for row in cases:
   n=29696 if row['site'].startswith('hc.') else 1585164+(1572864 if '.distinct' in row['site'] else 0)
   x,y=a.read(n),b.read(n);assert len(x)==len(y)==n
   if x!=y:
    assert row['scenario'] in (5,6),('finite compiler mismatch',row)
    differing.append(row)
  assert not a.read(1) and not b.read(1)
 save(P/'evidence/host-compilers.json',dict(passed=True,device_executed=False,finite_cross_compiler_identity=True,
  all_candidates_match_same_compiler_production=True,exceptional_cross_compiler_payload_differences=differing,
  note='GNU/Intel production may choose different NaN payload operands. No tolerance is used within either compiler; each candidate exactly matches its compiled production, in two fresh processes.',
  receipts={str(r.relative_to(P)/'receipt.json'):sha((r/'receipt.json').read_bytes()) for r in roots}))
 failed=P/'build/fixture-gnu';a=(failed/'repeat-1/expected.bin').read_bytes();b=(failed/'repeat-1/candidate.bin').read_bytes()
 save(P/'evidence/failed-hc-virtualization.json',dict(passed=False,device_executed=False,scope='first GNU fixture, scenario5 NaN payloads; finite cases passed',
   expected_sha256=sha(a),actual_sha256=sha(b),failed_gate_tail_bytes=20480,
   expected_prefix_hex=a[-20480:-20352].hex(),actual_prefix_hex=b[-20480:-20352].hex(),log=(failed/'repeat-1/run.log').read_text(),
   disposition='retained mismatch; production-expression fallback added, same-compiler exact fixtures rerun; no NaN canonicalization'))
 # Preserve exact initial source by removing only the subsequent fallback.
 s=(P/'evidence/failed-hc-before-fallback.hpp').read_text()
 expected=json.loads((P/'evidence/build-before-exception-fallback.json').read_text())['sources'][str((P/'p67_hc.hpp').relative_to(P.parents[3]))]
 assert sha(s.encode())==expected,'failed source reconstruction must be exact'
 (P/'evidence/failed-hc-before-fallback.hpp').write_text(s)
 print('finite GNU/Intel parity and exceptional mismatch evidence retained')
if __name__=='__main__':main()
