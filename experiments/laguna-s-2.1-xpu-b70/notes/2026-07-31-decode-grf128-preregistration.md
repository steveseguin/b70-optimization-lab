# Laguna width-12 INT4 decode 128-GRF-mode preregistration

Date: 2026-07-31 America/Toronto

## Premise

The exact `SCALE_VEC=1, DEQUANT_MAD=0` decode kernel uses about 94 distinct
GRFs and reaches roughly r105 in the prior matched BMG analysis, with zero
spill/fill. Nevertheless every grouped-GEMM launcher explicitly requests
`intelex::grf_size<256>`, and the build also supplies
`-cl-intel-256-GRF-per-thread`. The generated kernel therefore reports
`numGRF=256` and four hardware threads per EU. The 32 registers saved by the
verified SCALE_VEC optimization cannot improve occupancy under that forced
mode.

The production profile is instruction/latency bound rather than purely weight
bandwidth bound: expert streaming reaches 66-80% of the measured ceiling and
the dominant graph segments contain this grouped GEMM. If the width-12 decode
policy fits default 128-GRF mode without spills, additional resident hardware
threads may hide block-load, prefetch, and DPAS dependency latency without
changing any model arithmetic.

## Candidate shape

The first stage is code generation only: compile the durable
`w4a16_policy_m_8` probe with the BMG default-GRF option
`-cl-intel-128-GRF-per-thread`, holding source and every selector constant.

If that passes, implement a separately named default-off generic decode kernel
specialization that requests `grf_size<128>` only for the width-12
`w4a16_policy_m_8` route. Keep 256-GRF mode for prefill, other policies, M8
specializations, selector-off control, and every existing kernel. Removing the
global large-GRF backend override is permitted only if per-kernel properties
are proven to preserve 256 mode for all unaffected entry points.

No arithmetic, accumulation, reduction, model, weight, KV dtype, speculative
policy, teacher, prompt, topology, or metric changes.

## Stage gates

1. Extend the durable IGC probe runner with a fail-closed 128/256 mode input
   and compile the exact incumbent source in both modes. No production source
   change, full build, or GPU use yet.
2. Stop if the 128-GRF decode probe spills/fills, fails compilation, changes
   DPAS count, changes the 32 BF16 scale multiplies, materially grows total
   instructions or dependency barriers, or does not report `numGRF=128`.
3. Before a full build, prove from generated names/options that the candidate
   can coexist with the unchanged 256-GRF control and that prefill/other
   policies remain forced to 256. Stop if the toolchain collapses both modes
   onto one kernel identity or requires changing all grouped GEMMs globally.
4. Build the production DSO only after those static gates. Preserve source,
   binary hash, compiler identity, and all per-entry GRF/spill summaries.
5. Run a changed-input component comparison against the 256-GRF kernel.
   Require bitwise equality and no runtime/device error. Because arithmetic is
   source-identical, any mismatch indicates wrong dispatch or compiler/runtime
   instability and stops the lane.
6. Only then run one cold exact score on the verified 121.037 BF16-KV stack,
   with target 146/145 and draft 14/13 unchanged. A result within the noise
   band requires matched interleaved confirmation before promotion.

No reboot, reset, FLR, driver reload/unbind, shared-memory deletion, metric
window change, quality relaxation, teacher regeneration, retry after a failed
gate, or best-of-run selection is authorized.

## Expected value

This changes a resource/latency class rather than shaving a handful of
instructions. If 128-GRF mode is spill-free and increases resident threads,
it can affect the entire dominant INT4 segment while keeping exact arithmetic
byte-for-byte at source. The decisive compile-only screen is cheap. No
throughput gain, let alone 130 tok/s, is claimed before measurement.
