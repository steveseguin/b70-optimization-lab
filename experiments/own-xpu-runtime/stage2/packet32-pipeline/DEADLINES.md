# Expected durations and independent watchdogs

No device ran. Expected durations are printed hypotheses only, never timeouts.

| Window | Expected work + first JIT | Default watchdog | Submission bound |
| --- | ---: | ---: | ---: |
| K0 | 30 + 17 s | 600 s | no kernel execution |
| K1a / K1b / K2 | 1800 + 17 s | 10800 s | 4 s |
| W0p | 30 + 17 s | 600 s | 0.1 s |
| W2s / W2n / W2d / W2c | 1900 + 17 s | 10800 s | 4 s |

Every watchdog is at least four times its estimate and at least 300 seconds.
Native model local waits/drain use 60 seconds; fixture waits remain 300 seconds;
canary local waits use five seconds. Coordinator model hand-over waits are
bounded at 600 seconds, with a separate whole-window deadline. Startup ready
waits use the window deadline and keep polling faults/memory/peer liveness.
Native channel waits are also finite. CPU full-model gates use a larger
3600-second per-half bound, never a device default.

One cooperative stop is followed by at most 65 seconds of coordinator drain
waiting; a still-busy native owner is retained and reported. Faults are recorded
before teardown. W2 token timing does not query GPU timestamps and labels kernel
submission time unmeasured. W2c and W0p enable local profiling; cross-card GPU
clocks are never compared for overlap.
