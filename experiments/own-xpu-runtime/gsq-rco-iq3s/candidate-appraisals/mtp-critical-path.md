# Current MTP critical path and next lever

The current a0f9 engine is chiefly limited by approximately30ms target halves and failed-speculation redo, not by a large measured controller bookkeeping stall. A launch-only fusion of17 already-fast IQ3 gate/up pairs is a small structural change to roughly1,140 launches per rank-half. Prefer investigating arithmetic-preserving block metadata hoisting in untouched dense Q4_K/Q5_K/IQ4_XS before building that fusion. This is an appraisal, not a new speed result.

## Retained twelve-prompt evidence

Read only24 audited `suite-request.json` files and four prompt00 rank timing JSONL files; every byte hash matched the frozen actual index. No state/model payload was opened. All12 pairs emitted128 tokens per arm and had127 guesses in MTP:1,160 hits,364 misses,zero unavailable guesses,76.12% acceptance. Acceptance varies67.72–85.83% across prompts; misses18–41 per prompt.

| Quantity | Retained measurement |
|---|---:|
| Target-only decode, all12 |94,248.687 ms /1,524 intervals =16.170 tok/s |
| MTP decode, all12 |65,026.015 ms /1,524 intervals =23.437 tok/s |
| MTP hit-cycle mean / median |34.106 /34.643 ms (1,160) |
| MTP miss-cycle mean / median |70.072 /68.603 ms (364) |
| Explicit redo total / mean per miss |12,323.120 /33.855 ms |
| Rank0 rollback command wall total / mean |1,410.632 /3.875 ms (364) |
| Decode-labelled draft wall mean / median |3.072 /3.074 ms (1,524) |
| Waiting for draft-publication mean |2.056 ms (1,524 decode-labelled rows) |

The controller's cycle records and first-to-last emitted-token interval have slightly different endpoints; their sums are not interchangeable. `redo_ms` spans rollback, corrected rank0 half and accept, about18.95% of measured MTP decode. It is a measured cost, **not** an available free saving: the correction is required for exact verification. The1.411s rollback command wall is included inside redo, not additive. Snapshot copying and a corrected half must be preserved unless independently replaced.

The rank trace contains2,750 rank0 halves versus2,386 rank1 halves: exactly364 extra rank0 corrections. Mean recorded half busy times are30.432/30.423ms; command receive-to-complete means31.204/30.470ms. Accepted tokens mostly run overlapping target halves; misses add roughly one rank0 half plus rollback. The two ranks are already similarly sized in this workload.

## What the draft timings actually measure

Rank0's op9 acknowledges asynchronous draft submission in0.426ms mean; that is **not** full draft compute. `mtp.hpp::poll_result` reports submission-to-publication wall time and explicitly sets GPU time to-1 because event timestamps are deferred. All2,374 retained draft GPU fields are-1; target rank-trace GPU fields are0 in this token-timing run. Neither is a measured zero-cost kernel.

The1,524 rows with defined hit/miss correspond to decode predictions; their total draft wall is4.682s. The other850 teacher-forced/unlabelled rows total1.026s (mean1.207ms); the head is usually omitted during known-prompt processing. Draft wall and publication wait overlap rank1 work, so neither sum can simply be subtracted from65.026s. The misleadingly named `rank1_before_half_ms` is draft submission to a later rank1 start: median0.449ms but mean8.468ms on labelled rows. It includes correction/scheduling across cycles and is not pure IPC overhead.

There may be a few milliseconds of residual lead-time gain from a faster full-vocabulary draft or earlier safe publication, but this evidence cannot isolate the critical-path fraction or split the draft into kernels. Accept command wall totals are below1ms per rank across all MTP requests; optimizing those tiny acknowledgements is not supported as a large lever.

## Host enqueue and fusion scale

Prompt00 actual rank-half timing exists. In MTP, rank0 has243 half rows (214 ordinary positions plus29 corrections), with mean30.134ms completion,5.049ms enqueue-loop CPU time,24.260ms reported wait and0.576ms preparation. Rank1 has214 halves,30.327ms completion,4.373ms enqueue and25.932ms wait. Retirement averages about0.21ms. These fields overlap hardware progress and are not independent GPU/CPU additive budgets; timing JSONL also has non-half diagnostic rows, which were explicitly excluded from half-only reductions.

An IQ3-only concatenated gate/up launch saves8 submissions on rank0 and9 on rank1 per half: below0.8% of the1,143/~1,139 launch counts. No per-format current class attribution establishes how much time those17 pairs consume; dividing the938.435+925.481ms all-format gate/up class time by layer count would invent a cost estimate. Dual accumulators could share input work, but register pressure and distinct weight decoding remain. A launch-only win is likely modest; a large end-to-end claim is unsupported.

## Prefill: larger envelope, larger engineering change

The862 total prompt tokens cost26.229s target-only and27.681s MTP to first emitted token across12 requests. MTP prompt wall is29.86% of prompt+decode time in this short-prompt corpus. The existing controller already overlaps known next-token rank0 work with rank1; it still issues one token-position half at a time and advances the teacher-forced draft state. All48 indexed `prefill-timings.jsonl` and48 `progress.jsonl` files are empty; all48 rank `timings.jsonl` files are nonempty. This does not mean no prefill: native half traces contain it.

Exact two-row/layer-major prefill could amortize launches and reuse weights, making it a materially larger future lever, especially for long prompts. But P212/P213 production helpers were compile-only on an older model/dispatch; they do not qualify this GSQ model, two-rank controller or draft. Real work includes per-row HC/PLE/gather routes, causal GDN/QSA state, per-slot experts, original BF16 rounding,32-position capacity boundaries, final-prompt exclusion, inter-rank handoff, teacher-forced draft history, RESET and all checkpoint bytes. No batched math or host shortcut can be presumed exact. It is a substantial integration project, not the next small kernel patch.

## More concrete near-term arithmetic candidate

`gsqn::lane_sum<12/13/23>` walks `k=lane; k<K; k+=32` and calls the scalar decoder for every coefficient. For256-element blocks, strip-mining as `block`, then eight groups with `k=block*256+group*32+lane` preserves each lane's accumulation order exactly. Hoist only block-invariant decoded halves and packed header fields; retain every FP multiplication/subtraction and the SG32 adjacent tree/BF16 conversion.

Q4_K/Q5_K currently compute two half conversions for each coefficient (`d`,`dmin`); source-level per-lane work can change16 conversions per block to2. IQ4_XS can change8 to1 and hoist the shared high-scale word. Group scale/minimum fields still vary across eight groups and cannot be treated as one common scale. Q5 high bits and IQ4 codebook selection remain per-element. Do not distribute `(factor*code)-offset` into a different sum or use FMA. Signed zeros, subnormals and exceptional halves need exact checks. The compiler may already eliminate part of this work; source counts are not instruction or timing proof.

Exact current dense census:116 eligible packed-direct `gemv` sites, allK2560:43 Q4_K,31 Q5_K,42 IQ4_XS. The routed IQ4_XS pair is outside this dense-only proposal.

| Role | Q4_K | Q5_K | IQ4_XS |
|---|---:|---:|---:|
| GDN QKV |2|10|2|
| GDN z |10|4|8|
| QSA qgate |1|3|3|
| QSA k / v |0|2(v)|1(k)|
| Shared expert gate |16|4|15|
| Shared expert up |14|8|13|

The all-format QKV+z class envelope is2,305.101ms (18.32% of12,582.182ms), but includes already-optimized Q6/Q8; there is no current dense-format timing split. Thus this is a source-backed work-reduction hypothesis, not an18% savings claim. Zero resident-memory expansion is needed. Start with strict dense shapes/shared-input facade and an unchanged scalar oracle plus one fixed actual case per format, then a balanced native comparison; leave routed experts and MTP draft untouched. Root subsequently selected this116-site dense-only direction, with fixed Q4_K layer0 GDN z, Q5_K layer1 QKV and IQ4_XS layer2 GDN z micro cases; no implementation was performed in this appraisal.

## Evidence and source pins

The companion JSON retains per-prompt statistics and all28 actual metadata path hashes. Its first exploratory aggregation correctly refused a heterogeneous timing row (`KeyError`); the recorded final reduction counts only rows containing the requested half field. No evidence was altered and no runtime repeated.

- `experiments/own-xpu-runtime/gsq-rco-iq3s/dense-q6-p33/evidence/native-build.json` — `33b6add96c907a24a95b9b3161f96b1b78fb9edc4e9d4a050b11edf8e5f8c6ab`
- `experiments/own-xpu-runtime/gsq-rco-iq3s/dense-q6-p33/operating/evidence/device-a/review.json` — `8e9c69ae212a45f1bf2491dd25a75743b01a19395064d52b06d713497f686d14`
- `experiments/own-xpu-runtime/gsq-rco-iq3s/dense-q6-p33/operating/evidence/device-a/artifact-index.jsonl.gz` — `ac8a034fa32ed06b01d847c61e7a14184983631c8548d1f65878df20af034ad6`
- `experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/private/source/diet-native/native-base/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/native_controller.hpp` — `cbc2c25f2e64a3ff77e2ce4e2d6cfeaf94217a79bb098853588abf66d4cde4c9`
- `experiments/own-xpu-runtime/gsq-rco-iq3s/state-bundle/build/source-v4/rank.hpp` — `3048c31d11102e3692ac9f5c3276ec342d8b9c2cf5891ec657ae371e4cb9ae71`
- `experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/private/source/diet-native/native-src/mtp.hpp` — `deaa729573f2bb0304a9882ccede5267f6d272b5736a45a9dd6057eb0f0df542`
- `experiments/own-xpu-runtime/gsq-rco-iq3s/native-formats/packed.hpp` — `4afcfb8a12bc9704ccb6a1f5b17bc5d315c69c894caaa5fd5e4140e106372c4f`
- `experiments/own-xpu-runtime/gsq-rco-iq3s/native-formats/device_formats.hpp` — `59a03eb73a63741a4405de6b364808e1ee5ce5676d8dd7d6389e60ab2347c726`
- `experiments/own-xpu-runtime/gsq-rco-iq3s/graph/new-plan.json` — `4d37ea499b0994a69664309d8f3c88aefc908e5034ac441b63f02e02151cf78b`
- `experiments/own-xpu-runtime/gsq-rco-iq3s/metadata/new-census.json` — `b47eae82a10854f47f23acc96e44d920a8b04ea1511f100aa1395418c41ca8a1`
- `experiments/own-xpu-runtime/gsq-rco-iq3s/profiling/dense-q6-class/launch-b/evidence/device-b/review.json` — `30ed538b78040d04367fe7e99956c8ff2e483cef99194de1445f1476226bd039`
- `experiments/own-xpu-runtime/gsq-rco-iq3s/candidate-appraisals/mtp-critical-path-metadata.json` — `7b5fdd2a7db9721a80c5959f92e15ac3723d54e0b1c148a24a38a7dd78bb2f21`
