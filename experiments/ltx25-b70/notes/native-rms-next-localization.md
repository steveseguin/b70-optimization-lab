# Conditional native compiler first-divergence localization

September 14, 2026. Prepared while compiler-screen-03 is running; this is a
source-backed diagnostic plan, not a measured failure or cause.

If native RMS preservation still changes output bytes, capture only the first
failed block24 invocation before any in-place updates. Keep its resident weights
by reference. Save the small input and conditioning tensors, their metadata and
hashes. Do not copy the complete checkpoint or retry the failed graph gate.

Trace boundaries in source execution order: initial AdaLN and Q/K projections;
native RMS and RoPE outputs; SDPA output and gate logits; sigmoid gating, output
projection and residual addcmul. If those match, inspect feedforward linear,
GELU, second linear and residual. Sigmoid, GELU and residual arithmetic are
hypotheses, not measured causes.

Use an independently verified eager FX interpreter for reference snapshots and
a private copy of the emitted wrapper for compiled snapshots. Retain the exact
kernels; returning additional intermediates through a new compilation can change
fusion and invalidate the comparison. Snapshot before generated buffer reuse.
Require instrumented final outputs to reproduce the observed failing hashes.
Compare full bytes plus shape, strides, dtype and device. Stage1 video tensors
are about 0.5 MiB each and gate logits are much smaller. This diagnostic is not
implemented or qualified as a speed optimization; native execution needs its own
bounded admission and original-output checks.
