# Flash-Next immediate-exit fault reproduced — 2026-10-10

**Verdict: immediate abrupt exit after local-reference release reproduces the
exit fault; orderly cleanup and the ten-second-idle variant passed.** This
supports the teardown/lifetime class in the preregistered table. It does not
identify the native allocation or certify the complete four-rank remedy.

This is CPU-only analysis of saved evidence, at nice 19 with
`OMP_NUM_THREADS=2`. No GPU/device, container, server, launch, systemd, port
8188 or LTX unit operation was performed. Existing run directories and the
host halt were read only. The coordinator's native runs are distinguished
below from this documentation task; no native tests were repeated.

## Evidence, identity and timestamps

Paths abbreviated `runs/` are beneath `../reopen-20261008/`. The new window
used card `0000:23:00.0`, boot `4aafe57b-a54f-4bfd-b4ed-9f1cbb8830c7`, image
UMD `image-26.27.39122`, and image
`vllm/vllm-openai-xpu@sha256:e4446310b1d30015e8fdc1a0a2ef1669ac6bef857cbe772487571ed5c1a926a9`.
The slab arms share source SHA-256
`a5bec8bb47799547bd814789b3b0b9395327768f317c99e341002ffa527e1558`,
indirect gather, exact-size pinned policy, input hash and expected/output hash.
Each completed one gather and one explicit synchronization. They differ in
exit mode/timing and health/window; this is not a randomized repeat series.
The owner receipt and host watcher admitted the runs before the third fault.

| Saved run | Outcome | Scope |
| --- | --- | --- |
| `probe-clean-exit-20261010b` | Passed; exact bytes; cleanup sync 1; watcher passed, zero new faults | Explicit release/cache cleanup and normal exit |
| `probe-exit-sleep-20261010b` | Passed; exact bytes; cleanup sync 0; watcher passed, zero new faults | Local-reference release, ten-second idle, then abrupt exit |
| `probe-first-forward-20261010c` | Passed; `bytes_equal=true`, `teardown_complete=true`; watcher passed, zero new faults | One rank/layer, production-size host allocations, applied teardown |
| `probe-abrupt-immediate-20261010c` | Failed postflight; bytes equal, worker wait status 0, four new fault-class lines | Local-reference release followed immediately by `os._exit(0)` |

The failed receipt remains `stage=bytes_equal_waiting_postflight`,
`passed=false`, with `postflight_exception` reporting the watcher STOP.
The watcher's failure is the intended fault detection, not an admission bug.
The four classified lines are **one new incident**, the third on this boot.

All times below are UTC on October 10. Slab markers come from each
`receipt.json:lifecycle`; first-forward markers come from `stages.jsonl` and
`teardown/loader-7.jsonl` in its run. Kernel microseconds come from the failed
receipt and `watcher.json:journal_admission.counted_fault_lines`, whose saved
`-04:00` times are converted to UTC. The run's
`kernel-fault-window-*.log` and `watcher.log` corroborate the event at
second resolution.

| Arm / event | UTC |
| --- | --- |
| Clean comparison complete | 17:45:47.743568 |
| Clean `before_free` / `after_free` | 17:45:47.744141 / 17:45:47.881249 |
| Clean `before_exit` | 17:45:48.184720 |
| Sleep `after_return` | 17:46:20.236139 |
| Sleep `idle_begin` / `idle_end` | 17:46:20.236435 / 17:46:31.192302 |
| Sleep `before_exit` | 17:46:31.192889 |
| First-forward mixed result complete | 18:06:42.614796 |
| First-forward rank receipt: drained / UVA released | 18:06:43.521022 / 18:06:44.330555 |
| First-forward rank receipt: pinned released / post-cache sync | 18:06:44.588285 / 18:06:45.374527 |
| First-forward rank receipt complete / before normal exit | 18:06:45.374583 / 18:06:45.376260 |
| First-forward guardian observes worker exit, code 0 | 18:06:47.114716 |
| Immediate comparison complete | 18:07:18.962362 |
| Immediate `before_return` / `after_return` | 18:07:18.962720 / 18:07:18.963156 |
| Immediate `before_exit` | 18:07:18.963453 |
| First `Fault response: Unsuccessful -ENOENT` | **18:07:19.034122** |
| BCS engine memory CAT error / BCS engine reset | 18:07:19.034343 / 18:07:19.034654 |
| Second `-ENOENT` fault response | 18:07:19.036484 |

Only **0.297 ms** separates the immediate arm's after-return and before-exit
markers; the first logged fault follows before-exit by **70.669 ms**.
The sleep arm leaves **10.956750 s** between after-return and before-exit,
including its fresh watcher handshake. These are marker/log intervals, not
measurements of the exit instruction, faulting instruction or VM-close time.
The last clean immediate-arm watcher sample was updated at 18:07:18.248575;
it does not provide continuous observation up to exit.

Original new-window receipts remain host-local/untracked at review time;
this commit records their paths, hashes and selected contents without changing
or staging them. SHA-256 (`receipt.json`, then `watcher.json`):

- `runs/probe-first-forward-20261010c/`:
  `f9f8dbcd62ed8b70906fe6f288e9dde77ec848f661405ed3c8abc23af4cfe045`;
  `4a7a4861613b349af50439dad1e52a4d65baa7a88342439c98a5ae5f789b7384`.
- `runs/probe-abrupt-immediate-20261010c/`:
  `57abc1bd9f026356feba884c01724d16cd5251c4c71810ad29a1ba78b7c868ff`;
  `f8e6ecec527d577c78c4c9b58c69e72a00fbd834a47a769e46819c9ce54efc76`.

The earlier clean/sleep receipt hashes and tracked copies are in the
[earlier result note](2026-10-10-exit-probes-result.md#saved-results) and
[evidence index](../reopen-20261008/evidence/exit-probes-20261010/index.json).

## Interpretation against the preregistration

The [table's “Clean exit clean; abrupt exit faults” row](../reopen-20261008/probe/README.md#preregistered-interpretation)
now applies. It supersedes the first window's provisional “Both clean” verdict.
The supported candidate is **abrupt process exit while native work or mappings
may still be live immediately after release**. Abrupt exit after ten seconds
passed, so “any abrupt exit always faults” is not supported. Nor is a repeatable
failure rate established by one new immediate arm; the halt marker's word
“deterministically” is the coordinator's description, not a statistical result.

The gather had already synchronized and its blocking readback matched exactly.
Do not call this an unfinished gather or a proven pending payload copy. Dropping
Python references is a request to release ownership, not a census of native
queues or mappings. The changed interval can allow completion of runtime
commands/event markers, deferred frees and pinned-USM unmap work before process
VM teardown. Runtime-owned queue/ring mappings are another candidate. No saved
trace identifies which of those was pending or when a pinned allocation was
actually unmapped. The 3 MiB slab exceeds the 1 MiB cache threshold; it cannot
simply be assumed to remain cached. See the
[source/ownership audit](2026-10-09-exit-lifecycle-analysis.md#what-actually-survives-the-original-worker).

Both immediate and sleep modes drop the same Python local references before
exit. The ten-second arm adds elapsed time and a watcher handshake, not normal
native finalization. Its pass makes timing relevant; sleep is neither a proven
synchronization primitive nor a production remedy. Clean exit adds ordered
release, another sync, cache release and interpreter/native finalization.
It is the production remedy to qualify. These results do not uniquely separate
slab lifetime from internal queue/ring lifetime or prove a particular driver bug.

The two October 9 tiny probes also returned exact bytes and dropped locals
before immediate abrupt exit: image UMD fault at **01:39:27.868476 UTC**;
host UMD fault at **02:27:32.185435 UTC**, both BCS `-ENOENT`/reset. The new
reproduction strengthens their common exit-boundary explanation and further
weakens “image UMD version alone” as the discriminator. Their exact native
mapping/queue cause remains unidentified.

**Attempt 7 remains a separate unresolved startup incident.** Its first CCS
fault on October 8 was **21:11:18.369060**, before the recorded controller
SIGINT completion at **21:11:19.113462** and all recorded crash/death reports.
All four workers still had positive RSS immediately around that fault.
It was profiling a full TP4 model, not the tiny post-readback exit. The
[later ordering audit](2026-10-09-attempt7-ordering.md) takes precedence over
inferences from untimed stacks: no evidence establishes that teardown caused
its first fault. Unobserved earlier native failure/VM closure remains possible.
The first-forward pass narrows the one-layer mixed-host compute concern, but
cannot clear 96 allocations/rank, full PLE, TP4/collectives, complete startup
or model outputs. The October 8 Screen 1 fault also preceded its OOM victims;
do not relabel all incidents as one proven exit bug.

## Required worker exit path and remaining qualification

The already-applied [teardown overlay](../reopen-20261008/overlay-fix-teardown/README.md)
must be the **only cooperative exit path for every Flash-Next worker** in this
Screen 1b configuration: normal return, calibrate-load, partial construction,
recoverable exceptions/allocation failure, SIGINT and SIGTERM. Signals request
cancellation; they must not interrupt cleanup. Stop new work, drain streams,
release graph/table/UVA aliases before pinned owners, close PLE, release
registries/worker/pools/communicators in the reviewed order, then final sync,
device/host cache release, post-cache sync and normal process finalization.
Require each rank's complete ordered receipt and clean post-worker kernel
checks. No direct `os._exit` or supervisor kill is an acceptable success path.

The first-forward diagnostic applied overlay manifest
`e00bb55d8378ecd0065e82a8c3b6fdd59268bd33aae6e0f356ca48f067926f2d`.
Its all-device control and mixed-host path produced identical output hash
`b81ca57210a8451892d470c260ac0ec663346690b41e86a550608cecf0c592ab`,
using 88,473,600-byte w13 and 44,236,800-byte w2 host allocations.
Rank 0 completed all 17 teardown phases. This is native one-layer diagnostic
support, not four-rank shutdown or whole-model qualification. The receipt says
`native_queue_destruction_verified=false`; native signal/VM-close tracing was
unavailable. Partial-load, SIGINT/SIGTERM and full four-rank native exits plus
unchanged exact-output/fresh-runtime gates remain open. No speed claim follows.

A catchable OOM/allocation exception can unwind through teardown if the runtime
can still drain. **Kernel OOM kill, SIGKILL, fatal native crash, host failure or
an external forced kill cannot be made graceful by Python.** Prevent avoidable
OOM exposure before allocation: the 96 GB load guard checks projected pressure,
bounds staging and cancels while workers can still drain; the independent
24 GiB available-memory watchdog retains reserve. These reduce OOM risk, not
guarantee its absence under every race or native allocation. Do not lower caps,
allow swapping, loosen guards or kill a stalled synchronization as cleanup.
A failed/hung release parks and preserves the worker for owner intervention.

A direct-pointer or “abrupt with references retained” arm is **not recommended**
now. Retaining owners is a different experiment from both October 9 probes;
changing to direct addressing would add another variable. The immediate arm
has reproduced the fault, and neither arm would qualify the production remedy.
Do not spend another fault window on it unless a later, specific unresolved
mechanism requires it and is separately authorized.

## Halt and next step: attempt 8, text only

At review, the coordinator's halt remains at
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/FAULT.json`, written
18:08:23 UTC, SHA-256
`e87bb120bfd5e95a2dde3217e28af9e4bd862496b9ac69413950a62c9b669cc6`.
It was not removed or altered. The saved bounded post-incident health receipt
`experiments/ltx25-b70/data/resume-20261008/postflight-after-third-incident-20261010T180823Z.json`
ran **18:08:43–18:08:48 UTC** and reports **passed**, four exact copy
roundtrips/repeat GEMMs and no new probe-window fault lines. It separately
counts eight earlier fault-class lines on this boot.
Its SHA-256 is `4b69313e806e9ee49fa6d9e8106a6bacc9c116ea12d0374c01bf4cd19f5900ad`.
Passing bounded health does not resolve the third-incident halt or prove safety.
No further health probe, restart, reset or reboot was performed here.

After the owner resolves the halt, recommend **one Screen 1b calibrate-load
attempt 8 under the teardown overlay**, with no generation and no automatic
MTP1 follow-up. It measures full loading/startup/plateau and four-rank teardown.
Keep the immutable image, exact large pinned policy, placement, 4 GiB PLE cache,
0.90 utilization, target arithmetic and full 16-bit KV unchanged.

[ATTEMPT7-BUDGET](../reopen-20261008/ATTEMPT7-BUDGET.md#revised-budget) uses
measured earlier inputs but its totals are **predictions**, not certified bounds:
76.374190 GB steady, 76.642626 GB loading, 78.790109 GB including an assumed
2 GiB later retention, 83.085077 GB also allowing a desired 4 GiB file working
set. Attempt 7 actually reached **79.208 GB** pressure and a **41.882 GiB**
minimum available-memory reading before fault; no ready plateau was measured.
Retain **96,000,000,000 bytes** as the load-only ceiling. At the saved MemTotal,
that leaves 28.179132 GB available, 2.409329 GB above the unchanged 24 GiB
watchdog line. It is not a serving-memory allowance or proof of full-size fit.

Preconditions, all required before the coordinator executes any launch:

1. Explicit owner decision resolving this third incident and accepting the new
   Flash-Next window. The host `FAULT.json` must be absent **as a result of that
   authorized resolution**, not deleted by this task or by a launcher.
2. Fresh passing four-card health from the admitted boot/window, younger than
   six hours, clean journal since health, and no later fault. The saved passing
   post-incident probe alone grants no permission.
3. Exclusive idle four-card window and at least five minutes after the previous
   server's completed stop; no displacement of LTX or contact with port 8188.
   FAULT absence and this gap are coordinator preconditions, not checks to assume
   `screen.py` enforces automatically. Lane port 19988 must be available.
4. Existing image/model/overlay identities pass their checks; a new, nonexistent
   attempt-8 directory; sufficient disk and host/device memory. Preserve all old
   STOP files and run directories. The coordinator owns the later long-job unit.

**Admission caveat:** `screen.py` accepts only the old, hash-pinned owner receipt
at 01:18:31 UTC for boot `4aafe57b`. Every fault at/after that acceptance refuses;
the third incident therefore invalidates its use even with fresh health.
A new path passed to `--owner-acceptance` is not currently supported. If the owner
accepts continuing this same boot, first separately review/pin that new decision
and update/test admission without weakening the stop rule; no such runtime edit
is made here. Do not edit the old receipt or reuse its cutoff. On an
owner-authorized **fresh clean boot**, omit the old flag because its boot ID
cannot match; the owner's authorization remains a prerequisite outside the CLI.

The exact existing-interface command below is for that **fresh-boot case only**,
after every precondition above. It is text, not executed or queued. Its wrapper
limits this command's CPU scheduling/threads; it does not claim the later
systemd worker inherits those settings.

```sh
nice -n 19 env OMP_NUM_THREADS=2 SCREEN_PRIVILEGED_FD_SCAN=1 python3 \
  /home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/reopen-20261008/screen.py run \
  --mode calibrate-load --loading-ram-guard-gb 96 \
  --health-receipt /PATH/TO/FRESH-SAME-BOOT-HEALTH-RECEIPT.json \
  --run-dir /home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/reopen-20261008/runs/screen1b-mmap-calibrate-load-20261010-attempt8 \
  --execute
```

Exact stop and acceptance rules, retained from the
[controller](../reopen-20261008/screen.py),
[calibration](../reopen-20261008/calibration.py) and teardown contract:

- First fault response, CAT error, engine reset, timed-out job, coredump,
  native crash, exception, failed check, missing required journal/identity
  evidence or STOP ends submissions. Preserve evidence and the halt; no retry,
  second arm, automatic recovery or restart loop.
- Before allocation, projected pressure **>96 GB** cancels loading. The
  0.5-second watchdog stops at **MemAvailable <24 GiB**, any reported card's
  **free VRAM <2 GiB**, or failed required host observations. Unknown VRAM
  cannot qualify a later run. Guards remain cooperative STOP/one-SIGINT paths.
- Readiness has a **1,800-second** bound. After healthy readiness and the
  expected model ID, collect a **20-second plateau**, then stop once. No
  generation request. Observe shutdown for **300 seconds**; if incomplete,
  preserve container/workers for the owner, never escalate to forced kill.
- A clean exit requires four ordered `rank_teardown_complete` receipts,
  container exit 0 without OOM/error, idle cards and clean kernel postflight.
  Missing native completion is a failed attempt even if container exit is 0.
- Calibration qualification additionally requires at least 40 plateau samples,
  no sample gap >1.5 seconds, complete worker/cgroup accounting, observed
  loading/plateau host peak **<=90 GB**, plateau pressure **x1.15 <=90 GB**
  (plateau <=78.260870 GB), and known **>=4 GiB free on every card** throughout
  loading/plateau. The 96 GB cancellation ceiling does not relax these gates.
  Any failure forbids automatic MTP1 admission; a passing calibration still
  needs review and the separate quality/fresh-runtime/performance gates.

This documentation change modifies no runtime, overlay, receipt or guard.
Validation is limited to cross-checking the saved JSON/timestamps/hashes,
command/source review and Markdown/diff integrity; it adds no native result.
