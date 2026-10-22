#!/usr/bin/env python3
"""Verify sealed fix-4 qualification and unchanged incident/device evidence."""
import gzip,json
from pathlib import Path
from storage import admit,digest,verify_archive
import seal45
from copy_adoption_gate import verify
P=Path(__file__).resolve().parent;E=P/'evidence/copy-extent-fix'
def main():
 admit(1_000_000);gate=verify()
 before=json.loads((E/'before-build-receipt.json').read_text());after=seal45.read('build-receipt.json')
 assert after['passed'] and len(after['gate_receipts'])==len(seal45.GATES) and len(after['artifacts_sha256'])==41
 for n,h in after['sources'].items():assert digest(P.parents[3]/n)==h,n
 for n,h in after['gate_receipts'].items():assert digest(P/n)==h,n
 for n,h in after['artifacts_sha256'].items():assert digest(P/'build'/n)==h,n
 protected=json.loads((E/'protected-inputs.json').read_text())
 for n,h in protected.items():assert digest(P/n)==h,n
 for n in ('owner.cpp','owner_api.hpp','dispatch_registry.hpp','p39_submit.cpp','p39_fused.hpp','p33_submit.cpp','p33_fused.hpp'):
  key=str((P/n).relative_to(P.parents[3]))
  if key in before['sources']:assert digest(P/n)==before['sources'][key],n
 assert before['nongemv_fixture_host_sha256_by_context']==after['nongemv_fixture_host_sha256_by_context']
 assert before['p33_linked_fixture_host_sha256']==after['p33_linked_fixture_host_sha256']
 chain=seal45.read('wrapper-merge-tests.json')['coordinator_chains']
 assert chain['passed'] and chain['copy_adoption_gate_sha256']==digest(P/'copy-adoption-gates.json')
 verify_archive(P/chain['archive']['path'])
 with gzip.open(P/chain['archive']['path'],'rt') as stream:
  members={r['path']:r['sha256'] for line in stream if (r:=json.loads(line)).get('kind')=='file'}
 assert [(r['context'],r['draft_rank']) for r in chain['rows']]==[(4096,0),(4096,1),(32768,0)]
 for run in chain['rows']:
  assert len(run['windows'])==9 and all(w['passed'] for w in run['windows'])
  for w in run['windows']:
   member=str((Path(run['command'][-1])/w['window']/'window.json').relative_to(P));assert members[member]==w['sha256']
 binding=seal45.read('window-seal-binding.json');assert binding['passed'] and binding['build_receipt_sha256']==digest(P/'build-receipt.json')
 changed={n:dict(before=before['artifacts_sha256'].get(n),after=h) for n,h in after['artifacts_sha256'].items() if before['artifacts_sha256'].get(n)!=h}
 result=dict(passed=True,device_executed=False,abi_changed=False,copy_guard_changed=False,
  gate_receipts=len(seal45.GATES),build_artifacts=41,selection_choices=len(gate['selection_rows']),selection_checks=gate['selection_checks'],
  full_extent_cases=gate['extent_result'],gate_counts=after['gate_counts'],coordinator_chain_rows=chain['rows'],
  coordinator_archive=chain['archive'],protected_files_verified=len(protected),changed_artifacts=changed,
  build_receipt_sha256=digest(P/'build-receipt.json'),cpu_tests_sha256=digest(P/'cpu-tests.json'),
  window_seal_binding_sha256=digest(P/'window-seal-binding.json'),copy_adoption_sha256=digest(P/'copy-adoption-gates.json'),
  device_artifact_sha256={n:h for n,h in after['artifacts_sha256'].items() if n.startswith('device/')})
 (E/'qualification-summary.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:v for k,v in result.items() if k not in ('coordinator_chain_rows','changed_artifacts')},indent=2))
if __name__=='__main__':main()
