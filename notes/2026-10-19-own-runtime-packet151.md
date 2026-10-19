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
