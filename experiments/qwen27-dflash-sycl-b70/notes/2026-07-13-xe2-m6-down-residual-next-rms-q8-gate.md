# Xe2 M=6 down -> residual -> next RMS/Q8 gate

Date: 2026-07-13

Status: rejected before runtime integration; protected `llama.cpp` source was not changed

## Question

Could the 57 full187 Q4_0 FFN-down layers clear the required `2 ms` target
verification-cycle gate by extending the exact down-DPAS residual epilogue
through the following RMSNorm, learned norm weight, and canonical/DPAS-ready
Q8_1 production?

The integration gate is `2 ms / 57 = 35.088 us` saved per eligible layer, or
at least a `3%` same-build end-to-end crossover.

## Exact graph census

The Qwen graph is:

```text
blk.i ffn_down (M=6, 17408 -> 5120)
  -> ADD(saved attention residual)          post_ffn
  -> build_cvec                             normally no-op
  -> blk.i+1 RMSNorm                        i = 8..63
  -> learned norm-weight MUL
  -> next attention/GDN projection Q8_1
```

Full187 slots `130..186` are exactly `blk.8..blk.64.ffn_down.weight`, all
Q4_0. Therefore:

- 56 boundaries (`blk.8..blk.63`) feed the next decoder layer's attention
  RMSNorm;
- the 57th (`blk.64`) feeds the final RMSNorm and Q6_K vocabulary head, which
  is a different consumer contract;
- `blk.0..blk.7` use Q4_1 down weights and remain a separate fallback lane;
- attention/GDN output -> post-attention RMSNorm is a separate 64-boundary
  family. Existing `MMVQ+ADD+RMS+Q8` logs report 64 eligible boundaries per
  target graph and must not be treated as evidence that the full187 down-DPAS
  path composes with that matcher.

The down result plus residual must still materialize as F32: it is the next
layer input and the saved residual for the next block. A legal larger fusion
can remove the separate ADD and avoid materializing normalized/weighted F32,
but the global RMS reduction cannot safely be folded into the multi-workgroup
down DPAS kernel without an additional synchronization boundary.

## Measured gate evidence

Two existing exact results bound this proposal before another runtime patch:

1. The real-shape M=6 SwiGLU/Q8/down-DPAS/residual comparator saved
   `7.765 us/layer` in an optimistic submit-and-wait wall measurement and only
   `2.814 us/layer` by event sums. Across 57 layers this is `0.443 ms` wall or
   `0.160 ms` event time.
2. The broader guarded residual+RMSNorm+norm-weight+Q8 implementation averaged
   `48.806 tok/s` versus `47.999 tok/s` over an eight-run, four-card strict
   MTP3 crossover: `+1.68%`, approximately `0.96 ms` at the then-current
   roughly 57 ms speculative cycle. It covered 64 eligible boundaries, not
   just the 57 full187 down transitions.

Even adding the optimistic `0.443 ms` down-tail wall saving to the entire
measured `0.96 ms` broad RMS/Q8 gain gives only about `1.40 ms/cycle`. This is
an intentionally generous upper bound: it credits all 64 RMS/Q8 boundaries to
the 57-layer proposal and multiplies a serialized submit-and-wait saving into
the production cycle. It is still only `70%` of the `2 ms` gate and remains
below the `3%` end-to-end gate.

The full187 operation trace is consistent with the rejection. FFN down itself
is `7.419 ms` over all 64 layers, but this proposal does not reduce its weight
read or DPAS work. It attacks only the already-small ADD/RMS/MUL/quantization
tail.

## Correctness contract retained for any future revisit

A real integrated fixture must contain, for one M=6 transition:

- layer index and full benchmark/run identity;
- the down input in canonical Q8_1 and full187 DPAS SoA/correction layouts;
- the `6 x 5120` saved residual;
- the ordinary `6 x 5120` F32 down output and post-FFN sum;
- the following 5120-element F32 norm weight and RMS epsilon;
- the ordinary next activation's canonical Q8_1 bytes and DPAS SoA/correction
  bytes.

Comparison must preserve the ordinary F32 down reduction and residual-add
rounding points. Canonical Q8 metadata must use an observable half-rounding
boundary; `float(sycl::half(value))` is insufficient under BMG AOT because the
compiler may remove the round trip. The proven form materializes volatile
half bits before conversion back to float.

## Decision

Do not add a hot-module operation, graph matcher, runtime flag, build, strict
suite, or LocalMaxxing submission for this boundary. It cannot plausibly reach
the hard gate and would overlap higher-value integration work for a sub-2 ms
ceiling.

The next target-side fusion lane must change the dominant projection economics
or cover a substantially larger recurrent/attention pipeline, rather than add
another small epilogue. The 57 full187 down weights remain valuable for DPAS
verification, but not as the anchor for this residual/RMS/Q8-only extension.
