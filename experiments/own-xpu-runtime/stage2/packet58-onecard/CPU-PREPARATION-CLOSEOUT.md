# Packet58 CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Can packet56's unchanged target kernels support one B70 with an 18 GB LRU
expert cache and exact pinned-host or streamed misses? Unsloth UD-IQ3_XXS,
revision 766911a6b7369840a91dbcd95f9f997acaab6cd6, packet49 split32 oracle,
plain greedy decoding, BF16 KV, 4K context, October 17, 2026.

## Outcome

CPU preparation passes. Both host and device binaries compile; no device
binary ran. Cache arithmetic/lifetime, persistent request reset, passive
admission and evidence gates pass. Actual one-card correctness, memory fit,
zero-copy access/bandwidth and model speed remain unmeasured.

## What worked

An independently written global LRU cache redirects the same production
expert kernels through fenced pointer tables. Copy-only queue ordering keeps
host sources, cache slots and tables live until their events complete.
CPU hit/miss/mixed expert outputs match frozen production arithmetic.
The [route replay](CACHE-POLICY.md) supports trying global LRU without claiming
a one-card hit rate. The request loop preserves only immutable weights.

## What failed or remains uncertain

Review caught small repeated host buffers that could overstate PCIe bandwidth,
an untracked DMA exception path, stale pinned-byte reporting and incomplete
prerequisite hash coverage. These are fixed before device admission; their
findings remain in the review files. An initial tiny-model request used more
positions than its eight-position default and refused; the proper bounded
pipeline-mini context gate passes. No device fault occurred in preparation.

Between-position fills are currently fenced and charged, not overlapped with
next-position compute. Host-USM unsupported devices fail closed at K1.
The admitted full-bank host budget is tight. MTP and external 128-token scope
review remain separate work; no 512-token headline gate passes here.

## Evidence and patches

[CPU build](CPU-BUILD.md), [cache gates](CACHE-CPU-GATES.md),
[cache review](REVIEW-CACHE.md), [submission review](REVIEW-SUBMISSION.md),
[CPU cache receipt](evidence/cache-cpu-gates.json),
[Python gate receipt](evidence/python-cpu-gates.json),
[reset receipt](request-reset-cpu.json), [CPU K1 golden](k1-cpu.json),
[memory budget](MEMORY.md), [retention](ARTIFACT-RETENTION.md).
All implementation changes are in this separate packet; sealed parents and
packet57 are untouched.

## When to revisit

The coordinator runs the two fresh K1 windows, then KD/W2m and three complete
suites using [WINDOW.md](WINDOW.md). Fresh memory, fault, ownership and storage
admission are mandatory. Use those results to select zero-copy or streamed
misses and measure the next larger optimization; no lane is declared finished.
