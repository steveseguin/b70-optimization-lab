# Expected durations and watchdogs

Estimates are reporting only. Watchdogs are at least 300 seconds and at least
four times the estimate, including the inherited 17-second startup allowance.
These are conservative operational allowances, not measured packet40 speeds.

| Window | Expected work seconds | Default watchdog seconds |
| --- | ---: | ---: |
| K0 | 30 | 600 |
| K1a, K1b | 2400 each | 10800 each |
| K2 | 21600 | 86468 |
| W0p | 30 | 600 |
| KD | 1800 | 10800 |
| W2m-speed, W2m-exact, W2mc | 2100 each | 10800 each |
| WS64, WS64x, WSs | 7200 each | 30000 each |
| WS128, WS128x | 14400 each | 60000 each |

Suite allowances scale with requested repeats. The maximum admitted window is
172800 seconds. No estimate itself terminates work. Native waits use absolute
deadlines and cancellation checks; the Python supervisor polls IPC and fresh
kernel log lines. Cooperative owner drain is bounded to 60 seconds and wrapper
ownership drain to 65 seconds. A remaining owner is recorded and retained,
never force-killed. No failed window restarts.

K2 retains all 66 QSA lengths and 200 repetitions. Packet38's observed grid
needed more than four hours before other classes, so the former three-hour
watchdog was inadequate. The six-hour planning allowance and
`4 * (21600 + 17) = 86468` second watchdog are operational bounds, not a
packet40 duration measurement or throughput prediction.
