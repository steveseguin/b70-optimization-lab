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
