# Packet58y: attribution after overlapped cache maintenance

CPU-only preparation, time box 75 minutes from 18:07 UTC. Main matches origin/main
at initial fetch (38d4ecee4). Unrelated dirty orchestration files are preserved.
No device run, service, live queue, frozen packet or host setting is changed.

## Preregistered decision gate — before any packet58y device data

A next one-card implementation needs a supported projection of **at least +3%**
throughput on the class-balanced 99-interval metric. For a token span T this
requires saving at least T * (1 - 1/1.03), or 2.9126% of its wall time.
Use each prompt's measured spans, then medians within classes and across classes.
A perfect-removal bound below +3% kills that lever for this evidence. A larger
bound only admits further investigation; it is not a measured gain. Unknown
critical-path costs remain unknown and cannot pass the gate by assumption.
No changing arithmetic, weights, BF16 KV, prompt reuse or packet49 oracle.

This is a diagnostic, not a record or promotion. One model load, overlap mode,
all twelve fixed prompts, 128-token cap, every generated token checked against
`iq3-p49-split32-v1`. Cache starts empty and persists as immutable weights only.
First/cold prompt stays in the evidence and aggregate; no warm-up filtering.

Host spans use steady_clock around existing work and existing waits only.
No added per-kernel fences, external profiler, queue profiling or graph-event
profiling. Device durations without valid timestamps are null, never zero.
The existing compute-tail wait includes zero-copy miss kernels: their separate
critical-path duration is unidentifiable without perturbing execution. Record
zero separate miss-wait calls and label their actual stall cost unknown.
Fill copies have no blocking per-token wait in the overlap path; retain their
submissions, pending state, actual published-pointer miss counts and payload
bytes. These are logical payload counts, not measured PCIe traffic.

## Coordinator handoff constraint

New proposal only: proposed-p58y-attrib-A.txt, card 0 / lane A / whole host.
Expected duration at most 900 seconds; watchdog 7200 seconds (8x).
Batch immediately after packet58x smoke and bracket in their SAME whole-host
hold, with lane B paused and drained continuously. Never acquire a standalone
hold for this diagnostic. Preparation plans temporary copies and never queues.
Packet58u measured admission, drain fix, native getrlimit gate, closed launch
environment, lanequeue screen-<job> unit names and recorded oneAPI path remain.

Larger-cache versus miss-path ranking remains pending packet58y device evidence.
The brief's historical 58v figures and 58x +2.2% projection are motivation,
not a replacement for the new split. Prepared analysis will report bounded
levers and explicitly identify costs that cannot be separated.

## CPU preparation milestone

The +3% preregistration was committed and pushed as `19efcaa4a`. The new
[packet](../experiments/own-xpu-runtime/stage2/packet58y-onecard-attribution/README.md)
copies 58v with symlink-preserving operations; no frozen parent is modified.
It adds host spans, existing-wait categories, ten enqueue-family counters,
actual published-pointer misses and commanded fill/table bytes. Production
queues remain unprofiled; device-class durations and separate miss-stall time
are explicitly unknown. The fixed metadata fits within 58v's existing allowance.

Both compilers pass. The retained build is 80,564,739 bytes; the largest compiler
child used 709,616 KiB RSS. The native miniature retains identical tokens and
all 32 BF16 fixture files across an untraced control and two traced repeats.
The full-size mock, source-byte fixtures, delayed-copy protocol, drain/teardown,
three real intercepted launch boundaries, parser refusals and 98 Python tests
pass. The oracle is still bound through the original packet49 authority.

A record chain began using host memory during preparation. The real admission
check correctly refused a full model when available RAM fell below the unchanged
95,435,761,152-byte threshold. The CPU launch replay now records that actual
observation and separately uses a clearly labeled synthetic admitted snapshot
to exercise the remaining startup path. The actual memory policy and its
one-byte-below refusal run unchanged. This is no device admission waiver.

The first temporary three-job plan caught 58x being resealed by its preparer;
that failed log is retained. Once its overlap proposals were sealed, all three
plans passed in order: 58x smoke, 58x bracket, 58y attribution. The new proposal
pins those predecessor hashes and requires their clean same-boot receipts plus
the continuous PAUSE-B marker. The plan reserves 4,026,531,840 bytes for all
three jobs against 32,742,936,576 root-free bytes, preserving the 25 GB floor.
Nothing was queued. Expected 58y duration is 10–15 minutes with a 120-minute
watchdog. Native output checking, library path, environment closure, drain and
getrlimit gates are retained. No GPU, service or host setting changed here.

The readiness marker binds implementation commit `015291e69`, the exact proposal
and seal. It was the final content write of preparation and was committed and
pushed as `2c7f66d1f`. No speed result or selected next lever is claimed before
actual device evidence.

A parallel read-only review caught a trace-integrity gap before readiness.
The real suite now refuses missing, truncated, reordered, wrong-token or
inconsistent traces before it can pass; all twelve traces are required. The
reviewer rechecked this fix. Same-hold checks also enforce predecessor stage
chronology; the coordinator still owns excluding intervening lane-A jobs.

## Evidence reader prepared after readiness

[The analysis reader](../experiments/own-xpu-runtime/stage2/packet58y-onecard-attribution/analysis/README.md)
is ready. It checks the sealed build, all eight predecessor receipts, hashes,
boot and stage order, recorded hold identity, exact output and complete traces.
It ranks six measured host/wait buckets against the preregistered +3% gate,
retaining the cold first prompt and the 99-interval class-balanced definition.
Perfect-removal bounds are labeled bounds; none passes an implementation gate.
It also rereads the larger-cache bracket and reports whether its measured
screen clears +3%, without claiming an independently known miss-path cost.

Eleven synthetic CPU tests pass, including exact +3% boundaries, corrupted
traces, empty predecessor coverage and replacement of stale successful reports
after invalid evidence. A read-only review prompted those last three checks.
The actual report is **pending device evidence**, with no split or ranking.
The analyzer is separate from the sealed launch sources; the readiness marker,
proposal and binary remain unchanged. No new hold or queue entry was created.

## Packet58yb — sibling-free hold gate and minimal reseal (October 18)

The old gate depended on mutable sibling proposals, receipts and seals. It now
requires only the current coordinator's existing continuous one-card whole-host
hold. PAUSE-B must be a regular non-symlink file whose text names that hold;
both its mtime and ctime must strictly predate this job's current lane-A START.
The gate rechecks the file's device, inode, timestamps and contents, and the
START, between stages and throughout the gaps. Whole-host admission remains.
The coordinator owns order. No separate hold is allowed.

The active contract, proposal, plan and evidence reader have no predecessor
requirement. The fresh output is `card0-attribution-b/attrib`; the temporary
queue contains only this diagnostic and was never queued live. Readiness binds
a local byte-identical proposal snapshot so it does not pin mutable ops state.
The external proposal file was checked against that snapshot before readiness.

The nested pin gate rejects outside paths except the original oracle and exact
frozen native compiler inputs. Inherited source and memory-evidence dependencies
were localized as byte-checked snapshots/archives. Historical manifests remain
historical, rather than being mistaken for current source seals. No frozen
sibling was changed. Retention and restoration instructions are in
[RETENTION.md](../experiments/own-xpu-runtime/stage2/packet58y-onecard-attribution/RETENTION.md).

All **104 policy tests, 19 admission replay tests and 10 analysis tests** pass.
The three actual Python entry paths reach intercepted native exec under the
closed launch environment and `screen-packet58y-attrib-A.service` identity.
The hold gate itself consumes scratch PAUSE-B/START fixtures in those probes;
no service or native process is started. The earlier wrong-unit regression
still refuses. All numerical memory bounds reproduce from local metadata.
The native artifact hashes exactly match the pre-repair seal; the target stays
`iq3-p49-split32-v1`, with unchanged BF16 KV and output checks.

The seal and the real coordinator's temporary queue plan pass. Failed planning
attempts are retained: they exposed nested historical pins and old copy hashes,
which were repaired before readiness. The actual live hold check refuses
because PAUSE-B is absent, as required. Device correctness and attribution remain
pending; no speed or next-lever claim changes. The earlier 18:42 pre-device
refusal is preserved. No model tensors or full-shape buffers were read or run,
no GPU/service/sudo/settings action occurred, and no live queue changed.

Validation used nice 19, cores 8–15 and 24–31, Python `-B` and closed stdin.
Largest child RSS was 38,461,440 bytes, below 2 GiB.
[Repair closeout](../experiments/own-xpu-runtime/stage2/packet58y-onecard-attribution/PACKET58YB-CLOSEOUT.md),
[reproducible CPU reseal](../experiments/own-xpu-runtime/stage2/packet58y-onecard-attribution/reseal_cpu.py),
[CPU receipt](../experiments/own-xpu-runtime/stage2/packet58y-onecard-attribution/evidence/reseal-cpu.json).
READY-FOR-DEVICE is the final content write; commit/push use only this packet,
this note and the authorized proposal. Unrelated orchestration work is preserved.
