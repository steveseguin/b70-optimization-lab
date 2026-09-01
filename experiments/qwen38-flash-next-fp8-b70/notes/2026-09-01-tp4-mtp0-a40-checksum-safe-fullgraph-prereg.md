# Qwen3.8 Flash-Next FP8 A40 checksum-safe full-graph preregistration

Date: 2026-09-01
Status: frozen before GPU launch

## Question

Can the accepted TP4 MTP0 target-only lane execute with size-1
`FULL_DECODE_ONLY` graph dispatch while preserving the complete quality and
exact-output authority battery?

## Identity

A40 changes only fresh attempt/port/evidence paths (`40` / `19712`) and repairs
the A38/A39 successor-generator defect. Model revision, TP4/EP4 placement,
MTP0, 4352-token limit, 128 MiB KV allocation, synchronous 12 GiB/rank PLE,
source/runtime/kernel identities, graph-safe oneCCL, graph configuration,
sampling, prompts, and client battery are unchanged from A37-A39.

The generator still performs the identity substitution, then requires exact
mode-specific counts before restoring the protected oneCCL SHA-256 literal:
three launcher occurrences, three client occurrences, and two supervisor
occurrences. A missing or extra occurrence fails source generation. The final
generated sources must contain only
`43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700`.

## Frozen interpretation

- Any preflight or runtime-verifier failure is a bounded negative with zero
  speed or quality credit.
- A speed observation receives no promotion credit unless the complete
  unchanged quality/authority battery passes.
- The diagnostic trace remains enabled for this causal arm. Even a full pass is
  a candidate requiring a separately identified trace-off repeat before
  promotion.
- Existing `5.515783 tok/s` MTP0 and `20.727176 tok/s` MTP4 results remain
  protected regardless of outcome.
- No reboot or per-boot consumption rule applies; reuse is admitted by locks,
  fresh paths, exact identity checks, bounded health preflight, cleanup, and
  postflight.
