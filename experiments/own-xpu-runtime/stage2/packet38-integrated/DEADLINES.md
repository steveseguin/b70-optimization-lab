# Expected duration and watchdog

The wrapper refuses a launch unless `(expected + 17 seconds) <= watchdog / 4`,
with a minimum 300-second watchdog. The 17 seconds allow first-kernel startup.
This is a prelaunch admission check, not an early runtime stop. A caller-supplied
watchdog is checked too, including zero. Estimates are not measured speed claims.

| Window | Expected seconds before allowance | Watchdog seconds | Basis and uncertainty |
| --- | ---: | ---: | --- |
| K0 | 30 | 600 | Small bundle-build window; earlier K0 passed. Startup varies. |
| K1a/K1b | 120 each | 10800 each | Earlier fresh-owner runs took about 100 seconds each; round up to two minutes. All 66 QSA exactness lengths remain. |
| K2 | 1596 (26.6 minutes) | 10800 | Six shapes × measured 216 seconds/shape + about 300 seconds for the remaining/GEMV work from packet37. Conservatively gives no credit for the resident-buffer repair. |
| W0p | 30 | 600 | Small 1,000-handover canary; planning estimate, unrun here. |
| KD | 1800 | 10800 | Two fresh draft capture owners, roughly 900 seconds each including loading; unmeasured packet38 planning allowance. |
| W2s/W2n/W2d/W2x/W2c | 1900 each | 10800 each | One load, prompt processing and 64-token diagnostic request; inherited planning allowance, no packet38 measurement yet. W2c is the wrapper's class-profile alias. |
| W2m/W2mc | 2100 each | 10800 each | Same request with draft load/work and profiling allowance; inherited planning allowance, unmeasured here. |
| WS/WSs | 7200 each | 30000 each | Persistent ranks, one load/warm-up and 24 requests (12 prompts × 2); two-hour planning allowance, unmeasured here. Re-estimate from W windows before admitting a larger suite. |

K2's admitted estimate is **1613 seconds (26 minutes 53 seconds)** including
startup, below its 2700-second quarter-watchdog budget. Its previous 66-shape
configuration implied 14,556 seconds before startup (66 × 216 + 300), not 1800:
it could not fit even the whole 10,800-second watchdog. The partial run was
cooperatively stopped without a GPU fault; see
[evidence](evidence/20261012-k2-grid-exceeds-watchdog/README.md).
The resident QSA repair removes large setup costs but has no new device duration
measurement. Use K2b to replace this conservative estimate with observation.

Window deadlines include load, warm-up and all requests. Native mailbox waits
check cancellation every 10 ms. Python polls IPC every 50 ms and the new kernel
journal every 250 ms. Owner drain is 60 s and wrapper ownership drain 65 s;
a remaining live owner is recorded, never force-killed. Per-kernel profiled
submission budget remains 4 s. These are safety limits, not speed predictions.
