# Packet 24 deadlines

No device ran. These are conservative planning estimates inherited from earlier
windows, with 17 seconds added for first-use JIT. They are not packet 24 measured
runtimes. Expectations are recorded only: only the admitted watchdog, a failed
correctness check, a driver fault, or an explicit signal stops a window.

| Window | Expected work, s | JIT allowance, s | Expected total, s | Submission budget, s | Default watchdog, s | Minimum accepted watchdog, s |
|---|---:|---:|---:|---:|---:|---:|
| K0 | 30 | 17 | 47 | No device submission | 600 | 300 |
| K1a / K1b | 1800 | 17 | 1817 | <4 | 10800 | 7300 |
| K2 | 900 | 17 | 917 | <=4 | 10800 | 3668 |
| W0 | 30 | 17 | 47 | <0.1 | 600 | 300 |
| W2 | 1897.718 | 17 | 1914.718 | 4 | 10800 | 7659 |
| W3 | 1200 | 17 | 1217 | 4 | 10800 | 4868 |
| W2k (profiling) | 1897.718 | 17 | 1914.718 | 4 | 10800 | 7659 |

The optional one-card W1 retains the W2 estimate and limits. Every watchdog is at
least 300 seconds and at least four times its expected total. K0/W0 accept at most
1800 seconds; other windows at most 10800. A changed watchdog must pass these
bounds. K1's 7300-second floor includes an additional margin above four times its
estimate. The driver job timeout is five seconds; the four-second submission
budget keeps a margin. K0 performs JIT only and creates no queue.

The wrapper polls the kernel journal and child at 250-ms intervals. Journal calls
have the retained two-second bound. On a fault, deadline, or signal, it writes the
boot latch and sends at most one SIGTERM. Cooperative drain is bounded at 60
seconds; it then records a still-live child for the coordinator, without a hard
kill. Postflight journal checking lasts five seconds. Owner teardown has its
existing bounded drain and preserves in-flight IDs on failure. Failure never
queues another launch or resets the driver. Source, binary, input, oracle, and
prerequisite-receipt hashes are checked before admission and after execution.

K2's native per-sequence event wait is 60 seconds, its owner teardown is 60
seconds, and every measured GPU event must remain at or below four seconds.
Its 200 repetitions are one preregistered experiment, not a retry loop.
