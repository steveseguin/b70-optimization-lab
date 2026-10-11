# Router padding diagnosis — closeout

<!-- campaign-closeout -->

## Question and identity

Which tensor caused the v4 boundary STOP on October 11? Official Flash-Next
FP8, Screen 1b vLLM 0.30.0 XPU/0.1.14.1 kernels, TP4/EP4, 64-token startup
profile, attempt-6 placement. This follow-up uses CPU only.

## Outcome

Localized: raw `[64,10]` int32 router IDs are all `-1` on every rank.
Production compatibility repair applied; 143 CPU tests pass. Native proof is
pending and there is no new quality certificate or speed measurement.

## What worked

Strict validation before alignment stopped malformed input without a new
kernel fault. All four snapshot hashes match 640 signed `-1` values. Frozen
source explains the padding producer and negative-index consumer. The new
production helpers preserve active routing and pass the unchanged boundary.

## What failed or remains uncertain

The pinned wheel lacks the older lab alignment negative-ID guard. The prior
single-rank probe bypassed the padding producer. Attempt 8 has no fault-VA
instruction match; the later clean refusal cannot identify every historical
fault. The v4 watcher snapshot covers about 270 post-exit seconds, short of a
complete 305-second gap. Native startup and whole-model exactness remain open.

## Evidence and patches

[Analysis](../../../../notes/2026-10-11-moe-boundary-caught-router-ids.md),
[receipt/source index](../evidence/moe-boundary-router-ids-20261011/evidence-index.json),
[CPU receipt](../evidence/moe-boundary-router-ids-20261011/cpu-validation.json),
[production patch](router-padding.patch), [seal](patch-manifest.json).
Original external run stays read-only. Compressed indexed receipts restore
with `gzip -dc` and must match their original hashes.

## When to revisit

Run the [v5 fixed production path with boundary ON](../overlay-moe-boundary/README.md)
in a fresh admitted coordinator window. Keep all existing memory/fault/quiet-gap
checks. A future native guard port needs its own build and parity gates;
the certified older-runtime patch remains preserved. No automatic retry.
