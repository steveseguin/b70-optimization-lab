# Packet58n analysis and CPU screen preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Why did packet58k's down-tile16 + route-fast + rec-both-plus bundle lose on
one card, and is a single lever worth screening? October 18, Unsloth
UD-IQ3_XXS, card 0, unchanged packet49 arithmetic, BF16 KV, plain decode,
twelve prompts × 128 tokens, 18 GB expert cache and 48.6 GB pinned experts.

## Outcome

CPU analysis complete; down-tile16-only bracket prepared, device outcome
pending. All 2,386 position-level cache counts/bytes agree. The bundle adds
7.83 ms host preparation with 12.7 major faults/token versus 0.13, while
cache wall and host wait spans fall. This explains the observed timing
location without establishing why host page residency changed. No new speed
or quality result is promoted. Both old arms are exact; the old bracket is
incomplete. The brief quotes the all-prompt median, distinct from the
registered class-balanced statistic.

## What worked

Receipt/epoch joins, source-backed byte accounting and host timing/fault
counters distinguish the observed host cost from unsupported PCIe theories.
Both fresh K1 host/mixed down cases improve with tile16, supporting an
isolated single-lever screen. Reusing unchanged native binaries avoids a
build and keeps retained build bytes at 39,526,592. All 82 Python checks,
seal verification and three temporary queue plans pass.

## What failed or remains uncertain

No per-layer device timings or ordinary-layer route counters were retained.
The cause of the host-I/O disparity remains unlocalized; physical PCIe read
volume and sparse-miss kernel behavior remain unknown. Device-cache-only
tiling needs new per-residency dispatch and conversion gates and is deferred.
The prepared candidate has not run; fresh candidate repeats/full-chain gates
remain necessary before any record or submission.

## Evidence and patches

[Analysis](ANALYSIS.md), [reproducer](analyze.py),
[source/raw snapshot manifest](analysis-inputs.json),
[per-position pairs](position-pairs.jsonl.gz),
[copied wrapper provenance](parent-screen-manifest.json),
[CPU checks](evidence/python-cpu-gates.json), [seal](build-receipt.json),
[temporary plans](evidence/queue-plans.json),
[new proposal](../../ops/lane-queue/proposed-p58n-screen-A.txt),
[restore and handoff](README.md). Raw receipt snapshots are retained here
because the source run files are ignored/untracked. No originals are removed.

## When to revisit

The coordinator can schedule the exact three-arm proposal in a 33–39 minute
whole-host gap under fresh admission. Examine retained preparation/fault
counters alongside the unadjusted endpoint result. No retry, alternate arm,
host-setting change or record chain is automatically authorized. This closes
the requested CPU preparation, not the one-card optimization lane.
