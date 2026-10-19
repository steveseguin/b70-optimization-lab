# Packet158 exclusion audit

All requested packet DO-NOT-REPEAT files were read. The exact grep matches,
line numbers and SHA256 identities are in `evidence/dnr-matches.txt` and
`evidence/source-audit.json`. Older pending language does not override later
measured closeouts. Old91,392-row wording is historical; packet114 fixes
**80,128** for this work.

| Packet and local citation | Retained exclusion / consequence for packet159 |
| --- | --- |
| [66](../packet66-mtp-depth2-probe/DO-NOT-REPEAT.md) | No probe submission/drain inside poll_result; restore exact prior attention extent; transaction-owned scratch; M=2 operator support does not prove a batched verifier. No depth2 proposal here. |
| [79](../packet79-draft-rank0/DO-NOT-REPEAT.md) | Rank0 draft placements lost2.3%/1.3%, reverse-hidden dependency and misses hurt. Draft stays rank1; no head duplication, rank relocation or topology workaround. |
| [101](../packet101-draft-geometry/DO-NOT-REPEAT.md) | Existing HC fusions and selected attention are not new wins. No wide-head revival, mutable parent seals or mistaken3200-byte storage stride. Each new branch is limited to one distinct implementation mechanism. |
| [105](../packet105-head-split/DO-NOT-REPEAT.md), [105b](../packet105b-head-split/DO-NOT-REPEAT.md) | Target-head split is already in the baseline; no speculative unverified suffix, missing reset-active flag, scratch accidentally captured by rollback, premature copy publication or one-prompt-only quality gate. First-request analysis is an early refusal, not the complete smoke. Preserve all startup windows, especially KD. |
| [106](../packet106-draft-split/DO-NOT-REPEAT.md), [106b](../packet106b-draft-split/DO-NOT-REPEAT.md) | Draft-prefix split lost in the [measured grid](../../../../notes/2026-10-18-own-runtime-packet106b-grid-result.md). Target split's+0.36% is not a draft win. No draft suffix dispatch, split protocol or extra mailbox. |
| [108](../packet108-draft-loads/DO-NOT-REPEAT.md) | INT8 eight-value-load micro closed: gate0.993×, down0.901×, below0.85 gate ([result](../../../../notes/2026-10-18-own-runtime-packet108-micro-result.md)). Do not retry load8 or hide a geometry/fusion change in it. Proposed routed reuse keeps scalar code/scale loads and changes only input reuse between two independent accumulator chains. Its distinctness must survive compiler inspection. Packet108's deferred **target shared-GEMV workgroup ordering** is also excluded; it is a different, already deprioritized mechanism. |
| [114](../packet114-draft-prefix/DO-NOT-REPEAT.md) | Prefix80,128 is immutable. No benchmark-selected N, compressed head, corpus retuning or changed draft proposals/acceptance. Target remains full vocabulary. |
| [120](../packet120-placement/DO-NOT-REPEAT.md) | 25/23 lost3.9% ([result](../../../../notes/2026-10-18-own-runtime-packet120-grid-result.md)); retain24/24. No imagined B−A slack, CPU limit leaking into device import, or allocation census mistaken for residency. |
| [122 budget](../packet122-draft-budget/DO-NOT-REPEAT.md), [122 HC](../packet122-draft-hc/DO-NOT-REPEAT.md) | Cyclic-context replay is diagnostic; useful-byte reference is not hard latency. HC subgroup remap/sigmoid parallelization closed at0.913× vs0.8 gate ([result](../../../../notes/2026-10-18-own-runtime-packet122-micro-result.md)). No HC reapplication, fresh full-bank allocation or substitution of historical times for current events. |
| [126](../packet126-early-draft/DO-NOT-REPEAT.md) | Stateful early draft needs private exact transactions and measured recoverable wait. Packet154 locates wait but does not manufacture slack. No guessed-token early compute, second unresolved target, position/cache advance or discard-only rollback. |
| [129](../packet129-draft-acceptance/DO-NOT-REPEAT.md) | No FP8/BF16 expert-format replacement, new quantization, acceptance tuning or second full expert bank. Keep the current INT8 bytes, FP32 scales and proposals. |
| [146](../packet146-prompt-lookup/DO-NOT-REPEAT.md) | No request-local n-gram/history lookup, learned draft, warmed prompt, response or KV reuse. |
| [156](../packet156-draft-slack/DO-NOT-REPEAT.md) | Existing post-prefix suffix slack supports only0.29–0.32%; closed before build. Do not repackage1.227 ms rank0 wait as rank1 idle slack. The two proposed changes execute in the original draft position. |

Additional source checks: [59](../packet59-fast-draft/DO-NOT-REPEAT.md) and
[59c](../packet59c-draft-select/DO-NOT-REPEAT.md) exclude all-on geometry/fusion
bundles; [107](../packet107-specialised-layers/DO-NOT-REPEAT.md) excludes the
failed QSA local-sharing mechanism; [112](../packet112-route-select/DO-NOT-REPEAT.md)
forbids calling selected route-fast new work; [34](../packet34-replay-bench/DO-NOT-REPEAT.md)
keeps whole-graph replay closed. [157](../packet157-draft-decomp/DO-NOT-REPEAT.md)
forbids adding host and GPU time or treating missing streams as zero time.

This packet closes no new measured arm. It prepares two narrow builds and
retains honest zero-saving outcomes. CPU proofs, a codegen change, a micro win,
a one-load bracket and full record qualification are separate gates.

## Draft-line closure (coordinator, 2026-10-19 ~03:10 UTC, hourly review 37)

| Attempt | Evidence | Outcome | Revisit only when |
| --- | --- | --- | --- |
| Make rank 1's draft faster (packet157 device decomposition → packet159 build of the top group) | The packet158 roofline (`ROOFLINE.md`, packet122 cyclic replay, two processes) puts the draft's kernel time at ≈ 1.38 ms. Positive gaps: routed experts 0.163, input/embedding 0.110, attention 0.088, attention projections 0.041, final norm 0.030, argmax 0.026, shared expert 0.024 ms. The head is 0.032 ms **under** its copy-bandwidth reference. The **sum of all positive gaps is ≈ 0.48 ms**. Packet147 needs ≈ 0.423 ms/hit for +2%, so 100% closure gives ≈ +2.3% and the lab's 20% transfer rule gives ≈ +0.45%. Host issue (packet154 `draft_issue` 1.571 ms/cycle) exceeds the summed kernel time by ≈ 0.19 ms. Packet34 measured graph replay neutral on the target half, and the most host batching could add is ≈ +0.9%. Packet157's own device decomposition smokes failed three times on analyzer strictness (wall deadline, 0.02 ms absolute tolerance, an "invalid device interval" check) after exact device work. | **Closed**: no packet159 draft build and no further draft diagnostics. Packet156 (suffix slack ≈ 0.3%) and packet120 (layer move −3.9%) were already closed. | A new mechanism that removes a measured ≥ 0.42 ms/hit from the draft's critical path (for example, a draft that does not serialize after the B half on the single CCS), with its own measured bound. |
