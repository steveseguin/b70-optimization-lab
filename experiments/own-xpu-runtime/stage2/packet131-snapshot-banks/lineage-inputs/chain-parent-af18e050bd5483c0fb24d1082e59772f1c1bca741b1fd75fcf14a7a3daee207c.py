#!/usr/bin/env python3
"""Verify repair evidence, current seal, unchanged references and protected bytes."""
import gzip,json
from pathlib import Path
from storage import admit,digest,verify_archive
import seal45
P=Path(__file__).resolve().parent;E=P/'evidence/route-gather-fix'
def main():
 admit(1_000_000)
 before=json.loads((E/'before-build-receipt.json').read_text());after=seal45.read('build-receipt.json')
 assert after['passed'] and len(after['gate_receipts'])==25 and len(after['artifacts_sha256'])==41
 for n,h in after['sources'].items():assert digest(P.parents[3]/n)==h,n
 for n,h in after['gate_receipts'].items():assert digest(P/n)==h,n
 for n,h in after['artifacts_sha256'].items():assert digest(P/'build'/n)==h,n
 changed={n:dict(before=before['artifacts_sha256'].get(n),after=h) for n,h in after['artifacts_sha256'].items() if before['artifacts_sha256'].get(n)!=h}
 protected=json.loads((E/'protected-inputs.json').read_text())
 for n,h in protected.items():assert digest(P/n)==h,n
 # No packet18 oracle or two-output route result was changed to match the fix.
 for n,h in before['sources'].items():
  if n.endswith(('/core_v2.hpp','/route42.hpp','/route42_submit.cpp','/runtime_kernels.hpp','/dispatch_registry.hpp','/adapter_fixture.cpp')):assert digest(P.parents[3]/n)==h,n
 assert before['nongemv_fixture_host_sha256_by_context']==after['nongemv_fixture_host_sha256_by_context'],'existing K1 fixture bytes changed'
 assert before['p33_linked_fixture_host_sha256']==after['p33_linked_fixture_host_sha256']
 pre=json.loads((E/'before.json').read_text());post=seal45.read('fusion-matrix-gates.json');seal45.fusion_bindings(post)
 adapter=str((P/'adapter.cpp').relative_to(P.parents[3]))
 assert pre['compiled_sources_sha256'][adapter]==before['sources'][adapter]
 assert set(pre['compiled_sources_sha256'])==set(post['compiled_sources_sha256'])
 assert [n for n,h in pre['compiled_sources_sha256'].items() if post['compiled_sources_sha256'][n]!=h]==[adapter],'before/after changed more than the production adapter'
 assert not pre['passed'] and len(pre['rows'])==6
 for arm in pre['rows']:
  assert arm['exit_code']==1 and arm['result']['failures']==6
  assert [(r['case'],r['version'],r['mismatches']) for r in arm['result']['adapter_rows'] if r['mismatches']]==[(8,0,2),(9,0,2),(49,0,2)]
  assert arm['result']['p39_checks']==56 and arm['result']['small_checks']==220
  assert digest(P/arm['log'])==arm['log_sha256']
 wrapper=seal45.read('wrapper-merge-tests.json');chain=wrapper['coordinator_chains']
 assert chain['passed'] and len(chain['rows'])==3
 verify_archive(P/chain['archive']['path'])
 with gzip.open(P/chain['archive']['path'],'rt') as stream:members={r['path']:r['sha256'] for line in stream if (r:=json.loads(line)).get('kind')=='file'}
 for run in chain['rows']:
  assert len(run['windows'])==9 and all(w['passed'] for w in run['windows'])
  for w in run['windows']:
   member=str((Path(run['command'][-1])/w['window']/'window.json').relative_to(P));assert members[member]==w['sha256']
 binding=seal45.read('window-seal-binding.json');assert binding['passed'] and binding['build_receipt_sha256']==digest(P/'build-receipt.json')
 summary=dict(passed=True,device_executed=False,gate_receipts=25,build_artifacts=41,
  build_receipt_sha256=digest(P/'build-receipt.json'),cpu_tests_sha256=digest(P/'cpu-tests.json'),window_seal_binding_sha256=digest(P/'window-seal-binding.json'),
  fusion_before_checks=pre['checks'],fusion_before_failures=sum(r['result']['failures'] for r in pre['rows']),fusion_after_checks=post['checks'],
  coordinator_chain_rows=chain['rows'],coordinator_archive=chain['archive'],gate_counts=after['gate_counts'],
  device_artifact_sha256={n:h for n,h in after['artifacts_sha256'].items() if n.startswith('device/')},
  changed_artifacts=changed,protected_files_verified=len(protected),abi_changed=False,packet18_reference_changed=False,existing_fixture_hashes_unchanged=True)
 assert all(n in changed for n in summary['device_artifact_sha256'])
 (E/'qualification-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 print(json.dumps({k:v for k,v in summary.items() if k not in ('coordinator_chain_rows','changed_artifacts')},indent=2))
if __name__=='__main__':main()
