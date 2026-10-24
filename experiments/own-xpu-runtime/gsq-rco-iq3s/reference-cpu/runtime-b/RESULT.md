# One independent reference request:32-token prefix agreement

The same SC117 IQ3_S shards loaded on CPU with actualBF16 attention K/V and
F32 recurrent R/S/P logs. One87-token numeric prompt generated32 greedy tokens,
with zero cached prompt tokens. All32 match the historical5aef custom prefix;
each selected token is the highest pre-sampling log-probability entry.

The original runner terminal remains failed: it expected the requested
temperature-1 to be echoed. The server schema clamps this to0, and the actual
sampler treats temperature<=0 as greedy. Independent source-bound readback
accepts that documented normalization without another model run. Every other
request/precision/closure condition remains checked. Exit0 followed one SIGTERM;
the complete run took29.48seconds. This is correctness evidence, not a speed test.

The earlier runtime-a loaded successfully but rejected missing dtype log lines
before any POST; its defaultverbosity3 suppressed the allocation logs. Runtime-b
changed only verbosity4 and fresh run identity. Both failed terminal receipts,
all response bytes and source corrections are preserved.

[Independent readback](evidence/closed-readback-review.json) and
[actual response](evidence/actual/response.json) retain the result. The monitor
retained process status/RAM samples, not raw FD/maps listings; its sampled device
and library checks are supported by frozen control flow rather than invented
post-exit descriptor evidence. The CPU-only ELF/source closure is separately
retained. This short agreement neither qualifies the oldBF16 recurrence nor
certifies the corrected native engine or broad model quality.
