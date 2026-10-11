# Packet 23 deadlines

Expected durations are conservative inherited planning proxies, reported only.
They never cause a signal. No new device durations were measured here.

| Window | Expected work + JIT (s) | Default watchdog (s) | Minimum (s) | Per-submission budget |
| --- | ---: | ---: | ---: | --- |
| K0: build every kernel, no execution | <60 estimated | 600 | 600 | no submissions |
| K1, each fresh component pair | 1800 + 17 | 10800 | 7300 | <4 s, fixture profiling gate |
| W0 | 30 + 17 | 600 | 300 | <0.1 s, profiling gate |
| W1 / W2 / W2d | 1897.718 + 17 | 10800 | 7659 | 4 s planning budget |
| W3 / W3d | 1200 + 17 | 10800 | 4868 | 4 s planning budget |

All watchdogs are at least four times expected total and at least 300 seconds.
K1 qualifies actual fused submissions before model windows. Token/drain modes
make no per-event duration queries; their per-submission budget is a planning
constraint supported by K1, not a measured pass in the speed run. Launch mode
retains the device breakdown for diagnosis. W0 always profiles its small canary.

The watcher polls the journal, requests at most one SIGTERM for a fault, missing
monitoring or watchdog, and waits 60 seconds before handing back a retained PID.
It never sends SIGKILL or retries. Native model drain/teardown waits are 60 s;
W0 completion waits are 5 s. The journal helper is bounded at 2 s, ldd at 10 s,
ionice at 2 s. Postflight watches for five seconds. Runtime/JIT calls can retain
an owner; a watchdog never grants permission to release live resources.

The repair adds K0 before any slow reference fixture. Its one process builds each
admitted device's complete kernel bundle. Host compile/link does not replace it.
Owner failure handling reports first, then attempts a 60-second drain. A known
zero-work failure exits with code 1; only genuinely unresolved work can park.
