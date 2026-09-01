# D67 preregistration: exact profile-only synchronization confirmation

Date: 2026-08-31

D66 reached readiness without a Xe event and proved that only one startup
forward per rank executes under `GPUModelRunner.profile_run()`. Its literal
runner failed because the frozen contract expected 2,080 decoder receipts while
the exact mechanism produced 1,040. The later unsynchronized warmup forward and
all four sampler passes completed.

D67 repeats D66 exactly. The only change is
`EXPECTED_DECODER_STAGE_RECEIPTS=1040`. The accepted count remains exact for
both `begin` and `pass`; neither missing nor additional receipts pass. The
immutable image, source path, model, TP2, MTP1, projection-repair-off state,
profile bound, eager mode, device order, memory limits, zero-request policy,
and four-receipts-per-sampler-stage contract are unchanged.

A pass requires the first and second health checks, exact decoder and sampler
counts, clean teardown, and no GPU, OOM, filesystem, or I/O fault in the
timestamp-bounded kernel delta. It qualifies startup mechanics only and cannot
authorize a speed, quality, determinism, or promotion claim.
