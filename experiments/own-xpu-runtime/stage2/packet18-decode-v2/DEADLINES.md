# Packet18 / packet20 deadline audit — October 11, CPU only

No device ran. No Level Zero discovery or `/dev/dri` access was used. The host
is in FAULT HALT; PID 183867 is untouched. These are future admitted-window
settings, not permission to run a device.

Ratios below are **limit / reference**, not a measured device speed claim.
No packet18 W0 or packet20 device run exists. Use the former W0 30 s planning
expectation plus the coordinator-reported packet13 ~17 s first-layer startup/JIT
measurement = **47 s** as a conservative W0 sizing proxy. For packet20 use its
upper 50 s work estimate plus 17 s = **67 s**. The 17 s is transferred evidence,
not a measurement of either new binary; first device qualification remains open.
W1/W2 use the larger of the old 1,200 s planning estimate and the retained
[frozen CPU gate](cpu-real-frozen.json)'s **1,897.718 s**, then add 17 s:
**1,914.718 s**. W3 uses max(1,200 s planning, [R5 CPU](cpu-real-r5.json)
913.907 s) + 17 s = **1,217 s**. These deliberately conservative proxies are
not comparable benchmark results. The old packet13 5,247 s path predates the
qualified parallel non-GEMV path; it is not this window's execution estimate.

| Packet / timer | Measured or estimated reference | Limit | Ratio (default; minimum) | On expiry / excess |
| --- | --- | --- | --- | --- |
| 18 W0 child watchdog | 47 s planning proxy including first JIT | 600 s; allowed 300..1800 | 12.77×; 6.38× | One SIGTERM to captured child, fault latch; no retry/kill |
| 18 W1/W2 child watchdog | 1,914.718 s conservative CPU + JIT proxy | 10,800 s; allowed 7,800..10,800 | 5.64×; 4.07× | One SIGTERM, latch; no retry/kill |
| 18 W3 child watchdog | 1,217 s planning + JIT proxy | 10,800 s; allowed 7,800..10,800 | 8.87×; 6.41× | One SIGTERM, latch; no retry/kill |
| 18 W1/W2/W3 native cooperative deadline | Same proxies; clock starts at Engine construction | Same `--seconds` as watchdog | At least the above ratios | Stop new work, attempt safe teardown/retain owner; no native signal |
| 18 W0 total expectation | Old 30 s estimate; retained pre-fix CPU mock 1.981 ms is not a device estimate | 30 s **report only** | Not a limit | Finish normally; set `total_expectation_exceeded`; never fails total time |
| 18 W0 aggregate device-work duration | No device measurement; new CPU mock has only work wall time | **No limit** | N/A | Record separately, exclude startup/JIT; no signal or pass gate |
| 18 W0 individual submission budget | Tiny 64-lane kernels/copies; native duration unmeasured | <100 ms profiled execution (10× below 1 s) | Device reference unavailable | Finish coverage and safe teardown; final receipt fails budget, no signal |
| 18 W0 completion waits / explicit teardown | Tiny work; no native measurement; waits begin after bundle preparation/submission | 5 s (formerly 1 s) | 50× the 100 ms submission budget, not a measured ratio | Failed wait retains ownership through safe drain or hold; no signal |
| 18 W1–W3 operation drain / teardown; 18 owner exception-destructor drain | Native batches/cleanup unmeasured | 60 s | N/A | Stop submissions; drain or retain owner, no signal |
| 20 child watchdog | 67 s planning proxy including first JIT | 600 s; allowed 300..1800 | 8.96×; 4.48× | One SIGTERM to captured child, latch; no retry/kill |
| 20 total goal | Original <60 s desired outcome | 60 s **report only** | Not a limit | Complete full matrix and teardown; `total_goal_exceeded=true` may pass |
| 20 native admission | Former 50 s cutoff removed | **No elapsed-time cutoff** | N/A | Only actual stop request / errors prevent new work |
| 20 completion poll / queue-empty / raw event+list+queue / owner copy+marker wait | Submission chains unmeasured; former 900 ms bound was not a measurement | 5 s (formerly 900 ms) | Native reference unavailable | Hold owner/resources; no signal or automatic retry |
| 20 native teardown | Already-completed work, unmeasured | 3 s | N/A | Unsafe drain parks owner; no signal |
| Both watcher drain after SIGTERM | Coordinator handback bound, not a healthy-runtime estimate | 60 s (20 formerly 5 s) | N/A | Return `child_still_running=true`; leave process/unit alive, no further signal |
| Both kernel journal subprocess | Five CPU-only reads; max 0.048036 s ([receipt](deadline-journal.json)) | 2 s | **41.64×** | Kill only timed-out journal helper; loss of monitoring latches and requests one child SIGTERM if live |
| Both loader `ldd` preflight | CPU helper, no device child exists yet | 10 s | N/A (no GPU signal) | Refuse before output/latch/native launch |
| Both `ionice -p` preflight | CPU helper, no device child exists yet | 2 s | N/A (no GPU signal) | Refuse before native launch |
| 18 / 20 postflight journal tail | Sampling duration after child exit | 5 s / 3 s, plus at most 2 s for last journal read | N/A | End sampling; faults/errors fail receipt; child already exited |
| Native synchronous runtime/JIT/queue APIs and retained-owner hold | Unmeasured blocking driver work | No unsafe hard deadline | N/A | Watchdog remains the only total-time signal deadline; a retained child is the coordinator's responsibility |

The 250 ms (packet18) / 50 ms (packet20) watcher polling intervals and native
100 microsecond / 1 ms polling sleeps are cadence, not expiry deadlines.
No shell `timeout`, systemd runtime limit, cgroup kill or shortened external
supervisor deadline may be wrapped around these commands. Preserve an owning
unit when the watcher hands back a live PID. The existing fault/signalled-stop
policy is unchanged; this repair does not authorize recovery.

## Timing definitions and gate reuse

W0 pre-materializes the executable SYCL bundle for both queues. Its
`startup_jit_ms` is that startup phase; `device_work_ms` is the sum of profiled
recorded event execution intervals, not the work-phase wall clock. Host/mock
runs have no device profiling and report zero device milliseconds. There is no
aggregate work bound needing a CPU-to-device margin. The fixed per-submission
100 ms gate is evaluated after completion and reported after normal teardown.

Packet20 startup/JIT includes initial bundle creation and each method's setup
(raw module JIT, queue/graph setup). `device_work_ms` is the sum of timestamp
**envelopes including host issuing gaps**, not pure kernel time. The original
per-row profiled spans and setup times remain available. Total wall goals never
change pass/fail. Native and watcher elapsed times are recorded separately.

Packet18's [reuse audit](deadline-reuse.json) retains original numerical and
sanitizer receipts, verifies unchanged numerical inputs and reverses the exact
model-neutral main/default and W0-only backend helper edits to their old hashes.
The canary branch is isolated and freshly CPU-tested. Old receipts are never
rewritten as new executions. Packet20 reuses unchanged fusion compiler/fixture
receipts with byte/hash checks; the changed issuing binary is freshly compiled.
