# DeepSeek V4 M=1 biased top-k gate (2026-07-15)

## Why this boundary

The phase-correct seven-token eager profile showed 40 non-hash MoE router
calls per token. Generic XPU routing launched separate bias, radix select,
radix sort, gather, normalization, scale, and copy kernels. Radix select and
sort alone consumed about 0.99 ms/token, leaving a measured boundary large
enough to clear the project's 0.50 ms/token source-integration gate.

The candidate intentionally consumes the existing FP32
`sqrt(softplus(gate_logits))` scores. It changes neither the gate GEMM nor the
score arithmetic. It produces sorted expert IDs and the corresponding
unbiased raw scores; existing PyTorch normalization and routed scaling remain
unchanged.

## Iterations preserved

1. Scalar SYCL `single_task`: bitwise exact over 40 changing inputs, but
   83.413 us versus 75.704 us for the reference chain. Projected regression:
   0.308 ms/token.
2. SIMD16 load plus lane-0 local-memory merge: bitwise exact, but 91.772 us
   versus 76.222 us. Projected regression: 0.622 ms/token.
3. Fully subgroup-parallel top-k: every lane holds ten of the 160 experts;
   six subgroup max/min reductions select the sorted top-6. This cleared the
   gate at 7.178 us versus 77.128 us, a 10.75x microbenchmark speedup and
   2.798 ms/token projection.

The two failed geometries matter: merely reducing launch count is not enough
when Xe2 executes the selection serially. The win comes from expressing the
entire selection as SIMD16 register work with subgroup reductions and no
global scratch or radix passes.

## Four-card evidence

All four B70s passed 40/40 changed-input epochs with bitwise-identical sorted
IDs and raw FP32 weights. Candidate medians were 7.223-7.280 us. Slowest-card
projected saving was 2.739 ms/token, comfortably above the 0.50 ms gate.

Artifacts:

- `data/m1-biased-topk-microgate-20260715.json` (scalar negative);
- `data/m1-biased-topk-simd16-microgate-20260715.json` (lane-0 merge negative);
- `data/m1-biased-topk-subgroup-reduce-microgate-20260715.json`;
- `data/m1-biased-topk-subgroup-reduce-card{0,1,2,3}-20260715.json`.

## Integration gate

The source path is default-off behind `VLLM_XPU_V4_M1_BIASED_TOPK=1`.
Promotion still requires reusable PIECEWISE graph capture, strict full-model
output parity, and a paired nonspec realistic-suite improvement. The first
three hash-MoE layers retain their existing lookup path; only the 40 normal
router layers use the new kernel at M=1.
