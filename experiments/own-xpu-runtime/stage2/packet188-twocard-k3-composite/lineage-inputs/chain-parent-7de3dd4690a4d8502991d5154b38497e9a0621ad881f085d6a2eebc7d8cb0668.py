#!/usr/bin/env python3
"""Finalize packet-local documentation only after the genuine CPU seal passes."""
import json,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent
read=lambda name:json.loads((P/name).read_text())
r=read('build-receipt.json')
assert r['passed'] and not r['device_executed'] and r['seal_status']=='complete_under_coordinator_reduced_cpu_plan'
c=r['cpu_capacity_gate_counts'];b=r['asan_capacity_boundary_counts']
assert c['retained_cases']==25 and c['token_matches']==200 and c['layer_matches']==5376
text=f"""# Completed CPU gates

No device ran. No device speed or residency is qualified.

| Gate | Completed evidence |
| --- | --- |
| Suite prefixes | GNU: three prompts × three capacities; nine cases, 72 tokens, 3,456 layer fixtures exact against the v2 oracle |
| Development pipeline | GNU: none, all-hit, all-miss and MTP at 4,096; four cases, 32 tokens, 1,536 layer fixtures exact |
| Intel composite | MTP with two forced misses and one hit at 4,096; four tokens, 192 layer fixtures exact; diagnostic Python mailbox injection |
| Block-boundary rollback | Two controllers × three modes × two compilers; 12 cases, 96 tokens, 384 layer fixtures; discarded position-32 speculative halves checked |
| ASAN/UBSAN boundary rollback | {b['cases']} cases, {b['token_matches']} tokens, {b['layer_matches']} layer fixtures; two discarded-boundary cases |
| Beyond-budget selection | Both host compilers; 854,164 checks, 96 selection fixtures, 32 attention fixtures and 96 nonfinite fixtures |
| Full operator arithmetic | Six capacity/compiler fixture arms plus two linked arms; 21,528 checks |
| Host validation-only | Three finite-grid K2 arms and one nongemv arm; 6,401 checks, separate from arithmetic evidence |
| Actual Engine native controller | 1,109 cases; native/Python token, fixture and final-state equality |
| Native standalone controller | 1,123 cases each in ordinary, ASAN/UBSAN and TSan builds |
| Native mailbox faults | Five checks and 32 repeated requests in each of three builds |
| Mini pipeline | GNU 130 cases, Intel seven, ASAN/UBSAN seven |
| MTP isolation | Seven cases in each of GNU, Intel and ASAN/UBSAN builds |
| Draft authentication | Four safe CPU rejection cases |
| Draft capacity capture | Two GNU references at 4,096 and 32,768, 94 confirmed rows each; both match 63 frozen packet38 valid-prefix fixtures |
| Ownership and lifetime | Ten suites across both compilers; 15 prepared-invalidation ASAN/UBSAN checks |
| Argument bounds | 16 serializer checks; 410 linked device captures, maximum 752 bytes; 1,025-byte negative compile refused |
| Wrappers and admission | 37 inherited window tests; ten new tests covering 22 window/capacity/manifest combinations; 27 memory admission checks |

The full seal binds {len(r['gate_receipts'])} required gate receipts and
{len(r['artifacts_sha256'])} retained binary hashes. See
[build-receipt.json](build-receipt.json), [BINARY-HASHES.md](BINARY-HASHES.md) and
[CPU-REPRO.md](CPU-REPRO.md). Validation-only counts never substitute for
arithmetic comparisons. Historical failures remain in their ledgers/archives.

All coordinator device windows, measured short-context wall cost, physical
residency/driver overhead and long real conversations remain unqualified.
"""
(P/'CPU-GATES.md').write_text(text)
f=P/'README.md';s=f.read_text().replace('CPU preparation in progress. No device ran and no speed is claimed.','CPU qualification passed under the coordinator’s reduced plan. GNU covers all\nthree allocation capacities; Intel has the required composite case. No device\nran and no speed is claimed. [CPU-GATES.md](CPU-GATES.md) gives the counts.')
s=s.replace('build-receipt.json will mark\nqualification complete only after the actual CPU gates and compiled artifacts\nare verified.', 'build-receipt.json binds the completed CPU gates and compiled artifacts.\nDevice qualification remains pending.')
f.write_text(s)
f=P/'CLOSEOUT.md';s=f.read_text().replace('Qualification is in progress. A successful build is not a CPU or device gate.\nThe final authority will be build-receipt.json, emitted\nonly after all required current-binary CPU receipts pass. No speed is claimed.', 'CPU qualification passed under the coordinator’s reduced plan. The 25 retained\ncases matched 200 tokens and 5,376 layer fixtures (13 GNU real-model cases\nplus 12 rollback cases). The Intel composite matched four tokens and 192\nlayers with two forced misses. Both requested GNU KD references passed. See\n[CPU-GATES.md](CPU-GATES.md) and [build-receipt.json](build-receipt.json).\nAll device windows remain pending. No speed is claimed.')
f.write_text(s)
f=P/'SEAL-AUDIT.md';s=f.read_text().replace('`seal_context.py` is implemented and syntax checked. **The seal has not run.**', '`seal_context.py` completed successfully against the current compiled artifacts.\n[build-receipt.json](build-receipt.json) is the hash-bound CPU qualification seal.')
s=s.replace('The real-model capacity matrix and six draft capture arms remain pending;\nthe final seal has not run.', 'The reduced real-model gates and both requested GNU draft references passed.\nThe final seal includes all required current-binary receipts; see CPU-GATES.md.')
f.write_text(s)
f=P/'DRAFT-CAPACITY-GATE.md';s=f.read_text().replace('`capacity_draft_gate.py` is prepared but has not been executed by its author.', '`resume_draft_references.py` passed the two coordinator-required GNU CPU\nreferences at 4,096 and 32,768. Each matched all 63 frozen valid-prefix fixtures.');f.write_text(s)
(P/'binary-sha256.txt').write_text(''.join(h+'  build/'+name+'\n' for name,h in sorted(r['artifacts_sha256'].items())))
subprocess.run(['nice','-n','19','ionice','-c','3','python3','-B',str(P/'integration_inventory.py')],check=True)
print('Final CPU docs generated from the completed seal')
