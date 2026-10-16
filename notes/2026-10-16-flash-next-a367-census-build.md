# A367 M=2 diagnostic census CPU build — 2026-10-16

Built [a separate sealed packet](../experiments/own-xpu-runtime/stage1/packet4-prep/a367-census/README.md)
from replay `7aca7df2a` (seal `bb473f8e`). No GPU, health probe, model weight read,
server launch, privileged command or host setting change ran. Replay,
calibration, driver and the clean runtime source were not edited. The record
remains 46.854250 tok/s; today's 47.110 exact reproduction remains its own receipt.

The memory watcher now samples on its fixed 0.5-second cadence while a separate
thread reads rank RSS/cgroup attribution. Rows carry the scan's start time;
plateau requires all four ranks, cgroup current and age at most two seconds.
The blocked-read test proves attribution cannot delay memory samples. The
cmdline-once cache, ESRCH handling, 1.5-second gap trip, reserve, local ext4
scratch, short RPC path and all admission/exit/watch gates remain.

One client sends code-review and customer-email, once each, at 128 tokens,
temperature 0, seed 20260609 and thinking off. Its first 128 IDs are compared with
the A367 record. Mismatch is a finding; malformed/missing/stale-cache evidence
still fails. This is a diagnostic subset and its final promotion gate stays false.

## Tracing decision

Graph kernel visibility is **unproven**, not established as impossible.
The source-built PTI contains graph hooks, but Laguna eager device tracing
failed and its graph arm never ran; another paused Laguna trace stalled during
startup; DeepSeek device timestamps killed a worker. See the [feasibility
record](../experiments/own-xpu-runtime/stage1/packet4-prep/a367-census/TRACING-FEASIBILITY.md)
for exact paths, source anchors and citations. No old unsafe flag combination
is silently repeated. Three arms are preregistered and CPU-built:

1. `graph-reference`: untraced diagnostic timing/output reference, first.
2. `graph-census`: conditional unchanged-graph device visibility experiment.
3. `eager-census`: conditional graph-off device census, explicitly eager.

Each needs a separate bound owner window. No automatic fallback, retry or
follow-on launch exists. The tracer wraps only the server and starts paused.
Resume acknowledgement precedes marker enablement after plateau/delay; finally
removes markers and pauses. Its finite 4096-record buffers and unique session
retain per-process traces under the RAID run directory. Unit control uses exec
semantics under these flags, preserving the captured API PID for one SIGINT.

Host-only ITT wrappers preserve arithmetic and use metadata only. Graph scopes
wrap actual replay. Draft proposer scopes report **B=batch size**, not model M.
The CPU analysis joins same-thread host scopes to H2D flow IDs to device kernel
IDs. It does not assume asynchronous kernels execute inside host timestamps.
Rank receipts, trace hashes, run identity and admitted arm are checked. Unknown
families and missing correlation remain explicit; prefill and other target
scopes are separate from requested verify/draft coverage. Outputs are
`census.json` and `census.md`; lifecycle is `census-run.json`. Kernel sums, busy
union, wall span and real idle gaps stay distinct. Ranked sinks and small-kernel
clusters cite the design dispatch audit and exact-preserving boundaries.

The tracer executable and DSO were hash-checked only. No tracer smoke ran:
source `tools/unitrace/src/tracer.h:49` calls `InitializeL0`, which calls
`zeInit(ZE_INIT_FLAG_GPU_ONLY)` in `src/utils/utils_ze.h:26-30`, even for ITT-only
initialization. A `/bin/true` target alone would not establish no-device access,
so this build does not claim runtime tracer qualification.

## Size, memory and open risks

Expected trace output: **0.2–2 GiB**; additional tracer host memory:
**0.25–1 GiB**, with **1 GiB planning allowance**. These are estimates, not
measurements or upper bounds. Replay's approximately 1.9 GB headroom above the
reserve would fall to about 0.8 GB with 1 GiB tracer memory. The proposed minimum
start floor cannot cover measured generation need plus reserve even before
tracing; owner acceptance does not guarantee fit.

The planned whole-run write budget is 10 GiB. A separate size watcher requests
one graceful stop at 8 GiB, retaining 2 GiB for drain; a final after-exit size
receipt fails above 10 GiB. It is not a filesystem quota. Buffered writes can
overshoot the soft stop. Scratch remains local ext4, bulky output stays RAID.
Offline analysis runs after complete exit/watch, one trace at a time with a
1 GiB per-file bound; larger evidence needs reviewed offline sharding.

Device visibility, actual ITT emission, four-rank complete correlation,
tracing memory and write peaks remain unmeasured. Generic GEMMs may require
reviewed family mappings. Trace startup/teardown can stall; paused collection
is not free. Graceful teardown and client draining have soft limits, never kill
escalation. Owner-window expiry may preempt the workload. Eager times cannot be
used to fill graph timing buckets, and no timing here is a benchmark headline.

## CPU validation and review

**399 tests pass**: census 166, replay 84, calibration 75, driver 59, payload 6,
tree 9. All four active seals have **zero mismatches**. Three plan arms are
CPU-only; shell and Python syntax checks pass. [Final receipt and logs](../data/2026-10-16-flash-next-a367-census-build/cpu-tests.json).

The first aggregate runner forgot the old suites' OMP=2 test environment and
resolved driver-relative seal paths against the repo. Those harness mistakes
caused two failing suites and nine false missing-file reports. The runner was
fixed without modifying protected packets, then all suites passed. Initial
receipt/calibration/driver logs are retained alongside final evidence.

Parallel tracing research and independent read-only diff review were used.
Review caught and closed the sampler publication race, final output accounting,
rank and arm evidence binding, draft dimension labeling and expected-outside-
scope coverage. Independent latest targeted checks passed 82 tests; no remaining
blocker was reported. These overlap the 399 tests and are not added to that count.

## Seal and pending owner approval

- Preregistration SHA256: `3b25693a7d6b2d004f0a669d768195f2d85347a699eccd2c0e0152b25009f569`
- Seal SHA256: `658a24d1f2f795d6593e614b0a5b1cce261d90a6793977c6f757f038a5253092`
- Pending approval remains **approved=false**.
- [Exact script-file launch/check sequence](../experiments/own-xpu-runtime/stage1/packet4-prep/a367-census/LAUNCH-RUNBOOK.md).

Exact approval sentence:

> I authorize one A367 diagnostic census on steve-b70s with a census-only MemAvailable start floor of 114840824 KiB, a 0.5-second watchdog and the 12000000 KiB live reserve, under preregistration SHA256 3b25693a7d6b2d004f0a669d768195f2d85347a699eccd2c0e0152b25009f569 and seal SHA256 658a24d1f2f795d6593e614b0a5b1cce261d90a6793977c6f757f038a5253092. Tracing is diagnostic and makes no speed claim. This accepts the unmeasured tracer and generation-memory risk, does not lower the packet-4 fixture floor, and does not resolve the halt or authorize another launch.

The owner/coordinator records this sentence and binds the selected arm in a
fresh owner-window before any device action. No approval is being requested or
recorded by the CPU build itself.
