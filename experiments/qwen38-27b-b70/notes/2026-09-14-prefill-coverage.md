# Published prefill coverage: bounded follow-up inventory

September 14, 2026, after the three selected follow-up measurements passed. This
inventory covers the **32 setup rows** in the [homepage model table](../../../index.html),
including its experimental and withheld-headline rows. Setup identities and
existing timing coverage were checked against the [package catalog](../../../packages/catalog.json)
and the linked package/family evidence. This is a focused audit of published
evidence, not an exhaustive search of historical raw runs or model storage.

The comparison cell means exactly **512 input tokens, one user, no reused
prompt cache, server prefill timing**. The September 13 vLLM measurement uses
the interval from first scheduled execution to first token. HTTP TTFT, prompt
tokens divided by HTTP TTFT, llama-bench engine throughput, and llama-server
prompt-evaluation counters are distinct measurements. Existing useful curves
remain valid under their own definitions; none supplies an inferred 512-token
cell.

## Main Qwen configurations

R304 means the published vLLM XPU 0.29.0 image with the lab's qualified overlay.
R308 is its optional single-request repair. The four existing short-prefill
controls were measured through a default-off allocation experiment overlay:
R308 for 4B/9B TP1, R304 for both 27B TP2 setups. They are separately identified
baseline measurements, not optimized-runtime promotions. All listed W4A16
short-prefill configurations use CLASSPAD0 and fixed draft depth.

| Model / quantization | B70s | Runtime / draft | Existing exact-512 server prefill | Decision on this two-card host |
| --- | ---: | --- | --- | --- |
| Qwen3.5 4B W4A16 | 1 | R308 control overlay; MTP3, 67k draft shortlist | 3,942 input tokens/s; [September 13 packet](2026-09-13-short-prefill-results.md) | Reuse existing evidence. |
| Qwen3.5 4B W4A16 | 2 | R304; MTP3, 67k shortlist | 7,367 input tokens/s; [follow-up](2026-09-14-prefill-followup-results.md) | **Completed; 12/12 reference outputs exact.** Same available model and runtime, additional topology measurement; corpus differs from the earlier TP1 test. |
| Qwen3.5 9B W4A16 | 1 | R308 control overlay; MTP3, 67k shortlist | 2,467 input tokens/s; [September 13 packet](2026-09-13-short-prefill-results.md) | Reuse existing evidence. |
| Qwen3.5 9B W4A16 | 2 | R304; MTP3, 67k shortlist | 4,419 input tokens/s; [follow-up](2026-09-14-prefill-followup-results.md) | **Completed; 12/12 reference outputs exact.** Same available model and runtime, additional topology measurement; corpus differs from the earlier TP1 test. |
| Qwen3.5 9B dynamic FP8 | 1 | vLLM XPU R276 / 0.27.2 lineage; MTP3, INT4 draft head | Missing; [guide](../../../repro/qwen35-9b-fp8-b70/README.md) has strict-suite and longer-context TTFT | Hardware count fits, but a separate model/runtime qualification would exceed the three-configuration scope. Deferred. |
| Qwen3.8 27B AutoRound INT4 | 1 | R304; MTP4, 67k shortlist | 1,209 input tokens/s; [follow-up](2026-09-14-prefill-followup-results.md) | **Completed; 12/12 reference outputs exact.** Available INT4 target and runtime; useful one-card option. |
| Qwen3.8 27B AutoRound INT4 | 1 | R304; no MTP | Missing; [INT4 package](../../../packages/qwen38-27b-int4-fixed-k-tp2-b70/package.json) preserves separate decode evidence | Feasible topology, but a fourth setup and separate server configuration. Deferred. |
| Qwen3.8 27B AutoRound INT4 fixed-K | 2 | R304 control overlay; MTP4, 67k shortlist | 2,198 input tokens/s; [September 13 packet](2026-09-13-short-prefill-results.md) | Reuse existing evidence. |
| Qwen3.8 27B AutoRound INT4 fixed-K | 2 | R304; no MTP | Missing; [INT4 package](../../../packages/qwen38-27b-int4-fixed-k-tp2-b70/package.json) preserves separate decode evidence | Available target, but another server configuration beyond the bounded selection. Deferred. |
| Qwen3.8 27B official FP8 / lab W8A16 | 2 | R304 control overlay, R187 serving profile; MTP1 | 2,885 input tokens/s; [September 13 packet](2026-09-13-short-prefill-results.md) | Reuse existing evidence. |
| Qwen3.8 27B official FP8 / lab W8A16 | 2 | Published no-MTP profile; package now points to R304, historical timing remains separately identified | Missing; R139's 2K–32K [HTTP timing/proxy evidence](../data/2026-09-02-qwen38-fp8-fixed-k-real-content-depth-r150-result.json) is not exact-512 server prefill | Available two-card target, but another configuration beyond the selected three. Deferred. |
| Qwen3.8 27B official FP8 / lab W8A16 | 2 | Historical R187 lineage; MTP5 | Missing; [FP8 package](../../../packages/qwen38-27b-fp8-tp2-b70/package.json) preserves this draft setting separately | Requires its own runtime/draft identity and gates; do not borrow MTP1's value. Deferred. |

The three selected baseline measurements are complete. No optimization win
is claimed. Their [controller](../scripts/run-prefill-followup-stage.py)
uses one process per configuration and retains qualified output references.
Runtime ownership, endpoint state, model hashes and GPU health must be checked
by the main operator immediately before each launch. Selection is not evidence
that a server is currently running.

## Qwen3.8 27B llama.cpp setups

These seven homepage rows use separately patched native llama.cpp recipes
based on `mndodd/llama.cpp` revision `4302fb599`. The grouped rows below retain
each GPU count and draft choice; grouping means the same coverage decision,
not interchangeable measurements. All seven exact-512 server-prefill cells
are missing.

| Target / draft | B70s represented | Existing timing evidence | Decision |
| --- | --- | --- | --- |
| Q4_K_M; no MTP | 1 and 2, separate rows | TP1 [engine pp2048 sweep](../data/2026-08-22-q4km-tp1-context-kv-sweep.json), TP1/TP2 2K–32K HTTP TTFT in the [TP1](../../../packages/qwen38-27b-q4km-tp1-b70/package.json) and [TP2](../../../packages/qwen38-27b-q4km-tp2-asrock-b70/package.json) packages | Hardware counts fit; protected historical sources/weights exist in CURRENT.md. Deferred to a separate llama-server timing pass; no cross-runtime substitution. |
| Q4_K_M + Q4_0 draft; MTP2 | 1 and 2, separate rows | TP1 [2K–32K real-content HTTP TTFT](../data/2026-08-27-qwen38-q4km-q4mtp-tp1-mixed-content-depth-r1-result.json); [TP2 package](../../../packages/qwen38-27b-q4km-q4mtp-mtp2-tp2-b70/package.json) has separate serving evidence | Requires matched draft/runtime replay and prompt-evaluation extraction; deferred within the three-configuration limit. |
| Q8_0; no MTP | 1 and 2, separate rows | TP1 [engine pp2048 sweep](../data/qwen38-q8weights-f16-tp1-local-20260825-r2/result.json); TP2 [server prompt-evaluation counters at 2K–32K](../data/qwen38-q8-tp2-http-depth-prefill-20260825-r3-attempt1/summary.json) | TP2 has direct server timing, but different lengths and a repeated-token fixture. No interpolation to 512; matched server replay deferred. |
| Q8_0 + Q4_0 draft; MTP2 | 1 | [Package](../../../packages/qwen38-27b-q8-q4mtp-mtp2-tp1-b70/package.json) preserves qualified decode; no matching published exact-512 prefill | Separate near-capacity target/draft setup and runtime verification; deferred. |

## Other homepage setups

“Missing” below means no matching exact-512 server-prefill result was found in
the reviewed published package/family evidence. It does not mean that the
model has never undergone a prefill-related experiment.

| Model / quantization | B70s | Runtime / draft | Existing timing coverage | Decision |
| --- | ---: | --- | --- | --- |
| LFM2.5 2.6B Q8_0 | 1 | llama.cpp `9fee29e943`; no MTP | Missing; [raw-engine pp2048 sweep](../../../repro/lfm25-26b-q8-b70/lfm25-26b-q8.sweep.json) | Hardware fits; separate runtime/model availability and server-metric checks deferred. |
| Ornith 1.5 35B-A3B Q4_K_M | 1 | llama.cpp `9fee29e943` plus accepted twelve-feature patch; no MTP | Missing; [raw-engine pp2048 sweep](../../../repro/ornith-15-35b-a3b-q4km-b70/ornith-15-35b-a3b-q4km-twelve-feature.sweep.json) | Hardware fits; accepted patched runtime needs its own replay. Deferred. |
| Laguna-S-2.1 INT4 | 4 | native vLLM `1a7f61fe`; DFlash11 | Missing; [package](../../../packages/laguna-s-2.1-int4-b70-125tps/package.json) lists timing sweep as missing | Published topology unavailable on two B70s. |
| Gemma 4 26B-A4B Q8 | 1 | llama.cpp `c926ad098`; Q4_0 MTP draft, depth 3 | Missing; [741–32,571-token profile](../../../data/gemma4-26b-a4b-q8-b70-context-performance-profile-20260702.json) uses prompt tokens / TTFT as a proxy | Hardware fits and protected recipe exists; separate runtime and counter methodology deferred. |
| Muse-Glimmer 30B Q8/WOQ | 4 | llama.cpp `030ebb55`; DFlash draft n=15 | Missing; [package](../../../packages/muse-glimmer-30b-q8-woq-b70/package.json) lists timing sweep as missing | Published four-card topology unavailable. |
| Qwen3.6 35B-A3B Quark W8A8 INT8 | 4 | vLLM XPU June strict program; no MTP | Missing; [family evidence](../../../families/qwen-35b.json) includes p512/o512 HTTP TTFT, not server prefill | Published four-card topology unavailable; do not relabel TTFT as prefill. |
| Qwen3.6 35B-A3B AutoRound INT4 | 1 | vLLM XPU combined-runtime-guards r16; no MTP | Missing; [family evidence](../../../families/qwen-35b.json) is an i128/o1024 raw-engine screen | Hardware count fits, but experimental identity remains open and historical runtime needs verification. Deferred. |
| MiniMax M2.7 AutoRound INT4 | 4 | vLLM `c51df430` / llm-scaler overlay; no MTP | Missing; [package](../../../packages/minimax-m27-int4-autoround-b70/package.json) lists timing sweep as missing | Published four-card topology unavailable; preserve owning lane. |
| DeepSeek V4 Flash 180B, community K160 FP8/FP4 experts | 4 | vLLM XPU record stack `264c7f2/3131567/48fda4f`; DSpark7 | Missing; [family evidence](../../../families/deepseek-v4.json) retains HTTP TTFT | Four-card topology unavailable; fully resident target also exceeds two-card capacity. |
| Nemotron 3.5 Lightning 30B-A3B UD-Q4_K_M | 1 | llama.cpp `9fee29e943`; no MTP | Missing; [raw-engine pp2048 sweep](../../../repro/nemotron-35-lightning-30b-a3b-b70/nemotron-35-lightning.sweep.json) | Hardware fits; strict headline pending, distinct runtime/model checks deferred. |
| Ornith 1.5 9B Q8_0 | 1 | llama.cpp `9fee29e943`; no MTP | Missing; [raw-engine pp2048 sweep](../../../repro/ornith-15-9b-q8-b70/ornith-15-9b-q8.sweep.json) | Hardware fits; strict headline withheld after output-gate failure. Separate quality/runtime work deferred. |
| Qwen3.8 Flash-Next 125B-A6B FP8 | 4 | native vLLM `2a372e86`; no MTP | Missing; [package](../../../packages/qwen38-flash-next-fp8-tp4-mtp0-w13n64-b70-34tps-20260908/package.json) lists timing sweep as missing | Published four-card topology unavailable; preserve owning lane and host stability constraints. |
| Qwen3.8 Flash-Next 125B-A6B FP8 | 4 | native vLLM `6d872457`, exact serial GDN overlay; MTP1 | Missing; [8K–32K HTTP TTFT](../../../repro/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/evidence/a382-a394-context-profile.json) belongs to a separate capacity profile | Published four-card topology unavailable. No prefill inferred from TTFT. |

Catalog-only historical Flash-Next MTP1 replay packages (27/32/37/38 tok/s)
share the four-card hardware blocker but retain different runtime identities;
they are not extra homepage rows or substitutes for the current configuration.
The catalog-only Qwen3.8 Q5_K_S vision/MTP package also has a target-only
llama-bench pp2048 curve, not a matching MTP service prefill measurement. None
expands this session's selected scope.

The three selected baseline measurements are complete with preserved setup
identities and replay-verified evidence; other gaps remain explicitly unmeasured.
Optimization selection is documented in the separate
[prefill review](2026-09-14-prefill-optimization-review.md).
