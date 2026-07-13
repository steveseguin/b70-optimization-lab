# Xe2 M6 SwiGLU -> canonical Q8 SoA -> down DPAS prototype

Date: 2026-07-13

Status: isolated prototype passed; protected llama.cpp source not changed

## Question

Can the active M=6 FFN boundary be collapsed from:

1. SwiGLU to an F32 tensor;
2. production-compatible Q8_1 quantization to a row-major canonical tensor;
3. repack to the signed-S8 SoA and correction records consumed by Xe2 DPAS;
4. the existing packed Q4_0 down projection; and
5. a separate residual add

into direct SwiGLU -> signed-S8 SoA/correction production, the existing down
DPAS kernel, and a residual epilogue without changing any bits?

The isolated comparator is:

- `../xe2-verifier/swiglu-q8-down-fusion.cpp`;
- `../xe2-verifier/build-swiglu-q8-down-fusion.sh`.

It uses the real down shape `M=6`, `K=17408`, `N=5120`, signed-S4 x signed-S8
DPAS, eight strided K splits, joint width two, and the production correction
formula.

## Stable result

Command:

```bash
ZE_AFFINITY_MASK=2 XE2_ITERS=200 \
  experiments/qwen27-dflash-sycl-b70/xe2-verifier/build-swiglu-q8-down-fusion.sh
```

Evidence outside Git:

`/mnt/fast-ai/bench-results/qwen27-xe2-verifier/swiglu-q8-down-fusion-canonical-order-20260713-gpu2-200.log`

The BMG AOT result was:

| Path | Boundary wall median | Relevant event medians | Correctness |
|---|---:|---|---|
| Five-op control | `106.636 us` | SwiGLU `2.292`, canonical quant `1.979`, repack `1.250`, DPAS `87.396`, residual `0.834 us` | reference |
| F32 SwiGLU + direct SoA + DPAS residual | `103.370 us` | `2.292`, `1.562`, `88.646 us` | bit exact |
| Direct SwiGLU-Q8 SoA + DPAS residual | `98.871 us` | `3.125`, `87.812 us` | bit exact |

The full boundary saved `7.765 us`, or `7.9%`, in this submit-and-wait
microbenchmark. Its event-time sum saved only `2.814 us`; therefore the whole
decoder estimate must not multiply the wall result as if every removed host
wait existed in production.

Both candidates had:

- zero Q8-byte differences;
- zero scale/correction metadata differences;
- zero output-bit differences;
- zero maximum or RMS output error.

## The important correctness finding

The first direct implementation appeared numerically plausible but was not
canonical. Its Q8 values were already exact, yet it had:

- `3264 / 3264` scale records with different float bits;
- `3263 / 3264` correction records with different float bits;
- `16154` differing metadata bytes;
- all `30714` output floats with different bits;
- `0.097` maximum and `0.025` RMS output error on the random stress input.

The cause was the local expression used by the current fast M6 quantizer:

```cpp
float(sycl::half(value))
```

The BMG AOT compiler can remove that local float-to-half-to-float round trip.
The canonical path writes the half to global memory and reads it back, so the
rounding cannot be removed. A volatile F32 SwiGLU product did not change the
metadata failure.

The direct kernel became canonical-exact only after materializing each half as
volatile 16-bit bits before converting it back:

```cpp
volatile uint16_t bits = sycl::bit_cast<uint16_t>(sycl::half(value));
float rounded = float(sycl::bit_cast<sycl::half>(uint16_t(bits)));
```

This matters beyond this fusion. It explains why the earlier one-kernel "fast"
metadata path can drift even when its source appears to contain an explicit
half conversion. It gives the project a one-kernel, canonical-exact SoA
producer and removes the reason the `K=17408` down path currently needs a
second repack kernel and canonical temporary.

## Exact implementation boundaries

No protected source was edited during this prototype. The proposed guarded
source change is:

### 1. `ggml-sycl/mmvq.cpp`

- Add a direct canonical SoA producer next to
  `ggml_sycl_quantize_q8_xe2_m6_canonical` at lines 24-96. It should accept
  either an F32 source or gate/up sources plus input stride.
- Preserve the current reduction ordering, `amax` then `sum`, signed-S8 layout
  `(ki*M + row)*32`, and correction
  `8 * (qsum * half_rounded_d - half_rounded_sum)`.
- Use volatile 16-bit half materialization. Do not use the current local
  `float(sycl::half(...))` idiom at lines 136-139 as the canonical path.
- Template or overload `ggml_sycl_q4_0_xe2_m6_slm` at lines 145-231 with an
  optional residual pointer and row stride. Add residual after the eight SLM
  partials are accumulated and immediately before the one final F32 store.
- Add a guarded public helper beside
  `ggml_sycl_mul_mat_q4_0_xe2_m6` at lines 320-384. The helper takes gate, up,
  gate/up stride, optional residual, packed down weights, and destination.
- Retain the existing down DPAS body and packed-weight ABI v2. This experiment
  does not justify changing its tile, split, or accumulation order.

### 2. `ggml-sycl/mmvq.hpp`

- Declare the guarded SwiGLU/down helper next to the M6 and dual M6 interfaces
  at lines 79-105.
- Document that it is BMG, M=6, Q4_0 ABI-v2 only, and that its queue must
  preserve submission order.

### 3. `ggml-sycl/ggml-sycl.cpp`

- The graph-level SwiGLU matcher is at lines 7242-7280. It already identifies
  GLU, identity metadata nodes, and the down `MUL_MAT` consumer.
- The M6 dispatch currently rejects a current SwiGLU consumer at lines
  4809-4810. Replace this unconditional rejection with a guarded call to the
  new helper when the logical consumer is the matched down tensor.
- `ggml_sycl_mul_mat_add` at lines 5080-5096 bypasses
  `ggml_sycl_mul_mat`, so the optional residual path must be checked there as
  well. Pass the logical down tensor separately from the ADD destination so
  `swiglu_q8_is_current_consumer()` is tested against the correct node.
- On a successful SwiGLU/down/residual dispatch, skip the GLU identity chain,
  down node, and ADD node exactly once, clear `g_swiglu_q8_fusion`, and retain
  the existing power-of-two counters/logging.
- Keep the path default-off under an explicit experiment flag until the full
  correctness suite passes.

The larger follow-up should move matching earlier to the adjacent gate/up pair
at lines 7131-7135 and 4849-4929. A same-tile joint gate/up workgroup can compute
both matrices for 32 output columns, reduce both, produce one 32-value SwiGLU
Q8 block, and then launch down DPAS. That removes the gate/up F32 tensors too.
The current dual kernel assigns separate workgroups by matrix, so it cannot
safely perform SwiGLU without redesign; there is no cross-workgroup barrier.

## Scratch ownership

For `M=6`, `K=17408`:

- signed-S8 values: `6 * 17408 = 104448` bytes;
- scale/correction records: `6 * 544 * 8 = 26112` bytes;
- candidate SoA scratch: `130560` bytes;
- old canonical temporary: `6 * (17408 + 544 * 4) = 117504` bytes;
- old total quantization scratch: `248064` bytes.

The direct path reduces quantization scratch by `117504` bytes (`47.4%`). The
first non-graph experiment can use the existing function-local pool allocation
because the active queue is in order and graph mode is currently rejected by
the M6 matcher. A reusable graph must not capture that transient allocation.
Before graph enablement, move the `130560`-byte buffer to fixed-address,
execution-slot-owned storage keyed by device, M, K, and verifier width.

Gate/up tensors remain graph-owned input buffers in the first integration.
The residual is borrowed read-only for the duration of the ordered down
submission. No extra residual scratch is required.

## Correctness and promotion gates

1. Build BMG AOT; reject runtime JIT as evidence.
2. Re-run this random comparator with at least 200 iterations and require zero
   Q8, metadata, and output-bit differences.
3. Run captured real tensors from first, middle, and final FFN layers and
   require canonical Q8 bytes and metadata to be bit exact.
4. Use the existing M6 shadow oracle on real down projections. The fused
   residual output must match the current DPAS-plus-ADD result bit-for-bit;
   candidate versus generic MMVQ remains subject to the already-promoted real
   projection tolerance.
5. Require deterministic token parity on strict no-spec decode and unchanged
   target verification/acceptance on DFlash5.
6. Run the fixed 12-prompt cold realistic suite with `cached_tokens=0`, followed
   by repeat and long-context quality gates.
7. Diff the complete run identity before interpreting speed. Submit to
   LocalMaxxing only if the strict matching record is genuinely exceeded.

## Expected whole-cycle value

The model has 57 packed down projections in the current promoted lane.

- Event-sum extrapolation: `2.814 us * 57 = 0.160 ms` per full M=6 verifier.
- Microbenchmark wall upper bound: `7.765 us * 57 = 0.443 ms`.

The current full187 cycle is about `64.559 ms`, so this first fusion is likely a
roughly `0.25-0.69%` cycle improvement, not a path from 44 to 100 tok/s by
itself. It is still a useful low-risk composition because it is exact, removes
three launches at each matched boundary, establishes canonical direct-SoA
production, and enables the larger gate/up-to-down FFN pipeline.

Do not represent this isolated result as a decode record. The next engineering
decision should weigh its small expected end-to-end return against the larger
joint gate/up producer fusion and measured GDN/attention cycle gaps.

## Priority decision

Do not integrate the complete small-boundary fusion ahead of higher-ceiling
verifier work. Its expected `0.25-0.69%` cycle return is below the project's
integration priority.

Retain the direct canonical-SoA producer as a prerequisite component. It is a
small, independently testable mechanism needed by either a full gate/up-to-down
pipeline or wider M=9/M=16 DPAS verification, and the forced half-bit rounding
fix prevents a known correctness trap in both.
