# DeepSeek V4 Flash REAP/XPU B70 Handoff

Last reviewed: **2026-07-14**

## Current Decision

The public K160 construction gate passes, but the first performance gate fails.
The controlling plan is
[`../../plans/2026-07-13-deepseek-v4-flash-b70-investment-gated-plan.md`](../../plans/2026-07-13-deepseek-v4-flash-b70-investment-gated-plan.md).

Current stage: **artifact verified; TP4+EP construction and correctness pass;
graph-off performance fails; XPU graph capture blocked**.

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
- validated smoke context: 2K at 95% memory utilization
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

## Immediate Blockers

1. Breakable XPU graph capture fails because `xpu_sparse_decode_fp8.py` calls
   `combined_lens.max().item()` inside capture, forcing a prohibited host wait
   on a command-graph event.
2. The native graph-off TP4+EP floor is only 2.616 tok/s after TTFT, about 19x
   below the 50 tok/s investment gate. Do not add speculation at this speed.
3. Native MXFP4 versus symmetric INT4 still lacks complete selector,
   performance, replay, and fallback evidence at real model shapes.
4. The public K160 avoids heterogeneous construction, but the final
   hash-preserved candidate still needs 256 experts in layers 0-2 and K later.
5. `quality/calibration-v1-plan.json` is materializable but its 8,000 prompts
   and true REAP observations have not been captured. `suite-v1.json` is only a
   frozen prompt contract; executable rubrics/scorers are still required.
6. K160 remains an experimental, hash-pruned smoke checkpoint; its quality and
   provenance caveats prevent a "smartest" promotion.

## Protected State

Do not reset, clean, or repurpose:

- `/home/steve/src/vllm`;
- `/home/steve/src/vllm-xpu-kernels`;
- `/home/steve/src/llama.cpp`.

Create clean DeepSeek-specific worktrees. Preserve the old AutoRound experiment
packet as rejected evidence.

## Next Permitted Work

Patch the sparse FP8 decode path so it does not materialize a device scalar on
the host during capture. Re-run the 1K/95% graph attempt and require correct
`XPUExpertsMxFp4` decode plus a large speed step before expanding the lane.
Profile the graph-off 2.616 tok/s result only enough to separate sparse MLA,
MXFP4 MoE, and all-to-all costs. Do not start speculation, resume the large
official-source download, or build quality packs until base decode is on a
credible path toward 50 tok/s. Preserve all failure logs and the structured
summary in
[`../../data/deepseek-v4-k160-tp4-bringup-20260714.json`](../../data/deepseek-v4-k160-tp4-bringup-20260714.json).
