# Packet74 CPU preparation closeout

<!-- campaign-closeout -->

## Question and identity

Question: can dense GGUF blocks replace expanded codes/scales while keeping
packet70's target arithmetic and reduction order? Identity: packet70 copied
sources, packet49 oracle, iq3-p49-split32-v1, full BF16 KV, wide64 experts,
24/24 split, rank1 draft-HC, batch rollback.

## Outcome

Outcome: four views are prepared for the coordinator. GNU/Intel byte gates,
both engine builds, device-microbenchmark compile, four linked-selector
checks,79 wrapper mocks,14 possible screen plans and two private queue plans
pass. No GPU or full model ran. This closes CPU preparation, not the lever or
model lane. Device correctness, determinism, actual peak VRAM and speed remain
unknown; a slower or inexact candidate stays unadopted.

## What worked

Useful mechanism: direct packed block reads with alternating-alignment handling,
register decoding and unchanged lane arithmetic. No row staging or decode
scratch.

## What failed or remains uncertain

Negative history: earlier packed kernels were slower; see the task
note. Limitation: head-only needs a separate unchanged draft prefix, reducing
its net residency saving to8.94 MB. Dense packing covers selected projection
classes; fused HC/small tuples are outside this candidate.

## Evidence and patches

Retain [CPU bytes](evidence/cpu-byte-identity.json), [build identity](build-device-receipt.json),
[microbenchmark build](evidence/microbench-build.json), [VRAM](VRAM.json),
[selections](selections/), [final validation](evidence/final-validation.json),
[history](../../../../notes/2026-10-17-own-runtime-packet74.md), and all sources.
## When to revisit

Next condition: coordinator-run exact device screens and matched timing, then
full-chain qualification before any adoption or submission. If unpack costs
lose, retain device evidence and require a new load/unpack mechanism to reopen.
