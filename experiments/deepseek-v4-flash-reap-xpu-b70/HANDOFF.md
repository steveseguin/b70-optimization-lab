# DeepSeek V4 Flash REAP/XPU B70 Handoff

Last reviewed: **2026-07-13**

## Current Decision

Strategic go; public K160 download and clean runtime bring-up are active. The controlling plan is
[`../../plans/2026-07-13-deepseek-v4-flash-b70-investment-gated-plan.md`](../../plans/2026-07-13-deepseek-v4-flash-b70-investment-gated-plan.md).

Current stage: **Stage 0 passed; Stage-1 scaffold passed; K160 download active**.

The first runnable checkpoint is `0xSero/DeepSeek-V4-Flash-180B` K160 revision
`7c360e1cd4a5168099dbc54d16d929bf6df04990`. It has 160 experts in every layer
and is a smoke/performance candidate only. K168/K176/K180 remain later
hash-preserved quality candidates; K180 is not predetermined.

## Frozen Source And Controls

- source: `deepseek-ai/DeepSeek-V4-Flash`
- source revision: `60d8d70770c6776ff598c94bb586a859a38244f1`
- public K160 revision: `7c360e1cd4a5168099dbc54d16d929bf6df04990`
- clean vLLM: `382bbd51448b2f58c73b3e51d051bc352166ba91`
- clean XPU kernels base: `dda91d171fbc3f51d1d65a7f8839714b1efffd42`
- exact-shape test commits: `552c9ce`, selector fix `840482d`
- primary truth: fixed official-source teacher logits/tasks captured after the
  Stage 4 source download
- secondary all-expert behavior control: bullerwins IQ3_XXS revision
  `2be25f699d3efe806def93b0ae5dc632a824abb1`
- hardware/product: one active generation on four B70 32 GB GPUs
- initial context: 8K
- speculation: disabled until nonspeculative decode approaches 40-50 tok/s

## Immediate Blockers

1. Native MXFP4 versus symmetric INT4 has not passed the complete exact-shape
   correctness, selector, performance, replay, and fallback gate at
   H4096/I2048/top-k6/M1,4,8.
2. The public K160 avoids heterogeneous construction, but the final
   hash-preserved candidate still needs 256 experts in layers 0-2 and K later.
3. Loader success does not prove native XPU MoE dispatch; BF16 expansion is a
   failed gate.
4. `quality/calibration-v1-plan.json` is materializable but its 8,000 prompts
   and true REAP observations have not been captured. `suite-v1.json` is only a
   frozen prompt contract; executable rubrics/scorers are still required.
5. The reviewed archive move completed and internal free space is about 165
   GiB after runtime/build caches. Moved paths remain available through
   compatibility symlinks.
6. DeepSeek V4 remains absent from the validated optimized XPU model matrix.

## Protected State

Do not reset, clean, or repurpose:

- `/home/steve/src/vllm`;
- `/home/steve/src/vllm-xpu-kernels`;
- `/home/steve/src/llama.cpp`.

Create clean DeepSeek-specific worktrees. Preserve the old AutoRound experiment
packet as rejected evidence.

## Next Permitted Work

Finish and cryptographically verify the K160 snapshot, promote its manifest-
verified copy to NVMe, then attempt the unchanged TP4+EP/8K graph-off
nonspeculative load. In parallel, extend the passing low-level scaffold into
the explicit metric, selector/fallback, performance, replay, and TP4+EP gates.
Record every pass and failure in
[results/experiment-ledger.md](results/experiment-ledger.md). Resume the
official-source download only after the runnable checkpoint has produced the
first Intel construction/memory evidence.
