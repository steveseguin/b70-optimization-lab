# Laguna long-context mixed-depth analyzer

Date: 2026-08-03 America/Toronto

Status: **fail-closed offline analyzer implemented and CPU-tested; the
accepted-position hypothesis remains unmeasured and no source treatment is
authorized yet**.

## Purpose

The previous 32K diagnostic runner already records request-local accepted
tokens by draft position. Its attempted run failed operationally before model
loading, so there is no evidence from which to decide whether a seven-row
long-context drafter may safely retain the width-12 target verifier.

`tools/analyze_laguna_long_mixed_depth.py` now turns the next successful bench
artifact into a deterministic decision. It accepts only the frozen seven-row
sequence:

1. one 1,024-token first-live warmup;
2. 32,640-token early row and its 256-token sentinel;
3. 32,640-token middle row and its sentinel; and
4. 32,640-token late row and its sentinel.

It rejects an extra, missing, reordered, or renamed row and independently
checks the prompt-build manifest.

## Required evidence

The analyzer requires the bench artifact to be a candidate
`PASS_ORACLE_EXACT` result with every intrinsic, retrieval, cache-zero,
prompt-identity, token, text, and accepted-position consistency check true.
Every row must expose exactly positions 0 through 10 and the position sum must
equal the ordinary accepted-token counter.

The source-prototype gate passes only when:

- all three 32,640-token rows accept zero tokens at positions 7--10 and report
  a maximum accepted position no greater than 6; and
- all three 256-token sentinels accept at least one token beyond position 6,
  proving that any future depth reduction must be explicitly long-only.

A passing analyzer result says only
`PASS_IMPLEMENTATION_AUTHORIZED`, `source_implementation_exists=false`, long
draft depth 7, and target verifier width 12. It does not authorize an endpoint
run, claim correctness for padding/invalid-proposal semantics, or predict a
speedup.

Six CPU-only tests pass. They cover the valid frozen sequence plus long-row
deep acceptance, shallow sentinels, metric-schema drift, oracle drift, and row
reordering. Ruff formatting/lint and whitespace checks pass.

## Boundaries

No model, endpoint, device, native component, benchmark, or probe was run. The
earlier diagnostic remains an operational failure and was not reclassified.
The device/NVMe quarantine remains controlling; a fresh diagnostic requires
separate authorization. Until that artifact passes this analyzer, no mixed-
depth source implementation should be created. The protected short record
remains `125.4619731637751 tok/s`.
