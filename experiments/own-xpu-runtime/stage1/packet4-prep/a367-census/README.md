# A367 M=2 diagnostic census packet

CPU reseal, October 17, 2026; device evidence from the coordinator is incorporated. No model, GPU process, health probe or native
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

Run **only `graph-census` next**. The eager arm remains secondary and separately
admitted. The untraced graph reference is optional: replay c already provides
full-suite untraced timing. No automatic fallback or retry.

The ITT microtest saw all eight kernels in all 50 graph replays when tracing
was active at capture, and zero replay kernels when capture was paused. Paused
tracing did not stall four-rank oneCCL initialization. The traced ranks finished
their work then segfaulted at exit; the untraced control exited cleanly, with
zero GPU faults. Full-model four-rank attribution remains to be measured.
The subsequent full-model run `a367c-20261017T002647Z` crashed in all four
workers during lazy XCCL creation in profiling, about ten seconds after the old
loading-line resume. It never reached requests and failed despite zero GPU
faults and a completed watch. The capture-entry rendezvous replaces that trigger.
See [device evidence and limits](TRACING-FEASIBILITY.md).

## Memory and safety

MemAvailable, MemTotal and GPUActive plus live checks stay on a fixed 0.5-second
cadence. A separate thread scans rank RSS and cgroup current. Each sample carries
the latest completed scan with its own **start** timestamp; a blocked scan cannot
refresh old attribution. Plateau rows require all four distinct rank PIDs/RSS,
cgroup current and attribution no older than two seconds. The cmdline-once cache,
ESRCH handling, 1.5-second gap trip and 12,000,000 KiB live reserve remain.
The timed sampler performs no output-mount file I/O. Rows stay in memory; a
separate writer appends to ext4 scratch. Live file checks run in a separate
thread. After all owners and clients exit and the watch finishes, the writer
drains; its file is checked against the rows, copied to output/samples.jsonl,
and hashed in samples-persistence.json before scratch removal. A missed cadence
still trips; blocked live-file checks cannot block memory reads.

The proposed start floor is **114,840,824 KiB**, default-refused until the exact
new owner sentence is recorded. Replay measured 104,784,640 KiB generation need
and about **1.9 GB headroom above the reserve**. The tracer's **0.25–1 GiB
additional host memory** is an unmeasured planning range; budget 1 GiB, leaving
roughly 0.8 GB of that observed margin. This is not an upper bound. A start at
exactly the proposed floor cannot cover even the measured replay generation
need plus reserve; it can trip. Approval accepts risk, not an assurance of fit.

The old **0.2–2 GiB** request-only trace estimate is not a bound for the expanded
capture-to-request window. Keep the **10 GiB** planned-write allowance on RAID
and its 60 GiB reserve. Traces go to local ext4 at
`/home/steve/.cache/a367-trace/<run-name>/`, outside deleted scratch; admission
requires **8 GiB free** there. A separate metadata watcher measures that local
trace directory and requests one graceful stop at **6 GiB**. Drain may exceed
the soft stop; it is not a quota. Copy traces to RAID after the lifecycle using
the runbook, hash the copy, and retain the local originals. Scratch still
requires 4 GiB. The tracer uses finite 4,096-event buffers.

Server: nice 0, all online CPUs, OMP=1. Client: nice 0, CPUs 4-15,20-31. Same
source/stage/model checks, current owner/health/payload/boot gates, one SIGINT,
all-session exit and 305-second watch. No restart, kill escalation or resident
service. Soft teardown can wait indefinitely; owner recovery may be needed.
The one-hour window can expire before worst-case budgets complete.

## Tracing and analysis

Unitrace wraps only the server, starts paused and follows spawned processes.
The census-only, source-pinned V2 `GPUModelRunner.capture_model` wrapper holds
each rank at entry, after paused profiling and KV initialization but before
target or draft graph capture. Each rank atomically writes
`capture-ready-rank-R.json` (rank, PID and monotonic timestamp) to local ext4
scratch, then waits for `capture-go`. Every 600 seconds it prints an overrun
notice and keeps waiting; there is no timeout exception or kill. The supervisor
requires all four distinct rank/PID receipts, attempts resume exactly once,
records the acknowledgement and then atomically writes `capture-go`. It also
writes go when resume fails: requests and normal teardown continue, but graph
attribution is invalid. Loading log text never triggers resume. Cleanup releases
any waiting ranks before graceful shutdown; the copied receipt retains all
rank timestamps and release evidence after scratch is removed.

Tracing stays active through capture, readiness, plateau, the 30-second sleep
and both requests. Census ITT scopes become active for the requests. Pause
immediately after the client finishes and again idempotently in cleanup, before
normal shutdown requests destroy communicators. An unexpected worker crash or
independent safety stop can precede this normal ordering. Pausing does not
unload the tracing layer or guarantee a clean exit.

The [communicator audit](COMMUNICATOR-AUDIT.md) finds default WORLD already
used before load and TP plus MTP using existing groups during paused profiling.
EP and the separate vLLM WORLD device groups can remain unused; no active late
group first use was found for this exact TP4/PP1/DP1/PCP1/DCP1/MTP1 launch.
No blanket warm collective is added: that would allocate unused communicators
and change memory use. **Residual risk:** native XCCL/oneCCL could create
stream/operation-specific resources after resume; Python source cannot exclude
that. The next device run remains a feasibility test.

The secondary eager arm skips `capture_model`. Its census-only wrapper instead
waits after `Worker.compile_or_warm_up_model` returns, after profiling, KV setup
and warmup, before readiness. It uses the same four-rank file handshake and
does not claim graph attribution. Only graph-census is next.

Graph markers wrap actual replay calls, not only Python model
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

Traced nonzero server exit or segfault is recorded as `expected_tracer_exit_crash`
with the microtest evidence path. `clean_exit` still records whether the API
return code was zero; it is not the traced census gate. Every owner must be gone,
the full 305-second watch must have zero GPU fault lines, and both requests must
finish. No kill escalation or retry; a teardown overrun keeps its receipt and
waits. `census_valid` additionally requires four complete rank traces with ITT
verify markers, timestamped verify kernels and flow attribution. Startup kernels
outside request markers may remain unassigned; whole-trace segmentation and
census validity are distinct fields. The real ITT fixture and its original-event
indices are retained in `fixtures/`.
