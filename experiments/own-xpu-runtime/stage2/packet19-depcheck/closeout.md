# CPU chained-path audit — closeout

<!-- campaign-closeout -->

## Question and identity

On 2026-10-11, audit packet16 resident two-card Flash-Next IQ3 decode after
its captured simultaneous GPU faults. Build a CPU checker for ownership,
RAW/WAR/WAW ordering, poison and lifetime. Test the original model plan/weights
and retained arithmetic-v1 oracle; exact inputs and source hashes are in the
build receipt. Host steve-b70s remained in FAULT HALT. No device ran.

## Outcome

The unsafe admission method is closed: a synchronous CPU mock alone cannot
qualify a new native chained topology. The audit found unwritten snapshot reads,
not a missing application dependency or foreign compute binding. The native
fault cause remains unproven. This closes the CPU audit arm, not the runtime lane.
Gate outcomes are recorded in [build-receipt.json](build-receipt.json).

## What worked

A queued CPU backend with explicit allocation/range contracts detects ordering,
ownership, initialization and release faults. Independent negative tests cover
WAR and cross-queue dependencies. The shipped real plan has a global event chain,
so randomized schedules correctly find only one ready operation. Index guard
negative tests check malformed inputs separately. Source enumeration expands
native split GEMV phases that the CPU mock fuses.

## What failed or remains uncertain

Snapshot poison was hidden by hashing only populated slices. Empty site logs
were also misleading: unchecked runs do not emit per-site progress. No evidence
maps the captured fault addresses to application allocations. Driver event/backing
behavior, EnableDeferBacking, native arithmetic and the conservative foreign-event
host fence still require a separately admitted device test. The CPU checker
cannot qualify these by simulation.

## Evidence and patches

[README](README.md), [ranked audit](ROOT-CAUSE.md),
[hazard review](review-hazards.md), [checker review](review-sanitizer.md),
[patch series](fixes/series), [packet18 handoff](INTEGRATE.md).
Original incident files remain in packet16; [incident-inputs.json](incident-inputs.json)
pins them. Retained gzip traces are complete CPU submission records; the native
trace is explicitly source-derived. Build scripts reconstruct ignored build
outputs; scratch is removed after receipts and hashes are retained. Official
model bytes and the existing local CPU oracle remain external inputs, not
invented or publicly reproducible release assets.

## When to revisit

After the owner's reboot and coordinator admission, begin with a few-KiB
shared-context Q0→Q1→Q0 event/copy canary, conservative host fences and bounded
fault monitoring. No 53 GB load before that passes. Apply reviewed packet18
hunks and rerun its own arithmetic-bound CPU gates as described in INTEGRATE.md.
