# A367 M=2 diagnostic census packet

CPU build only, October 16, 2026. No model, GPU process, health probe or native
supervisor execution ran. The certified 46.854250 tok/s result is unchanged.
This packet copies the replay lifecycle at `7aca7df2a` (seal `bb473f8e`). The
replay, calibration, driver and certified source export remain untouched.

After readiness, a 20-second plateau and the full 30-second delay, the frozen
client sends **code-review** and **customer-email** once each: 128 output tokens,
temperature 0, seed 20260609, thinking off, no cache reuse. It records full text
and token IDs, comparing the first 128 IDs to the same A367 record prompts.
A mismatch is a finding, not a lifecycle failure. A missing/malformed response,
wrong prompt, missing token IDs or reused cache still fails. This is diagnostic;
`realistic_final_gate.passed` must be false. No speed claim is authorized.

## Arms

Each is one separately admitted launch, never a queued campaign or fallback.
The owner-window binds the selected arm as well as preregistration and seal.

| Arm | Graphs | Trace | Interpretation |
|---|---|---|---|
| `graph-reference` | FULL_DECODE_ONLY, sizes 1/2 | none | Short diagnostic timing and output reference |
| `graph-census` | unchanged | conditional device/ITT trace | Graph visibility and correlation feasibility experiment |
| `eager-census` | disabled | conditional device/ITT trace | Eager census only; times do not describe graph replay |

Graph kernel visibility is **unproven**, not proven impossible. PTI has graph
capture/replay hooks, but previous Laguna and DeepSeek full-model traces stalled
or killed workers; even paused tracing had startup overhead. Both trace arms
are CPU-built and device-unqualified. The graph reference is the first arm;
review it before admitting a trace arm. Empty, submit-only or incompletely
correlated traces remain incomplete findings. See [the evidence and sizing
analysis](TRACING-FEASIBILITY.md). No torch.profiler, device-event timing or
xpu-smi is used.

## Memory and safety

MemAvailable, MemTotal and GPUActive plus live checks stay on a fixed 0.5-second
cadence. A separate thread scans rank RSS and cgroup current. Each sample carries
the latest completed scan with its own **start** timestamp; a blocked scan cannot
refresh old attribution. Plateau rows require all four distinct rank PIDs/RSS,
cgroup current and attribution no older than two seconds. The cmdline-once cache,
ESRCH handling, 1.5-second gap trip and 12,000,000 KiB live reserve remain.
RAID writes and live checks can still stall; a missed cadence still trips.

The proposed start floor is **114,840,824 KiB**, default-refused until the exact
new owner sentence is recorded. Replay measured 104,784,640 KiB generation need
and about **1.9 GB headroom above the reserve**. The tracer's **0.25–1 GiB
additional host memory** is an unmeasured planning range; budget 1 GiB, leaving
roughly 0.8 GB of that observed margin. This is not an upper bound. A start at
exactly the proposed floor cannot cover even the measured replay generation
need plus reserve; it can trip. Approval accepts risk, not an assurance of fit.

Expected raw trace size is **0.2–2 GiB**, unmeasured, under a whole-run **10 GiB
planned-write allowance**. PTI uses 4,096-record buffers instead of unlimited
buffers. An independent metadata thread requests one graceful stop at 8 GiB,
leaving 2 GiB planned for drain. Buffered growth/teardown can exceed that soft
margin; this is not a hard filesystem quota. All traces/logs are on RAID;
compiler/cache/tmp/RPC scratch stays on local ext4. The unchanged free-space
reserve is 60 GiB plus the planned 10 GiB writes; local scratch requires 4 GiB.

Server: nice 0, all online CPUs, OMP=1. Client: nice 0, CPUs 4-15,20-31. Same
source/stage/model checks, current owner/health/payload/boot gates, one SIGINT,
all-session exit and 305-second watch. No restart, kill escalation or resident
service. Soft teardown can wait indefinitely; owner recovery may be needed.
The one-hour window can expire before worst-case budgets complete.

## Tracing and analysis

Unitrace wraps only the server, starts paused and follows spawned processes.
After the delay the supervisor resumes its unique named session, checks the
acknowledgement, then enables host ITT scopes. It disables scopes and pauses in
a finally block. Graph markers wrap actual replay calls, not only Python model
forward. The marker code reads tensor metadata only; it adds no tensor operation,
CPU value read, synchronization or arithmetic replacement. ITT emission and
actual device correlation remain unverified until a separately admitted run.

Run the CPU analyzer **after all owners exit and the watch finishes**, using the
script-file commands in [LAUNCH-RUNBOOK.md](LAUNCH-RUNBOOK.md). `census-run.json`
is the lifecycle receipt; `census.json` and `census.md` are analysis products.
The manifest binds raw trace hashes and worker PID/rank receipts. GPU Chrome
lane IDs are not worker PIDs. Same-thread ITT scopes join H2D flow IDs to kernel
IDs; overlapping wall timestamps never establish asynchronous ownership.
Missing/ambiguous scopes, IDs and family names stay explicit and incomplete.

Per step: kernel count, summed device work, busy-interval union, wall span and
idle gaps. Largest sinks and small-kernel clusters cite the dispatch audit in
[the glue-fusion design](../../../../../notes/2026-10-16-flash-next-m2-glue-fusion-design.md).
Unknown GEMMs must not be called shared experts or LM head without evidence.
Already fused or absent work is not a fusion saving; BF16 round boundaries,
stable sort, expert-map sentinels, two one-row collectives and state rollback
must be preserved. Eager durations never fill graph buckets.

CPU tests cover blocked attribution, freshness, admission, faults, client/exit
ordering, marker transparency, synthetic correlation/overlap/unknowns and trace
mapping. Seal pins code, tests, docs, workload/record, design audit and the
unchanged replay dependencies. Pending approval and build receipts stay outside
the seal to avoid circular hashes. No owner approval is recorded by this build.
