# Packet71 CPU preparation closeout

<!-- campaign-closeout -->

## Question and identity

Prepare a dependent depth-two MTP engine for the packet64 target arithmetic
`iq3-p49-split32-v1`, preserving packet49 as the output oracle. CPU-only work on
October 17, 2026; packet64 sources and packet68c kernels copied and pinned.

## Outcome

Ready for a coordinator-run lane-B smoke. Both pipelined serial and production
M2 settings are sealed. No full model ran and no device speed or correctness
result is claimed.

## What worked

Private current/future row transactions allow two-card overlap without committing
unverified state. Small engine fixtures match packet64 for every acceptance
prefix: 1,854 plan/spare byte comparisons, metadata and five draft-cache checks.
Each compiler passes 1,428 M2 operator byte checks, including cross-compiler
agreement. Seven wrapper tests pass.

## What failed or remains uncertain

Early fixtures found stale lookup metadata and incorrect extent/bank ordering;
the final sources fix both. Mixed expert quantization requires per-site serial
fallback. The original drained serial schedule has been superseded by the
current/future tile pipeline. Full-model causal state, device arithmetic, memory
headroom and speed await smoke/quick runs. The analyzer omits measured pipeline
copy and repair costs; its rates must not become results.

## Evidence and patches

[Token/state receipt](fixture/receipt.json), [operator receipt](fixture/m2-receipt.json),
[shape inventory](evidence/metadata-gate.json), [wrapper tests](evidence/wrapper-tests.log),
[build receipt](build-device-receipt.json), [kernel imports](packet68c-import.json),
[source/restore instructions](RETENTION.md), [design](DESIGN.md).
Historical serial receipts are under `milestones/serial/`; verbose intermediate
states and build logs are retained locally under ignored `evidence/raw/` and
`build/`. Those local verbose files are not public reproducibility evidence.

## When to revisit

The coordinator runs the sealed one-prompt 32-token smoke, then the matched
12-prompt quick screen in [jobs](screen/jobs.json). Any mismatch blocks speed
claims and requires localization before another device attempt. Passing these
short screens is not a full quality qualification or promotion gate.
