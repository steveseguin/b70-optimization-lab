# RETRACTED: "the Laguna MoE runs one row at a time at width 12"

Date: 2026-07-28 America/Toronto

Status: **retracted the same session it was written.** The claim was not
supported by the instrument that produced it. Scored baseline unchanged at
**100.074 tok/s conventional**; sealed record `101.94172124017027`.

## The claim, and why it was wrong

Logging every fused-expert invocation across a 13/13-exact run reported
`num_rows=1` as the only value ever seen, and I concluded that the width-12
verifier issues about 576 single-row expert-GEMM launches per cycle.

The log was placed inside `_effective_laguna_m8_w1_n_tile`, which is called
from within this block in `_apply_kernel`:

```python
if self._laguna_batched_exact_moe and 1 <= num_rows <= 8:
    ...
    _effective_laguna_m8_w1_n_tile(self._laguna_m8_w1_n_tile, num_rows)
```

A twelve-row call skips that branch, so the logging function is never reached
and **cannot observe the case it was meant to measure**. Seeing only `1` is
what this instrument would report whether the decode path used one row or
twelve. It is consistent with prefill's deliberate per-row split and with
nothing else.

## What is actually established

`LagunaMoE.forward` has two branches:

- `batched_exact_rows`, taken when `VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE=1`, the
  layer is the exact spec target, `1 <= rows <= xpu_laguna_exact_max_m()`, and
  `_xpu_is_exact_decode_or_verifier_rows(rows)` holds. That helper returns True
  for one row, or for any row count when the forward context carries
  `xpu_exact_spec_verifier`. During a verifier pass at width 12 this should be
  **True**, so the twelve rows go to `_forward_flat` together.
- `exact_spec_rows`, the `not batched_exact_rows` fallback, which splits per
  row. Its comment states the reason plainly: the generic `M>1` XPU remap path
  uses atomic row counters and is not repeatable for this top-10 EP4 model, so
  even target-only token 0 can change.

So per-row execution **is** deliberate where it happens, and it exists to hold
the bitwise contract. What remains unknown is which branch the scored width-12
decode actually takes, and what row count reaches the kernel there.

## Answered

With the probe moved above every row-count branch, a full 13/13-exact run
reports the distinct counts reaching `_apply_kernel`:

```text
seen=[1, 12, 863, 8192]
```

`12` is the scored verifier decode, `863` the longest prompt's prefill, `8192`
the warmup, and `1` the deliberate per-row exact path. **The width-12 decode
batches: twelve rows reach the kernel in one call.** The retracted claim was
wrong and is now settled by measurement rather than by inference.

This relocates the target. The roofline gap is inside the wide-M expert GEMM
itself, not in per-row launch overhead, and the `N32`/`N128` policies are
genuinely unreachable at twelve rows because they require exactly eight -- the
tile sweep is closed on its merits, not by an accident of the guard.

## Correct way to answer this

Instrument `_apply_kernel` at its top, before any row-count branch, rather than
inside the `<= 8` path. Log `num_rows` once per distinct value. That sees every
call regardless of which branch handles it.

## Standing

The cycle attribution from per-segment profiling is unaffected and still holds:
**69.2%** of a verifier forward in the graph segments containing the expert
GEMM, 22.1% in the 97 collectives, 8.7% in attention, against about **38% of
the bandwidth roofline**. The MoE path remains the right target. What is not
established is the row count it runs at.

## Lesson

An instrument placed inside a conditional can only report on the branch it
sits in. This one was gated on `num_rows <= 8` and then used to draw a
conclusion about `num_rows == 12`. The reading was real; the inference from it
was not.
