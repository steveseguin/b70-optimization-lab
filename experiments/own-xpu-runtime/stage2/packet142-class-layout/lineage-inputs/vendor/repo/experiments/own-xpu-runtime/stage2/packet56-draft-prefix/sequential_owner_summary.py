#!/usr/bin/env python3
"""Verify final CPU seal, retained chain proof, unchanged binaries and protected files."""
import json,gzip
from pathlib import Path
from storage import digest,verify_archive,admit
P=Path(__file__).resolve().parent;E=P/'evidence/sequential-owner-fix'
def main():
 admit(1_000_000)
 before=json.loads((E/'before-build-receipt.json').read_text());after=json.loads((P/'build-receipt.json').read_text())
 assert after['passed'] and len(after['gate_receipts'])==24 and len(after['artifacts_sha256'])==41
 for n,h in after['sources'].items():assert digest(P.parents[3]/n)==h,n
 for n,h in after['gate_receipts'].items():assert digest(P/n)==h,n
 for n,h in after['artifacts_sha256'].items():assert digest(P/'build'/n)==h,n
 changed={n:dict(before=before['artifacts_sha256'].get(n),after=h) for n,h in after['artifacts_sha256'].items() if before['artifacts_sha256'].get(n)!=h}
 assert not changed,'host-only repair unexpectedly changed a build artifact'
 protected=json.loads((E/'protected-inputs.json').read_text())
 for n,h in protected.items():assert digest(P/n)==h,n
 wrapper=json.loads((P/'wrapper-merge-tests.json').read_text());chain=wrapper['coordinator_chains']
 assert chain['passed'] and len(chain['rows'])==3
 verify_archive(P/chain['archive']['path'])
 with gzip.open(P/chain['archive']['path'],'rt') as stream:
  members={r['path']:r['sha256'] for line in stream if (r:=json.loads(line)).get('kind')=='file'}
 for run in chain['rows']:
  for window in run['windows']:
   member=str((Path(run['command'][-1])/window['window']/'window.json').relative_to(P))
   assert members[member]==window['sha256'],'chain window differs from retained bytes: '+member
 binding=json.loads((P/'window-seal-binding.json').read_text())
 assert binding['passed'] and binding['build_receipt_sha256']==digest(P/'build-receipt.json')
 summary=dict(passed=True,device_executed=False,gate_receipts=24,build_artifacts=41,
  build_receipt_sha256=digest(P/'build-receipt.json'),cpu_tests_sha256=digest(P/'cpu-tests.json'),
  window_seal_binding_sha256=digest(P/'window-seal-binding.json'),wrapper_tests=wrapper['tests'],
  coordinator_chain_rows=chain['rows'],coordinator_archive=chain['archive'],
  runtime_sha256={m:after['artifacts_sha256'][m+'/own-rt-iq3'] for m in ('gnu-host','icpx-host','asan','device')},
  device_artifact_sha256={n:h for n,h in after['artifacts_sha256'].items() if n.startswith('device/')},
  changed_artifacts=changed,protected_files_verified=len(protected),gate_counts=after['gate_counts'])
 (E/'qualification-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 print(json.dumps({k:v for k,v in summary.items() if k not in ('coordinator_chain_rows','device_artifact_sha256','gate_counts')},indent=2))
if __name__=='__main__':main()
