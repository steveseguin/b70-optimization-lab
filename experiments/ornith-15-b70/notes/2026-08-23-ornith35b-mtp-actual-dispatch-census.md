# Ornith 1.5 35B MTP1 actual dispatch census

## Outcome

The embedded draft is not the dominant MTP1 launch surface. After the accepted
one-row fusions and skip rules, a steady two-row target-verifier graph still
dispatches **1,442** generic SYCL kernels; the alternating embedded-draft graph
dispatches only **29**.

This is diagnostic evidence only. It selects optimization boundaries and does
not imply a throughput value.

## Measured steady graphs

| graph | logical nodes | result rows | generic launches |
| --- | ---: | ---: | ---: |
| target verifier | 3,816 | 2 | 1,442 |
| embedded draft | 91 | 1 | 29 |

The verifier's largest surviving classes are 430 `ADD`, 311 `MUL_MAT`, 130
`UNARY`, 120 `MUL_MAT_ID`, 110 `MUL`, 61 `GET_ROWS`, and 60 each of `CPY` and
`L2_NORM`. Of the 430 additions, 280 are the seven ordered expert reductions in
each of 40 MoE layers.

The complete machine-readable census is in
`../data/2026-08-23-ornith35b-mtp-actual-dispatch-census.json`; the raw trace is
`../data/2026-08-23-ornith35b-mtp-actual-dispatch-census.log.gz`. The temporary,
default-off instrumentation is preserved as
`../patches/llamacpp-ornith15-mtp-actual-census-diagnostic-20260823.patch`.

## Interpretation

This is precisely where Ornith's Qwen lineage transfers: most accepted
target-only matchers intentionally require one row, so they fail closed on the
two-row verifier. Extending proven boundaries with exact row/stride guards is a
more credible MTP path than optimizing the already-small draft graph first.
