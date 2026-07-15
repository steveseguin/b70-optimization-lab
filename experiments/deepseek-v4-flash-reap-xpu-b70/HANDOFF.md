# DeepSeek V4 Flash REAP/XPU B70 Handoff

Last reviewed: **2026-07-15**

## Current Decision

The public K160 construction gate passes, but the first performance gate fails.
The controlling plan is
[`../../plans/2026-07-13-deepseek-v4-flash-b70-investment-gated-plan.md`](../../plans/2026-07-13-deepseek-v4-flash-b70-investment-gated-plan.md).

Current stage: **artifact verified; TP4+EP correctness and persistent graph
replay pass; tuned four-head/16-warp split-FP8 QK geometry is the current
trustworthy 40.0210 tok/s strict record and clears the 40 tok/s base gate**.

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
- promoted vLLM: `fa3e27b461ce7846ba71aefb161c40a017319fd2`
- promoted XPU kernels: `83ef7b667a4ccb1ced0f3a48c31cb3341e269dc6`
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

1. The current trustworthy strict record is **`40.020972 tok/s`** median with
   `39.608039` p10, at
   `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/split-fp8-geometry-b4-qk16-recordidentity-20260715T0144Z`;
   LocalMaxxing `cmrlnp01l12q4mj01p58ynsyd`. It retains selective W8A16 and
   exact shared-expert activation/quant fusion, then changes split FP8 QK from
   16-head/8-warp to 4-head/16-warp programs. All cached-zero, replay, canary,
   and focused bitwise gates pass. The preceding 34.067121 tok/s record remains
   the matching control.
2. Reusable graphs are working. Direct paged FP8 attention first raised the
   record to 21.5448 tok/s; split QK/LSE plus tiled PV raised it another 38.41%.
3. The first scale-prepack and W8A16 records were invalid because they also
   transposed `wo_a` scales consumed by the special BF16 BMM cache. Corrected
   W8A16 reaches 34.015/33.924 tok/s but is a rejected quality side lane: only
   83.3% early greedy-token parity with W8A8 and a failed long math-invariant
   gate. Preserve the exact-shape microbench as speed evidence, not promotion.
4. The earlier exact residual was about 23.3 ms non-collective, 8-9 ms TP
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
   MLA hotspot was prefill, not decode. A seven-token eager decode trace put
   dense GEMMs near 6.55 ms/token, mHC near 4.05 ms, MXFP4 MoE near 3.35 ms,
   and split QK near 2.74 ms. Tuning the last bucket produced the current
   record; see `notes/2026-07-15-split-fp8-geometry-record.md`.
5. The public K160 avoids heterogeneous construction, but the final
   hash-preserved candidate still needs 256 experts in layers 0-2 and K later.
6. `quality/calibration-v1-plan.json` is materializable but its 8,000 prompts
   and true REAP observations have not been captured. `suite-v1.json` is only a
   frozen prompt contract; executable rubrics/scorers are still required.
7. K160 remains an experimental, hash-pruned smoke checkpoint; its quality and
   provenance caveats prevent a "smartest" promotion.
8. TP2+DP2+EP4 is now correctness-functional but performance-closed. The
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
The current record-identity DeepSeek server is listening only on
`127.0.0.1:18080` for follow-up experiments. The reboot auto-started the Gemma
backend/frontdoor services; both were stopped for DeepSeek work and remain
stopped. The external `/mnt/usb-models` volume did not
automount, but the active K160 model is on `/mnt/fast-ai` and the promoted
launcher loads oneCCL from the DeepSeek virtual environment first.

## Next Permitted Work

Keep the exact selective-W8A16 shape list, MXFP4 N64, tuned split FP8 attention,
native mHC, TP-only in-place all-reduce, and shared-expert activation/quant
fusion in the record lane. The base has crossed 40 tok/s, so a separate
speculative screen is now permitted, but must be compared against the 40.021
tok/s identity and retain exact target verification. Preserve N32 as an
exact-replay failure and N128 as an unpromoted sub-1% speed/changed-output
side lane. The next work is the producer/consumer boundary around the 87
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
Return to a fresh record-lane non-collective timeline and choose a fusion that
leaves the proven oneCCL collective intact.
