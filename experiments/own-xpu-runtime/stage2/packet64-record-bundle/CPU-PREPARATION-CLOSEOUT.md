# Packet64 record-bundle CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Can packet61x's prefix, spin/pure-spin and HC engine expose both rank1 target
placements plus packet63 draft-HC and packet62 batched rollback as sealed
choices, while retaining a placement-aware full chain? October 17, 2026,
steve-b70s; CPU helpers only. Target is the same quantized IQ3 model and
packet49 oracle, with full BF16 KV. Source identity is in the build receipt.

## Outcome

Accepted for coordinator device qualification. One binary has eight sealed
views; prepared default is 24/24, production draft, control copies. Resealing
is about 1.3 seconds. No packet64 GPU result or speed claim exists.

## What worked

Target fixtures equal packet56. All four kernel choices have two matching
fresh draft runs. Controller checks cover 1,123 cases; mailbox fault tests and
pure-spin tests pass. The 975-descriptor copy fixture is byte exact.
Both placements pass memory admission. All 32 wrapper plans pass. Chain and
submission tests pass 113 tests plus seven subtests. The extended input and
write-path checker and chain plan pass for both placements.

Packet61x fixes from `53ffe4605` supply local KD scratch, complete input/write
checks and hash-bound early resume. Lane admission from `c495d1d6a` supplies
whole-host speed windows and a hold-lane-B companion. Parent packets and
running jobs remain unchanged.

## What failed or remains uncertain

CPU tests cannot establish device equality, draft acceptance, timing or live
lane overlap. K0's short owner must still leave the module's passive device
proof; missing proof fails closed. Complete K0..WS128 is pending. The strict
512-token final gate is false under this inherited 128-token record path.

Review found and fixed hard-coded resume destinations in the plan/submission
entry points and missing prerequisite admission-sidecar checks. Synthetic
submission tests initially used the wrong launched-owner set; correcting the
fixture retained the production two-fresh-owner requirement.

## Evidence and patches

[Validation manifest](cpu-validation.json), [CPU gates](evidence/cpu-gates.json),
[tests](evidence/final-tests.log), [memory](evidence/memory-admission.json),
[path checks](evidence/input-checks.json), [build identity](build-device-receipt.json),
[retention/restoration](RETENTION.md), [commands](WINDOW.md).
The lane module's upstream patch and reference receipt are retained locally;
`chain_pipeline.py` is the private masked chain adapter, preserving the sealed
engine pipeline used by the eight screens.

## When to revisit

The coordinator completes the outstanding screens, fast-reseals the chosen
view, then runs the registered chain. Fresh exactness, deterministic repeats,
full input checks and whole-host speed proof decide qualification. If a
stopped packet64 chain already passed K0..W0p, explicit same-identity resume
can retain only those hash-bound early receipts and rerun all model windows.
