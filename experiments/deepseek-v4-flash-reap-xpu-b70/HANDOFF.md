# DeepSeek V4 Flash REAP/XPU B70 Handoff

Last reviewed: **2026-07-15**

## Current Decision

The public K160 construction gate passes, but the first performance gate fails.
The controlling plan is
[`../../plans/2026-07-13-deepseek-v4-flash-b70-investment-gated-plan.md`](../../plans/2026-07-13-deepseek-v4-flash-b70-investment-gated-plan.md).

Current stage: **artifact verified; TP4+EP correctness and persistent graph
replay pass; selective W8A16 for four high-value projection families plus an
exact clamped-SwiGLU/FP8-quant shared-down producer is the current trustworthy
34.0671 tok/s strict record**.

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
- promoted vLLM: `38260cda833367a8dbf4896679d93f9d5da74f95`
- promoted XPU kernels: `ae815123408603bb45b5df4d745be8375cf1985c`
- primary truth: fixed official-source teacher logits/tasks captured after the
  Stage 4 source download
- secondary all-expert behavior control: bullerwins IQ3_XXS revision
  `2be25f699d3efe806def93b0ae5dc632a824abb1`
- hardware/product: one active generation on four B70 32 GB GPUs
- validated record context: 1K at 95% memory utilization
- speculation: disabled until nonspeculative decode approaches 40-50 tok/s

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

1. The current trustworthy strict record is `34.067121 tok/s`, confirmed at
   `34.049735 tok/s`, at
   `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/shared-expert-fused-act-quant-20260715T0140Z`;
   LocalMaxxing `cmrlf1hn609glmj019rsjdl4r`. It enables selective W8A16 for
   fused WQA/WKV, Q-B, O-B, and shared gate/up, while the shared-down path uses
   an exact clamp-at-10 SwiGLU + E4M3FN quant producer feeding canonical W8A8.
   All cached-zero, replay, canary, executable-quality, and frozen-invariant
   gates pass.
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

## Current operational blocker

Only BDF `0000:23:00.0` is runtime-healthy. The other three B70s are stuck in
inaccessible D3cold/runtime-error state after an ASPM policy probe; policy is
back at `default`, no GPU process remains, and FLR, xe unbind/rebind, and bus
reset all failed. Reboot the host before any TP4 work, then require four-device
discovery and a minimal per-device tensor allocation before resuming. See
`notes/2026-07-15-aspm-device-recovery-blocker.md`.

## Next Permitted Work

Keep the exact selective-W8A16 shape list, MXFP4 N64, split FP8 attention,
native mHC, TP-only in-place all-reduce, and shared-expert activation/quant
fusion in the record lane. Preserve N32 as an
exact-replay failure and N128 as an unpromoted sub-1% speed/changed-output
side lane. The next work is the producer/consumer boundary around the 87
ordered reductions; the MHC post/pre + RMSNorm candidate is a preserved loss.
Require
changed-input replay, exact canaries, long-math quality checks, and the strict
cold suite for every promotion. Do not add speculation before 40-50 tok/s.
The first post-reboot experiment is the zero-code 87-call
`CCL_SYCL_FORCE_RECORDING_PATH=0/1` upper-bound gate. Only patch oneCCL to fold
its separate sequence/update kernel into the LL256 ring when that A/B exposes
at least `0.50 ms` per-token-command-stack headroom.
