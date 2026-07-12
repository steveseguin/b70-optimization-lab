# 2026-07-12 M=1/M=4 logical-op device timeline

## Method and limits

The SYCL backend now has diagnostic-only `GGML_SYCL_OP_TIMING=1`. It places
profiling barriers around each dispatched logical graph-loop iteration and
reports the device interval as `[SYCL-OP]`. It is off by default. The mode
waits after every logical operation, so its absolute totals are perturbed and
must not be used as throughput. Individual kernel intervals and proportions
are useful for attribution; the existing cycle timer remains authoritative for
the unperturbed totals.

One B70 (GPU 3), Q8 KV, FlashAttention on, graph off, and the winning guarded
fusion stack (`MMVQ_ADD`, `MMVQ_ADD_RMS_Q8`, `SWIGLU_Q8`, `GDN_CACHE`) were
profiled at M=1 and M=4. The first JIT pass was discarded. Two stable M=1
passes summed to 50.60 ms each under per-op synchronization; the stable M=4
pass summed to 57.90 ms. Raw logs are:

- `/mnt/fast-ai/bench-results/qwen27-dflash-sycl-b70/op-timing-m1-winning-gpu3-20260712.log`;
- `/mnt/fast-ai/bench-results/qwen27-dflash-sycl-b70/op-timing-m4-winning-gpu3-20260712.log`.

## Measured attribution

| logical category | M=1 diagnostic ms | M=4 diagnostic ms | M=4 - M=1 |
| --- | ---: | ---: | ---: |
| MUL_MAT dispatches | 31.26 | 34.51 | +3.26 |
| SwiGLU-fused down MMVQ (reported at GLU initiator) | 5.76 | 7.93 | +2.17 |
| RMSNorm | 2.29 | 2.45 | +0.16 |
| MUL / UNARY / ADD / RoPE / CONT | 6.16 | 5.27 | -0.89 |
| GET_ROWS / CONCAT / GDN / L2Norm / SSM_CONV | 4.35 | 5.02 | +0.66 |
| FlashAttention | 0.88 | 0.66 | -0.22 |
| total | 50.60 | 57.90 | +7.30 |

Projection shapes make the weight path concrete. At M=1, ordinary MUL_MAT
time was 12.59 ms for the 128 gate/up projections, 5.30 ms for 72 5120-wide
outputs, 3.11 ms for 48 10240-wide recurrent projections, 2.90 ms for 96
small 48-wide projections, 2.48 ms for 48 6144-wide projections, 1.75 ms for
the LM head, and the remainder was attention projections. The 64 fused down
projections added 5.76 ms under the GLU label.

Normalizing the diagnostic proportions to the existing unperturbed 37.0 ms
M=1 cycle yields about 27.1 ms in projection/SwiGLU-down paths and 9.9 ms in
all other device work. Thus the earlier 24.3 ms favorable weight-read floor
was not a whole-model projection measurement: real projection shapes are
about 2.8 ms above it, and measured non-projection work accounts for the
remaining roughly 9.9 ms. The supposed 13 ms framework-only bucket does not
exist on the device critical path.

For M=4, projection plus fused-down time rises by 5.43 ms in the diagnostic,
accounting for 74% of the complete 7.30 ms M=4 penalty. This agrees with the
unperturbed target-verifier increase from about 37 ms to 42.5-45.8 ms. The
GDN/state family contributes only about 0.66 ms of the diagnostic increase;
attention does not explain the verifier penalty.

## Concrete next target-pass opportunity

The next >=5 ms target is the existing reordered Q4_0 x Q8_1 multi-column
MMVQ, not another small epilogue. Its `mul_mat_vec_q_reorder_ncols<4>` inner
loop keeps four scalar partial sums and performs a scalar `for (j)` over the
four candidate activations after each shared Q4 load. The measurement shows
that this M=4 path adds 5.43 ms across projections even though weights are
already shared.

Build a Xe2 SIMD4 DP4A verifier specialization with an offline interleaved
four-column Q8 activation pack and vector-lane accumulators, so one Q4 decode
feeds all four candidate dot products without the scalar candidate loop and
its added instruction/register cost (compiler spill behavior still needs an
assembly or occupancy check). This is distinct from the closed DPAS/XMX v1/v2
layouts: it preserves the proven reordered Q4/DP4A weight path and changes
only multi-column activation/accumulation. Gate it first on the real 17408,
10240, 6144, and 5120 projection shapes. The integration gate is an aggregate
M=4 projection delta of at least 5 ms with exact production comparison.

The measured data rejects further generic graph work and isolated scalar
fusion as explanations for the M=4 penalty. Full recurrent layerlet fusion
can still attack the roughly 10 ms M=1 non-projection remainder, but the
already-tested raw-gate and epilogue fusions show that launch removal alone is
not enough; it needs a kernel architecture that avoids materialization without
lengthening the GDN critical kernel.
