# Qwen3.6 Live ABI Sidecar Plan

This is a design artifact derived from disabled-by-default live ABI smoke logs.
It is not a speed claim and it does not replay stale pointer values.

## Coverage

- Records: `48`
- Ranks: `{'0': 12, '1': 12, '2': 12, '3': 12}`
- Layers: `2` unique layer names
- Required tensors present: `True`
- Shape/dtype/contiguity checks passed: `True`

## Derived Sidecar ABI

The live logs already expose the tensors needed for a zero-copy sidecar:
- `hidden_states`
- `topk_weights`
- `topk_ids`
- `w13`
- `w13_scales`
- `w2`
- `w2_scales`
- `output`
- `remapped_hidden_states`
- `rows_per_expert`
- `unpermuted_row_to_permuted_row`
- `gemm1_a`
- `gemm1_a_scales`
- `gemm1_output`
- `act_output`
- `gemm2_a`
- `gemm2_a_scales`
- `gemm2_output`

Representative descriptor:

- GEMM1: `M=65536, K=2048, N=256`
- GEMM2: `M=65536, K=128, N=2048`
- Experts: `256`, top-k: `8`
- Active experts in sample: `11`
- Route offsets cover all rows: `True`

## Missing C++ Work

- Build a C++ sidecar entry point that accepts Tensor-derived device pointers and derived grouped offsets without serializing to files.
- Wrap live XPU/USM pointers in oneDNN memory objects on the same rank-local SYCL device and prove no implicit host copy.
- Cache packed w13/w2 weights and oneDNN grouped-matmul primitives by layer/shape; update rows_per_expert and offsets per call.
- Run GEMM1 plus activation/quant plus GEMM2 and final gather with max_abs_diff=0.0 versus xpu_fused_moe before timing claims.
- Add a kill switch and per-rank fallback to current xpu_fused_moe on any sidecar validation failure or unsupported shape.

## Bigger Bets Added

- A route-class layerlet generator backed by oneDNN parity fixtures, targeting only hot route classes where launch and epilogue fusion can beat oneDNN.
- A fixed-shape c1 decode lane that bypasses general vLLM scheduling for latency-critical single-user traffic after the prompt is admitted.
- Expert-parallel or hot-expert replication simulations that spend the large remaining VRAM budget to reduce c1 cross-card latency.
- A verifier-owned speculative transaction API with temporary KV/request state, so DFlash/MTP/n-gram proposers can be tested without changing accepted model outputs.
- A Level Zero command-list supernode for one token that captures MoE, dense, attention, and TP collective boundaries without lowering precision.

## Next Guarded Call

Start with a disabled-by-default sidecar path for one layer/rank that wraps live XPU tensors in oneDNN memory, executes GEMM1 and GEMM2 with cached primitives, falls back on any unsupported condition, and records final-layer `max_abs_diff=0.0` before endpoint timing is considered.
