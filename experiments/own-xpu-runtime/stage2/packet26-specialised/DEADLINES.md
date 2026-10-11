# Packet 26 deadlines

No device ran during preparation. The expected durations below are conservative
planning allowances, not measured packet 26 speeds. Startup/JIT adds 17 seconds
to the work allowance. An expectation never signals a process or fails a run.
Only the independent watchdog, correctness failure, explicit stop or device fault
can do that.

| Window | Expected work, s | Expected with JIT, s | Per submission budget, s | Watchdog, s | Minimum accepted, s |
|---|---:|---:|---:|---:|---:|
| K0 | 30 | 47 | No device submissions | 600 | 300 |
| K1a | 1800 | 1817 | <4, measured | 10800 | 7268 |
| K1b | 1800 | 1817 | <4, measured | 10800 | 7268 |
| K2 | 900 | 917 | <=4, measured | 10800 | 3668 |
| W0 | 30 | 47 | <0.1, measured | 600 | 300 |
| W1 (optional) | 1900 | 1917 | 4, declared | 10800 | 7668 |
| W2 control | 1900 | 1917 | 4, declared | 10800 | 7668 |
| W2m measured dispatch | 1900 | 1917 | 4, declared | 10800 | 7668 |
| W2c profiling | 1900 | 1917 | <=4, measured | 10800 | 7668 |

Every accepted watchdog is at least 300 seconds and at least four times the
expected duration including JIT. K0/W0 accept at most 1800 seconds; others at
most 10800. `--seconds` changes only this watchdog. The per-event four-second
budget leaves a margin below the recorded five-second driver job timeout.

Token mode creates queues without profiling and never requests event timestamps.
Consequently W1/W2/W2m cannot measure or certify their per-event execution budget;
it is a declared admission budget, qualified by the measured fixture/canary/class
windows. They must not silently turn profiling on to claim otherwise. W2c checks
the budget using actual event timestamps. None of these event budgets is a total
window runtime bound. Native `--wait-seconds 60` is a separate cooperative wait
bound, including previously queued work, and is not a GPU execution measurement.

The wrapper polls the journal and child every 250 ms. Each journal call is bounded
at two seconds. On a fault, deadline or explicit stop it first saves its receipt
and boot latch, then sends one SIGTERM to its captured child PID. It gives the
child 60 seconds to drain and records a still-live PID if it does not finish.
There is no hard kill, retry, driver reset or automatic next window. Clean exits
receive five seconds of journal postflight; a current journal read can add up to
two seconds. Keep the owning user unit alive while a retained child remains.

The native failure helper flushes error text and the ownership snapshot before
teardown. It parks only when the final receipt reports genuinely in-flight work.
K0 only builds linked kernel images; it creates no queue and submits no work.
K1a and K1b are separately invoked fresh processes. K2's 200 repetitions per arm
are one registered measurement window, not a retry after failure.
