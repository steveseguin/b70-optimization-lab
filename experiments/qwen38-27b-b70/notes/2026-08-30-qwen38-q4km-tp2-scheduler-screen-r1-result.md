# Qwen3.8-27B Q4_K_M TP2 scheduler screen r1 — no candidate advanced

All six preregistered c64 arms completed on this host's two B70s and passed the
output-isolation gate: 384/384 measured responses returned 128 complete token
IDs, cached prompt tokens stayed at zero, and there were no cross-base oracle
collisions.

| arm | c64 aggregate tok/s | vs fresh control |
| --- | ---: | ---: |
| batch 1024, ubatch 256, ctx 32768, 8 threads | 160.745 | -1.16% |
| **batch 2048, ubatch 256, ctx 32768, 8 threads (control)** | **162.634** | **0.00%** |
| batch 4096, ubatch 256, ctx 32768, 8 threads | 162.032 | -0.37% |
| batch 2048, ubatch 512, ctx 32768, 8 threads | 165.502 | +1.76% |
| batch 2048, ubatch 256, ctx 16384, 8 threads | 162.418 | -0.13% |
| batch 2048, ubatch 256, ctx 32768, 16 threads | 161.500 | -0.70% |

No arm reached the frozen +3% threshold (167.513 tok/s), so none advances to
replication. In particular, the one-run ubatch-512 improvement is not promoted.
It is within the size of a modest scheduler effect and does not justify changing
the package or the published 165.387 tok/s two-attempt c64 result.

After every result and qualification file had been written, the runner's
cleanup raced an interrupt to the outer timeout with a direct server signal.
All six processes consequently logged a CPU-side teardown segfault or an
immediate second-interrupt termination. This does not change the completed
HTTP measurements, but it is a runner defect and is recorded rather than
hidden. Both B70s remained `normal`; the kernel log contains no Xe fault,
reset, hang, CAT fault, device loss, or OOM. The runner now signals the server
exactly once, waits up to 60 seconds, and escalates only if it survives.
A non-performance one-slot TP2 load/health/single-SIGINT smoke then exited
with wrapper status 0 and zero new kernel-error matches; its
[receipt](../data/2026-08-30-qwen38-q4km-tp2-single-signal-cleanup-smoke.json)
is retained separately and contains no throughput claim.

This closes batch size, micro-batch size, unused short-context KV allocation,
and host-thread count as easy c64 levers in the tested ranges. The next useful
work is profiling the qualified target-only c64 path and tying the next screen
to a measured kernel or TP communication cost.

The [result contract](../data/2026-08-30-qwen38-q4km-tp2-scheduler-screen-r1-result.json)
links the deterministic [102-artifact evidence archive](../data/qwen38-q4km-tp2-scheduler-screen-20260830-r1/manifest.json).
