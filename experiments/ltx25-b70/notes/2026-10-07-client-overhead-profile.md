# Read-only client overhead profile, 2026-10-07

The source/identity check costs about **2.0 ms per call** in the authorized 103
startup window. At 87 calls that is roughly 0.173 seconds, so rehashing alone does
not explain 102's roughly 0.926-second receive-span excess at its recorded event
count. A later isolated synthetic test measured about17.23ms per ledger save and8.50ms
per event flush/fsync. This supports testing redundant-write removal while
preserving all checks; it does not establish end-to-end GPU idle time.

[Profile data, source hashes, file sizes and complete cProfile caller edges](../data/resume-20261007/client-overhead-profile.json)
were recorded at **17:41:38 UTC** against sealed packet 103 and the actual server
PID 3286256/start ticks 26857357. The contract SHA256 is
`53865536011f36a09a57a33f52a94fb7e91e36c69587fc0859d02b5477926990`.

## Method and observed cost

A separate CPU process imported the sealed client with bytecode writes disabled,
constructed `Client` from that contract and used the real passive PID/boot check.
Construction invokes one `check_fixed`; ten further calls were measured with wall
and process-CPU clocks, then five calls were measured under cProfile: **16 total**.
No endpoint, transport, `acquire`, `checkpoint`, `save_state`, request execution,
GPU operation, source edit or client-ledger write was invoked. Only the assigned
profile report and note were written. No cache or host setting was changed.

| Measurement | Result |
| --- | ---: |
| Constructor, including one check and plan/schedule validation | 34.75 ms |
| Ten unprofiled checks, mean wall time | 1.994 ms |
| Ten unprofiled checks, median wall time | 1.959 ms |
| Ten unprofiled checks, mean process CPU time | 1.992 ms |
| Five profiled checks, total | 14.893 ms |
| Regular-file reads per check | 9 |
| Regular-file payload read per check | 891,762 bytes |

Each check reads the contract, server identity, 749,907-byte plan, setup schedule,
and five bound source files. It separately reads boot ID and `/proc/PID/stat`;
those procfs bytes are excluded from the regular-file total. cProfile recorded
45 `read_file` calls and 70 `safe_path` calls across five checks. Their cumulative
times were 8.36 and 7.23 ms respectively; these overlap and must not be added.
SHA256 itself took about 2.05 ms across all five checks. Repeated path validation
and filesystem operations are a meaningful part of this small read-only cost.
Use unprofiled wall measurements for estimates because profiling adds overhead.

## What this does and does not explain

102's recorded event counts were 85–89 per scored request, and its mean gap from
server success to the next execution start was 1.148 seconds. The recorded
client execution-start-to-success span exceeded the corresponding server span
by 0.926 seconds. These are different metrics, not additive latency components.
The 103 startup measurement uses the larger full-suite plan, on the same host,
but not the exact 102 timed workload or concurrent CPU pressure. Unmatched status
or other messages also trigger checks before being discarded, so recorded event
count is not a measured total checkpoint count. The 0.173-second calculation is
only a sizing estimate, not a hard attribution or upper bound.

Inspection shows a full `checkpoint` additionally probes free space and writes a
new ledger file, fsyncs it, fsyncs the directory, replaces the old ledger, and
fsyncs the directory again. Each accepted event separately flushes and fsyncs the
log. Those operations were excluded from the read-only profile. The separate
synthetic follow-up below measured them without touching the live ledger.

Keep 103's delivery method unchanged while it establishes ten-fixture parity and
continuity. In a later sealed client, first add bounded timing counters around
validation, storage probing, ledger persistence and log persistence without
changing their behavior. Preserve source/contract/process binding, immediate
fault handling, single-submit/no-retry semantics, capture/write budgets, exact
request/output linkage and durable submission/terminal/failure evidence. Any
later batching or changed validation cadence needs an explicit reviewed contract
and corruption/crash controls; it must not silently weaken those guarantees.
A client change also needs its own matched delivery control before its gains are
attributed to model computation. No new model-speed or reliability claim follows
from this CPU profile.

## Follow-up synthetic I/O test, 17:45:10 UTC

The coordinator separately authorized ten ledger saves and ten event writes in a
new owned fixture directory, before the 17:46 startup cutoff. The exact sealed
103 `save_state` method ran on a `Client.__new__` clone containing a **copy** of
the completed 102 ledger, with its directory set exclusively to
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/cpu-client-io-profile-103`.
No real client method other than `save_state` ran in this test. Ten synthetic
JSONL lines were written, flushed and fsynced in a separate file in that folder.
A wrapper checked each descriptor's path before calling the real `os.fsync` and
recorded its duration. All 40 calls targeted owned fixture files/directories.

The ten ledger saves averaged **17.226 ms** and the ten event write/flush/fsync
operations **8.499 ms**. Fsync calls consumed 253.47 ms of roughly 258 ms elapsed.
Within each ledger save, the new-file fsync averaged 8.478 ms and the post-replace
directory fsync 8.418 ms. The temporary-name directory fsync was only about
0.001 ms: removing that alone would have negligible value in this sample.

The fixture preserves its copied input, final synthetic ledger, synthetic events
and profile. Total payload bytes written, counting all ten rewritten ledger
payloads and the profile file, were **67,306 bytes**, below the 1-MiB cap. This
counts application payloads, not filesystem journal or device write amplification.
The original profile's self-size estimate missed 59 bytes added by its final
accounting field; the repository JSON records the corrected total while preserving
the original diagnostic artifact and hash.

This provides evidence that durable persistence can be expensive enough to explain
a substantial backlog. It does **not** prove the exact contribution in 102 or 103:
the copied ledger, message sizes, device contention and number of discarded events
differ. Do not multiply these timings into a claimed model-speed improvement.
Do not remove fsyncs or budget/fault checks on this basis.

A later reviewed candidate could evaluate an append-only checkpoint journal with
explicit durable commit points, avoiding a fresh-file-plus-rename cycle for every
transient progress event. That changes recovery behavior and needs crash/truncated
write/replay tests, exact charged-byte accounting, identity/source binding, durable
submission and terminal records, and no resubmission after uncertain outcomes.
Keep it separate from the current full-suite qualification. First instrument the
actual client operation breakdown without changing behavior, then compare any
candidate under the same request delivery and quality gates.
