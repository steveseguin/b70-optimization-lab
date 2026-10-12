"""Seal only current-binary CPU evidence; no inherited pass is credited."""
import json,hashlib,gzip
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build';ROOT=P.parents[3]
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(4*1024*1024):h.update(b)
 return h.hexdigest()
def main():
 from build import sources
 names=['draft-auth-gates.json','pipeline-draft-agreement.json','mtp-controller-tests.json','owner-gates.json','fixture-gates.json','validation-gates.json','entry-codes.json','window-tests.json','identity-tree-tests.json','kernel-sizes.json','expert-down-review-gates.json','state-machine-tests.json','review-controller-tests.json','review-native-faults.json','canary-host-gates.json','resident-host-gates.json','target-source-identity.json','rollback-inventory.json']
 names += [f'mini-{c}.json' for c in ('gnu-host','icpx-host','asan')]
 names += [f'mtp-gates-{c}.json' for c in ('gnu-host','icpx-host','asan')]
 names += [f'real-{prefix}{m}.json' for prefix in ('','icpx-host-') for m in ('none','ngram','hit','miss','mtp')]
 names += ['real-campaign-gnu-host.json','real-campaign-icpx-host.json']
 prompts=('incident-retrospective','code-review','customer-email','benchmark-analysis')
 names += [f'agreement-{n}.json' for n in prompts]
 names += [str(f.name) for pattern in ('reference-*-repeat-*.json','reference-reproduction-source.json','capture-repeat-*.json','remaining-cpu-receipt.json') for f in P.glob(pattern)]
 gates={n:json.loads((P/n).read_text()) for n in names}
 assert all(v.get('passed') is True for v in gates.values())
 assert gates['resident-host-gates.json']['cases']==15
 assert {(r['compiler'],r['mode']) for r in gates['resident-host-gates.json']['rows']}=={(c,m) for c in ('gnu-host','icpx-host','asan') for m in ('none','ngram','hit','miss','mtp')}
 entries=('own-rt-iq3','nongemv-fixtures','k2-fixtures','jit-smoke','authority-tests','owner-retirement-tests','chain-tests','queue-tests','lifetime-tests')
 binaries={str(f.relative_to(B)):sha(f) for c in ('gnu-host','icpx-host','asan','device') for f in (B/c).iterdir() if f.name in entries}
 for c in ('gnu-host','icpx-host','asan'):
  for prefix in ('mini-','mtp-gates-'):assert gates[prefix+c+'.json']['binary_sha256']==binaries[c+'/own-rt-iq3']
 for c,prefix in (('gnu-host',''),('icpx-host','icpx-host-')):
  for m in ('none','ngram','hit','miss','mtp'):
   r=gates[f'real-{prefix}{m}.json'];assert r['binary_sha256']==binaries[c+'/own-rt-iq3'] and r['token_matches']==8 and r['layer_matches']==r['layer_total']==384
 for n in prompts:assert gates[f'agreement-{n}.json']['binary_sha256']==binaries['gnu-host/own-rt-iq3']
 flags=['-fno-fast-math','-ffp-contract=off'];precision={};links={}
 for c in ('gnu-host','icpx-host','asan','device'):
  required=flags+(['-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt'] if c=='device' else [])
  cc=json.loads((B/c/'compile_commands.json').read_text());ll={str(f.relative_to(B)):f.read_text() for f in (B/c).rglob('link.txt')}
  assert cc and ll and all(all(x in r['command'].split() for x in required) for r in cc) and all(all(x in text.split() for x in required) for text in ll.values())
  precision[c]=dict(flags=required,compile_count=len(cc),link_count=len(ll),compile_commands_sha256=sha(B/c/'compile_commands.json'));links.update(ll)
 from math_gate import check
 from queue_gate import check as queuecheck
 fixturehashes={}
 for n in prompts:
  run=json.loads((P/f'capture-run-{n}.json').read_text());assert run['binary_sha256']==binaries['gnu-host/own-rt-iq3']
  out=Path(run['output'])
  fixturehashes[n]={str(f.relative_to(out)):sha(f) for pattern in ('row-*/*.bf16','row-*/*.bin','draft-final-state/*.bin') for f in out.glob(pattern)}
 official=json.loads((P/'official-tensors.json').read_text())
 receipt=dict(schema='own-runtime.iq3.packet36.build.v1',passed=True,device_executed=False,real_model_device_qualified=False,source_anchor='2e8ec7585c',arithmetic='iq3-p17-detmath-v2',sources=sources(),artifacts_sha256=binaries,precision=precision,link_commands=links,input_sha256=sha(B/'input/input.json'),official_manifest_sha256=sha(P/'mtp-manifest.tsv'),official_tensor_receipt_sha256=sha(P/'official-tensors.json'),official_tensor_sha256={n:r['sha256'] for n,r in official['tensors'].items()},official_file_sha256={n:r['sha256'] for n,r in official['files'].items()},gate_receipts={n:sha(P/n) for n in names},draft_capture_fixture_sha256=fixturehashes,draft_capture_input_sha256={n:sha(P/f"capture-input-{n}.json") for n in prompts},math_gate=check(),queue_gate=queuecheck(),memory_plan=json.loads((P/'memory-plan.json').read_text()),max_compile_jobs=2,numeric_threads_per_rank=2,max_cpu_bound_processes=4,anonymous_memory_limit_bytes=10_000_000_000)
 (P/'build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 (P/'BINARY-HASHES.md').write_text('# Binary SHA256\n\nNo device binary ran.\n\n| Binary | SHA256 |\n| --- | --- |\n'+''.join(f'| {n} | {h} |\n' for n,h in binaries.items()))
 report=['# CPU results\n','No device ran; no speed is claimed.\n','| Prompt | Device-arithmetic draft acceptance | Packet31 FP8 acceptance | Agreement with FP8 | Agreement with int8 |','| --- | ---: | ---: | ---: | ---: |']
 for n in prompts:
  r=gates[f'agreement-{n}.json'];ref=r['references'];report.append(f"| {n} | {r['target_acceptance']*100:.4f}% ({sum(x['hit'] for x in r['rows'])}/64) | {ref['mtp_fp8_iq3']['acceptance']*100:.4f}% | {ref['mtp_fp8_iq3']['token_agreement']*100:.4f}% | {ref['mtp_int8_iq3']['token_agreement']*100:.4f}% |")
 report+=['',f"Authentication rejection/teardown controls: {gates['draft-auth-gates.json']['cases']}; resident binding cases: {gates['resident-host-gates.json']['cases']}.",'','Real oracle gates: five modes under each of GNU and Intel host builds; each 8/8 target tokens and 384/384 layer fixtures. No target tolerance.','',f"Mini-model cases: "+', '.join(f"{c}={gates['mini-'+c+'.json']['cases']}" for c in ('gnu-host','icpx-host','asan'))+'.',f"Provider fault/state/cache cases: "+', '.join(f"{c}={gates['mtp-gates-'+c+'.json']['cases']}" for c in ('gnu-host','icpx-host','asan'))+'.','',f"Compiled kernel captures: {gates['kernel-sizes.json']['kernel_classes']}; maximum {gates['kernel-sizes.json']['max_after']} bytes; 1025-byte negative control rejected.",'','Full per-position logit distances and sample/output hashes: agreement-*.json. Exact source/binary/official-tensor hashes and all gates: build-receipt.json.']
 distances=['','| Prompt | Reference | Mean position RMS logit distance | Largest absolute logit distance |',
            '| --- | --- | ---: | ---: |']
 for n in prompts:
  for variant in ('mtp_fp8_iq3','mtp_int8_iq3'):
   rows=[r['references'][variant] for r in gates[f'agreement-{n}.json']['rows']]
   distances.append(f"| {n} | {variant} | {sum(r['logit_rms'] for r in rows)/len(rows):.9f} | {max(r['logit_max_abs'] for r in rows):.9f} |")
 report+=distances+['','Distances use the complete vocabulary at every scored position; they describe draft arithmetic only.']
 (P/'CPU-RESULTS.md').write_text('\n'.join(report)+'\n')
 total=sum(gates[f'agreement-{n}.json']['positions'] for n in prompts)
 hits=sum(sum(r['hit'] for r in gates[f'agreement-{n}.json']['rows']) for n in prompts);alpha=hits/total
 # Keep the complete measured table, omitting the following prose section.
 brief=report[2:4+len(prompts)]
 brief+=['',f'Pooled acceptance is {hits}/{total} ({100*alpha:.4f}%). These are development prompts, not a benchmark suite.',
         f'For this prompt mix the cycle model is {alpha:.8f}*max(A,B+D) + {1-alpha:.8f}*max(max(A,B)+R,B+D). Device A/B/D/R are not measured.',
         '', 'All ten real-model CPU modes passed: 8/8 tokens and 384/384 layer fixtures per mode, across GNU and Intel builds. Full gate counts and binary identities: [CPU results](CPU-RESULTS.md) and [build receipt](build-receipt.json).']
 readme=P/'README.md';body=readme.read_text();start=body.index('<!-- cpu-results:start -->')+len('<!-- cpu-results:start -->');end=body.index('<!-- cpu-results:end -->')
 readme.write_text(body[:start]+'\n'+'\n'.join(brief)+'\n'+body[end:])
 (P/'cpu-tests.json').write_text(json.dumps(dict(passed=True,device_executed=False,gates={n:sha(P/n) for n in names},real_modes_per_compiler=5,real_tokens_per_mode=8,real_fixtures_per_mode=384,provider_cases_per_compiler={c:gates['mtp-gates-'+c+'.json']['cases'] for c in ('gnu-host','icpx-host','asan')}),indent=2)+'\n')
if __name__=='__main__':main()
