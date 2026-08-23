# Ornith 1.5 35B two-row MTP rollback-state fusion

## Outcome

**EXACT RESEARCH; NOT PROMOTED.** A purpose-built Qwen/Ornith two-token state
fusion collapses GET_ROWS, CONCAT, and both rollback-snapshot CPYs in each of 30
recurrent verifier layers. It preserved every canonical transcript and showed
an order-resistant isolated gain, but its marginal result on the preferred
MTP1 verifier stack was neutral/slightly negative.

## Why the one-row fusion could not simply be reused

The actual verifier trace has a two-row cache source `[24576,2]`, a five-row
convolution input `[5,8192]`, and two state snapshots per recurrent layer:

- view offset 4 bytes -> `[old1, old2, token0]` into rollback slot 1;
- view offset 8 bytes -> `[old2, token0, token1]` into rollback slot 0.

That accounts for 30 GET_ROWS, 30 CONCAT, and 60 CPY launches per verifier
cycle. The accepted one-token kernel writes only one snapshot and is therefore
not graph-equivalent.

## Candidate and safety boundary

The default-off
`GGML_SYCL_FUSED_ORNITH_SPEC_CONCAT_STATE_DIRECT=1` matcher requires the exact
cache, gather, concat, view offsets, two ordered CPYs, destination slot
addresses, convolution consumer, types, strides, and non-overlap observed in
the trace. One work-item owns one channel. It reads all three values from the
device-selected source slot before writing either rollback slot, then
materializes every graph-visible result:

- the selected GET_ROWS output;
- all five convolution-input values;
- both three-value rollback snapshots.

A four-token smoke test recorded 120 hits, exactly 30 layers per verifier step.
Every 128-token candidate recorded 2,490 hits and no parent state-fusion hits.

## Isolated screen

All four transcripts had canonical SHA-256
`0f162aebc81f0a28ffd82704b20729ca4dc71b929644c5803639a3ad40828a2e`.

| arm | generation tok/s |
| --- | ---: |
| control A1 | 65.1 |
| candidate B1 | 65.6 |
| candidate B2 | 65.7 |
| control A2 | 65.1 |

Arm means were `65.10 -> 65.65 tok/s` (+0.84%), and both candidates beat both
controls.

## Marginal screen on the preferred MTP1 stack

Both arms also enabled the exact two-row residual/RMS and ordered-MoE fusions.
All four combined-stack transcripts remained canonical.

| arm | generation tok/s |
| --- | ---: |
| stack control A1 | 66.9 |
| stack + state B1 | 67.2 |
| stack + state B2 | 66.9 |
| stack control A2 | 67.5 |

Arm means were `67.20 -> 67.05 tok/s` (-0.22%) with split pairwise outcomes.
The candidate therefore did not advance to fresh-server testing.

## Decision

Retain
`../patches/llamacpp-ornith15-mtp2row-two-snapshot-state-research-20260823.patch`
as a stackable exact research component and preserve the structural diagnostic.
Do not enable it by default, add it to the preferred MTP1 stack, call it a
serving gain, or change the target-only package. It may be useful if a later
larger recurrent fusion absorbs its materialization cost.

