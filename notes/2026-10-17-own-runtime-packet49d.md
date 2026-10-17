# Packet49d: banked exact kernels with a sealed late selection

The new packet is built separately from 49c. It keeps the same arithmetic,
weights, full 16-bit KV, card split 23/25, draft rank 1 and 4096-token capacity.
The existing packet49 oracle supplies its model reference. 49c's running chain
and unit are untouched. No GPU, service, sudo or host-setting operation is part
of this preparation.

The three banked 53b winners are integrated for ordinary M=1 calls and both serial
M=2 rows: expert gate/up virtual8 split stream, expert down virtual16, and small
FFN Q6 virtual4. All eligible 54 candidates are included: two routing schedules,
two recurrence schedules and HC mix-vector4. Selection is resolved at init.
The model process hashes the actual JSON bytes before parsing them.

The coordinator writes the selection only after 54's two timing owners finish.
The tool replays their raw receipts and requires banked plus selected savings of
at least 40us in each owner. A fast reseal checks the existing CPU proof and binds
the selection without rebuilding kernels or rerunning numerical gates. Initial
CPU preparation therefore does not authorize 49d device windows.

## CPU verification

- Submission and SPEED6 compatibility: 109 tests and 12 subtests pass.
- New all-choice GNU fixture: 682 checks pass, including 402 byte-comparison cases.
- Actual-engine GNU gate: two fresh processes, 5472 comparisons each, pass.
- GNU, device and scoped ASAN/UBSAN builds pass; one device build includes all choices.
- All-choice gate: four fresh GNU/ASAN processes, 682 checks and 402 byte-comparison cases each, same output digest.
- Inherited fresh-owner, plan, GNU/ASAN full-state snapshot, split32, expert and round-two gates pass.
- All 67 packet protocol tests pass. CPU-only early/model command plans pass.
- The immutable CPU preparation seal passes and re-verifies in 1.63 seconds: 31 retained artifacts and 470 source bindings. Runtime source revision: `a58ed0d9a`. The final selected seal remains absent.

The first fixture run failed because its negative case used an allocation that
was no longer small. The production guard was correct. The fixture now uses a
12-byte input; failed receipts and the correction are retained. Exceptional
NaN/Inf cases compare every byte to production on the same backend but are
excluded from the portable CPU/device digest; ordinary finite/subnormal cases
remain included. This is not a tolerance or a change to model arithmetic.

## Storage and commands

Root initially had 19,916,554,240 bytes free. The new build has a strict 1.5GB cap.
The largest observed build was 1,084,542,983 bytes. Recorded compiler-object
cleanup and verified exact sanitizer archives leave 521,796,014 retained bytes.
Final root free space is 18,853,928,960 bytes, against a 14,925,008,466-byte
requirement: 3,928,920,494 bytes of margin, including the 8GB free floor.
The superseded 49b reserve and completed-oracle growth reserve are zero; 49c must
finish before 49d launches. The new chain retains an 8GB root floor and reserves
its own future writes. No parent evidence is deleted.

[Exact selection, fast-reseal, early and model commands](../experiments/own-xpu-runtime/stage2/packet49d-round3/WINDOW.md).
The early sequence is K0 → K1a → K1b → K2 → W0p; model sequence is
KD → W2m → WS → WSs → WS128x → WS128. K2 includes all new choices and
banked winners. Output is
`/home/steve/own-xpu-runtime-results/packet49d-round3/build/device-cards01-a`.

## Submission tooling

Commit 1f23e7eee recognizes 49d with its own final seal and runtime revision.
It verifies each native owner's observed selection hash and reads the current
floor from `scripts/packet49_record_threshold.json`. The coordinator updates
that ledger after a successful 49c submission using the bound result and actual
returned submission ID. The approved 49c submission arrived during preparation:
`cmvc9xc0f06o0le01x7afsrcw`. The updater replayed its bound result and advanced
the floor to **45.695513175425305 tok/s**, retaining the old record in history.
The 109 tests and 12 subtests pass again with that updated ledger.
New result bundles pin their threshold; historical
49c/SPEED6 validation stays supported. The helper prepares evidence only.
The strict 512-token gate stays false for the authorized 128-token comparison.

[Integration](../experiments/own-xpu-runtime/stage2/packet49d-round3/INTEGRATION.md),
[independent review](../experiments/own-xpu-runtime/stage2/packet49d-round3/REVIEW-INDEPENDENT.md),
[CPU closeout](../experiments/own-xpu-runtime/stage2/packet49d-round3/CPU-PREPARATION-CLOSEOUT.md).

The copied historical ASAN retention receipt was refused by the new build's
hash binding. Its identity is recorded with the preparation corrections; the
unused new-packet copy was removed and replaced by a verified inventory of
this packet's five sanitizer binaries. The parent's receipt was untouched.

## Device-selection outcome received during closeout

The completed packet54 decision reports combined savings of **30.003 / 30.0015
microseconds**, below the brief's **40 microseconds in each owner** requirement.
The real `selection_gate.py --windows` command revalidated the completed evidence
and refused in 0.37 seconds, before changing selection or creating a final seal.
[Refusal receipt](../experiments/own-xpu-runtime/stage2/packet49d-round3/evidence/selection-admission-refusal.json).
The choices it evaluated were route-exp32-rank4, rows4-shared and production HC.

A concurrent coordinator note in commit `57ccb5e53` proposes proceeding below
40 microseconds. This preparation does not apply that exception: it conflicts
with the explicit threshold in this task. CPU preparation is complete; under
that threshold, no 49d device window is admitted. The documented fast-reseal and
queue commands remain available for a qualifying decision. No kernel rebuild
or numerical rerun is required to bind a qualifying selection. The measured
CPU binding check took 1.63 seconds; a successful full fast reseal is not claimed
because the actual decision is below its gate.
