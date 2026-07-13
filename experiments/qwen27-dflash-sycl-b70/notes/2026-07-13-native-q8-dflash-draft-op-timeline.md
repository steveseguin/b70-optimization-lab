# Native Q8 DFlash5 draft operation timeline

Date: 2026-07-13 UTC

## Scope and identity

This is a diagnostic TP1 profile of the native Q8_0 DFlash draft model on one
Arc Pro B70. The target remained the RAM-cached Qwen3.6-27B Q4_0 model. The
draft used F16 K/V, flash attention, `n_max=5`, graphs off, and the production
SYCL projection path. `GGML_SYCL_OP_TIMING=1` serialized every logical op, so
these rows are attribution evidence rather than throughput results.

Retained log:

`/mnt/fast-ai/bench-results/qwen36-27b-mtp-gguf-q4-b70/servers/q8-dflash-draft-audit/llamacpp-gpu2-port19442-20260713T123124Z.log`

The profiling server used GPU2 and port 19442 and was stopped after the run.

## Real model and projection shapes

The DFlash model has five layers, hidden size 5120, FFN size 17408, 32 query
heads, 8 KV heads, head width 128, four sliding-window layers, and one full
attention layer. At DFlash5 the decoder runs once at M=6: the committed token
plus five mask tokens.

Every five-layer draft projection is Q8_0:

- Q: K=5120, N=4096, M=6, five tensors;
- K and V: K=5120, N=1024, M=6, ten tensors total;
- attention output: K=4096, N=5120, M=6, five tensors;
- FFN gate and up: K=5120, N=17408, M=6, ten tensors total;
- FFN down: K=17408, N=5120, M=6, five tensors.

The final shared target LM head is Q6_K, K=5120, N=248320, M=6. The DFlash
encoder is a separate Q8_0 K=25600, N=5120 projection. It is part of the
feature/injection phase, not the 10-11 ms draft-block decoder.

At M=6, reordered Q8_0 projections dispatch activation quantization through
`quantize_and_reorder_q8_1_soa`, then
`reorder_mul_mat_vec_q8_0_q8_1_sycl_ncols<6>`. The Q6_K LM head uses the
corresponding reordered `reorder_mul_mat_vec_q6_k_q8_1_sycl_ncols<6>` path.

## Measured steady-state M=6 contribution

Nine full-width repeat cycles had a median device queue time of approximately
10.11 ms. Logical kernel time summed to approximately 8.49 ms; about 1.55 ms
remained between timed kernels as submission/barrier/queue gaps.

| Component | Median or representative time | Share of logical kernel time |
|---|---:|---:|
| Q6_K LM head | 3.18 ms | 37% |
| 15 FFN projections | 3.52 ms | 41% |
| 20 attention projections | 0.93 ms | 11% |
| five flash-attention ops | 0.18 ms | 2% |
| norms, RoPE, GLU, residuals, cache writes | 0.65 ms | 8% |
| inter-kernel queue/submission gap | 1.55 ms | outside logical-op sum |

The projection weights read per draft block are approximately 1.043 GB for
the LM head, 1.420 GB for FFN, and 0.279 GB for attention. Their effective
rates are roughly 328, 404, and 300 GB/s respectively. Projection reads alone
therefore account for about 7.63 ms versus a 4.51 ms 608-GB/s physical
roofline.

## Concrete next implementation

The highest-value single boundary is a DFlash-only fused Q6_K M=6 LM-head and
argmax kernel. It owns about 3.18 ms of the 10.11 ms draft decode, and CPU
sampling adds another approximately 1.0 ms after decode. With `p_min=0`, the
native DFlash loop only consumes the top token for noise rows 1 through 5;
probabilities and the row-0 logits are unused.

Implement a BMG-specialized path that reuses the reordered Q6_K/Q8_1 dot
semantics but reduces `(logit, token_id)` per row on device. One workgroup
should own a vocabulary tile, produce five partial maxima, and a small second
kernel should reduce the tile maxima to five token IDs. Copy only those IDs to
the host and bypass `common_sampler_sample` for the guarded DFlash greedy,
`p_min=0` case. This removes the 248320x6 F32 logits boundary and the roughly
1 ms host top-k loop without changing the target verifier.

Correctness gates are exact token IDs against the existing Q6_K path across
the fixed corpus and unchanged accepted prefixes. Performance gates are less
than 2.5 ms for the LM-head/reduction boundary and at least 0.8 ms lower
end-to-end draft-plus-sample time. The existing joint gate/up prototype is the
complementary FFN optimization; the LM-head/argmax boundary is the next
independent target because it is the largest individual operation.
