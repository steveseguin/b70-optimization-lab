# Packet134 submission replay — attribution closeout

<!-- campaign-closeout -->

## Question and identity

Does rank0's host fail to enqueue its speculative target half quickly enough
to explain packet128b's 1.679 ms hit compute gap and 1.885 ms command gap?
CPU-only reanalysis on steve-b70s, October 18, 2026. Source authority is
packet124c bundle7, unchanged `iq3-p49-split32-v1`, full BF16 KV, 24/24 split,
rank1 draft, 80,128-row draft prefix, split target head. Observations come from
packet128b's twelve 64-token requests and fixed fixtures 10–16, 84 complete
cycles. Input source and receipt identities are frozen in [input-pins](input-pins.json).

## Outcome

**Reject submission replay as the next lever supported by these receipts.**
On hits, 1.594 ms occurs after the snapshot and before the target sequence;
0.085 ms is internal to that sequence. On misses, an additional 2.046 ms
precedes correction, with about 0.085 ms internal to each half. Each current
half has 564 kernel events. The host spends 2.860 ms enqueuing the speculative
half while compute occupies 11.363 ms on hits; these times overlap.

The command gaps measure something else: 1.276 ms of the 1.286 ms pre-half
hit gap overlaps rank1's pending draft command. Another 0.598 ms is between
half completion and accept, including suffix service and verification. The
same miss boundaries are 1.293/1.305 ms and 0.602 ms before rollback.
The explicit rank0 wait for hidden-state publication averages only 0.0012 ms
in this trace. Full means and medians are in [ATTRIBUTION.md](ATTRIBUTION.md).

No runtime change was built or adopted. The conditional closeout branch means
there is no new smoke, bracket, proposal or device admission. No GNU/Intel
runtime, controller, reset or queue gate is claimed. The record is unchanged.

## What worked

Same-compute-clock endpoint attribution isolates the large gaps without
subtracting invalid copy clocks. Same-request host interval intersections
expose the draft-command wait omitted by the publication-only metric.
All four original rank0 budget rows reproduce means/medians within 1e-9 ms.
All 84 cycles retain complete 24-layer/564-kernel speculative coverage and
all 18 misses retain correction coverage. All 182 parent symlinks are unchanged.

Sixteen CPU tests pass, including deliberate timing-domain, continuity,
receipt, symlink and false-overhead-pass errors. No kernel or numerical
optimization qualified; these are analysis checks only.

## What failed or remains uncertain

Packet128b's own overhead gate failed: 51.475451 tok/s versus a required 52.2.
The sampled speculative halves spend about 5.211 ms in profiling on hits.
This can alter the relative readiness of the two ranks. Neither an ordinary
bundle7 critical path nor a forecasted replay gain can be inferred.

Preparation contains host lookup/decode/uploads and reports major faults,
but their individual durations are absent. Major-fault counts do not establish
that every preparation delay is disk I/O. Excluded event/fixture boundaries
are unobserved, not zero. The draft-command overlap is host time, not pure
draft compute. Historical packet34 replay neutrality is a different workload.

## Evidence and patches

- [Numeric report](ATTRIBUTION.md), [per-cycle evidence](evidence/attribution.json),
  [source and raw-receipt hashes](input-pins.json).
- [Reproducer](analyze.py), [adversarial tests](test_analysis.py),
  [validation receipt](evidence/validation.json), [test log](evidence/tests.log),
  [analysis-only seal](evidence/analysis-seal.json).
- [Source interpretation and ledger review](README.md), including packets
  22/34/35/61/61x/70 and current prepared commands/native controller.

No implementation patch was attempted. The retained raw packet128b files stay
at their original pinned paths; they are not copied into this packet. Replaying
the analysis needs those local raw files. They are not promised as public Git
assets. This packet retains compact outputs and hashes, not model weights.
Build bytes are zero; total packet files are below 1 MiB.

## When to revisit

Reopen recording only when low-overhead, matched current-runtime timing shows
material gaps *inside* the target submission sequence, or a new schedule
needs replay for ownership. Require unchanged kernel identity/order, resident
inputs, no captured H2D, bounded shared allocation ownership, byte/rollback/
reset/argument/queue/drain gates and a sealed 12 × 64 smoke before a bracket.

The immediate measurement target is token preparation: separately time lookup
reads, exact decoding and transfers, then test an exact residency or transfer
change under current memory admission. Preserve the full pending-draft wait
when timing startup. No host page-cache or memory setting change is authorized.
