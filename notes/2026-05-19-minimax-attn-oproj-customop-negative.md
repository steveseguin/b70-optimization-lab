# MiniMax M2.7 Attention o_proj Custom-Op Negative

Date: 2026-05-19

## Summary

Tested a guarded MiniMax attention `o_proj` custom-op boundary on top of the current strict high. The patch wrapped decode-sized attention `o_proj` plus its existing row-parallel hidden-state allreduce in `vllm.minimax_m2_attn_o_proj`, mirroring the successful MoE full-forward custom-op approach.

This was motivated by the current-high rank-0 sync timing diagnostic, where FP16 hidden-state allreduce/projection boundaries dominated the visible synchronized time and logits were only about `0.605 ms/token`.

## Result

- Model: `Lasimeri/MiniMax-M2.7-int4-AutoRound`
- Hardware: 4x Intel Arc Pro B70 32GB
- Runtime: vLLM `0.20.1-local`, XPU TP4
- Shape: p512/n1536, ctx2048, MBT512, block256, batch 1
- Candidate: `VLLM_MINIMAX_ATTN_OPROJ_CUSTOM_OP=1`, `VLLM_MINIMAX_ATTN_OPROJ_CUSTOM_OP_MAX_TOKENS=4`
- Mean output tok/s: `89.100464`
- Mean total tok/s: `118.800619`
- Output repeats: `88.918249`, `88.804369`, `89.208849`, `89.470389`
- Current promoted mean output tok/s: `89.314195`
- Delta: `-0.213732` output tok/s, about `-0.24%`

## Quality

The candidate passed the full strict gate:

- raw145 n64 exact hash: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- raw145 n256 exact hash: `58f6e8251c7a0a17e8c441278b5861f7d5da914fa1823ecd10484b296f2d7537`
- semantic suite hash: `adacbf144264486ea7d378ebb6a4c0ba23951b72c4cf86251a762b07ebef5805`
- 16-run arithmetic repeat hash: `578ec378bf31cb16fb49ac5c0043270fd00a0f7898e18ac498a41ffe775d7994`
- extended sixpack hash: `1e3560554f57b2b56cec8f49f28bc8ba12e9e0ced26bdc99a976f1433c99caa7`

No quality logs contained `Traceback`, `Exception`, `Bad address`, `Broken pipe`, or guard-trigger failures.

## Decision

Reject and do not submit to LocalMaxxing. The patch is quality-preserving but slower than the current promoted result. The active source and installed venv were reverted after recording.

Lesson: simply pushing attention `o_proj` behind a Python custom-op boundary does not improve the current graph schedule. The next useful path is not broad custom-op wrapping; it is either site-labeled collective timing, a lower-level XPU kernel/fusion around hidden-state allreduce plus epilogue, or attention/MoE graph scheduling work that reduces real GPU/CCL dependency latency rather than only Python boundary count.

## Artifacts

- Summary: `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-attn-oproj-customop-plus-currenthigh-20260519-strict-tp4-ctx2048-mbt512-bs256-20260519T220203Z-summary.json`
- Patch: `patches/minimax-attn-oproj-customop-negative-20260519.patch`
- Data: `data/minimax-m27-attn-oproj-customop-negative-20260519.json`
