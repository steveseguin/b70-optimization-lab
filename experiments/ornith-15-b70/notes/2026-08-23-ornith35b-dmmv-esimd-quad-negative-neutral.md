# Ornith 1.5 35B-A3B: four-row ESIMD dense reuse regresses broadly and is neutral at the output head

Date: 2026-08-23 EDT

Status: **CLOSED — broad negative; output-head-only neutral; do not ship**

Ornith inherits enough of Qwen's architecture that the lab's Qwen dense-GEMV
work is a useful candidate library. It is not assumed to transfer. This test
first confirmed that the mixed `Q4_K_M` model's dense K-quant projections use
the reordered ESIMD DMMV path, then evaluated a four-row variant of its existing
two-row kernel. The candidate retained each row's stock 32-lane arithmetic but
reused the FP32 activation vector across four output rows instead of two.

Correctness was exact. In same-frozen-binary, forced greedy 128-token runs, both
the broad and output-head-only candidates matched the canonical transcript
SHA-256
`d25039a7a21fccc7eaf5f9414803f80c1e3b58cc900ad8034448df8edb57e38c`.
Instrumentation counted 29,340 broad candidate calls and 130 output-head-only
calls, so both tested doors were active.

The broad Q2_K through Q6_K dense path was a clear regression:

| Arm | Runs (tok/s) | Mean |
| --- | --- | ---: |
| control | `119.816232`, `120.330762` | **120.073497** |
| four-row candidate | `117.969641`, `117.310932` | **117.640287** |

That is **-2.03%**. Restricting the same kernel to the Q6_K output head at the
exact `[248320,2048]` weight shape removed the regression but not enough cost:

| Arm | Runs (tok/s) | Mean |
| --- | --- | ---: |
| control | `120.450051`, `120.563346` | **120.506699** |
| output-head candidate | `120.553517`, `120.669067` | **120.611292** |

The scoped difference is only **+0.087%**, below the engine promotion
threshold. No server or canary screen was justified, and the accepted runtime
is unchanged.

The complete output-head-scoped source is preserved at
`../patches/llamacpp-ornith15-dmmv-esimd-quad-output-head-neutral-20260823.patch`.
Raw mirrored engine rows and the structured exactness/performance conclusion
are under `../data/2026-08-23-ornith35b-dmmv-esimd-quad-*`.
