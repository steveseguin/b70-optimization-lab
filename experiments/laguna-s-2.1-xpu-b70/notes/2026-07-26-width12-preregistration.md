# Laguna — width-12 bounded structural test: preregistration

Date: 2026-07-26 America/Toronto, written **before** the run.

## Baseline this is measured against

Same-session width-8 control, current HEAD: **94.822732** tok/s scored median,
3.7010 emitted per cycle, 39.03 ms per cycle, 13/13 bitwise exact, 146/145
captured and replayed on all four ranks. Approved record: 94.920039.

## Treatment

`M=12, spec=11, metadata=1, draftgraph=0` at current HEAD. Note the leg disables
the two M8-only fusions (`SHARED_ELEMENTWISE`, `QKNORM_ROPE`) at any width other
than 8, so those are part of the treatment and not held constant. That is a
known confound and is recorded rather than hidden.

## What is being tested

Whether the three batched-M1 bound fixes — column-parallel, row-parallel, and
replicated — actually restore a batched topology at width 12. The prior width-12
attempt produced **685 graphs / 684 eager breaks** against the audited 146/145;
`685 − 146 = 539 = 11 × 49`, i.e. `(M−1)` extra breaks per layer, the signature
of per-row serialization. That run then exhausted device memory inside a Level
Zero replay and left the host unusable.

## Preregistered expectations

- **Topology: exactly 146 graphs / 145 eager breaks.** The count should not
  depend on M if batching is preserved, since the collective and attention
  boundaries per layer are unchanged. The wrapper asserts 146 outright, so a
  sane-but-different count also fails — deliberately.
- **Exactness: 13/13** bitwise against the canonical q=1 teacher.
- **Emitted per cycle:** the validated flat-acceptance model predicts 4.0123 at
  depth 11 from a depth-7 fit; a prior run measured 3.958. Expect ~3.96–4.01.
- **Scored median:** if cycle time is unchanged, 94.822732 × (3.958/3.7010)
  ≈ **101.4**, i.e. this alone is expected to fall **short of 102**.

## Stop conditions

Stop immediately, with no retry and no relaxation, on any of:

1. Capture segments exceed the ceiling of 292 (2× audited) — raises as a Python
   error rather than an OOM, by design.
2. Graph count differs from 146/145 on any rank.
3. Ranks differ structurally from one another.
4. Exactness below 13/13.
5. `cached_tokens` non-zero on any prompt.
6. Memory pressure trending toward OOM.
7. Unclean shutdown or surviving workers.

A topology materially above 146/145 is a structural failure to be fixed, never a
count to learn or a ceiling to raise.

## What a pass would and would not establish

A pass establishes that width 12 is exact and batched, and yields its scored
median. It does **not** authorize width 16 by constant-bumping, nor the tree.
Both need their own preregistration.
