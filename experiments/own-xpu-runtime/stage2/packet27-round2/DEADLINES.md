# Packet 27 timing estimates and independent bounds

No device ran during preparation. Estimates below are operational hypotheses,
not measured execution or speed claims. An expected duration is printed in the
receipt but does not terminate work. Limits remain independent of estimates.

| Window | Expected work | First-JIT allowance | Default watchdog | Watchdog / total estimate | Per-submission budget |
| --- | ---: | ---: | ---: | ---: | ---: |
| K0 | 30 s | 17 s | 600 s | 12.8x | no kernel submission |
| K1a | 1,800 s | 17 s | 10,800 s | 5.94x | 4 s |
| K1b | 1,800 s | 17 s | 10,800 s | 5.94x | 4 s |
| K2 | 1,800 s | 17 s | 10,800 s | 5.94x | 4 s |
| W0 | 30 s | 17 s | 600 s | 12.8x | 0.1 s |
| W2 | 1,900 s | 17 s | 10,800 s | 5.63x | 4 s; token queues do not query timestamps |
| W2m | 1,900 s | 17 s | 10,800 s | 5.63x | 4 s; token queues do not query timestamps |
| W2c | 1,900 s | 17 s | 10,800 s | 5.63x | 4 s, measured with profiling |

The wrapper rejects any watchdog smaller than both 300 seconds and four times
(expected work + JIT allowance). It permits at most 1,800 seconds for K0/W0 and
10,800 seconds for the longer windows. The commands use 600/10,800 seconds.
K1/K2 need longer estimates than the original packet because they enumerate all
GEMV candidates, both FFN formats and the additional sequential small-tuple owner.
The expected K2 duration is 1,800 seconds, not a short per-class timeout.

The 4-second per-submission budget is over four times the largest 2.14-ms
measured predecessor kernel and over four times the longest 2.3-ms large-GEMV
hypothesis. It is an explicit upper bound, not an expected latency. W0's 100-ms
budget similarly leaves a wide margin for its tiny chained kernels. The recorded
5-second driver-job bound is not changed by this packet. No kernel, firmware,
power, memory, swap or page-cache setting is changed.

Fixture submit waits are independently bounded at 300 seconds. Cooperative
teardown/draining is bounded at 60 seconds. The window watchdog is a campaign
safety bound and never substitutes for per-submission checking. W2/W2m avoid
profiling overhead, so their receipt labels the submission budget unmeasured;
K1/K2 and W2c provide explicit profiling checks instead of claiming token queues
measured it.

A fault or failure is recorded before teardown. One cooperative termination
request is permitted; a child still busy after its drain is retained for the
coordinator. No failed request cycles a server, resets a device or retries a
window. No hard-kill cleanup is part of these scripts.
