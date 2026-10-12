# Packet 32 CPU preparation closeout

<!-- campaign-closeout -->

## Question and identity

Question: can the packet29 arithmetic-v2 runtime keep both layer halves active
without shared device ownership, and safely discard a wrong next-token guess?
Identity: quantized compressed Qwen3.8 Flash-Next UD-IQ3_XXS, source anchor
`04e99e40e6`, unchanged `iq3-p17-detmath-v2`, unchanged BF16 state/KV and dispatch
vocabulary. Host mini and real gates exercise the same rank/controller paths;
only the host device backend and layer-streaming storage differ from native.

## Outcome

The implementation is two native rank processes, each with one single-device
context and queue, joined by host byte IPC. The controller overlaps known prompt
inputs and optionally guesses generation inputs with n-grams. Scripted guesses
are diagnostic. Rank 0 writes GDN/convolution candidates into alternate banks;
QSA append rows are overwritten on redo. Rank 1 only receives confirmed work.
No arithmetic source, reduction order, weights or precision was changed.

## What worked

### CPU evidence

The authoritative completed counts and binary bindings are in
[cpu-tests.json](cpu-tests.json) and [build-receipt.json](build-receipt.json).
All eight real-model rows passed and are sealed: 64/64 tokens and 3,072/3,072
layer fixtures in total. All-hit scripts recorded 7/7 hits; all-miss scripts
recorded 7/7 misses with exact redo. N-gram recorded one guess and one miss in
each compiler run, so no speed benefit is inferred for this prompt.

- GNU mini: 130 cases, including all 126 binary hit/miss patterns of lengths
  1–6, n-gram, prompt overlap disabled, and a 64-token randomized run.
- Second-compiler mini and ASan/UBSan mini: 7 cases each. Every short case checks
  8 tokens, 32 layer fixtures and 1,188 rank-0 state files against sequential.
- Resident prepared-binding path: 12 cases (four modes under GNU, Intel host,
  and ASan/UBSan), including complete state comparisons.
- Pure controller: 1,093 hit/miss/no-guess patterns through length 6 and 12 long
  randomized sequences; 5 test groups include n-gram lookup and terminal discard.
- Independent IPC/teardown review: 11 protocol tests. Native host FAIL and STALL:
  2 tests; both ranks stop without signals, retained PIDs or leaked owner bytes.
- The W0p native host path: both compilers, 1,000 handovers and 1,000 tiny kernels
  per rank, shared bytes checked and both owners safely retired.
- Inherited fixture gate: 4 fresh processes, two per compiler. Each checks 111
  fixtures from 93 source fixtures, 2,604 GEMV checks, 196 small-GEMV checks and
  51 adapter-only checks. Odd lengths, route ties and route NaNs remain covered.
- 10 owner/lifetime suites, 21 admission/window tests, 10 validation checks,
  6 negative entry checks, and 1,056 symbolic ordered-reduction checks.
- 306 kernel captures, maximum 744 bytes; the deliberately oversized 1,025-byte
  capture fails compilation. Precise flags pass on every compile and link command.
- 35 arithmetic/kernel/dispatch source files match packet29 byte for byte.
  Expert-down finite checks: 31,416 per process in four fresh processes.

Real-model gate: the 87-token prompt and 8 target-generated tokens, all four
providers (`none`, `ngram`, all-hit script, all-miss script), under both host
compilers. Each mode matched **8/8 tokens and 384/384 layer fixtures**
against the v2 incident-retrospective oracle. See the eight `real-*.json` receipts
and the two `real-campaign*.json` process/memory receipts. CPU wall time is never
a model performance claim. The build seal refuses missing or mismatched gates.

## Reviews and fixes

The independent rollback review derived its own inventory from the launch dump
and code: 1,015 buffers, 890 sites, 37 banked temporal buffers totaling 29,601,792
extra bytes, 24 QSA append arrays, 3 temporal controls, 4 external inputs and
947 overwrite-only buffers. See [ROLLBACK.md](ROLLBACK.md),
[review-rollback.md](review-rollback.md) and `rollback-inventory.json`.

The independent identity review found an uninitialized alternate bank; both
banks are now initialized. [review-identity.md](review-identity.md) records the
unchanged arithmetic and the inherited nonfinite limitation below.

The controller review found and fixed an expected-FINISH exit race, non-idempotent
failed cleanup, misleading handover/idle timing, and missing fault watching during
drain. Class timing now sets diagnostic flags at both receipt levels. See
[review-controller.md](review-controller.md). No unresolved review finding remains
in the reviewed CPU preparation.

## What failed or remains uncertain

No device ran. No speed is claimed. The native binary was compiled, never
executed or used for device discovery. The next evidence is the coordinator's
K0 → K1a/K1b → K2 and W0p → W2s/W2n/W2d/W2c windows in
[WINDOW.md](WINDOW.md), including the prompt-overlap-off control. W0p must pass
before any full-size concurrent run. Native runtime concurrency, fault draining,
GPU exactness, actual overlap, per-rank memory and host-shadow removal remain
open until those windows complete. The 64-token device oracle comparison is
prepared; CPU gates generate eight tokens as requested.

The unchanged expert-down kernels retain packet29's finite-input qualification.
The separate nonfinite diagnostic does not pass; its NaN-payload behavior is not
promoted into a quality guarantee. Route NaN handling is tested. This packet
adds no new arithmetic approximation to hide that inherited limitation.

No MTP provider is built. Its interface, pre-rank-1 timing slot and shared fields
are reserved. Timing models (none ≈ T, hit ≈ T/2, miss ≈ T for balanced halves)
are models only. Imbalance, transfers, checkpointing and fixture capture are
unmeasured costs on the new process model.

## Evidence and patches

Retained evidence includes sources, launch dumps, independent inventory/reviews,
full fixture-receipt archive, compact gate receipts, exact build identity and
byte-verified preparation-log archive. Ignored final binaries and coordinator
inputs remain ready; scratch is removed by `cleanup.py`.

## When to revisit

Revisit on a failed
coordinator gate or a new model/plan/kernel identity, never by silently reusing
old receipts. This closes CPU preparation, not the optimization lane.
