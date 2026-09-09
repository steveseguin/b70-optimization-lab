# Preliminary: existing 27B data argues against the GDN group size (2026-09-09)

Written before chain 5 runs, from data already on disk, so the prediction is on
record ahead of the controlled test rather than after it.

## The question

The 4B's `f3` arm found a step in depth-3 divergence between c16 and c20 — 0.93%
pooled below, 8.33% above. Two mechanisms predict a boundary at exactly 16
sequences and are confounded there:

- **(a) the GDN speculative group.** `VLLM_XPU_GDN_SPEC_GROUP=16` processes
  speculative rows in groups of at most 16 sequences, so above 16 the rows are
  partitioned and which group a request lands in depends on the rest of the batch.
- **(b) the captured decode shape.** `max_cudagraph_capture_size` counts tokens
  and a depth-3 step is 4 tokens per sequence, so 64 tokens is 16 sequences and
  c20 is the first rung with no captured graph.

## The natural experiment

The 27B lane already ran `mtp4` ladders at five group sizes while chasing R228 to
R278: `0`, `1`, `4`, `16` and `64`. Pooled by group size and rung:

| arm | c4 | c8 | c16 | c32 | c64 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `g0` | 0/8 | 0/16 | 0/32 | 2/64 | 11/128 |
| `g1` | 1/4 | 0/8 | 0/32 | 2/64 | 3/64 |
| `g4` | 0/4 | 0/8 | 1/16 | 0/32 | 4/64 |
| `g16` | 9/72 | 6/144 | 7/368 | 36/736 | 93/1408 |
| `g64` | – | – | 2/112 | 11/224 | 7/128 |

## What it says

Hypothesis (a) makes two sharp qualitative predictions and both fail:

- **`g1` should be the worst arm.** With a group size of one, every sequence is
  its own group and the partitioning is maximal at every concurrency above 1. It
  is instead among the quietest: 4.7% at c64 against `g16`'s 6.6%.
- **`g64` should be near-exact up to c64.** Sixty-four concurrent requests fit in
  a single group, so there is no partitioning to depend on. It reads 1.8% at c16
  and 4.9% at c32, indistinguishable from the others.

Meanwhile every arm, whatever its group size, is quiet through c8-c16 and rises
from c32 — which is roughly where `mtp4`'s capture ceiling sits (64 tokens over 5
tokens per sequence is 12 sequences).

So the weight moves toward (b), the uncaptured decode shape.

## Why this is preliminary and not a result

- The cells are small: `g1` and `g4` have 4 to 64 requests per rung against
  `g16`'s hundreds. A 0/32 at that size is weak evidence of anything.
- The arms are not controlled. They come from campaigns testing different
  patches — `nosplit-binv`, `serialn-binv`, `request-shape-ab`, `graph-drafthead`
  — and the group size was not the only thing that changed between them.
- It is a different model at a different depth from the 4B measurement it is
  being used to interpret.

A qualitative prediction failing at both ends is worth more than the cell counts
suggest, but not enough to close the question.

## What the 9B lane's lockstep result says about hypothesis (b)

Read after this note was drafted, and it weakens the capture hypothesis
independently. `2026-09-08-a-lockstep-batch-is-deterministic-the-ladder-is-not.md`
ran 64 identical prompts in a constant-composition batch **under
`FULL_DECODE_ONLY` capture at sizes 1 to 64**, matching the ladder, and got 64
identical outputs — capture did not reproduce the divergence. Their conclusion is
that divergence needs the batch composition to vary, and that every
row-count-dependent op contributes so no single one can be fixed to remove it.

If that is right, the capture ceiling is unlikely to be what creates the step
either, and `k128` should be a null. That is a cleaner prediction than the one
this note started with, and it is worth stating that under their account **both**
of the hypotheses here are expected to fail. The step between c16 and c20 would
then be neither the grouping nor the ceiling, and the arms are worth running
mainly to eliminate them by measurement rather than by inference — which is what
that lane's own history suggests is the reliable route.

## How many row-count thresholds are actually in play

Enumerating the ones visible in this lane's own container environment and in the
9B lane's probes, with the concurrency each lands at when depth 3 puts four rows
per sequence:

| threshold | at | depth-3 concurrency |
| --- | ---: | ---: |
| RMSNorm row dependence (9B probe) | 16 rows | c4 |
| `VLLM_XPU_FP16_LINEAR_ROWCHUNK` | 32 rows | c8 |
| FP16 vocabulary projection strategy switch (9B probe) | 33 rows | c9 |
| `VLLM_XPU_GDN_SPEC_GROUP` | 16 sequences | c16 |
| `max_cudagraph_capture_size` | 64 tokens | c16 |

Five thresholds, four distinct concurrencies, and only the last two sit at c16.
That is the concrete form of the 9B lane's conclusion that every
row-count-dependent op contributes and fixing them one at a time cannot move the
number: an arm that makes one of these invariant leaves four others in place.

It also bounds what chain 5 can conclude. Eliminating the GDN group and the
capture ceiling removes the two candidates at c16 but says nothing about the
three below it, and the ladder is already non-exact from c12 - so whatever the
c16 step is, something is already happening before it.

## The prediction on record

If (b) is right, chain 5 should show:

- `s08`, `s16` and `s32` all stepping between **c16 and c20**, because they hold
  the capture ceiling at 64 tokens and only vary the group size;
- `k128` stepping between **c32 and c40** instead, because it raises the ceiling
  to 128 tokens, which is 32 sequences at depth 3, and c40 needs 160.

If (a) is right the steps in `s08`/`s16`/`s32` move to c8, c16 and c32 and `k128`
does not move. If neither moves, something else changes at 16 to 20 sequences.

The practical stake: if it is the capture ceiling, raising it is a cheap real
improvement for any speculative lane serving more than `capture_max/(1+depth)`
users — capture cost here is 2 seconds and 0.13 GiB. If it is the grouping, the
knob is already exposed and costs nothing to change.
