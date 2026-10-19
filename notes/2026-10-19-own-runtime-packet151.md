# Packet151 sibling-cost preparation

Prepared on steve-b70s, on main, for the two-card lane B. Rebase refused the
pre-existing unrelated dirty files; fetch initially confirmed HEAD and
origin/main both at 2916fe5c790b474b9755a1338e92092afa6ad56b.
The frozen-path inventory was run successfully. No existing packet or live
queue was edited. No GPU, service, sudo, host-setting change or model payload
read was performed by this task.

The packet136 arithmetic and packet149 vendored harness are copied into
[packet151](../experiments/own-xpu-runtime/stage2/packet151-sibling-cost/README.md).
The abandoned draft-census tree is left untouched and is not being committed.
The alternate token is deterministic, `(token+1) % vocabulary_size`.

Milestone 1: the packet68c paired dense/expert arithmetic has been ported to
bundle8's cached expert-scale layout. GNU and Intel each pass two fresh runs
of 1,478 byte checks, including real matrix dimensions with synthetic weights.
All four hashes match. Peak child RSS was 944,164 KiB. No GGUF bytes were read.
This is an operator proof, not full-model or device quality evidence.

The integrated host and device binaries compiled. Eight analyzer tests pass,
including missing/empty stream rejection, changed outputs, inconsistent clocks,
nonfinite values, smoke coverage and the fixed 1.952 ms threshold. State,
entry, admission and final seal checks remain pending at this milestone.

A whole-host hold began around 00:17 UTC. The compiler arbiter refused the
next turn. The task stopped its own waiting Python build supervisor (before
compilation) and paused until the named packet58ah unit became inactive at
00:43 UTC. No process from the record chain was stopped or modified.

The current implementation shares large dense/expert operations but retains
serial M=1 submissions for HC, small tuples, fused shared-down and non-matrix
operations. It therefore does not yet satisfy the brief's complete M=2 scope.
The packet README states that limit; readiness must remain false unless it is
resolved and the state, memory, entry, report and pin gates all pass. There is
no cost measurement and packet132 is not reopened or newly closed by this work.

Storage planning uses 240 MB per view, 1.2 GB total, based on packet149's measured
402 MB bracket (under 3x). The device floor remains 25 GB; this CPU task stops
below 30 GB and caps builds at 300 MB. No proposal is queued.

### packet151c — upper-bound scope (October 19)

The owner narrowed the requested device experiment to the existing partial M=2
build: **upper bound (partial M=2: HC/small tuples/shared-down/non-matrix serial)**.
The analyzer now reopens packet132 when the measured extra cost is at most
1.952 ms. A higher result is inconclusive and calls for full M=2; it cannot
close packet132. Policy calibration remains on packet114 independent text,
never the 12-prompt suite. All nine analyzer tests pass, including the smoke's
own missing/empty-stream refusals. No device measurement has been made.

Fetch confirmed HEAD and origin/main at d61bfcdf1bb43ec5ac1a962f8cc9b632dbb98da6;
rebase refused the unrelated dirty tree. Initial free disk was 30.757 GB.

Milestone 2: the inherited GNU/device build and two-compiler paired-arithmetic
receipts still match their source and binary hashes. The expanded state gate
passes twice with the same kept-state hash, covering accepted hits, misses,
rollback, isolated scratch, request reset and subsequent reuse. Static memory
admission independently derives both ranks from the parent ledger, adds the
bounded 256 MiB sibling allocation on rank0 and retains the physical-free floor.
It is a conservative plan; the actual device census is still pending.

The shared report helper is frozen. A private packet151 copy fixes its synthetic
fixture and pause-sensitive CPU deadlines; the shared launch-environment script
is executed unchanged with the private pause-aware native parser sandbox.
Ten analyzer tests pass. Smoke reporting rejects both missing and empty half
and sibling streams from its own output. No empty stream is treated as zero cost.

Temporary plans and both report rehearsals pass for the two lane-B proposals;
the live coordinator pin guard passes. No queue was changed. Expected durations
are 240–600 seconds for smoke and 720–1200 for the bracket; both watchdogs are
4800 seconds. Writes stay 240 MB per view. Historical retention/payload manifests
are preserved in lineage-inputs/p151-first-build, rather than discarded or treated
as current source pins. Final source-bound gate refresh and readiness seal follow.

The inherited staged removal of generated build files from Git is completed
without deleting the local files: the two generated build directories are
moved aside only during the explicit-path commit, then restored unchanged.
The binaries remain locally available and hash-bound; source, build commands,
original constants, receipts and historical manifests remain tracked.

Final packet151c review: all 15 current CPU receipts pass and their recorded
sources match. This includes real closed-environment/unit-name entry through
both intercepted native execs, unchanged resource-limit checks, all 78 worker
requests, cooperative failure handling, strict real smoke/bracket reporting,
private `ops/rehearse_entry.py --report`, the unchanged shared `ops/launch_env.py`,
temporary queue plans and the live pin guard. The CPU-only replay entry now
runs these gates without inherited GGUF/full-shape steps. Earlier failed
pre-seal report/pin diagnostics remain under lineage-inputs/preseal-diagnostics.

Final checked build footprint: 84,313,763 bytes, below 300 MB. Root free was
30.335 GB at the final source review, above the 30 GB stop floor. All compilation
used the shared compiler-turn arbiter. No GGUF payload was read, no GPU or service
was started, and no host setting or live queue was changed.

The source, receipts, proposals and this note are committed before the finalizer
writes READY-FOR-DEVICE.json as the last packet write. That marker records the
source commit and exact proposal hashes, with ready_for_device=true and
queued=false. This admits an upper-bound measurement, not a quality or speed
claim: device output equality and the actual sibling cost remain pending.

### packet151d — preparation refusal repair (October 19)

The failed lane-B smoke at 01:37:25–01:39:01 UTC remains untouched in
`v5/evidence/device-sibling-smoke-B/`. Its rank0 preparation records exist,
but its token timing streams are empty. The first sibling schedule was being
prepared during prefill, and the new paired SYCL operations called `q.submit`
instead of the owner's `prepared_submit` capture boundary. That submits work
while the owner expects to collect a command, then trips “native operation
bypassed preparation”. The new command groups also needed value captures so
their argument blocks survive preparation.

The paired dense, finish, expert and helper operations now enter the same
preparation hook as their originals, with captures by value. No arithmetic,
reduction order, quantization or KV format changed. Sibling selection is now
inactive for `fixture == 0` prefill; corrected halves remain excluded.

The real-shape preparation gate reads the failed rank0 launch argv and the
saved tensor plan, with the Intel device compile command (no HOST_ONLY define).
Its backend uses disjoint inert weight addresses, real-sized runtime buffers,
and marker events. It reads no GGUF payload and never constructs a device
queue. Frozen M=1 operations are mocked because several query device capability
before capture; those operations already prepared successfully in the failed
native run. Every new paired operation must populate the actual native
SubmissionCapture. Old direct submissions are trapped before queue contact.
This is a dispatch/preparation proof, not full-model numerical inference.
The CPU sandbox remains nice19 despite the original argv declaring native nice0.

Fixture bring-up first caught the CPU/native nice mismatch, then overlapping
placeholder weight extents, then a frozen M=1 capability query. These were
fixture problems, not GPU incidents; the final fixture models disjoint weight
extents and mocks only the inherited operation boundary. The retained debug
trace is CPU-only. No GPU, service, sudo, settings change or live queue edit was
performed for this repair.

The production host/device rebuild, two GNU and two Intel arithmetic runs,
and two fresh miniature state runs share one reseal compiler-arbiter turn.
The preparation regression uses separate arbiter turns during fixture bring-up.
All four arithmetic runs pass 1,478 byte comparisons and retain the prior
`7d4ca1c5030aef0011c19bc146e049e5d791783f05f90f62d4aa8472b25b08ac`
output hash. Both state runs retain
`b52b061962d5915cb849fbc0ba3a70b7dd25bec4a0bbe74a6afcc391170e08a3`,
including hits, misses, rollback, scratch isolation and request reset, with an
added prefill exclusion check. Device equality and cost remain pending.

The CPU-only rebuild floor is now 29 GB with the existing 300 MB total build
cap: unrelated activity put root free space just below 30 GB (29.991 GB at the
check). The device admission floor remains 25 GB. CPU compiler waits use the
pause-aware clock; the regression has no wall-clock inference deadline. No
cold-TTFT deadline was added to the smoke's data proof.

The old-code CPU negative reproduces the exact failure after load and all 748
ordinary rank0 sites prepare: `blk.0.gdn.qkv`, operation
`p68c::ProductionDense<iq3::Type::Q6_K,2560,1,false>`. The real geometry is
hidden width 2560, expert width 640 and top10. The failure is in the first
prefill's paired-command preparation, before any half timing is written.

The final preparation regression passes: prefill positions 0 and 1 have zero
paired captures; positions 2, 31, 32 and 33 prepare 114 paired sites per schedule,
552 native captures total, traversing both parities and the 32→64 context
extent. The old-code negative still fails at `blk.0.gdn.qkv`. A further fixture
correction supplies positive synthetic marker intervals to satisfy the existing
profiling validator; those numbers are not measurements. See the packet's
[preparation closeout](../experiments/own-xpu-runtime/stage2/packet151-sibling-cost/PREPARATION-CLOSEOUT.md)
for the evidence boundaries and revisit conditions.

Final reseal: all 16 CPU receipts pass, including real entry/limit boundaries,
all 78 worker requests, strict smoke/bracket reports, temporary queue plans,
private `ops/rehearse_entry.py --report`, and the live coordinator pin guard.
The two proposals now use `packet151d-sibling-smoke-B` and
`packet151d-sibling-bracket-B`, writing to fresh `device151d-sibling-smoke-B`
and `device151d-sibling-v5-B` directories. Neither is queued. Peak recorded
child RSS is 1,404,904 KiB, below 4 GB. The original failure inputs are hash-bound
in `v5/evidence/p151d-failure-inputs.json`; the full failed smoke stays on disk.
Source, receipts, proposals and this note are committed and pushed first;
`READY-FOR-DEVICE.json` is written last and committed/pushed separately.

### packet151e — bracket smoke lookup repair (October 19)

The 02:18:14 UTC bracket refusal happened before device work: its fixed folder
name selected the failed `device-sibling-smoke-B`, instead of the exact smoke
completed at 02:01:46 in `device151d-sibling-smoke-B`. The bracket now resolves
`--output` from the current lane-B smoke proposal and fails closed on missing,
failed, changed or mismatched smoke evidence. It retains every existing device
completion, teardown, artifact hash, oracle and exact-output check.

The Python-only reseal preserves the smoke's original wrapper seal under
`lineage-inputs/p151e-before/`. A sealed prerequisite receipt binds the completed
window and that historical seal. Admission also checks the current native binary,
selection, dispatch, memory plan, smoke configuration, lane and variant against
the smoke identity. Both native binaries and all native source remain unchanged;
there was no rebuild. The passing and failed device folders remain untouched.

Four CPU regression tests admit the current passing smoke and reject the old
failed smoke, a missing output and a failed result. See
`v5/test_smoke_precondition.py` and `v5/evidence/p151e-smoke-precondition.log`.
Real intercepted entry checks, real report checks, temporary queue planning,
the private `ops/rehearse_entry.py --report` and coordinator pin checks pass.
The first private report rehearsal stopped in its CPU sandbox because its
fixture still mocked the old prerequisite reader; its retained log is
`v5/evidence/p151e-rehearse-initial.log`. The private helper now recognizes the
new reader, without changing report validation or the shared helper.

Only the bracket proposal changes: `packet151e-sibling-bracket-B`, writing to
fresh `v5/evidence/device151e-sibling-v5-B`. The current smoke proposal and live
queues are unchanged. Source and receipts are committed/pushed first, then
`READY-FOR-DEVICE.json` is rewritten last with `ready_for_device=true` and
committed/pushed separately. The bracket cost measurement remains pending.

All checks used nice19, CPUs 8–15/24–31, Python `-B`, closed stdin and a 2 GiB
process memory cap. No GPU, service, sudo, settings change, GGUF payload read
or compile was performed. Rebase refused unrelated dirty files; fetch confirmed
HEAD and origin/main at `cf21667b09c393d26314111a7b35c7bf6c443e44` before edits.
