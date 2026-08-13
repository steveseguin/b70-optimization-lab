# 2026-08-13 Muse Q8 width-16 SYCL MMQ negative

## Question

Could the dormant SYCL Q8_0 MMQ path remove the very expensive quantized-weight
dequantization at the fixed 16-row Muse verifier width and materially move TP4
decode toward 100 tok/s?

## Patch and safety scope

The experiment patch is preserved at
`patches/2026-08-13-muse-q8-width16-mmq-negative.patch`. It enables MMQ only
for Q8_0 weights, F32 input/output, exactly 16 rows, and non-split buffers.
Because the normal width <= 8 optimization rewrites Q8_0 weights in place from
AoS to an MMQ-incompatible SoA layout, the flag also disables Q8_0 reorder for
the process lifetime and rejects any tensor already marked reordered. A
one-time first-hit marker was included. The normal environment-off path is
unchanged.

Source base was `1ff6bcb6c`; the source diff was deliberately reverted after
the negative screen and was never committed.

## Validation

Authoritative targets `test-backend-ops`, `llama-server`, and `llama-bench`
built successfully in `build-sycl-b70-aot-bmg-g31` after sourcing oneAPI.

Focused backend correctness on one B70:

```text
GGML_SYCL_Q8_0_MMQ_WIDTH16=1 ONEAPI_DEVICE_SELECTOR=level_zero:0 \
  test-backend-ops test -b SYCL0 -o MUL_MAT \
  -p 'type_a=q8_0,type_b=f32,m=16,n=16,k=(256|1024).*'
```

Result: 10/10 supported cases passed the CPU reference comparison.

## Real-model performance result

Model:
`/mnt/fast-ai/llm-models/muse-glimmer-30b-gguf/Muse-Glimmer-30B-UD-Q8_K_XL.gguf`

Identity: TP4 tensor split, four B70s, full offload, prompt width 16, no token
generation, batch/ubatch 1024, flash attention on, 8 CPU threads, five
repetitions, graph disabled, meta parallel submit enabled. Production was
stopped and the shared GPU lock held.

| arm | avg pass | reported tok/s |
|---|---:|---:|
| control, MMQ flag 0 | 146.160 ms | 109.469 |
| candidate, MMQ flag 1 | 281.806 ms | 56.777 |

Candidate/control time ratio: **1.928x**. Pass time regressed **92.81%** and
reported throughput fell **48.13%**. The difference is too large to require a
third arm. The artifact is a mixed K-quant file, but it contains enough Q8_0
work for disabling reorder/enabling MMQ to be decisively harmful.

Raw artifacts:

- `/mnt/fast-ai/bench-results/muse-glimmer-30b/q8-width16-mmq-20260813/control.json`
  SHA256 `5e2f2ee4f610e33cf24067d4957f68529957a5a78b0aa4fdd41278850bdefd29`
- `/mnt/fast-ai/bench-results/muse-glimmer-30b/q8-width16-mmq-20260813/candidate.json`
  SHA256 `6ff5bf289ff2e4ebb6c4b5b4143922b7a9ab0bae795647629708993073920ac1`

## Decision

**Close/reject.** The generic DP4A MMQ implementation is numerically plausible
on its bounded backend tests but badly untuned for Muse's real width-16 shapes.
Do not materialize a full Q8_0 Muse target merely to pursue this kernel, and do
not confuse the `UD-Q8_K_XL` filename with a homogeneous Q8_0 layout.

This result does not train or modify the DFlash drafter. It also does not alter
the BF16 production source or recipe.
