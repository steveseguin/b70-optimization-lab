# Qwen3.8 TP2/MTP1 profile-only decoder-sync D66 count false-fail

Date: 2026-08-31

D66 activated decoder-boundary synchronization only while
`GPUModelRunner.profile_run()` set its process-local profile marker. The server
reached API readiness, every dummy-sampler stage completed four times, and the
timestamp-bounded kernel log was clean. No request was served.

The exact decoder accounting was 1,040 `begin` and 1,040 matching `pass`
receipts, not the preregistered 2,080:

`65 layers × 8 boundaries × 2 ranks × 1 profile forward = 1,040`

The later startup warmup forward is not executed by `profile_run()`, so it
correctly emitted no decoder-stage receipt. Importantly, that unsynchronized
warmup forward still completed on both ranks and all sampler stages passed.
D66 then failed its exact receipt gate before the second health check. It is a
literal procedural/cardinality failure, not retroactively called a pass and not
a performance result.

D67 repeats the immutable image and configuration with only the expected
decoder receipt count corrected from 2,080 to 1,040. The narrow result suggests
that ordering the first compile/profile forward is sufficient to protect the
later warmup and leaves normal request forwards free of decoder barriers.

Raw evidence:
`/mnt/fast-ai/bench-results/qwen38-tp2-mtp1-profile-only-decoder-sync-20260831-d66/`.
