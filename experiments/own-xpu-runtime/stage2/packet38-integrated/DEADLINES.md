# Expected duration and watchdog

Estimates are reported only. They never stop work early. Every watchdog is at
least four times (expected +17 s first-kernel allowance) and at least300 s.

| Window | Expected seconds | Watchdog seconds |
| --- | ---: | ---: |
| K0 | 30 | 600 |
| K1a/K1b | 2400 each | 10800 each |
| K2 | 1800 | 10800 |
| W0p | 30 | 600 |
| KD | 1800 | 10800 |
| W2s/W2n/W2d/W2x | 1900 | 10800 |
| W2m/W2mc | 2100 | 10800 |
| WS/WSs | 7200 | 30000 |

Window overall deadlines include load/warm-up/all requests. Native mailbox waits
are bounded and check cancellation every10 ms. The Python supervisor polls at
50 ms during IPC and watches new journal lines every250 ms. Owner drain uses
60 s and wrapper ownership drain65 s; a remaining live owner is recorded, never
force-killed. Per-kernel profiled submission budget remains4 s. These bounds
are safety limits, not speed predictions.
