# DeepSeek V4 Flash REAP/XPU B70 Handoff

Last reviewed: **2026-07-15**

## Current Decision

The public K160 construction gate passes, but the first performance gate fails.
The controlling plan is
[`../../plans/2026-07-13-deepseek-v4-flash-b70-investment-gated-plan.md`](../../plans/2026-07-13-deepseek-v4-flash-b70-investment-gated-plan.md).

Current stage: **artifact verified; TP4+EP correctness and persistent graph
replay pass; the direct routed-MoE plus wide-epoch nonspeculative base is
43.7667/43.6986 tok/s; row-exact attached MTP1 plus a strided-batch compressor
and selective M=2 W8A16 is the target-verified speed record at
55.5245/54.7089 tok/s**.

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
- promoted vLLM: `3a74a38a3c2e98bd6c409e57e72011933a8148c8`
- promoted XPU kernels: `ef307a8f45a0dc3794a8775e2e5d6c7484b63a1b`
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
2. The current target-verified speed record is attached **MTP1 with a
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
The DeepSeek endpoint is intentionally stopped between bounded GPU gates. The
restorable nonspeculative record recipe is
`nospec-direct-moe-wideepoch-candidate-20260715T2220Z`, using vLLM
`a681dbb2b`, XPU kernels `6522849b0`, exact-version oneCCL `48fda4f0e`, and the
wide collective epoch. Its sustained 70/70 exact gate passes. The separate
target-verified MTP1 record remains
`mtp1-rowexact-bmm-w8a16-m2-candidate-20260715T2000Z` at 55.524496 tok/s.
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
nonspeculative base is 43.766673
tok/s and row-exact MTP1 with the batched compressor is the 55.524496 tok/s
target-verified speed record.
MTP2 and larger repeated-single-layer widths are closed by negligible
second-position acceptance and a service deadlock. Carry the 43.766673 tok/s
direct-routed-MoE base and wide-epoch oneCCL repair into the proven row-exact
MTP1, batched-compressor, selective-M=2-W8A16 recipe. Keep exact target
verification and require sustained rollover-crossing replay before promotion.
The next bounded source candidate after that is extending the exact
shared-expert clamp/SwiGLU plus FP8-quant producer from M=1 to M=2; the current
source explicitly excludes the verifier width, and the prior M=1 full-model A/B
saved about 0.55 ms. Require a changed-input exact hardware gate and at least
0.50 ms/cycle projection before loading TP4. The
grouped-MXFP4 small-N
scheduler race is now understood: resetting its global counter inside
workgroup 0 raced increments from other workgroups. Moving the reset to an
ordered queue fill makes N32 and N128 exact over 40 changed graph epochs, but
fixed N32 saves only 1.05 us per complete MoE layer and fixed N128 is 0.3%
slower than N64. The fix and revert are preserved; keep N64. The next work is
the producer/consumer boundary around the 87
ordered reductions; the MHC post/pre + RMSNorm candidate is a preserved loss.
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
