# DeepSeek V4 Flash REAP/XPU B70 Handoff

Last reviewed: **2026-07-14**

## Current Decision

The public K160 construction gate passes, but the first performance gate fails.
The controlling plan is
[`../../plans/2026-07-13-deepseek-v4-flash-b70-investment-gated-plan.md`](../../plans/2026-07-13-deepseek-v4-flash-b70-investment-gated-plan.md).

Current stage: **artifact verified; TP4+EP correctness and persistent graph
replay pass; corrected W8A8 scale prepack is the current trustworthy
30.239 tok/s strict record**.

The first runnable checkpoint is `0xSero/DeepSeek-V4-Flash-180B` K160 revision
`7c360e1cd4a5168099dbc54d16d929bf6df04990`. It has 160 experts in every layer
and is a smoke/performance candidate only. K168/K176/K180 remain later
hash-preserved quality candidates; K180 is not predetermined.

## Frozen Source And Controls

- source: `deepseek-ai/DeepSeek-V4-Flash`
- source revision: `60d8d70770c6776ff598c94bb586a859a38244f1`
- public K160 revision: `7c360e1cd4a5168099dbc54d16d929bf6df04990`
- clean vLLM: `61c87db645c256651b5a366f538898485077ad32`
- clean XPU kernels base: `dda91d171fbc3f51d1d65a7f8839714b1efffd42`
- XPU kernels: `d553fd2ac0cfc86edbb4fe9c65d567318931fe91`
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

1. The current trustworthy strict record is `30.2390162 tok/s`, p10
   `29.7545702`, at
   `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/tp4-w8a8-woa-corrected-n64-20260714T1940Z`;
   LocalMaxxing `cmrl2619q06hwmj011j5rtnbt`. Its confirmation and support run
   reached 30.239 and 30.230 tok/s; all rows emitted 128 token IDs cached-zero.
2. Reusable graphs are working. Direct paged FP8 attention first raised the
   record to 21.5448 tok/s; split QK/LSE plus tiled PV raised it another 38.41%.
3. The first scale-prepack and W8A16 records were invalid because they also
   transposed `wo_a` scales consumed by the special BF16 BMM cache. Corrected
   W8A16 reaches 34.015/33.924 tok/s but is a rejected quality side lane: only
   83.3% early greedy-token parity with W8A8 and a failed long math-invariant
   gate. Preserve the exact-shape microbench as speed evidence, not promotion.
4. The earlier exact residual was about 23.3 ms non-collective, 8-9 ms TP
   communication, and 2 ms queue/host gaps. W8A16 removes roughly 4 ms of the
   dense path. Removing all 87 redundant all-reduce clones gained only 0.30%,
   proving collective wait—not the clone—is the communication boundary. The
   next work is MXFP4 small-M dispatch and collective producer/consumer fusion.
5. The public K160 avoids heterogeneous construction, but the final
   hash-preserved candidate still needs 256 experts in layers 0-2 and K later.
6. `quality/calibration-v1-plan.json` is materializable but its 8,000 prompts
   and true REAP observations have not been captured. `suite-v1.json` is only a
   frozen prompt contract; executable rubrics/scorers are still required.
7. K160 remains an experimental, hash-pruned smoke checkpoint; its quality and
   provenance caveats prevent a "smartest" promotion.

## Protected State

Do not reset, clean, or repurpose:

- `/home/steve/src/vllm`;
- `/home/steve/src/vllm-xpu-kernels`;
- `/home/steve/src/llama.cpp`.

Create clean DeepSeek-specific worktrees. Preserve the old AutoRound experiment
packet as rejected evidence.

## Next Permitted Work

Keep `VLLM_XPU_V4_BLOCK_FP8_W8A16=0`, MXFP4 N64, split FP8 attention, native
mHC, and TP-only in-place all-reduce in the record lane. Preserve N32 as an
exact-replay failure and N128 as an unpromoted sub-1% speed/changed-output
side lane. The next work is exact-W8A8 producer/quantization fusion and the
producer/consumer boundary around the 87 ordered reductions. Require
changed-input replay, exact canaries, long-math quality checks, and the strict
cold suite for every promotion. Do not add speculation before 40-50 tok/s.
