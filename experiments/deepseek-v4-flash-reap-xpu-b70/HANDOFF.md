# DeepSeek V4 Flash REAP/XPU B70 Handoff

Last reviewed: **2026-07-14**

## Current Decision

The public K160 construction gate passes, but the first performance gate fails.
The controlling plan is
[`../../plans/2026-07-13-deepseek-v4-flash-b70-investment-gated-plan.md`](../../plans/2026-07-13-deepseek-v4-flash-b70-investment-gated-plan.md).

Current stage: **artifact verified; TP4+EP correctness and persistent graph
replay pass; split/tiled FP8 sparse attention plus TP-only in-place all-reduce
plus small-M block-FP8 W8A16 is the current 33.887 tok/s strict record**.

The first runnable checkpoint is `0xSero/DeepSeek-V4-Flash-180B` K160 revision
`7c360e1cd4a5168099dbc54d16d929bf6df04990`. It has 160 experts in every layer
and is a smoke/performance candidate only. K168/K176/K180 remain later
hash-preserved quality candidates; K180 is not predetermined.

## Frozen Source And Controls

- source: `deepseek-ai/DeepSeek-V4-Flash`
- source revision: `60d8d70770c6776ff598c94bb586a859a38244f1`
- public K160 revision: `7c360e1cd4a5168099dbc54d16d929bf6df04990`
- clean vLLM: `9fe91a6d6c36806b0428b6c3487bd10b05eee20c`
- clean XPU kernels base: `dda91d171fbc3f51d1d65a7f8839714b1efffd42`
- XPU kernels: `473a55e2a8b34da3c97c143401955d0c5746120b`
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

1. The current strict record is `33.8866379 tok/s`, p10 `33.3446529`, at
   `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/tp4-block-fp8-w8a16-20260714T1930Z`;
   LocalMaxxing `cmrl12pke06ehmj01i9a1f0gu`. All 12 prompts emitted 128 token
   IDs and reported cached-zero.
2. Reusable graphs are working. Direct paged FP8 attention first raised the
   record to 21.5448 tok/s; split QK/LSE plus tiled PV raised it another 38.41%.
3. Load-time FP8 scale prepack first raised the record to `30.2953052 tok/s`.
   Routing only M<=2 block-FP8 dense calls through BF16-activation W8A16 then
   removed 215 activation quantizers per token and reached the current record;
   prefill/larger M retain W8A8. The exact five-shape microbench and source are
   preserved in `scripts/bench-fp8-dense-shapes.py` and the current note.
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

Keep `VLLM_XPU_V4_BLOCK_FP8_W8A16=1`, split FP8 attention, native mHC, and the
TP-only in-place all-reduce in the record lane. Audit the exact MXFP4 M=1
dispatch for an existing smaller tile/policy and inspect producer/consumer
boundaries around the 87 ordered reductions. The standalone MHC/RMS fusion and
oneCCL twoshots paths are measured losses and remain default-off. Require
changed-input replay, exact canaries, and the strict cold suite for every
promotion. Do not add speculation before the 40-50 tok/s nonspeculative gate.
