# Packet49 CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Prepare a separate two-card IQ3 engine from packet45 SPEED6 at `34c62b433`
with packet47 split32 QSA, while retaining the record's other settings.
The target is the admitted Unsloth UD-IQ3_XXS checkpoint, capacity4096,
23/25 target layers, draft rank1, BF16 KV, write-set snapshots and the pinned
SPEED6 non-QSA dispatch. This October17 preparation uses CPUs only.

## Outcome

The runtime change and coordinator chain are built and sealed. GNU host,
Intel device and GNU sanitizer builds pass; the scoped seal verifies with
32 binary/artifact hashes and 425 source hashes. Device qualification,
full-model oracle completion and speed remain pending. The historical
39.422tok/s result remains unchanged. No packet48 GEMV is enabled: the
production-matched packet48b windows must identify qualifying kernels first.
This closes CPU preparation, not the optimization lane or a performance lever.

## What worked

The integrated split32 bridge has independent CPU coverage for M=1/M=2,
including tails, state bounds and fresh-process agreement. The full-model
oracle runs in a durable CPU-only unit using its independent scalar reduction.
Its completion receipt is separate from the build seal, allowing the
oracle-free K0/K1a/K1b/K2/W0p chain to run first. The unchanged non-QSA
dispatch is pinned and must pass fresh K2 checks.

## What failed or remains uncertain

Packet48 dense controls used a different wrapper; expert controls also used
different fixture and measurement conditions. No single timing cause has
been proved. The initial oracle launch refused before weight access because
idle I/O priority was missing; the manually corrected launch is running.
The initial oracle compilation needed an include-path repair; its overwritten
log is explicitly retained as a reconstruction. A CPU snapshot harness first
refused a missing evidence directory; its successful rerun is recorded.

M=2 is supported by the bridge, while full-engine verification retains
SPEED6's sequential per-row attention schedule. Device exactness, speed,
one-card operation and whole-suite fresh-device repeat coverage remain open.
The 128-token suite matches the old record; it is not the 512-token public gate.

## Evidence and patches

- [Task note and final validation record](../../../../notes/2026-10-17-own-runtime-packet49.md)
- [Coordinator commands and oracle barrier](WINDOW.md)
- [Independent source review](REVIEW-INDEPENDENT.md)
- [Independent attention review](REVIEW-QSA.md)
- [Independent queue review](REVIEW-ORCHESTRATION.md)
- [Oracle identity, unit and completion checks](oracle/README.md)
- [Production GEMV reconciliation](../../../../notes/2026-10-17-own-runtime-packet48b-reconciliation.md)
- [External artifact retention and restoration rules](ARTIFACT-RETENTION.md)

Source deltas and gate summaries remain in this packet; binary and full raw
receipts are retained under `/home/steve/own-xpu-runtime-results/` through the
packet symlinks. Historical packets and unrelated work remain untouched.

## When to revisit

The coordinator runs packet49's early windows and packet48b's matched
comparisons under current device admission, serially on their shared card.
After the oracle passes its completion check, run KD and the model windows.
Integrate any newly qualified GEMV winners in a further recorded source/build
identity and rerun the required device chain. Preserve both old and new token
streams and report their differences before interpreting the new speed.
