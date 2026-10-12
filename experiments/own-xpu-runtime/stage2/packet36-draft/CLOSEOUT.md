# Official draft head — CPU preparation closeout

<!-- campaign-closeout -->

## Question and identity

Can packet32's exact two-rank IQ3 target use the official one-token MTP head
without letting guesses alter emitted tokens or target state? This packet copies
packet32 anchor `2e8ec7585c` and retains `iq3-p17-detmath-v2`. The draft reads
`Qwen/Qwen3.8-Flash-Next-FP8`, revision
`bcd9f01ddc9cff2316eb84281bebcd5b058bddce`, with the quantized target's embedding
and head. All work here was CPU-only on the four-card host, at nice19/idle I/O,
with inherited affinity and two numeric threads per native process. The target
is the separately labeled quantized compressed model, not the official FP8 lane.

## Outcome

The CPU preparation passed 46 sealed gate receipts. All ten real-model modes
matched 80/80 token checks and 3,840/3,840 layer fixtures in total. Draft acceptance
was 199/256 (77.7344%), compared with packet31’s 198/256, across four development
prompts. Proposal agreement was 253/256 with its FP8 reference and 255/256 with
its int8 reference. Details are in [CPU results](CPU-RESULTS.md) and the
[build receipt](build-receipt.json). The exact measured per-prompt
acceptance and proposal agreement are in those receipts and [README](README.md).
They are development-prompt measurements, not device performance or a benchmark
headline. No device binary ran and no speed is claimed.

The allocation plan leaves 3,041,228,086 bytes of rank1 capacity after adding
3,345,271,094 bytes for the draft. This clears the requested 1.5 GB allocation
margin; driver overhead and residency are not measured.

## What worked

A separate rank1 DRAFT command consumes only confirmed hidden streams and the
shifted confirmed token. It overlaps rank0 completion or redo. Separate writable
allocations isolate its cache, indexer, controls and scratch; the resident target
head is immutable and shared. Only target HALF replies enter the emitted output.
The resulting ideal cycles are `max(A,B+D)` on a hit and
`max(max(A,B)+R,B+D)` on a miss, before protocol overhead.

BF16 dense weights and group16 expanded int8 routed experts reuse specialized
runtime operation bodies. This is **draft-only requantisation of the official
draft head; cannot change output**. The full head remains the default. Authenticated
file and tensor hashes reject missing or altered official bytes. CPU tests compare
target tokens, all retained target layer fixtures, provider fault behavior, and
complete draft cache/control bytes. [Pipeline agreement](pipeline-draft-agreement.json)
joins real two-rank proposals and cache bytes to the independent captured-input
path under both compilers.

## What failed or remains uncertain

Independent review found a disabled-provider sequence check that could abort a
later target step, an ineffective stall injection, receipt timing gaps and missing
KD identity/fault checks. These were corrected and retested; details are in the
three review notes and [do-not-repeat record](DO-NOT-REPEAT.md).

Host/device draft byte parity, actual device allocation residency, kernel timing,
whole-request decode speed and the benefit of overlapping draft work remain
unmeasured. A genuinely stuck GPU command cannot safely become a no-guess fallback
on the same queue: it follows owner/fault retention rules. Shortlist heads and
speculative draft-cache rollback are unqualified. No claim is made that draft
arithmetic matches the publisher or packet31 bit for bit.

## Evidence and patches

The complete copied runtime and focused additions live in this directory;
[source provenance](source-origin.json) and [target identity](target-source-identity.json)
bind the unchanged target arithmetic. [Official tensors](official-tensors.json)
records every official tensor read. Per-position distances are in
`agreement-*.json`; current binary hashes are in [Binary hashes](BINARY-HASHES.md).
[Wiring](review-wiring.md), [isolation](review-isolation.md) and
[controller](review-controller.md) reviews were independent.

Packet31 removed its scratch captures after publishing hashes. Missing inputs
were regenerated privately from its CPU recipe and checked against those hashes;
no packet31 file or model file was changed. [Retention](RETENTION.md) explains
tracked receipt archives, byte-verified scratch cleanup and ignored coordinator
binaries/input/fixture files. Model weights themselves are not in Git.

## When to revisit

The next step is the coordinator's authorized [device windows](WINDOW.md): the
inherited K/W set, KD with two fresh owners and exact draft bytes, W2m with the
unchanged target v2 oracle, and diagnostic W2mc class timing. A speed verdict
requires two separately registered fresh rank pairs. Respect fault latching,
cooperative stop, loading-rank protection and no retry/reset/hard kill.
[Integration notes](INTEGRATE.md) describe later host-path and replay merges;
each needs fresh source, CPU, KD and target oracle gates.
