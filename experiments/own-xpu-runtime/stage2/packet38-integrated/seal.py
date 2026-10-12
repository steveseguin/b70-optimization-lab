"""Seal the integrated packet from current CPU receipts; never runs device code."""
import hashlib,json,gzip
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(4*1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def main():
 from build import sources
 names="""argument-block-tests.json argument-state-gates.json prepared-invalidation.json prepared-host-benchmark.json submission-overlay-gates.json review-prepared-gates.json p33-candidate-gates.json p33-linked-fixture-gates.json k2-admission-tests.json k2-selection-tests.json p38-k2-selection-tests.json p38-kernel-gates.json p38-qsa-capacity-gates.json p30-attention-cpu.json p30-small-cpu.json owner-gates.json fixture-gates.json validation-gates.json entry-codes.json window-tests.json identity-tree-tests.json kernel-sizes.json expert-down-review-gates.json state-machine-tests.json mtp-controller-tests.json review-controller-tests.json review-native-faults.json canary-host-gates.json resident-host-gates.json rollback-inventory.json draft-auth-gates.json pipeline-draft-agreement.json native-controller-cpu.json native-controller-asan.json native-controller-tsan.json native-mailbox-faults.json native-mailbox-faults-asan.json native-mailbox-faults-tsan.json native-mini-cpu.json receipt-metadata-gates.json suite-gate-results.json real-controller-gates.json review-resume-controller.json review-resume-reset.json review-resume-authority.json review-resume-storage-gates.json review-resume-window-storage-gates.json draft-window-cleanup-gates.json reset-retention-gate-results.json resume-input-integrity.json review-draft-capture.json window-cpu-fixtures.json window-cpu-models.json suite-real-cpu.json""".split()
 for c in ('gnu-host','icpx-host','asan'):names.extend([f'mini-{c}.json',f'mtp-gates-{c}.json'])
 for c,prefix in (('gnu-host',''),('icpx-host','icpx-host-')):
  names.append(f'real-campaign-{c}.json')
  names.extend(f'real-{prefix}{m}.json' for m in ('none','ngram','hit','miss','mtp'))
 names.extend(f'real-native-{m}.json' for m in ('none','ngram','hit','miss','mtp'))
 prompts=('incident-retrospective','code-review','customer-email','benchmark-analysis')
 names.extend(f'agreement-{n}.json' for n in prompts)
 gates={n:json.loads((P/n).read_text()) for n in names}
 for n,r in gates.items():assert r.get('passed',r.get('source_review_passed')) is True,('gate incomplete',n)
 entries=('p33-linked-fixtures','own-rt-iq3','nongemv-fixtures','k2-fixtures','jit-smoke','authority-tests','owner-retirement-tests','chain-tests','queue-tests','lifetime-tests','prepared-invalidation-tests')
 binaries={str(f.relative_to(B)):sha(f) for c in ('gnu-host','icpx-host','asan','device') for f in (B/c).iterdir() if f.name in entries}
 # Native controller and reset evidence must name this exact final host binary.
 host_sha=binaries['gnu-host/own-rt-iq3']
 mini=gates['native-mini-cpu.json']
 assert mini['binary_sha256']==host_sha and mini['cases']==1109 and mini['exhaustive_ternary_patterns']==1093
 assert mini['long_random_cases']==12 and mini['long_random_tokens']==64 and mini['host_memory']=='resident' and mini['host_path']=='prepared'
 assert gates['receipt-metadata-gates.json']['gates']==10
 suite=gates['suite-gate-results.json'];assert suite['binary_sha256']==host_sha
 proofs=suite['reset_proofs'];assert len(proofs)==4 and {(r['controller'],r['draft']) for r in proofs}=={(c,d) for c in ('python','native') for d in ('none','mtp')}
 for proof in proofs:
  assert proof['exact'] is True and proof['prompts']>=3 and proof['orders']>=2 and proof['host_memory']=='resident' and proof['host_path']=='prepared' and proof['argument_audit'] is True
  evidence=proof['prompt_evidence'];assert len(evidence)>=3 and len({r['prompt_id'] for r in evidence})==len(evidence)
  for row in evidence:
   digests=row['canonical_sha256_by_order'];assert len(digests)>=2 and len(set(digests))==1 and row['fixture_files']==32 and row['state_files']>=(214 if proof['draft']=='mtp' else 208)
 assert suite['formula_test'] and suite['checker_snapshot_binding'] and suite['exactness_failure_continues']==[False,True,True]
 # Independent resumed reviews bind the source, dynamic gates bind the binaries.
 for name in ('review-resume-controller.json','review-resume-reset.json','review-resume-authority.json','review-draft-capture.json'):
  review=gates[name];assert review['source_sha256']
  for source,digest in review['source_sha256'].items():assert sha(P/source)==digest,('stale independent review',name,source)
 # Hash-bind both the gate executions and the standalone sanitizer builds.
 native_build=json.loads((P/'native-build-receipt.json').read_text());native_rows={r['binary']:r for r in native_build['binaries']}
 for gate,entry,count_field,count in (
  ('native-controller-cpu.json','native-controller-test','cases',1123),('native-controller-asan.json','native-controller-asan','cases',1123),('native-controller-tsan.json','native-controller-tsan-llvm22','cases',1123),
  ('native-mailbox-faults.json','native-mailbox-fault-test','gates',5),('native-mailbox-faults-asan.json','native-mailbox-fault-asan','gates',5),('native-mailbox-faults-tsan.json','native-mailbox-fault-tsan-llvm22','gates',5)):
  digest=sha(B/entry);row=native_rows['build/'+entry]
  assert gates[gate]['binary_sha256']==digest==row['sha256'] and gates[gate][count_field]==count
  if count_field=='cases':assert gates[gate]['ternary_patterns']==1093 and gates[gate]['long_random_cases']==24 and gates[gate]['bounded_spin_iterations']==0
  else:assert gates[gate]['repeated_requests']==32 and gates[gate]['spin_iterations']==0
  assert row['compile_and_link_same_invocation'] is True and all(flag in row['command'] for flag in ('-fno-fast-math','-ffp-contract=off'))
  for source,expected in row['source_sha256'].items():assert sha(P/source)==expected,('stale controller build',entry,source)
  binaries[entry]=digest
 for phase in ('fixtures','models'):assert gates['window-cpu-'+phase+'.json']['binary_sha256']==host_sha
 fixtures={r['window']:r for r in gates['window-cpu-fixtures.json']['rows']}
 for name in ('K1a','K1b'):
  assert fixtures[name]['fixture_binary_sha256']==binaries['gnu-host/nongemv-fixtures'] and fixtures[name]['linked_binary_sha256']==binaries['gnu-host/p33-linked-fixtures']
 assert fixtures['K2']['fixture_binary_sha256']==binaries['gnu-host/k2-fixtures']
 assert gates['argument-block-tests.json']['checks']==16 and gates['prepared-invalidation.json']['tests']==15
 for c in ('gnu-host','icpx-host','asan'):
  for prefix in ('mini-','mtp-gates-'):assert gates[prefix+c+'.json']['binary_sha256']==binaries[c+'/own-rt-iq3']
 for c,prefix in (('gnu-host',''),('icpx-host','icpx-host-')):
  for m in ('none','ngram','hit','miss','mtp'):
   r=gates[f'real-{prefix}{m}.json'];assert r['binary_sha256']==binaries[c+'/own-rt-iq3'] and r['token_matches']==8 and r['layer_matches']==r['layer_total']==384
 for n in prompts:assert gates[f'agreement-{n}.json']['binary_sha256']==binaries['gnu-host/own-rt-iq3']
 for row in gates['fixture-gates.json']['rows']:assert row['binary_sha256']==binaries[row['compiler']+'/nongemv-fixtures']
 for row in gates['p33-linked-fixture-gates.json']['rows']:assert row['binary_sha256']==binaries[row['compiler']+'/p33-linked-fixtures']
 for row in gates['owner-gates.json']['rows']:assert row['binary_sha256']==binaries[row['compiler']+'/'+row['name']]
 for row in gates['validation-gates.json']['checks']:
  if 'entry' in row:assert row['binary_sha256']==binaries[row['compiler']+'/'+row['entry']]
 for n in ('review-native-faults.json','draft-auth-gates.json'):assert gates[n]['binary_sha256']==binaries['gnu-host/own-rt-iq3']
 archived=gates['fixture-gates.json']['full_receipts'];blob=P/archived['path'];assert sha(blob)==archived['compressed_sha256']
 assert hashlib.sha256(gzip.decompress(blob.read_bytes())).hexdigest()==archived['uncompressed_sha256']
 precision={};links={}
 for c in ('gnu-host','icpx-host','asan','device'):
  flags=['-fno-fast-math','-ffp-contract=off']+(['-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt'] if c=='device' else [])
  cc=json.loads((B/c/'compile_commands.json').read_text());ll={str(f.relative_to(B)):f.read_text() for f in (B/c).rglob('link.txt')}
  assert cc and ll and all(all(x in r['command'].split() for x in flags) for r in cc) and all(all(x in v.split() for x in flags) for v in ll.values())
  precision[c]=dict(flags=flags,compile_count=len(cc),link_count=len(ll),compile_commands_sha256=sha(B/c/'compile_commands.json'));links.update(ll)
 from math_gate import check
 from queue_gate import check as queuecheck
 official=json.loads((P/'official-tensors.json').read_text())
 capture_inputs={};capture_fixtures={}
 for prompt in prompts:
  run=json.loads((P/f'capture-run-{prompt}.json').read_text());assert run['passed'] and run['binary_sha256']==host_sha
  root=Path(run['output']);expected=json.loads((P/f'capture-repeat-{prompt}.json').read_text())['sha256']
  actual={str(f.relative_to(root)):sha(f) for pattern in ('row-*/*.bf16','row-*/*.bin','draft-final-state/*.bin') for f in root.glob(pattern)}
  assert actual and actual==expected
  capture_inputs[prompt]=sha(P/f'capture-input-{prompt}.json');capture_fixtures[prompt]=actual
 if (P/'window-seal-admission-gates.json').exists():
  admission=json.loads((P/'window-seal-admission-gates.json').read_text());assert admission['passed']
  names.append('window-seal-admission-gates.json')

 receipt=dict(schema='own-runtime.iq3.packet38.build.v1',passed=True,device_executed=False,real_model_device_qualified=False,
  source_parents={'packet32':'a74a1c2045829134bc32cb420a5cd5c80751651f','packet36':'3048343bff','packet37':'3c03e29a4e'},arithmetic='iq3-p17-detmath-v2',
  sources=sources(),artifacts_sha256=binaries,precision=precision,link_commands=links,input_sha256=sha(B/'input/input.json'),
  nongemv_fixture_host_sha256=gates['fixture-gates.json']['output_sha256'],
  p33_linked_fixture_host_sha256=gates['p33-linked-fixture-gates.json']['output_sha256'],
  draft_capture_fixture_sha256=capture_fixtures,draft_capture_input_sha256=capture_inputs,
  official_manifest_sha256=sha(P/'mtp-manifest.tsv'),official_tensor_receipt_sha256=sha(P/'official-tensors.json'),
  official_tensor_sha256={n:r['sha256'] for n,r in official['tensors'].items()},gate_receipts={n:sha(P/n) for n in names},native_build_receipt_sha256=sha(P/'native-build-receipt.json'),
  math_gate=check(),queue_gate=queuecheck(),memory_plan=json.loads((P/'memory-plan.json').read_text()),
  max_compile_jobs=2,numeric_threads_per_rank=2,max_cpu_bound_processes=4,anonymous_memory_limit_bytes=10000000000,
  pending=['all coordinator device windows','device kernel timing and K2 selection','GPU controller equivalence and latency','complete twelve-prompt suite when all oracles arrive'])
 (P/'build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 (P/'cpu-tests.json').write_text(json.dumps(dict(passed=True,device_executed=False,gate_count=len(names),gates=receipt['gate_receipts']),indent=2)+'\n')
 (P/'BINARY-HASHES.md').write_text('# Binary SHA256\n\nNo device binary ran. Ignored build trees remain for coordinator windows.\n\n| Binary | SHA256 |\n| --- | --- |\n'+''.join(f'| {n} | {h} |\n' for n,h in sorted(binaries.items())))
 print('SEALED',len(names),'CPU gate receipts;',len(binaries),'binaries')
if __name__=='__main__':main()
