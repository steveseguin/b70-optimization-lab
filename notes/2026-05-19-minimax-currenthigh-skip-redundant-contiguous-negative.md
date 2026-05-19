# MiniMax Current-High Skip-Redundant-Contiguous Retest

Date: 2026-05-19

## Summary

`VLLM_XPU_LLM_SCALER_MOE_MINIMAX_SKIP_REDUNDANT_CONTIGUOUS=1` was retested on top of the current strict high. An earlier skip-contiguous screen was quality-safe but did not include the MiniMax full-forward MoE custom-op boundary, so this run checked the exact current stack.

Candidate recipe:

- Model: `Lasimeri/MiniMax-M2.7-int4-AutoRound`
- Hardware: 4x Intel Arc Pro B70 32GB
- Engine: vLLM `0.20.1-local`, XPU TP4
- Baseline recipe: FP16 activations, AutoRound INT4 W4A16, default XPU FlashAttention v2, PIECEWISE XPU graph, exact MiniMax router logits feeding llm-scaler INT4 MoE work-sharing, clone-safe compiled allreduce custom-op, direct in-place Q/K variance scale, MoE output allreduce inside the MoE custom-op, and MiniMax decode-sized router-linear plus fused MoE inside a guarded full-forward custom-op boundary
- Added env: `VLLM_XPU_LLM_SCALER_MOE_MINIMAX_SKIP_REDUNDANT_CONTIGUOUS=1`
- Shape: p512/n1536, ctx2048, batch 1, MBT512, block256

Result:

- Candidate: `89.141961` output tok/s, `118.855948` total tok/s, mean of four strict benchmark repeats
- Promoted baseline: `89.314195` output tok/s, `119.085594` total tok/s, mean of four strict benchmark repeats
- Delta: `-0.193%` output tok/s and `-0.193%` total tok/s
- Repeats: `89.337982`, `89.131295`, `88.812234`, `89.286333` output tok/s

Decision: reject and do not submit to LocalMaxxing.

## Quality Gate

The candidate passed:

- raw145 n64 exact: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- raw145 n256 exact: `58f6e8251c7a0a17e8c441278b5861f7d5da914fa1823ecd10484b296f2d7537`
- semantic suite: `adacbf144264486ea7d378ebb6a4c0ba23951b72c4cf86251a762b07ebef5805`
- 16-repeat arithmetic gate: `578ec378bf31cb16fb49ac5c0043270fd00a0f7898e18ac498a41ffe775d7994`
- extended sixpack: `1e3560554f57b2b56cec8f49f28bc8ba12e9e0ced26bdc99a976f1433c99caa7`

## Reliability Signal

The extended-sixpack shutdown log and the first benchmark repeat log printed `Bad address (src/pipe.cpp:367)`. The strict wrapper still completed all gates and all four benchmark repeats. Treat this as a minor reliability note, not a promotion blocker by itself, because the candidate was already slower than the promoted baseline.

## Artifacts

- Summary: `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-currenthigh-skip-redundant-contiguous-rerun-20260519-strict-tp4-ctx2048-mbt512-bs256-20260519T211842Z-summary.json`
- Quality dir: `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-currenthigh-skip-redundant-contiguous-rerun-20260519-strict-tp4-ctx2048-mbt512-bs256-20260519T211842Z-quality`
- Bench JSONs:
  - `/home/steve/bench-results/minimax-m2.7-strict-candidates/vllm-minimax-m27-autoround-tp4-p512n1536-20260519T213356Z.json`
  - `/home/steve/bench-results/minimax-m2.7-strict-candidates/vllm-minimax-m27-autoround-tp4-p512n1536-20260519T213644Z.json`
  - `/home/steve/bench-results/minimax-m2.7-strict-candidates/vllm-minimax-m27-autoround-tp4-p512n1536-20260519T213932Z.json`
  - `/home/steve/bench-results/minimax-m2.7-strict-candidates/vllm-minimax-m27-autoround-tp4-p512n1536-20260519T214219Z.json`

## Learning

Skipping unconditional `.contiguous()` calls inside the MiniMax llm-scaler MoE work-sharing path remains quality-safe, but it is not a decode-speed win on the current full-forward custom-op stack. The current bottleneck is still around graph/compiler/custom-op and collective boundaries rather than these local tensor-contiguity checks.
