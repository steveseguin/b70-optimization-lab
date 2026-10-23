# Conservative initial idle timing

## Question and identity

Can the coordinator avoid charging model loading against the entire initial
idle allowance while preserving the native clock's meaning? The helper binds
the unchanged packet198 device binary, source/build evidence and the exact
libstdc++ clock implementation. It performs CPU reads and arithmetic only.

## Outcome

Ten CPU tests and independent review pass. In a synthetic launch-time replay,
the retained packet199 report of 215480.035061 milliseconds permits adding
215 conservative seconds to the launch timestamp. This is a conditional lower
bound on the start of native idle waiting, not a measured live serving result.
The absolute deadline always remains based on the original pre-launch time.

## What worked

The pinned native source samples load start after process entry, records the
load duration before emitting ready, then starts the first idle deadline in
Reader::next. If L is sampled before launch and the measured interval is S..E,
then L <= S <= E <= I, where I starts native idle waiting. A duration d no larger
than E-S gives L+d <= I.

The helper subtracts a one-millisecond formatting allowance, floors whole
seconds in an independent Decimal context, and rounds the float addition down.
It accepts only the exact native JSON shape and checks its hash. A separate
reader limits the artifact to 512 bytes, refuses symlinks/nonregular files and
checks held directory/file identities and stability.

Read-only ELF/disassembly evidence shows the pinned C++ steady clock calls
clock_gettime with CLOCK_MONOTONIC, matching Python's monotonic clock. The
helper rechecks the source, binary and library hashes on disk.

## What failed or remains uncertain

Review found that caller-controlled Decimal precision could erase a safety
subtraction. The corrected helper uses its own precision and rounding context;
the prior eight-test candidate is retained under
`lineage/initial-idle-before-decimal-context/`.

The cold-start artifact contains no PID. A matching file hash does not prove
which process wrote it. The coordinator must bind fresh output and its held
directory to the admitted owner, use the same boot's monotonic clock, and verify
that the owner's actual mapped clock library matches with no symbol
interposition. A library present on disk is not proof of a process mapping.
All those obligations remain explicit; the helper returns live readiness false.
Ready-receive time is never substituted for native activity.

## Evidence and patches

- [Helper](initial_idle_origin.py) and [tests](test_initial_idle_origin.py).
- [Source and clock proof](receipts/initial-idle-origin-proof.json).
- [Independent review](receipts/independent-initial-idle-origin-review.json).
- [Root's combined helper checks](receipts/coordinator-helpers-cpu.json).

## When to revisit

Bind this calculation to a reviewed coordinator's actual owner/output/clock
provenance. Keep native absolute deadlines unchanged and preserve the fallback
of conservative launch-origin timing when provenance is unavailable. Existing
profiles, sealed native sources and running applications are unchanged.
