# D65 preregistration: TP2/MTP1 decoder-stage startup confirmation

Date: 2026-08-31

D64 activated the exact decoder/sampler instrumentation source, completed two
full model/profile passes on both TP ranks, reached API readiness, and produced
no Xe fault. Its literal runner result was a procedural false-fail because the
generic receipt gate expected one sampler pass per rank while the log proves
vLLM performs two. It exited before the required second endpoint health check.

D65 repeats D64 exactly. The only code/config change is
`DUMMY_SAMPLER_RUNS_PER_RANK=2`, making the expected count four per sampler
stage at TP2. The accepted receipt cardinality is frozen at exactly four for
each of all nine stages; neither missing nor additional receipts pass. The
decoder source, image ID, import path, projection-repair-off state, MTP1,
TP2, eager mode, 256-token profile bound, model, device order, memory limits,
and zero-request startup-only policy are unchanged.

A pass requires the first and second HTTP health checks, exact sampler receipt
counts, clean teardown, and a kernel delta free of GPU, OOM, filesystem, or I/O
faults. It confirms only that decoder-boundary synchronization prevents the
startup device loss. It does not qualify decode, TTFT, acceptance, quality,
determinism, or promotion. Any failure closes D65 without retry.
