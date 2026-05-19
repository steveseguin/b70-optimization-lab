# MiniMax M2.7 Post-89 tok/s Plan

Date: 2026-05-19

## Current Promoted Baseline

- Model: `Lasimeri/MiniMax-M2.7-int4-AutoRound`
- Hardware: 4x Intel Arc Pro B70, TP4, vLLM/XPU
- Current promoted result: `89.314195` output tok/s and `119.085594` total tok/s at p512/n1536, ctx2048, batch 1.
- Quality baseline: exact raw145 n64/n256 token hashes, semantic suite, 16-repeat arithmetic, and extended sixpack all match promoted references.
- LocalMaxxing result: `cmpct6t4m007fnw01yjdtlcs4`

## Promotion Policy

Only promote or submit a new result when all of these are true:

- Exact-token and semantic quality gates pass.
- The run is repeatable across at least four benchmark repeats.
- The mean output tok/s is above `89.314195` by more than normal run noise.
- No sampling, routing, quantization, or precision shortcut changes quality semantics.

Negative, quality-failed, or merely noisy results stay local/GitHub-only.

## Immediate Candidates

1. Current-high stack plus `CCL_TOPO_FABRIC_VERTEX_CONNECTION_CHECK=0`.
   - Rationale: communication-only knob, no model math change.
   - Risk: previous CCL topology override screens were negative on older stacks.
   - Status: strict quality-gated run in progress.

2. Current-high stack plus `VLLM_XPU_LLM_SCALER_MOE_MINIMAX_SKIP_REDUNDANT_CONTIGUOUS=1`.
   - Rationale: avoid redundant Python/framework tensor copies when the MoE input and router logits are already contiguous.
   - Risk: an older related screen was slightly negative, but it was not the exact current full-forward stack.
   - Promotion requires full strict quality and a repeatable speed win.

3. If both runtime-only candidates fail, return to source-level fusion.
   - Preferred direction: narrower fusion around the MoE/custom-op boundary or logits/MoE call boundary.
   - Avoid repeating known negatives: Q/K apply+RoPE helper, broad post-attention norm+MoE custom op, CCL `direct`, FP16/candidate router shortcuts, and larger full-forward token guards.

## Source-Level Work Queue

- Audit remaining decode-time CPU/framework boundaries in `minimax_m2.py`, `moe_wna16.py`, and `xpu_communicator.py`.
- Prefer math-preserving changes that remove import/call/copy overhead or custom-op graph breaks.
- Preserve exact operation ordering around residual add, RMSNorm, router logits, expert selection, and final allreduce unless a canary explicitly proves equivalence.
- For any new patch, save a patch note and strict run summary before considering LocalMaxxing.
