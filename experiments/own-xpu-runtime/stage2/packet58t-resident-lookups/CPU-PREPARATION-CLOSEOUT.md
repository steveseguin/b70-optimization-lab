# Packet58t resident lookup preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Can the packet58p one-card Flash-Next UD-IQ3_XXS engine eliminate file-backed
host lookup reads without changing packed bytes or arithmetic? October 18,
2026; CPU-only on steve-b70s. Frozen 58p/58j entry and kernel objects, tile16
selection, and a local copy of 58r's one-load bracket. Exact source and binary
identities are in [the seal](build-receipt.json).

## Outcome

CPU preparation passes. Device equality, full-size resident loading and speed
remain unmeasured. The unchanged packet49 oracle remains mandatory on device.
No benchmark record or complete model qualification is claimed.

## What worked

The source census identifies exactly two sparse tensors: one embedding row and
sixteen PLE rows per token, 3,540 packed bytes. The candidate copies their full
29,321,610,240 bytes into read-only anonymous memory at load, compares streaming
source and destination SHA-256, and refuses a missing resident table.

GNU and Intel copy/dequant tests pass twice each. Four fresh miniature engine
pairs have identical tokens and all 40 retained outputs, including the frozen
58p reference. All 32 resident decode preparations have zero major faults.
The independent 1,024-token packed-row replay also has zero resident major
faults after warm-up and makes no file reads in its resident loop.

Twelve full-size mock binding checks, ten native startup/oracle paths, twelve
chain argument paths, four screen argument paths, eight budgets and 48 K1
fixture cases pass. All 109 Python tests pass, including drain, seven local
teardown cases, missing evidence, altered kernel logs and memory receipts.
The generic teardown scanner recognizes the helper but has no one-card
template; the actual adapter is checked by the local integration tests.

## What failed or remains uncertain

The CPU file fixture is cached: both its original and resident paths have zero
major faults. It proves the new access path and exact bytes, not a cold-disk
performance gain. Full production copies cannot fit within this task's 8 GB
CPU allowance. Anonymous pages are not locked against swap. Copying reads the
source pages before the A0 control, so the one-load bracket cannot recreate
58n's earlier file-cache state. All views retain identical anonymous copies.

During preparation, copied executable permissions and inherited test budget
expectations needed correction. Initial Python failures are retained in
`evidence/python-initial.log`; final gates supersede them. No GPU was used.

## Evidence and patches

- [Inventory and memory accounting](ANALYSIS.md)
- [Explicit integration delta](resident_source.py), [copy owner](native/resident_lookup.hpp)
- [Copy/dequant/fault checks](evidence/resident-copy-cpu.json)
- [Native output checks](evidence/resident-engine-cpu.json)
- [Policy gates](evidence/python-cpu-gates.json), [build](evidence/build.json)
- [Temporary queue plan](evidence/queue-plans.json), [reproduction](README.md)

The retained build is 89,825,446 bytes; peak compile RSS is 711,872 KiB. Build
artifacts are ignored and restored/rebuilt using the README. No model payload,
full-size copied table or GPU output is tracked.

## When to revisit

Run the proposed whole-host card-0 A0/B0/A1 screen through the coordinator when
admitted. It uses twelve fixed prompts per view, all 128 output tokens checked
against packet49, and a 7,200-second watchdog for a 15–25 minute estimate.
Compare fault counts and preparation time alongside speed. The later chain
refuses until fresh evidence proves output equality, complete memory receipts,
zero resident preparation major faults and the registered speed/drift gate.
