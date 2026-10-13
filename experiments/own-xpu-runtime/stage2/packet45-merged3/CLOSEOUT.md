# Packet45 CPU merge closeout

<!-- campaign-closeout -->

## Question and identity

Merge packet40 suite/draft behavior into packet44 context handling, then add the
card-measured packet42 candidates, packet39 plan epilogues and selectable rank0
drafting. Parent identities are frozen in [merge-start.json](merge-start.json).
The model is the quantized compressed Unsloth UD-IQ3_XXS release, with official
draft tensors, unchanged arithmetic identity `iq3-p17-detmath-v2` and BF16 caches.
This work is CPU-only; the linked device binary has not been executed here.

## Outcome

The implementation and CPU qualification are recorded in
[build-receipt.json](build-receipt.json) and [cpu-tests.json](cpu-tests.json).
Only those exact source and binary hashes are covered. This closes preparation
of one merged packet; the optimization lane and device qualification remain open.
No earlier card saving is claimed as a merged speed result.

## What worked

Capacity wins every overlap with packet40. The draft uses K2-selected kernels
and non-blocking readback. Rank0 owns an additional output head and receives
position-bound final streams before rank1 runs its head; rank1 remains the sole
target-token authority. Accepting a correct half before starting the next draft
preserves overlap. Wrong halves drain and restore exact target state, including
both prepared launch banks. [Protocol review](review-draft-rank0.md),
[rollback contract](ROLLBACK.md) and [memory review](review-memory.md) retain the
independent findings and their fixes.

Measured prior halves were 16.6 and 17.1 ms, with a 2.85 ms draft. Moving two target
layers gives 22/26 layers for rank0 drafting. Assuming uniform rank0 layer cost,
the estimated new loaded halves are 18.0667 and 18.4833 ms. These are balancing
estimates, not new measurements. Rank1 drafting remains selectable at 24/24.

[KERNELS.md](KERNELS.md) records each measured predecessor delta, actual registered
candidate and plan-level removed launch. Packed gate and fused epilogues remain
separate legal plans. K2 compares fresh integrated chains and uses 3% for classes
above 2 ms/token, otherwise 10%, with the packet44 capacity-aware duration refusal.

## What failed or remains uncertain

The imported cooperative pool assumed capacity/4; a first repair using extent/4
also failed the actual 136-position fixture. Both failures remain in the fixture
ledger. The corrected mapping uses the number of newly completed/append pools.
The CPU campaign receipt initially allowed a partial prefix to appear passed;
completion is now explicit and regression-tested.

Packet42 dense.fourparts stays excluded. Its four shortened rows omitted retained
expanded metadata: real Q6/Q8 strides are 8112/7296 bytes, not 7680/6912. A single
shortened-row CPU fixture missed the multirow addressing defect seen on the card.
The original device mismatch and source analysis are retained in KERNELS.md.

CPU tests do not establish device exactness, physical allocation overhead,
reverse-handoff overlap or speed. Real CPU checks cover the first eight tokens
of one fixed prompt, not complete 32/64/128-token suites. The coordinator must run
all nine windows for every capacity/placement under current host admission.
Native controller sanitizer mocks cover rank1 placement; the actual merged
runtime cases separately exercise both placements.

## Evidence and patches

All implementation files live in this packet. [INTEGRATE.md](INTEGRATE.md) and
[merge-inventory.json](merge-inventory.json) list every difference against both
parents; parent evidence is untouched. [CPU-REPRO.md](CPU-REPRO.md),
[ARTIFACT-RETENTION.md](ARTIFACT-RETENTION.md), [BINARY-HASHES.md](BINARY-HASHES.md)
and the build receipt explain reproduction, retention and exact binary identity.
Failed and superseded CPU receipts are historical evidence and never substitute
for final source-bound gates.

## When to revisit

The coordinator's admitted [window chain](WINDOW.md) is the next step. Measure
both draft placements, actual 22/26 half times and memory on the cards before
choosing a device default or claiming speed. Any source change requires new
matching CPU gates and a new seal; any changed device selection requires the
fresh K1/K2 and quality chain. [DO-NOT-REPEAT.md](DO-NOT-REPEAT.md) preserves closed
failure mechanisms without treating the lane as finished.
