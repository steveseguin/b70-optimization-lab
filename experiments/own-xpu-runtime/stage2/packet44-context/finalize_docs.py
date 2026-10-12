#!/usr/bin/env python3
"""Finalize packet-local documentation only after the genuine CPU seal passes."""
import json,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent
read=lambda name:json.loads((P/name).read_text())
r=read('build-receipt.json')
assert r['passed'] and not r['device_executed'] and r['seal_status']=='complete'
c=r['cpu_capacity_gate_counts'];b=r['asan_capacity_boundary_counts']
assert c['cases']==38 and c['token_matches']==304 and c['layer_matches']==10368
text=f"""# Completed CPU gates

No device ran. No device speed or residency is qualified.

| Gate | Completed evidence |
| --- | --- |
| Suite prefixes | Three prompts × three capacities × two compilers; 18 cases, 144 tokens, 6,912 layer fixtures exact against the v2 oracle |
| Development pipeline | None, all-hit, all-miss and MTP × two compilers at 4,096; eight cases, 64 tokens, 3,072 layer fixtures exact |
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
| Draft capacity capture | Six arms, 94 confirmed input rows each; both compilers and all three capacities match 63 frozen packet38 valid-prefix fixtures per arm |
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
f=P/'README.md';s=f.read_text().replace('CPU preparation in progress. No device ran and no speed is claimed.','CPU qualification passed at all three allocation capacities. No device ran\nand no speed is claimed. [CPU-GATES.md](CPU-GATES.md) gives the completed counts.')
s=s.replace('build-receipt.json will mark\nqualification complete only after the actual CPU gates and compiled artifacts\nare verified.', 'build-receipt.json binds the completed CPU gates and compiled artifacts.\nDevice qualification remains pending.')
f.write_text(s)
f=P/'CLOSEOUT.md';s=f.read_text().replace('Qualification is in progress. A successful build is not a CPU or device gate.\nThe final authority will be build-receipt.json, emitted\nonly after all required current-binary CPU receipts pass. No speed is claimed.', 'CPU qualification passed. The 38-case matrix matched 304 tokens and 10,368\nlayer fixtures; all three capacities agree on the three suite prefixes.\nThe six draft arms and required support gates also passed. See\n[CPU-GATES.md](CPU-GATES.md) and [build-receipt.json](build-receipt.json).\nAll device windows remain pending. No speed is claimed.')
f.write_text(s)
f=P/'SEAL-AUDIT.md';s=f.read_text().replace('`seal_context.py` is implemented and syntax checked. **The seal has not run.**', '`seal_context.py` completed successfully against the current compiled artifacts.\n[build-receipt.json](build-receipt.json) is the hash-bound CPU qualification seal.')
s=s.replace('The real-model capacity matrix and six draft capture arms remain pending;\nthe final seal has not run.', 'The real-model capacity matrix and six draft capture arms also passed.\nThe final seal includes all required current-binary receipts; see CPU-GATES.md.')
f.write_text(s)
f=P/'DRAFT-CAPACITY-GATE.md';s=f.read_text().replace('`capacity_draft_gate.py` is prepared but has not been executed by its author.', '`capacity_draft_gate.py` passed all six CPU arms. Each matched the 63 frozen\npacket38 valid-prefix draft fixtures.');f.write_text(s)
(P/'binary-sha256.txt').write_text(''.join(h+'  build/'+name+'\n' for name,h in sorted(r['artifacts_sha256'].items())))
subprocess.run(['nice','-n','19','ionice','-c','3','python3','-B',str(P/'integration_inventory.py')],check=True)
print('Final CPU docs generated from the completed seal')
