# Packet84 CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Can packet81 expert reads, packet82 recurrence and packet83 draft heads compose
independently on the coordinator's pinned packet80 selection without another
merge build? This is the existing quantized compressed lane, unchanged target
arithmetic `iq3-p49-split32-v1`, full BF16 KV and packet49 oracle. Work ran on
steve-b70s CPUs on October 17, 2026 local time. No GPU or service was started.
The exact source/build identity is in build-device-receipt.json; the source
milestone is a21cac5db, based on packet80 at d7051c047.

## Outcome

CPU preparation passed. The factorized independent-operator matrix covers all
768 choices under GNU and Intel twice. The real production initialization,
post-load allocation and dispatch paths ran with a mock backend for both ranks
of all 1,344 allowed configurations (2,688 censuses). The miniature gate has
223 fresh runs: the packet80 reference and 111 configurations twice. Target
outputs and 96 intermediate fixtures per run match the reference; draft state
repeats exactly. The regression suite passed 1,488 tests and 776 subtests.
The final orchestration-focused suite passed 12 tests.

Q4 adds 146,227,200 bytes on rank 1, leaving 798,864,694 bytes of arena headroom
and 2,827,679,030 bytes of modeled free card memory including the inherited
reserve. All new draft choices require placement 1. Eight actual reselection
rehearsals passed, including all new draft choices and all inherited placements,
then restored the baseline. Reseals took 2.87–3.46 seconds; selected full dry
runs took 28.74–55.48 seconds. Neither recompiles, and cached proof and binary
hashes stayed unchanged. These are preparation timings, not model speeds.

## What worked

Packet80's source copy preserves its host, HC, route, norm and placement choices.
The new dispatch sites are independently selected. Hash-bound component byte
transcripts plus every full-shape dispatch capture avoid recompiling the product.
Lazy view seals and a separate selected dry run make coordinator changes cheap.
The selected dry run imports the real shared wrapper, exercises admission in
isolated test roots, checks K2, dispatch merge and submission consumers, and
runs all eleven window plans plus both screen-lane plans.

## What failed or remains uncertain

The inherited KD metadata assumed packet56's fixed prefix. It now binds the
selected row count and packet83 coverage hash; tampering tests cover both.
Initial inherited tests lacked reference.json or the not-yet-created selected
bundle. The pinned reference and correct preparation order resolved those
failures; the final regression log is the verdict. An earlier miniature pass
used the historical label parent75 for the actual packet80 binary; both raw
pass histories are retained, and the final report correctly says parent80.

The CPU matrix is factorized by independent operator, not 768 complete model
runs. Recurrence matches same-compiler production bytes, including NaNs; the
unchanged production NaN payload differs across compilers. Q4 matches an
independent scalar Q4 reference, not original Q6 draft arithmetic. Smaller
prefixes also change proposals. The unchanged target verifies every accepted
token. Real packet49 device parity, fresh-run determinism, physical residency,
acceptance and record performance remain unmeasured for the composed bundle.

## Evidence and patches

- [CPU byte matrix](evidence/cpu-byte-identity.json),
  [authentic Q4 head check](evidence/real-head.json),
  [full-shape captures](evidence/full-shape.json), and
  [per-card admission](evidence/memory-admission.json).
- [Miniature runs](evidence/cpu-gates.json),
  [negative cases](evidence/negative-gates.json),
  [cached proof](evidence/dry-run.json), and
  [reselection receipts](evidence/reselection.json).
- [Regression log](../../ops/packet84-orchestration/final-tests.log),
  [orchestration tests](../../ops/packet84-orchestration/orchestration-final-tests.log),
  and [current readiness](../../ops/packet84-orchestration/ready.json).
- [Parent/source pins](parent-source-manifest.json),
  [draft patch](packet83-draft.patch), and [retention/restore details](RETENTION.md).
  The compressed archive retains 156,549 generated/raw CPU files with verified
  per-member hashes; originals remain local. Binaries and inherited object
  dependencies are local research build products, not a standalone publication.

## When to revisit

Rerun the CPU-only orchestration helper when the source screens finish. It uses
each packet's own compare/best logic, requires exact 13/13 results and an
improvement over both same-lane controls on both lanes for every new selection,
and refuses unresolved or conflicting evidence. Resolved no-winner screens
retain the baseline. A coordinator may then use the recorded command after
verify_ready.py passes. Preparation never launches it. The fresh composed chain
must clear every device quality and performance gate before any submission.
