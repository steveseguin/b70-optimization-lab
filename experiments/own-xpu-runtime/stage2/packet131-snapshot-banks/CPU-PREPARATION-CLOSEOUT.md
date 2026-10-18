# Packet131 CPU preparation

<!-- campaign-closeout -->

## Question and identity

Can bundle7 avoid rank0's recurrent rollback capture on every speculative
cycle, preserving `iq3-p49-split32-v1` outputs and committed state? This is a
new symlink-preserving copy of frozen packet124c on October 18. Control uses
`batch`; candidate uses the dormant local packet62 `banks-batch` mechanism.
Every other production choice, including 24/24 placement, stays identical.

## Outcome

CPU qualification and both new seals pass; [readiness](evidence/ready131.json)
binds the completed gates. All eight 491-case state transcripts match exactly
across GNU/Intel, control/candidate and two fresh runs. Both selections pass
all eleven startup paths. Device correctness and speed remain pending. The production census
removes 29,601,792 of 48,627,432 capture bytes per cycle (60.87%). Extra private
bank storage exactly replaces removed backup storage: zero increase in owned
device allocation. No GPU, service, live queue or host setting changed.

## What worked

Keep committed and old-spare bytes intact, write the alternate destination,
and choose among six prebound physical pairs. Continue the existing flat
capture for QSA and nonbank outputs. Audit captured production pointers and
full-overwrite behavior, not only reduced fixture outputs. Include old spare
bytes, older QSA rows, cancellation, terminal fallback, reset and fresh repeats
in the state oracle. Preserve the actual oracle authority symlink.

## What failed or remains uncertain

An Intel CPU fixture required its own linker, a non-PIE link and the explicit
compiler library path. An overly small auxiliary CPU cap refused K2; startup
is run separately within the allowed 8-GiB process cap. These were CPU harness
issues; their logs are retained. GNU and Intel's original recurrence kernels
differ in NaN payloads for the explicit NaN fixture, while the candidate
matches its unchanged same-compiler reference byte for byte.

The original capture already uses two submissions. Its 0.523-ms sampled
compute event does not establish a bandwidth-only bottleneck or a promised
speed gain. Bank rotation drains the queue, which could offset the saved work.
CPU allocation accounting is not a new driver-residency measurement.

## Evidence and patches

- [Census](CENSUS.md) and [all capture extents](capture-extents.csv).
- [Exactness argument](EXACTNESS.md) and [source delta](snapshot-banks.patch).
- [Gate entry points and reproduction](README.md).
- [State receipt](evidence/state131.json), [production recurrence](evidence/recurrence131.json),
  and [reset regression](evidence/reset-regression.json).
- [Work note](../../../../notes/2026-10-18-own-runtime-packet131.md) and
  [retention/restoration](RETENTION.md).

## When to revisit

After CPU admission, the coordinator may admit the sealed lane-B 12 × 64
smoke, then the fresh-load C/X/C/X/C screen. Both candidate loads must match
the device oracle and acceptance counts, beat the controls, and satisfy the
control-drift gate. Allocation differences prevent a v5 runtime switch.
The short screen cannot establish a strict512 result or an external record.
Any changed sealed source or dependency invalidates admission.
