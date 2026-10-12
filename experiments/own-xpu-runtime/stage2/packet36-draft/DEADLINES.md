# Expected durations and watchdogs

No expected duration is a measured speed or an early kill deadline. Every
watchdog is at least four times its estimate (plus the inherited 17-second
allowance), and at least 300 seconds. No watchdog relaunches a process.

| Window | Expected seconds | Watchdog seconds |
| --- | ---: | ---: |
| K0, W0p | 30 | 600 |
| K1a, K1b, K2, KD | 1800 | 10800 |
| W2s, W2n, W2d, W2c | 1900 | 10800 |
| W2m, W2mc | 2100 | 10800 |

The draft's cooperative 300-second provider budget is checked between submissions;
its expiry drains and permanently disables the provider. It cannot preempt a
stuck device kernel. Each owner drain retains the inherited bounded deadline and
ownership rules. Fault/owner failure follows WINDOW.md, never fallback execution
on a busy queue. The 50ms injected stall is a CPU test fixture, not a watchdog.
