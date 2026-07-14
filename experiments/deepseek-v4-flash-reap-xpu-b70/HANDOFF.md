# DeepSeek V4 Flash REAP/XPU B70 Handoff

Last reviewed: **2026-07-13**

## Current Decision

Strategic go; tactical hold on large artifacts. The controlling plan is
[`../../plans/2026-07-13-deepseek-v4-flash-b70-investment-gated-plan.md`](../../plans/2026-07-13-deepseek-v4-flash-b70-investment-gated-plan.md).

Current stage: **Stage 0-1, before any full model download**.

K160 is the first full candidate if the low-cost gates pass. K168/K176/K180 are
selected later from measured warmed memory and quality; K180 is not
predetermined.

## Frozen Source And Controls

- source: `deepseek-ai/DeepSeek-V4-Flash`
- source revision: `60d8d70770c6776ff598c94bb586a859a38244f1`
- primary truth: fixed official-source teacher logits/tasks captured after the
  Stage 4 source download
- secondary all-expert behavior control: bullerwins IQ3_XXS revision
  `2be25f699d3efe806def93b0ae5dc632a824abb1`
- hardware/product: one active generation on four B70 32 GB GPUs
- initial context: 8K
- speculation: disabled until nonspeculative decode approaches 40-50 tok/s

## Immediate Blockers

1. Native MXFP4 versus symmetric INT4 has not been measured at exact
   H4096/I2048/top-k6/M1,4,8 shapes.
2. vLLM DeepSeek V4 assumes one global expert count; correct REAP needs 256 in
   layers 0-2 and K in layers 3-42.
3. Loader success does not prove native XPU MoE dispatch; BF16 expansion is a
   failed gate.
4. Ranking/map provenance and calibration-v1 identity are not frozen.
5. The internal NVMe currently has only about 11 GiB free. Stage 4 needs a
   documented storage/reclamation decision; do not delete artifacts ad hoc.
6. DeepSeek V4 remains absent from the validated optimized XPU model matrix.

## Protected State

Do not reset, clean, or repurpose:

- `/home/steve/src/vllm`;
- `/home/steve/src/vllm-xpu-kernels`;
- `/home/steve/src/llama.cpp`.

Create clean DeepSeek-specific worktrees. Preserve the old AutoRound experiment
packet as rejected evidence.

## Next Permitted Work

Follow Stages 0-3.5 in [benchmarks/stage-gates.md](benchmarks/stage-gates.md).
Record every pass and failure in
[results/experiment-ledger.md](results/experiment-ledger.md).

No existing script in this lane authorizes a full model download. Add the
official-source downloader only after Stage 4 authorization is recorded.
