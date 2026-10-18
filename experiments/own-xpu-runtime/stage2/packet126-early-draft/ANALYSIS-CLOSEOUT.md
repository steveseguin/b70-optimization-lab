# Packet126 guessed-token early draft — analysis closeout

<!-- campaign-closeout -->

## Question and identity

Can rank1 draft from its final target hidden state and the already-proposed
token before target-head verification, retain it on hits and restore/recompute
on misses? October18 CPU-only study, packet124 bundle8 BASE (native bundle7),
quantized compressed Flash-Next, `iq3-p49-split32-v1`, BF16 KV, two B70 cards
per lane, 24/24 target split, rank1 draft, split target head, fixed80,128 draft
prefix. Saved complete packet118 A/B candidate screens supply12×99 intervals
each. No new device run occurred.

## Outcome

**Inconclusive and not admitted to implementation.** The no-recovered-wait
simulation predicts −1.9517% on A and −1.9622% on B. Recovering a uniform
0.427631/0.432252 ms per interval would reach +0.5% before transaction costs.
That wait is unobserved. Decompositions matching the same current traces give
opposite decisions, so neither a positive gain nor a proved below-threshold
closeout is justified. This closes this CPU preparation at its evidence gate,
not the runtime lane or the underlying idea.

## What worked

The unchanged packet108/packet85 method joins by position and reproduces all
2,376 current intervals. The source DAG distinguishes target suffix work from
rank0 idle and accounts for every miss's wasted draft. All141 existing negative
indexes were inventoried. Eight analysis tests and the read-only packet124
drain scan pass. All archived input bytes are verified.

## What failed or remains uncertain

Separate head readiness, compute and merge-wait timestamps are absent. The
current command trace cannot identify recoverable wait; the old head timer
cannot fill that gap. Candidate byte/state parity, draft transactions,
all-position hit/miss correctness, startup windows, native launch-limit gate,
seals, 12×64 smoke and matched speed checks remain unperformed because build
admission is not established. No runtime patch, compile, build or queue
proposal was made. No GPU, service, frozen tree or host setting changed.

## Evidence and patches

[Source DAGs](README.md), [budget and sensitivity](RESULTS.md),
[simulator](simulate.py), [result](simulation.json),
[intervals](intervals.json.gz), [negative-index audit](prior-audit.json),
[prior comparisons](prior-results.json), [tests](test_simulate.py),
[boundaries](DO-NOT-REPEAT.md),
[work note](../../../../notes/2026-10-18-own-runtime-packet126.md).
RESULTS.md records retention/restoration for both original-byte archives.

## When to revisit

A separately authorized timing window must expose hidden-ready, prefix-ready,
suffix entry/exit/reply and merge entry/exit on the shared host clock, bound to
request/position/sequence. Admit only a schedule whose measured wait savings
exceed its wasted-draft/rollback costs and support the owner's ≥0.5% threshold.
Then implement in a fresh copy with transaction tests and all required CPU
gates before proposing the exact smoke and matched bracket. No GPU work or
queue change is authorized or proposed by this analysis.
