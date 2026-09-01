# D69 preregistration: bypass projection repair for dummy forwards

Date: 2026-08-31

D67 passed with projection repair disabled. D68 changed only repair enablement
and lost rank 1's device inside the repaired dense MLP during the first
synthetic 256-token profile forward. D69 introduces a scoped marker around
every `GPUModelRunner._dummy_run` and makes the projection hook bypass its
M=512 padding only while that marker is active. The decorator restores any
prior marker value in `finally`. Real inference requests do not call
`_dummy_run`, see no marker, and retain projection repair unchanged.

D69 is zero-request and startup-only. It otherwise repeats D68: exact
profile-only image lineage, TP2, MTP1, projection repair enabled, synchronization
inside the first profile forward, 256-token startup bound, eager mode, device
order, memory limits, exact 1,040 decoder receipts, and four receipts per
sampler stage. A pass requires both health checks, clean teardown, and no GPU,
OOM, filesystem, or I/O fault in the timestamp-bounded kernel log. It confirms
startup mechanics only; no speed, output, determinism, or promotion claim may
be made from D69.
