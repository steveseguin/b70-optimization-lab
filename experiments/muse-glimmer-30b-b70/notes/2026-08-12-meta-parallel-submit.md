# Parallel TP host submission

Date: 2026-08-12

## Decision

Keep `GGML_META_PARALLEL_SUBMIT=1` as a default-off exact kernel-path win.
It submits the four independent simple-backend graphs concurrently, joins the
host threads, and then runs the existing TP collective. Per-device queue order
and all arithmetic are unchanged. No drafter training was performed.

Source commit: `f9434ef2b` (`meta: add experimental parallel device
submission`). Experimental server SHA-256:
`8eea728f1752424475a49db07ecef8776cb42d5347f84f208243afdb8887f50f`.
The operation profiler was disabled because its shared counters are not
thread-safe.

## Fixed identity

- Muse Glimmer 30B BF16 target, stock BF16 DFlash, TP4 devices `0,1,2,3`;
- DFlash `n_max=15`, `p_min=0.15`;
- single request, `parallel=1`, greedy, prompt cache disabled, 256 generated
  tokens for prose, code, and JSON;
- oneDNN primitive cache, binding cache, and BF16 graph conversion cache on;
- direct BF16/oneMKL, command graphs, device argmax, and operation profiling
  off;
- only changed variable: `GGML_META_PARALLEL_SUBMIT=0/1`.

Canonical hashes were `914f754747d0edaa`, `cf2b2c4fd9e36fe5`, and
`4f813a9706abc163` for prose, code, and JSON.

## Strict adjacent results

| Order | Arm | Prose | Code | JSON | Mean t/s |
| --- | --- | ---: | ---: | ---: | ---: |
| control first | serial | 46.488 | 67.559 | 81.651 | 65.233 |
| control first | parallel | 48.507 | 70.428 | 84.696 | 67.877 |
| candidate first | parallel | 48.331 | 70.037 | 85.285 | 67.884 |
| candidate first | serial | 46.663 | 67.349 | 82.318 | 65.443 |

The candidate improved the arithmetic mean by `4.05%` in control-first order
and `3.73%` in candidate-first order. The pooled arm means are approximately
`65.338 -> 67.881 tok/s`, or `+3.89%`.

Every row produced all 256 tokens and all canonical hashes. Within each
adjacent pair, drafted and accepted counts were identical in all three
classes. The JSON draft count moved from 672 in the first pair to 674 in the
second pair for both arms, so that epoch variation does not confound the
within-pair comparison.

Raw evidence:

- `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/meta-parallel-submit-ab-v3-20260812.jsonl`,
  SHA-256 `ba1ebc9ded794e70bb7f2a2f04b790ba0b2a3d418150c352d7226223ace60aca`;
- `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/meta-parallel-submit-ab-v4-reversed-20260812.jsonl`,
  SHA-256 `0831662108cad14b568e0e8fdd3a3121dbf9c37c9017ff4be883cc0713404f20`.

The fresh v3 identity was used only after the authorized host reboot and full
four-device mapping, per-card compute, native peer-read, and XCCL recovery
gates passed. Production was restored after the window and passed the complete
model, cache-zero code, and vision gate in
`data/muse-health-20260812-parallel-submit-restore.json`.

## Narrowed oneMKL combination negative

The current `GGML_SYCL_BF16_MKL=1` gate was narrowed to verification widths
N=2 through N=16, leaving N=1 on the incumbent oneDNN path. It was tested on
top of parallel submission:

| Arm | Prose | Code | JSON | Mean t/s |
| --- | ---: | ---: | ---: | ---: |
| parallel control | 48.248 | 70.320 | 84.518 | 67.695 |
| parallel + oneMKL N2-N16 | 47.668 | 72.026 | 83.424 | 67.706 |

The ratio was only `1.00016x`, inside noise, while the code hash changed from
canonical `cf2b2c4fd9e36fe5` to `b4a2bda611510441` and proposal histories
changed. Reject this combination. Raw evidence:
`/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/meta-parallel-bf16-mkl-ab-20260812.jsonl`,
SHA-256 `81944bb0576509ddd700b071e970451948045045b77b36273f5d70b25bf675a0`.

## Next action

The retained exact stack is approximately `67.9 tok/s`, still not the
`>100 tok/s` objective. Continue kernel work with a guarded batch=2 oneDNN
gate/up projection that removes one logical FFN projection submission per
layer, then measure it adjacent to this retained parallel-submit stack.

## Update: batch=2 gate/up projection

Source commit `f2b7f2324` adds a default-off
`GGML_SYCL_DNNL_FFN_BATCH2=1` path. The meta backend keeps an exact adjacent
same-layer gate/up pair in one per-device subgraph, SYCL converts the shared
activation once and issues one strided oneDNN batch=2 GEMM, then meta reduces
the two outputs separately before their consumers.

The adjacent exact A/B measured:

| Arm | Prose | Code | JSON | Mean t/s |
| --- | ---: | ---: | ---: | ---: |
| parallel-submit control | 48.249 | 70.081 | 85.027 | 67.786 |
| parallel + FFN batch2 | 48.056 | 70.486 | 85.513 | 68.018 |

This is `+0.34%`, too small for a performance promotion without reversed-order
confirmation. All canonical hashes and all proposal counts matched exactly.
A separate verbosity-4 proof run emitted the actual execution marker for
`blk.0.ffn_gate.weight`: `m=4992 n=2 k=6656`, weight batch stride `66453504`,
output stride `20447232`. Its exact mean was `68.260 tok/s`.

Raw evidence:

- `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/meta-parallel-ffn-batch2-ab-20260812.jsonl`,
  SHA-256 `4fb1b632eadc4b71ab70c770fb1776d9a411967cb88b16a20f9017aac3b963ee`;
- `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/ffn-batch2-hit-proof-20260812.jsonl`,
  SHA-256 `f45cc8965ff323089a88ba37f783a6efb32f57c0876fed50da3bda13bfcc28af`.

Production was restored and the complete model/cache-zero code/vision gate
passed in `data/muse-health-20260812-ffn-batch2-restore.json`.

## Update: pretrained DSpark combination

The already converted public pretrained DSpark checkpoint was tested with
both retained inference-path wins: device-side global maxloc and parallel TP
submission. It remains exact but does not beat BF16 DFlash:

| Assistant | Prose | Code | JSON | Mean t/s |
| --- | ---: | ---: | ---: | ---: |
| BF16 DFlash + parallel submit | 48.021 | 70.160 | 84.282 | 67.488 |
| BF16 DSpark + device maxloc + parallel submit | 44.480 | 74.332 | 76.083 | 64.965 |

DSpark improves code but loses prose and JSON, for `-3.74%` on the fixed
three-class mean. All canonical hashes passed; the maxloc debug marker proved
the device collective executed. Keep DFlash as the champion. Raw evidence:
`/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/parallel-submit-dspark-vs-dflash-20260812.jsonl`,
SHA-256 `95a7db2ec5d26d642eee53be0270ec982255023fef212f0dd8786425c26b275d`.
Production restoration passed in
`data/muse-health-20260812-dspark-parallel-restore.json`.

## Update: OpenMP affinity screen

Binding the four parallel-submit workers with `OMP_PROC_BIND=SPREAD`,
`OMP_PLACES=cores`, and active waiting did not produce a stable additional
gain. The control-first pair improved by `1.23%`, but the reversed-order pair
improved by only `0.20%`; pooled uplift was approximately `0.71%`. This is too
small and order-sensitive to promote. Raw evidence remains at:

- `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/parallel-submit-omp-affinity-ab-20260812.jsonl`,
  SHA-256 `bf97e3c8bff45b9e15db850f0cf53fcf706b3072ebe330c62e07e22c4a736087`;
- `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/parallel-submit-omp-affinity-reversed-20260812.jsonl`,
  SHA-256 `e5094fe0c6e367e3ed2d63c4b6139df3acdebd73c135e9243f331397e22d9c09`.

Production restoration passed in
`data/muse-health-20260812-omp-affinity-restore.json`.

## Update: batch=2 attention projection reachability

Source commit `7f17d5ddd` adds default-off
`GGML_SYCL_DNNL_ATTN_BATCH2=1` pairing for Q+attention-gate and K+V. The first
run accidentally inherited the sweep harness's quantized-drafter default; it
is preserved as a misconfigured identity and must not be compared to the BF16
champion. Its raw file is
`/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/meta-parallel-attn-batch2-ab-20260812.jsonl`,
SHA-256 `eb650a61bae5d70ae086ee7df8a1b17f6c79eeb5c364982f6a4566f7e0cf118f`.

The corrected, reversed-order BF16-drafter A/B measured:

| Arm | Prose | Code | JSON | Mean t/s |
| --- | ---: | ---: | ---: | ---: |
| parallel + attention batch2 | 47.955 | 70.246 | 85.223 | 67.808 |
| parallel-submit control | 48.073 | 70.166 | 84.670 | 67.636 |

All canonical hashes passed. The apparent `+0.25%` is noise and is not a
kernel result: a separate `-lv 4` proof emitted neither the Q+gate nor K+V
first-hit marker, proving that both conservative pair plans were rejected at
runtime. The proof itself remained exact at `48.143 / 70.169 / 85.289`.
Source-side rejection diagnosis is required before another GPU A/B.

Raw evidence:

- `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/meta-parallel-attn-batch2-ab-v2-20260812.jsonl`,
  SHA-256 `2f422ed4b3486faf871f81697e8fad0d7c699c408b0bcc55c8aeaa3984004603`;
- `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/attn-batch2-hit-proof-20260812.jsonl`,
  SHA-256 `f6df9424fd2e9d4be4e4abfe48204eea450b1310e9d0905f4dbdd4d6c282ba7c`.

The pre-window and restored production gates both passed, including cache-zero
code and vision, in `data/muse-health-20260812-attn-batch2-preflight.json` and
`data/muse-health-20260812-attn-batch2-restore.json`.

The bounded rejection trace subsequently proved why neither attention pair
can execute safely in the current graph arena:

- Q+attention-gate's future output address is already the live `norm-N`
  allocation at the earlier Q projection;
- K and V intentionally reuse the exact same output address at their distinct
  graph lifetimes.

Do not weaken these guards. An allocator/lifetime rewrite would be required
before either non-adjacent batch is valid. The diagnostic run remained exact
at `48.082 / 70.241 / 85.313`; its raw result SHA-256 is
`34728c0bc9ece4d32b37c72ccda3e96db1e52be95aae05fc9938b7d4e4a0fc46`.

## Update: measured DFlash top-3 mismatch oracle

The corrected BF16-drafter trace used debug verbosity 5 and produced 8,328
candidate records over 188 verification rounds. Parser fixes distinguish the
authoritative acceptance line from the later debug summary and exclude draft
candidates logged before `p_min` or remaining-budget truncation. Five focused
tests pass.

Measured mismatch coverage is substantially below the optimistic structural
model:

| Class | Mismatch rounds | Top-2 coverage | Top-3 coverage |
| --- | ---: | ---: | ---: |
| prose | 80 | 28.8% | 43.8% |
| code | 53 | 50.9% | 79.2% |
| JSON | 44 | 34.1% | 50.0% |
| overall | 177 | 36.7% | 55.9% |

Even an oracle that evaluates every top-3-covered mismatch branch and receives
up to three matching stale suffix nodes for free raises emitted tokens by only
`21.2% / 28.6% / 18.1%` by class. Applied to the retained exact throughput,
that is a zero-added-cost mean ceiling of about `83.13 tok/s`; real tree
verification would be slower. Close sparse top-3 repair as a route to 100.

Evidence:

- trace log SHA-256
  `718a4ec334e3b3713f75ebc0fd0387b65f7316ab51442fdd4caac8ef437eaf6c`;
- sweep JSONL SHA-256
  `5ff65e61aec1469e0a48e2da09a0cd3b2f1cf21ea94fd64421ece5bb0f240ac1`;
- parsed analysis `data/muse-dflash-topk-coverage-20260812.json`, SHA-256
  `50b26ba347ecf572c8d6f811139d6d266f12804565d3dfa7827f9bd19d55302e`.

Production restoration passed the complete cache-zero code and vision gate in
`data/muse-health-20260812-topk-trace-restore.json`.

## Update: target-only lookahead feasibility negative

The fork's existing `llama-lookahead` Jacobi decoder was screened as the only
already-implemented, target-exact, no-training structure capable of amortizing
target weight passes. This was a feasibility screen on the fixed code prompt,
not a promoted suite run. Identity: BF16 target, TP4 tensor split, greedy,
`W=15`, `N=5`, `G=15`, retained exact primitive/binding/conversion caches and
parallel meta submission.

It decoded 257 tokens in 16.215 seconds, only `15.850 tok/s`, with 92 accepted
lookahead tokens. The mechanism evaluated 12,158 prompt/verification tokens
(`786.45 tok/s` batch processing), so its much wider Jacobi workload overwhelms
the accepted-token gain on this model. Close the current lookahead
implementation as a route to 100; do not spend a full three-class window on
it. Production restoration passed in
`data/muse-health-20260812-lookahead-restore.json`.

## Update: persistent OpenMP team negative

Source commit `41c93b612` adds a default-off
`GGML_META_PERSISTENT_PARALLEL_SUBMIT=1` path around the entire meta subgraph
loop. It preserves the implicit barrier after all per-device submissions,
runs the original status scan and collective on the master thread, then
barriers before the next subgraph. The experiment removes repeated OpenMP team
entry but cannot remove mandatory collective boundaries.

The reversed-order exact A/B measured:

| Arm | Prose | Code | JSON | Mean t/s |
| --- | ---: | ---: | ---: | ---: |
| persistent team | 47.996 | 70.255 | 84.201 | 67.484 |
| per-subgraph team control | 48.017 | 70.044 | 84.709 | 67.590 |

This is `-0.16%`, inside noise and not a promotion. Canonical hashes and
accepted counts matched; one prose draft-count difference (`1172` vs `1171`)
is the familiar end-budget variation. Raw JSONL SHA-256:
`10ba021f33ba8a09b976510b7cb24f35548fdfe28d811b9701314b7d122cf21b`.
Production restoration passed in
`data/muse-health-20260812-persistent-submit-restore.json`.

## Update: allreduce/postnorm fusion ceiling

The Muse target has exactly 104 F32 TP projection boundaries per verifier pass:
52 attention output projections and 52 FFN down projections. Of these, 103
continue directly through the already-fused SYCL RMSNorm+post-norm scale kernel
and a residual ADD; the final attention boundary has a gather variant.

An exact prototype would have to retain the current recursive-doubling F32
`out += tmp` ordering, reuse the existing RMS reduction tree, materialize the
scaled F32 intermediate before residual addition, and strictly guard graph
uses/aliases. It could remove only about 104 lightweight launches per pass.
The realistic ceiling is `0.5-1 ms/pass` (roughly 1-2%, around 69 tok/s); even
an intentionally generous 2 ms estimate cannot materially change the campaign.
Deprioritize this micro-fusion until a true device timeline identifies a larger
kernel island.

## Update: external profiler tooling

Intel PTI 1.0 was installed as a small tracing runtime. Intel VTune 2026.4 was
temporarily installed to obtain a nonintrusive GPU kernel timeline, but its
self-check rejected this unreleased host CPU/GPU microarchitecture for both
GPU characterization and source-analysis collection. VTune and its temporary
kernel modules were removed immediately and the recoverable APT archive was
cleaned. Production remained healthy. The campaign therefore advances an
in-process, default-off SYCL profiling-event timeline instead.

## Update: oneDNN Graph MLP audit

The installed oneDNN 3.11.2 Graph backend is not a higher-upside exact MLP
route. Its floating gated-MLP pattern forbids Muse's BF16-weight/F32-activation
and F32-output mix, and its GPU reference implementation still executes three
internal matmul primitives serially. RMSNorm has only a single-op matcher.

Muse already uses the standard Megatron FFN split: gate/up are column-parallel
and produce local 4,992-row shards, SwiGLU stays local, and only the row-parallel
down projection becomes partial and allreduces. Together with attention output,
that is the measured 104 collectives per pass. Thus a local MLP island does
exist, but Graph still cannot turn it into a true single primitive: mixed dtype
rejects the advertised pattern, its reference partition retains three matmul
submissions and all three weight reads, and the down collective is unchanged.
The smallest exact legal island is the shared F32-to-BF16 conversion plus
strided batch-2 gate/up GEMM already screened at only `+0.34%`. A larger Graph
wrapper would at most remove a small elementwise/wrapper fraction, projecting
roughly `69-70 tok/s`; opaque constant layouts could also duplicate up to
roughly `6.9 GB/card` of weights and change accumulation. Close this lane on
oneDNN 3.11.2.
