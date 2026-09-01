# D66 preregistration: TP2/MTP1 profile-only decoder synchronization

Date: 2026-08-31

D65 proved that decoder-boundary synchronization prevents the TP2/MTP1 device
loss, but its environment flag remained enabled after startup and would impose
eight device-wide barriers per layer on every request. D66 changes only the
scope of that known-stable mechanism: `GPUModelRunner.profile_run()` sets a
worker-local active marker immediately before its `is_profile=True` dummy
forward and clears it immediately after the existing final device sync. Decoder
barriers execute only while that marker is active. Normal request forwards see
the marker absent and perform no decoder-stage synchronization.

D66 is zero-request and startup-only. It keeps the D65 model, TP2, MTP1,
projection-repair-off state, eager mode, 256-token profile bound, sampler
instrumentation, exact two-profile-passes-per-rank receipt contract, device
order, and memory limits. A pass requires 2,080 complete decoder boundary
receipts, exactly four receipts for every sampler stage, both health checks,
clean teardown, and a timestamp-bounded kernel delta with no GPU, OOM,
filesystem, or I/O fault. It qualifies startup mechanics only; it cannot produce
a speed, quality, determinism, or promotion result.
