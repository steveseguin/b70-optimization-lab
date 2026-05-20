# MiniMax M2.7 WS Decode Buffer Reuse Negative

Date: 2026-05-20

## Summary

Tested a llm-scaler MiniMax WS decode-buffer reuse patch on the current strict 4x B70 promoted path. The safe form reuses only the routed intermediate scratch buffer inside `moe_forward_tiny_cutlass_nmajor_int4_u4_minimax_ws`; top-k scratch reuse is left behind a separate diagnostic flag because the first combined reuse attempt failed the raw145 quality hash and produced corrupted output.

The intermediate-only form passed the full strict quality gate, but it did not improve throughput. It measured slightly below the current promoted baseline, so this result is recorded as a negative/neutral experiment and was not promoted to LocalMaxxing.

## Result

- Model: `Lasimeri/MiniMax-M2.7-int4-AutoRound`
- Hardware: 4x Intel Arc Pro B70 32GB
- Engine: vLLM 0.20.1-local, XPU/Level Zero, llm-scaler INT4 MoE WS path
- Candidate label: `minimax-ws-reuse-decode-buffers-20260520`
- Prompt/output: p512/n1536
- Context: 2048
- Batch: 1
- Max batched tokens: 512
- Block size: 256
- Quality status: passed
- Output tok/s repeats: `88.607776`, `89.562868`, `88.804750`, `88.626026`
- Mean output tok/s: `88.900355`
- Mean total tok/s: `118.533807`
- Promoted baseline mean output tok/s: `89.314195`
- Delta vs promoted baseline: `-0.413840 tok/s` (`-0.46%`)

## Quality Gate

Passed:

- `raw145-n64-exact`
- `raw145-n256-exact`
- `semantic-suite-n64-r2`
- `arithmetic-repeat-n64-r16`
- `extended-sixpack-n64-r2`

Matching known-good hashes:

- raw145 n64: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- raw145 n256: `58f6e8251c7a0a17e8c441278b5861f7d5da914fa1823ecd10484b296f2d7537`
- arithmetic repeat: `578ec378bf31cb16fb49ac5c0043270fd00a0f7898e18ac498a41ffe775d7994`

## Implementation Notes

Patch behavior:

- `VLLM_XPU_MINIMAX_WS_REUSE_DECODE_BUFFERS=1` now means intermediate scratch reuse only.
- `VLLM_XPU_MINIMAX_WS_REUSE_INTERMEDIATES=1` is an equivalent explicit name.
- `VLLM_XPU_MINIMAX_WS_REUSE_TOPK_BUFFERS=1` is separate and diagnostic only; do not promote it without a new quality repair.
- `ensure_int4_moe_buffers` now keys the thread-local cache on token count, top-k, shared-expert count, hidden size, intermediate size, and XPU device index. The old token-count-only cache was too weak for safe cross-shape reuse.

Important finding: allocator churn around the MiniMax WS intermediates is not a meaningful bottleneck on the current 89 tok/s path. The next speed work should stay focused on kernel time and communication boundaries, especially MoE expert kernels, Q/K RMS allreduce/apply, output projection allreduce, and graph-captured decode scheduling.

## Artifacts

- Summary JSON: `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-ws-reuse-decode-buffers-20260520-strict-tp4-ctx2048-mbt512-bs256-20260520T060956Z-summary.json`
- Quality directory: `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-ws-reuse-decode-buffers-20260520-strict-tp4-ctx2048-mbt512-bs256-20260520T060956Z-quality`
- Build log: `/home/steve/bench-results/minimax-m2.7-ws-reuse-build/build-moe-int4-u4-oneapi2025-20260520T060432Z.log`
- Patch record: `patches/minimax-ws-reuse-decode-buffers-negative-20260520.patch`
- Data record: `data/minimax-m27-ws-reuse-decode-buffers-negative-20260520.json`

## LocalMaxxing

Skipped. The run was valid and quality-clean, but it was not a material improvement over the existing promoted `89.314 tok/s` result.
