# DeepSeek V4 Flash REAP/XPU B70 Handoff

Last reviewed: **2026-07-18**

## Current Decision

The public K160 construction gate passes, but the first performance gate fails.
The controlling plan is
[`../../plans/2026-07-13-deepseek-v4-flash-b70-investment-gated-plan.md`](../../plans/2026-07-13-deepseek-v4-flash-b70-investment-gated-plan.md).

Current stage: **artifact verified; TP4+EP correctness and persistent graph
replay pass; the direct routed-MoE plus wide-epoch nonspeculative base is
43.7667/43.6986 tok/s; the official three-stage DSpark7 draft now has a correct
private breakable PIECEWISE replay captured at exact query width M=7 while the
unchanged K160 target verifies at M=8. A fixed-address persistent sharded
Markov transaction with W1-only replication, exact M=8 strided-batch
compressors, selective M=8 W8A16, MXFP4 N128, and exact native M=8 router
normalization is the target-verified speed record at 80.163578 tok/s**.

Three independent strict suite medians are 75.845916 / 77.572536 / 80.163578
tok/s. All 36 realistic requests are unique and cache-zero, and four exact
canary suites pass before, between, and after the suites. LocalMaxxing approved
`cmrqp2uoa05ublg01lh6yluj8`. The source identity is vLLM `db1863c799`, XPU
kernels `6cad2518d`, and oneCCL `48fda4f0e`. Monolithic FULL draft replay is
correctness-rejected; fixed DSpark5 is performance-rejected. See
`notes/2026-07-18-m8-router-fusion-record-and-postrecord-closures.md`.

The native router fuses bias/top-k/gather/normalize/scale for the fixed M=8
target verifier. Every B70 passes 40/40 changing eager and 32/32 changing graph
cases bit-for-bit, projecting 1.205-1.222 ms/cycle saved. Matching PyTorch XPU
required its wide K=6 reduction tree `((w0+w4)+(w1+w5))+(w2+w3)` plus the
existing reciprocal/FMA correction. M=2 remains exact; M=4 remains one-ULP
different and is excluded from both the wrapper and selector. Keep
`VLLM_XPU_V4_ROUTER_NORM_MAX_M=8` in the record identity.

The new bundle bypasses activation quantization for four dense M=8 projection
families and selects the N128 Xe2 routed-MXFP4 tile. Four-card component gates
project 3.168-3.549 ms/cycle and 0.464-0.562 ms/cycle respectively. Batched
W8A16 is not bitwise row-invariant (maximum observed BF16 difference
0.0078125), so its authority is the full quality gate rather than a bitwise
micro-oracle. Keep `VLLM_XPU_V4_BLOCK_FP8_W8A16_MAX_M=8` and
`VLLM_XPU_MXFP4_SMALL_M_N=128` in the record identity; N32 remains rejected.

The post-record eager profile puts noncollective target work at 27.03-27.55
ms/cycle by rank: routed MXFP4 7.193 ms, dense GEMM 6.509 ms, sparse QK/LSE
3.538 ms, MHC 2.801 ms, PV 1.778 ms, and router radix/sort about 1.060 ms on
rank 0. Two isolated component wins do not survive the complete path. M=8
route-direct compact is exact but regresses realistic routes by 1.03-1.11 ms
per 43 layers. Split-FP8 `4/8/4` geometry passes 768/768 changing graph cases
and looks 2.54-2.59 ms faster in isolation, yet the clean endpoint falls to
72.460375 tok/s. Both are reverted/default-off. Do not reintroduce them
without a changed full-graph overlap model.

The M=8 compressor component uses one strided-batch FP32-output GEMM while
keeping each verifier row as an independent batch item. Real C4/C128 weights
pass 40/40 changed eager and 40/40 graph cases per shape on every B70. It is
5.93-7.03x faster than eight M=1 submissions in isolation and raises the
endpoint record by 5.93%. Keep
`VLLM_XPU_V4_COMPRESSOR_BATCHED_EXACT_MAX_M=8` in the record identity.

The exact-M7 cycle attribution and first two follow-up boundaries are now
closed. Named rank-local scopes put the eager Markov sampler at approximately
10.50 ms/cycle, the largest draft-side host scope. A separate reusable sampler
graph remains exact but retains 83 kernels and 14/15 collective breaks, rises
to approximately 10.82 ms, and reaches only 62.460903 tok/s. Combining the
model and sampler into one graph corrupts changed outputs and is rejected.

The guarded fused three-stage context-WKV projection is exact and reduces its
intended context-KV scope from 1.914 to 1.303 ms, but its two strict endpoint
medians are 64.269762/64.244449 tok/s. Keep it default-off. The successful
persistent Markov transaction saves 0.786613 ms/cycle at the slowest rank
without replicating W2. W1-only replication removes seven embedding
all-reduces and is now promoted; full W2 replication, fused argmax, tiny-pair
exchange, and pre-gather local add are rejected. See
`notes/2026-07-18-dspark-replicated-w1-record.md`.

The follow-up exact M=2 MXFP4 tile-policy lane is closed without promotion.
N32 regresses. N128 saves 0.247-0.283 ms per 43 routed layers across four
cards, but independent strict suites reach 62.649706/63.628477 tok/s while
same-binary N64 controls span 61.205692-63.101865. Keep N64; do not submit the
single above-record row. See
`notes/2026-07-16-mtp1-m2-mxfp4-policy-closure.md`.

Sub-gate fusion work now uses a portfolio gate. Compatible exact components
may be bundled when their conservative, non-overlapping measured lower bounds
sum to at least `0.50 ms/cycle`, followed by a frozen same-binary B-A-B service
crossover. The first portfolio combined M=2 QNorm/RoPE/direct-KV with N128
MXFP4. It passed the four-card exact gates and 10/10 post-service exact suites.
Bundle medians were 62.446116 and 62.767570 tok/s versus a 61.895036 control,
but neither beat the 63.349928 record. Preserve XPU portfolio commit `3e600bf`,
keep M=1/N64 promoted, and do not rerun this pair without a new compatible
component. See `notes/2026-07-16-mtp1-subgate-portfolio-policy.md`.

The following N64 QNorm-M2 + route-direct portfolio is promoted. The route
component still fails its standalone 0.50 ms gate at a worst-card
0.397 ms/cycle; it was admitted only with the independently proven,
non-overlapping QNorm-M2 floor. Four cards pass 336/336 changed graph cases and
the production wrapper passes 84/84. Same-binary B-A-B medians are
62.515661 / 61.717893 / 63.851301 tok/s, and 70/70 ordered exact suites pass.
LocalMaxxing approved `cmrocpuhq029hlg01g3yzglko`. The measured identity is
vLLM `4a6fd8747`, XPU kernels `18a44f440`, and oneCCL `48fda4f0e`; do not
rewrite its prototype ancestry after measurement. See
`notes/2026-07-16-qnorm-routeportfolio-record.md`.

The first attempted third component, fixed-M2 gather plus shared addition, is
closed before service. Its old `0.470 ms` headline overlapped the compact
route-direct scheduler. The isolated transplant passes 140/140 graph cases on
every B70, including output aliasing, but projects only `-0.0049` to
`+0.0038 ms/cycle` conservatively. Preserve default-off XPU `5d1a72e` and vLLM
`eb4e39b4d`; do not load the service. See
`notes/2026-07-16-mtp1-isolated-gather-shared-add-closure.md`.

The route-direct boundary remains closed as a standalone candidate. The first
upper-bound graphs were invalid because GEMM2 was ordered after gather; those
artifacts are retained but withdrawn. The corrected full chain uses real
GEMM1 -> clamped-SwiGLU -> GEMM2 dependence and passes 84/84 cases against
route-mapped fixed-M1 and gather oracles. The best 12-lane compact scheduler,
direct remap, generic activation, and generic gather saves 0.546-0.942 ms over
43 layers for patterns with local work but only 0.414 ms for all-remote EP,
below the 0.50 ms gate. Direct gather, four-lane GEMMs, and routed activations
are slower. Preserve XPU experiment commit `3aa2181`; do not integrate it by
itself. Its exact 12-lane/generic subset was later admitted only inside the
promoted QNorm-M2 portfolio described above. See
`notes/2026-07-16-mtp1-m2-route-direct-boundary-closure.md`.

The first launch-removing follow-up is closed before service too. The fused
SwiGLU/GEMM2-input kernel passes 84/84 changed-input cases bitwise, but it
recomputes the activation in every GEMM2 output-N tile and regresses all routes
with local work (worst projection `-9.133 ms` per 43 layers). Preserve signed
XPU commit `cfb0155`; do not integrate it. Deleting remap alone is not robust:
two exact upper-bound runs project `0.5002` and `0.4774 ms`. See
`notes/2026-07-16-mtp1-m2-fused-swiglu-gemm2-closure.md`.

The paired gate/up GEMM1 epilogue is now closed as implemented. It passes all
84 changed-input cases bitwise, but dual B fragments and dual FP32 accumulators
regress local routes by as much as `2.655 ms/43 layers` with 256 GRFs.
Restricting only this launcher to 128 GRFs recovers sparse cases but worsens
the six-local route to `-4.502 ms`; there is no paired-kernel spill warning.
Single-WG and SLM-premapped direct-remap variants remain below the gate at
`0.403-0.430 ms`. Preserve signed XPU commits `33e3ce4`, `5ea7608`, and
`c069ed8`; do not integrate or service-test them. The next bounded producer
attempt must split gate/up work across subgroups and exchange rounded BF16
fragments through SLM so one subgroup never owns both accumulator payloads.
See `notes/2026-07-16-mtp1-m2-remap-and-paired-gemm1-closure.md`.

The controlling 100/200 tok/s continuation roadmap is now
`../../plans/2026-07-16-deepseek-v4-flash-b70-100-200-tps-roadmap.md`. It keeps
four ordered options explicit: remaining high-value target fusion, TP4
communication/cycle restructuring, useful deeper target-verified speculation,
and a fixed-geometry SYCL/Level Zero decoder as the Intel equivalent of
HIPfire. The default-off fixed-M2 finite event chain is now closed at its graph
performance gate. The active path is the fixed-geometry decoder shell and
cached real-model parity/replay corpus, followed by exact M=4/M=8 verifier
economics and held-out deeper-speculation evaluation.

The first decoder-shell artifact now exists. Diagnostic vLLM `9fc754a` captured
the exact record's real M=2 cycle into 688 manifests and 1,030 deduplicated
blobs (150 MiB): 87 reductions and 85 MHC boundaries/rank, all linked and
cross-rank exact. The standalone four-B70 worker passes 70/70 full graph
replays without loading the model and measures 4.209382 ms at the slowest
rank. Use this as the default gate for future communication/MHC candidates.
See `notes/2026-07-17-m2-real-cycle-corpus-and-replay.md`.

The first M-width extension clears that shell's component gate. XPU kernels
`50646a2` add fixed M=4/M=8 MHC post/pre commands. With the proven M=2
collectives retained as segmented operations, M=4 improves from 6.944914 to
5.521133 ms/cycle (`1.423781 ms` saved) and M=8 from 12.350354 to 8.039061
ms/cycle (`4.311293 ms` saved). Both widths pass 16 changed eager schedules,
eager collective exactness, and 70/70 graph replays on all four cards. A single
wide `[4,4096]` BF16 collective is blocked: every rank sees 427,072 mismatches
over the 87 reductions in eager and graph paths, including positions 28/58.
Do not use its timing. Proceed to guarded integration with true sequential
verifier tensors and held-out complete-cycle acceptance; this component result
is not endpoint throughput or LocalMax evidence. See
`notes/2026-07-17-m4-m8-fixed-mhc-component-gate.md`.

The post-portfolio eager diagnostic is complete. It uses the exact promoted
source/selectors with graph replay disabled for attribution and measures
17.8497 ms/cycle of noncollective device work, down 1.6283 ms from the prior
19.4779 ms profile. Dense GEMM remains 6.5639 ms and compact routed MXFP4
remains the largest open kernel family at 3.9424 ms. See
`notes/2026-07-17-mtp1-postportfolio-eager-cycle-profile.md`.

The subgroup-split/SLM producer is closed before implementation against the
new record baseline. The old fused producer's best all-remote result was
0.520384 ms/cycle versus generic, while promoted route-direct already owns
0.397-0.414 ms of that scope. The generous incremental ceiling is only
0.123114 ms/cycle, and all-remote contains no local gate/up arithmetic. No
source, build, service, or GPU work was spent. Move to an exact fixed-M2
producer/allreduce/consumer upper bound around the 87 TP4 reductions. See
`notes/2026-07-17-mtp1-sg-split-incremental-upper-bound-closure.md`.

That fixed-M2 upper bound now passes twice. With a dependency-aware Arc LL
ring and a one-BF16 graph-visible MHC completion witness, two independent
40-epoch runs are bitwise exact on all four B70s and save
`0.953386/0.928339 ms/cycle` at the slowest rank. The experimental oneCCL
commit is `6fd2356`; it is isolated from production. An earlier apparent
3.6-3.9 ms result was timing-invalid because the sum-only Arc ring implemented
the requested `ReduceOp.MAX` as a sum; the fixed harness gathers rank times and
computes max on the host. Proceed to a default-off finite same-queue event
chain, then require dependent-producer, rank-skew, 40-epoch eager, and 70-replay
fixed-address exactness before a service load. See
`notes/2026-07-17-tp4-m2-producer-allreduce-consumer-upper-bound.md`.

The implemented finite chain uses isolated oneCCL `9636514` and XPU kernels
`a609e1f`. Two 40-epoch eager gates are bitwise exact, including rank skew, and
save 5.601/5.698 ms by bypassing Python/c10d submissions. The fixed-address
graph probe is also exact, but captured ordinary XCCL already removes that
cost: baseline is 4.265725 ms and candidate is 4.156179 ms, only **0.109546
ms/cycle** saved. Close before 70 replays, model load, portfolio admission, or
LocalMax. Future communication work must delete device/collective work. See
`notes/2026-07-17-tp4-m2-event-chain-closure.md`.

Fusing generic gather with the following shared BF16 addition is exact on all
84 cases but also misses the standalone real gate: all-remote reaches
`0.4479 ms/43 layers`; an empty-routed fast path raises it to `0.4701 ms`,
while six-local is only `0.5011 ms`. A subgroup-broadcast metadata cache is a
preserved loss. Literal remap deletion plus fused gather/add passes twice at
`0.5042/0.5239 ms`, but that leaves only `0.097-0.555 us/layer` for a real
implementation. Non-affine duplicate source rows cannot use the qualified Xe
block2D A load within that budget. Preserve XPU `820ecc5`, `576251b` /
`ba5ed8d`, and `4e2ce07`; do not service-test this standalone patch. The next
screen must create a unique `(token, expert)` route table inside the existing
M=2 router/top-k submission and consume it through both compact GEMMs and the
fused gather/add. See `notes/2026-07-16-mtp1-m2-gather-shared-add-gate.md`.

The first runnable checkpoint is `0xSero/DeepSeek-V4-Flash-180B` K160 revision
`7c360e1cd4a5168099dbc54d16d929bf6df04990`. It has 160 experts in every layer
and is a smoke/performance candidate only. K168/K176/K180 remain later
hash-preserved quality candidates; K180 is not predetermined.

## Frozen Source And Controls

- source: `deepseek-ai/DeepSeek-V4-Flash`
- source revision: `60d8d70770c6776ff598c94bb586a859a38244f1`
- public K160 revision: `7c360e1cd4a5168099dbc54d16d929bf6df04990`
- clean vLLM base: `61c87db645c256651b5a366f538898485077ad32`
- clean XPU kernels base: `dda91d171fbc3f51d1d65a7f8839714b1efffd42`
- promoted vLLM: `4a6fd874725312c53883b1d53970af1d0eccfc3f`
- promoted XPU kernels: `d15ce87d07376be53ea2d6f7ae0262ab79f7cb7b`
- primary truth: fixed official-source teacher logits/tasks captured after the
  Stage 4 source download
- secondary all-expert behavior control: bullerwins IQ3_XXS revision
  `2be25f699d3efe806def93b0ae5dc632a824abb1`
- hardware/product: one active generation on four B70 32 GB GPUs
- validated record context: 1K at 95% memory utilization
- speculation: now permitted as a separate measured lane; keep base and
  speculative results distinct and require exact target verification

## First Native Result

- verified hot model:
  `/mnt/fast-ai/llm-models/deepseek-v4-flash-xpu/current-k160`;
- passing run:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/tp4-smoke-20260714T132607Z`;
- native backend: `XPUExpertsMxFp4`, 40/160 experts per EP rank;
- memory: 24.95 GiB model and 2.11 GiB KV per rank, 5,925 KV tokens;
- correctness canary: `37 * 29 = 1073`;
- warm diagnostic decode: `2.616225 tok/s` after TTFT for 128 tokens;
- graph attempt:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/tp4-smoke-20260714T133502Z`.

## Current record and residual

1. The current trustworthy strict base is **`43.766673/43.698550 tok/s`**
   median, with `43.226357/43.186344` p10, at
   `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/nospec-direct-moe-wideepoch-candidate-20260715T2220Z`.
   Two further rollover suites reach 43.694210/43.667908. A same-build direct-
   off control is 41.991191/42.155092 tok/s, so direct M=1 routed-MoE fusion
   removes 0.84-0.97 ms/token. The repaired oneCCL ring widens its readiness
   identity from an 11-bit reused counter to a 24-bit collective epoch plus a
   7-bit communicator tag. Seventy exact captures pass 70/70, crossing the old
   deterministic failure positions 28 and 58. LocalMaxxing approved
   `cmrmnp7h81nntmj01lfenydgj`. See
   `notes/2026-07-15-direct-routed-moe-wideepoch-record.md`.
   The preceding repeatability-correct base remains at
   `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/nospec-graph-oneccl1712-bf16-allreduce128k-preload094-cache-fix-20260715T1530Z`.
   It retains selective W8A16, exact shared-expert activation/quant fusion,
   tuned split FP8 geometry, and fused Q RMSNorm/RoPE/direct UE8M0 FP8 KV
   insertion. vLLM `93fde4186` removes overlapping KV writes; exact-version
   oneCCL `6da44bc` routes only all-reduces above 128 KiB to the safe path.
   Both cold suites pass and ten exact captures pass 10/10. The older
   `40.135724` LocalMaxxing row `cmrm601ig1hsmmj017npoivfd` remains historical
   speed evidence but is not the consecutive-repeatability authority. The
   corrected `40.170350` row is retained as superseded LocalMaxxing evidence
   `cmrmebmzg1nm0mj01k30nv6vw`.
2. The preceding target-verified speed record is the combined **MTP1 QNorm-M2 +
   route-direct portfolio at `63.851301 tok/s`**. Same-binary B-A-B medians are
   62.515661 / 61.717893 / 63.851301 tok/s. Seventy exact capture suites pass,
   including former rollover positions 28 and 58; every qualifying request is
   cached-zero. All four cards pass 336/336 changed graph cases and the guarded
   production wrapper passes 84/84. See
   `notes/2026-07-16-qnorm-routeportfolio-record.md`. LocalMaxxing approved
   `cmrocpuhq029hlg01g3yzglko`. The preceding native M=2 router record remains
   superseded evidence at 63.349928 tok/s, `cmrncv39w003ylg01hogleazo`. The
   preceding native M=2 MHC
   record is 60.264242 tok/s, LocalMaxxing `cmrmvjbok1np3mj01p9il8486`.
   The preceding M=2 shared/routed fusion record was 57.412142/56.952065 tok/s.
   The preceding record is attached **MTP1 with a
   strided-batch FP32 compressor and selective M=2 W8A16 at
   `55.524496/54.708889 tok/s`**, LocalMaxxing
   `cmrmgacdq1nmimj01i4sfqytp`. Both real compressor shapes pass 40/40 changing
   eager and graph replays on every B70; the BMM is 1.84-1.91x faster than two
   M=1 calls plus concatenation. Four W8A16 shapes pass 40/40 changing
   M=1 calls. The earlier row-exact MTP1 record is 50.016860 tok/s. The first
   uncorrected 50.74/50.10 screen is invalid: after
   sustained request history it leaked prompt text after the correct `437`.
   `VLLM_XPU_V4_COMPRESSOR_M2_ROW_EXACT=1` repairs the verifier by preserving
   two M=1 FP32 compressor projections. Twenty ordered captures pass, ten
   after both strict suites; measured record acceptance is 77.68%. See
   `notes/2026-07-15-mtp1-rowexact-record.md` and
   `notes/2026-07-15-mtp1-w8a16-m2-record.md`.
   Reusing the single layer for MTP2 is closed: M=3 graph capture and 10/10
   initial exact captures pass with vLLM `4e47b18c9`, but second-position
   acceptance is only about 0.5-2.2% and a realistic request deadlocks the
   engine for at least 180 seconds. See
   `notes/2026-07-15-mtp2-reuse-deadlock-closure.md`.
3. Reusable graphs are working. Direct paged FP8 attention first raised the
   record to 21.5448 tok/s; split QK/LSE plus tiled PV raised it another 38.41%.
4. The first scale-prepack and W8A16 records were invalid because they also
   transposed `wo_a` scales consumed by the special BF16 BMM cache. Corrected
   W8A16 reaches 34.015/33.924 tok/s but is a rejected quality side lane: only
   83.3% early greedy-token parity with W8A8 and a failed long math-invariant
   gate. Preserve the exact-shape microbench as speed evidence, not promotion.
5. The earlier exact residual was about 23.3 ms non-collective, 8-9 ms TP
   communication, and 2 ms queue/host gaps. W8A16 removes roughly 4 ms of the
   dense path. Shared-expert activation/quant fusion adds another repeatable
   1.89%. Removing all 87 redundant all-reduce clones gained only 0.30%, proving
   collective wait—not the clone—is the communication boundary. The next work
   was register-resident M=1 MHC post/pre + exact-geometry RMSNorm across 85
   useful boundaries per token. That candidate is now closed: 40 changed
   states exposed small post/comb/norm bit drift and it regressed
   `20.326 -> 22.427 us`, projecting a `0.179 ms/token` loss. The promoted
   selective W8A16 mix also bypasses activation quantization for both K4096
   projection consumers, so dual FP8 output is not useful in this lane.
   Fresh phase-correct profiling then showed that the apparent 43-call BF16
   MLA hotspot was prefill, not decode. After the attention record, a corrected
   seven-token eager decode trace put dense GEMMs at 6.582 ms/token, MXFP4 MoE
   at 3.479 ms, the MHC kernel at 2.890 ms, and tuned split attention at 1.452
   ms. The enclosing `mhc_post_pre_m1_out` operator row is correlated scope,
   not extra device work; adding it caused the earlier roughly 4 ms MHC double
   count. See `notes/2026-07-15-record-lane-noncollective-gates.md`.
6. The public K160 avoids heterogeneous construction, but the final
   hash-preserved candidate still needs 256 experts in layers 0-2 and K later.
7. `quality/calibration-v1-plan.json` is materializable but its 8,000 prompts
   and true REAP observations have not been captured. `suite-v1.json` is only a
   frozen prompt contract; executable rubrics/scorers are still required.
8. K160 remains an experimental, hash-pruned smoke checkpoint; its quality and
   provenance caveats prevent a "smartest" promotion.
9. TP2+DP2+EP4 is now correctness-functional but performance-closed. The
   original stall is a oneCCL fast-SYCL communicator-switch cycle between
   disjoint TP pairs and crossed DP pairs. Safe native/generic paths return
   exact output but top out at `2.495917 tok/s`; see
   `notes/2026-07-14-tp2-dp2-dpep-recovery.md`.

## Protected State

Do not reset, clean, or repurpose:

- `/home/steve/src/vllm`;
- `/home/steve/src/vllm-xpu-kernels`;
- `/home/steve/src/llama.cpp`.

Create clean DeepSeek-specific worktrees. Preserve the old AutoRound experiment
packet as rejected evidence.

## Current operational state

The authorized host reboot recovered all four B70s. XPU discovery, per-device
allocation/compute, runtime status, and a four-rank exact XCCL reduction gate
pass; all four external links report Gen4 x16 and ASPM is back at `default`.
No DeepSeek service is currently running. The promoted DSpark7 M=8 batched-
compressor service was stopped after its final exact gate. Its restorable
current record is under `dspark7-xpu-compressor-m8-candidate-20260718T2030Z`. The
restorable nonspeculative record recipe is
`nospec-direct-moe-wideepoch-candidate-20260715T2220Z`, using vLLM
`a681dbb2b`, XPU kernels `6522849b0`, exact-version oneCCL `48fda4f0e`, and the
wide collective epoch. Its sustained 70/70 exact gate passes. The separate
row-exact MTP1 record remains historical at 55.524496 tok/s; the current
target-verified DSpark7 record is 71.506808 tok/s.
The reboot auto-started the Gemma
backend/frontdoor services; both were stopped for DeepSeek work and remain
stopped. The external `/mnt/usb-models` volume did not
automount, but the active K160 model is on `/mnt/fast-ai` and the promoted
launcher loads oneCCL from the DeepSeek virtual environment first.

## Next Permitted Work

Keep the exact selective-W8A16 shape list, MXFP4 N64, tuned split FP8 attention,
native mHC, TP-only in-place all-reduce, and shared-expert activation/quant
fusion, `VLLM_XPU_V4_M1_BIASED_TOPK=1`,
`VLLM_XPU_V4_M1_ROUTER_NORM=1`, and
`VLLM_XPU_V4_M1_DIRECT_ROUTED_MOE=1` in the record lane. The trustworthy
nonspeculative base is 43.766673 tok/s and native M=2 router-normalized MTP1 is
part of the 63.851301 tok/s target-verified QNorm/route-portfolio record.
Preserve `VLLM_XPU_V4_M2_ROUTER_NORM=1`,
`VLLM_XPU_V4_FUSED_QNORM_ROPE_KV_INSERT_MAX_M=2`, and
`VLLM_XPU_V4_M2_ROUTE_DIRECT_COMPACT=1` in future record-lane candidates;
disable only the two new portfolio selectors for exact same-binary controls.
MTP2 and larger repeated-single-layer widths are closed by negligible
second-position acceptance and a service deadlock. Carry the 43.766673 tok/s
direct-routed-MoE base and wide-epoch oneCCL repair into the proven row-exact
MTP1, batched-compressor, selective-M=2-W8A16 recipe. Keep exact target
verification and require sustained rollover-crossing replay before promotion.
The M=2 QNorm/RoPE/direct FP8 KV insertion, exact M=2 in-place all-reduce, and
MTP draft local-argmax candidates are complete. All remained exact, but their
independent confirmations reached 60.043135, 58.999027, and 59.094659 tok/s
respectively, below the preceding 60.264242 record. Keep their selectors default-off and
do not stack them merely from isolated projections. Evidence and exact source
identities are in
`notes/2026-07-16-mtp1-post-record-fusion-sweep.md`. The exception is a
predeclared compatible portfolio whose conservative,
non-overlapping lower bounds clear `0.50 ms/cycle`; require a same-binary B-A-B
crossover and normal exact/promotion gates. The first QNorm-M2 plus N128
portfolio was positive by 0.711806 tok/s over control but remained below the
record and is closed. See
`notes/2026-07-16-mtp1-subgate-portfolio-policy.md`.
Preserve `VLLM_XPU_V4_MHC_POST_PRE_M2_SINGLE_KERNEL=1` in every future
control. A new
TP4 service candidate now needs a measured complete-cycle ceiling large enough
to survive reusable-graph execution. The grouped-MXFP4 small-N scheduler race
is now understood: resetting its global counter inside workgroup 0 raced
increments from other workgroups. Moving the reset to an ordered queue fill
makes N32 and N128 exact. The new real M=2 gate closes both tile policies: N32
regresses by 0.287-0.300 ms per 43 layers; N128 saves only 0.247-0.283 ms and
does not robustly beat the record in two strict suites. Preserve experiment
commit `351a06a442`, keep N64, and do not spend another service load on small-N
tile selection. Exact dense-shape attribution also shows that the 6.580 ms
dense bucket is composed mostly of already optimized or closed projections.
The next noncollective lane must be an architectural M=2 grouped-MXFP4 change
that first projects at least 0.50 ms/cycle on all four cards. The communication
alternative remains the producer/consumer boundary around the 87
ordered reductions; the MHC post/pre + RMSNorm candidate is a preserved loss.
The first such architectural screen is now closed before service. XPU kernels
`ae1cbd472` replace the 40-expert persistent/atomic scheduler with a direct
twelve-route M=2 scheduler while preserving expert grouping. Card 0 passes
84/84 changed-input cases against generic, fixed-M1, and direct-gather oracles,
but the fail-closed minimum is only 0.262 ms/cycle for a valid all-remote EP
rank; typical and overlap cases reach 0.459-0.740 ms. Cards 1-3 were not run
after the frozen 0.50 ms gate failed, and no service integration was made. See
`notes/2026-07-16-mtp1-m2-compact-scheduler-closure.md`. The next plausible
noncollective boundary is a grouped M=2 route-direct chain that combines the
scheduler saving with removal of remap and final permuted gather. Do not
integrate it unless the combined exact hardware gate clears 0.50 ms on all
cards.
That combined screen has now been run with corrected operation ordering and is
closed below the gate: XPU `3aa2181` passes 84/84 exact cases, but the best
fail-closed minimum is 0.414 ms/43 layers. The first misordered graph artifacts
are invalid and preserved only as negative evidence. The next bounded boundary
is source-direct GEMM1: read the two verifier token rows directly and emit the
route map from the first N tile, eliminating the standalone remap launch while
keeping expert-grouped output for activation, compact GEMM2, and generic
gather. Deletion-only and real remap variants have since closed below the
gate, and the first dual-accumulator paired producer is exact but much slower.
The lower-register paired producer was not funded because its unchanged
all-remote ceiling lacks margin. Gather/shared-output addition is exact but
still below the real gate. The end-to-end unique `(token, expert)` router
screen is now closed before compact GEMM or service integration. The best exact
local-memory/subgroup-ballot emitter passes 40 changing eager and 32 graph
epochs but costs `3.132 us/layer` (`0.125 ms/cycle`); its
WG32/local-barrier-only shell costs just `0.076 us/layer`. Against the corrected
fast-path deletion ceilings of `0.538/0.527 ms`, the exact emitter leaves only
`0.413/0.402 ms/cycle`, below the frozen `0.50 ms` gate before downstream
consumption. Preserve XPU branch `codex/deepseek-v4-m2-unique-routes` through
signed restore commit `70e3824`. No measured noncollective M=2 source boundary
now clears the gate; further work requires a new architectural boundary with a
fresh exact upper-bound proof.
Require
changed-input replay, exact canaries, long-math quality checks, and the strict
cold suite for every promotion. Do not add speculation before 40-50 tok/s.
The zero-code 87-call `CCL_SYCL_FORCE_RECORDING_PATH=0/1` upper-bound gate is
closed. Forced recording added only `0.051506 ms` against the mean of two
controls, `10.3%` of the `0.50 ms` integration gate, with exact output on every
rank. Do not patch oneCCL to fold its sequence/update kernel into LL256. See
`notes/2026-07-15-oneccl-recording-sequence-upper-bound.md`. The next permitted
communication screen must overlap or shorten the ring/consumer critical path
and retain a hard projected savings gate before server integration.

That overlap feasibility gate now passes twice: submitting 85 independent MHC
kernels before 87 rings on a second stream hides `0.642` and `0.612 ms`, while
communication-first submission hides nothing. Proceed only with a test-only
persistent consumer that is resident before the ring and waits on nine
epoch-tagged per-wire readiness markers. Require marker tax `<=1 us`, exact
changed-state output, and `>=6 us` saved per boundary before full-model work.
Raising the LL threshold to 8192 saved only `0.169 ms/87`; ARC LL256 corrupted
all 64 sequential-replay epochs. See
`notes/2026-07-15-tp4-consumer-overlap-feasibility.md`.

Later cheap gates are also closed; see
`notes/2026-07-15-late-tp4-collective-and-placement-gates.md`. Eight-thread
LL256 geometry did not clear the `0.50 ms/87` gate. A correct two-round XOR
recursive-doubling protocol was slightly slower than paired ring controls.
Round-robin expert placement reached the intended physical map but corrupted
the first arithmetic replay, so the complete packed MXFP4 path is not yet
expert-map-clean and was rejected before speed testing. Cross-GPU profiler
timestamps are too distorted for arrival-skew conclusions. The resident
per-wire MHC consumer remains the only communication lane with a measured
positive upper bound. Its prerequisite passed: oneCCL `1edec457` publishes
release-ordered epochs after each final local wire writeback, remains bitwise
exact over 24 changed epochs, and costs at most `0.446 us/boundary` against the
faster paired control. The dependent resident consumer is now rejected: the
normal-priority polling workgroup prevents the ring marker from advancing, and
a low-priority queue makes no progress. See
`notes/2026-07-15-resident-mhc-consumer-forward-progress-failure.md`. The next
compact in-ring post/pre screen is also closed. Its 256-thread microgate was
bitwise exact and exceptionally fast, but 256- and 512-thread full-model runs
were nondeterministic. Matching all 87 collective positions, 42 real alias
pairs, four replays, rank skew, and dependent producers did not reproduce the
failure; stable double buffers and an explicit producer barrier did not fix it.
See `notes/2026-07-15-compact-ring-mhc-post-pre-closure.md`. Do not spend another
server load on this boundary without captured real-model intermediate tensors.
The subsequent noncollective screen is also closed. The same-hour paired
control reproduced 40.023086 tok/s. Shared/routed and attention-input streams
regressed; generic C4 fusion reintroduced indexer work that the 1K
full-selection route skips; a dedicated Triton compressor GEMV changed all 12
output hashes and reached only 39.724930 tok/s; alternate MHC geometry and
corrected MXFP4 small-N did not clear their projected gates. See
`notes/2026-07-15-record-lane-noncollective-gates.md`. Do not load another TP4
candidate until an exact real-model hardware gate projects at least 0.50
ms/token. The former compact-ring prerequisite is complete. A fail-closed
capture contains all 87 reductions, 85 post/pre boundaries, the final post,
and 42 real alias calls for one real M=1 token on every rank: 692 tensor files,
571,072,236 bytes, aggregate SHA-256
`6f8b7b9e7a1c78cc7a2005e2d92d292a80811405725dc43e190526e1be5a59eb`.
The compact candidate is bitwise exact on those values in eager mode and over
eight graph replays. Full-model pre/post observers and then a one-BF16
post-kernel fence prove that the old nondeterminism was a missing graph-visible
completion edge after the direct oneCCL hook, not bad fused arithmetic. The
minimal repaired path makes six alternating requests exact, but reaches only
34.708355 tok/s versus 40.020972 and changes all 12 strict output hashes. Close
the collective/MHC fusion lane and do not spend more server loads retuning its
fence or workgroup. See
`notes/2026-07-15-real-mhc-capture-and-graph-fence-closure.md`. The next
nonspeculative source candidate must attack a different large boundary and
clear the exact 0.50 ms/token projected gate before TP4 integration.
That final screen is now complete. A deletion-only direct GEMM2/gather upper
bound projects only 0.151-0.168 ms/token for typical three-local routing and
0.230 ms/token even for six local slots. A real 4/6/8 MiB next-weight L2
prefetch costs 71-85 us and changes the immediate consumer by only 0.884 us;
its projected effect ranges from a 0.239 ms loss to a 0.027 ms gain. Both lanes
are closed below the gate. See
`notes/2026-07-15-late-nospec-upper-bound-closures.md`. No remaining measured
nonspeculative source candidate clears 0.50 ms/token; move to MTP1 integration
or require a new architectural boundary with a fresh upper-bound proof.
The follow-up rank-arrival diagnostic is also closed before a model run. A
default-off oneCCL probe used same-device elapsed clocks and preserved exact
all-reduce output, but all marker variants timed out on every sample, including
the rank-local marker; several clock calibrations also exceeded the 2% gate.
Experiment/revert history is oneCCL `b6b6481`/`14db31d` and vLLM
`fc03ca89f`/`8721e07b4`. Do not infer skew from its timeout duration or return to
cross-device profiler timestamps. See
`notes/2026-07-15-tp4-rank-arrival-trace-closure.md`.
The following native dual Q/KV RMSNorm gate is exact but performance-closed.
XPU kernels `ef307a8` mirrors Triton's 128-thread/SG32 reduction and passes all
160 changing eager cases and 32 graph replays across four cards. Its
0.893-1.290 ms/token isolated projection does not survive the reusable graph:
two flag-on suites reach 39.9928/39.9174 tok/s versus a paired flag-off control
at 40.0950. vLLM `d8d7cf198` and the operator remain default-off. Do not spend
another server load on a standalone RMSNorm replacement; fuse the preceding
WQ_B producer with Q normalization/RoPE/KV insertion instead. See
`notes/2026-07-15-native-dual-rmsnorm-graph-loss.md`.
The next fusion succeeds: one M=1 Triton program keeps Q RMSNorm/RoPE arithmetic
and the old KV BF16 rounding point while writing the UE8M0 FP8 cache directly.
It removes a graph node and temporary KV row, passes all 160 changed eager and
32 graph epochs across four cards, and improves the isolated boundary 2.02-2.08x.
Strict suites reach 40.1357/40.1037 tok/s; LocalMaxxing
`cmrm601ig1hsmmj017npoivfd`. Keep it enabled. The next source target is the
preceding WQ_B producer epilogue. See
`notes/2026-07-15-fused-qnorm-rope-kv-insert-record.md`.
The subsequent WQ_B producer-fusion screen is closed before integration. The
benchmark-only true-M1 SYCL proof is near oneDNN at 23.559-23.700 us across all
four cards, but is not bitwise exact and cannot keep a 512-wide head in one
workgroup at that geometry. The head-contained form costs 53.330-53.644 us
before RMSNorm/RoPE/KV insertion, missing the 11.63 us/layer gate. Preserve
XPU-kernel `de979b9` and the scripts/results linked from
`notes/2026-07-15-wqb-m1-producer-fusion-closure.md`; do not integrate it. The
next bounded lane is the checkpoint's attached one-layer MTP with exact target
verification and base/speculative records kept distinct.
