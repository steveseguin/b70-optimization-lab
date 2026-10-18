# Packet58aa one-card MTP re-check — closeout

<!-- campaign-closeout -->

## Question and identity

On October 18, 2026, can the frozen packet58z one-card 29.260 tok/s line add
58h's official-derived draft and causal M=2 verification, keep the measured
host/device bounds and unchanged `iq3-p49-split32-v1` outputs, and support
at least +5%? CPU-only saved-evidence review, not an implementation experiment.

## Outcome

**No build.** The old host-memory rejection is superseded: this conservative
layout review needs 103.314 GB available. Device fit costs 3.337 GB of target
cache for resident drafting, leaving 18.216 GB. Resident projections are
25.03–29.16 tok/s against 30.723 required. Even the favorable shared-cache
sensitivity is 30.62 before draft pollution/misses. These are estimates only.

## What worked

The measured policy admits a conservative host extension without shrinking
reserves or relying on a 0.66 GB shadow for all new allocations. Head sharing
still adds zero weight bytes. Two retained route captures quantify per-layer
union growth; the delayed-publication replay charges new misses and cache loss.

## What failed or remains uncertain

No transferred timing scenario clears the gate. True causal M2 scheduling,
wrong-proposal routes, feedback, sparse remote-read timing and cache contention
remain unmeasured. Historical operator pairs are independent snapshots. The
shared-cache favorable sensitivity is not a complete implementable placement.
No GPU run, output-quality pass, fault or runtime patch occurred here.

## Evidence and patches

[Analysis](ANALYSIS.md), [reproducer](analyze.py), [numeric results and source
hashes](analysis.json), [all layer unions](route-union-by-layer.csv),
[negative index](DO-NOT-REPEAT.md),
[work note](../../../../notes/2026-10-18-own-runtime-packet58aa.md).
Frozen packet trees and orchestration stay unchanged. No implementation patch
is created because the build gate fails.

## When to revisit

A distinct exact mechanism or complete causal timing evidence supporting
less than 58.164893 ms per 1.787-token expected cycle, including all draft,
state and cache costs, while retaining the measured host policy and 1.5 GB
device reserve. This closes this composition, not the one-card lane.
