# The draft lm_head is ~28% of the decode step (2026-09-09)

`a13dh0`: depth 3 with `DRAFT_HEAD=0`, matched against the depth-3 baseline, both serial on a quiet
card 0. This is a **measurement** arm - the draft-only INT4 lm_head is on by default here, so turning
it off sizes the term rather than trying to improve it.

| | acceptance | step ms | tok/s | gates |
| --- | ---: | ---: | ---: | --- |
| draft head ON (INT4, default) | 2.764 | 24.97 | **110.68** | 12/12 |
| draft head OFF (FP16) | 2.812 | 34.62 | **81.24** | 12/12 |

- The INT4 draft head is worth **+36.2%** end to end (110.675 / 110.692 against 81.230 / 81.259).
- It removes **9.64 ms from a 34.62 ms step - 27.9% of the step.**
- Acceptance is unchanged (+1.7%, and marginally *higher* without INT4, consistent with a
  quantisation of the same projection producing the same tokens). Both configurations are lossless
  against the same MTP0 oracle, so the entire gain is step cost, not better drafting.

That +36.2% is larger than the +27.6% the same lever was worth on the FP8 route, so its value does
not transfer between quantisations and had to be measured here.

## Why this changes the remaining ladder

Until now the surviving knobs were ranked by plausibility. This gives a size. **The draft lm_head is
a ~10 ms term inside a ~25 ms step even after INT4 quantisation** - by far the largest single
component identified in this campaign. Its own tuning knobs therefore act on something demonstrably
enormous rather than something that merely sounds relevant:

```
VLLM_XPU_DRAFT_LM_HEAD_INT4_GROUP_SIZE = 128     (a5g32, a5g64)
VLLM_XPU_DRAFT_LM_HEAD_INT4_CHUNK_ROWS = 2048    (a12dch)
VLLM_XPU_DRAFT_LM_HEAD_INT4_SCALE_DTYPE = bf16   (queued)
VLLM_XPU_DRAFT_LM_HEAD_INT4_APPLY_ROWS = 0       (queued)
```

A 20% improvement on a 10 ms term is about 8% end to end, which is larger than anything else still
reachable in this lane.

## It also explains the depth ladder mechanically

Each additional draft depth is another pass through this expensive head. That is why step cost grows
about 2.9 ms per depth while acceptance saturates near three tokens - the two facts are the same
fact seen from different ends. The vocabulary is 248,320 rows, so the projection is large relative to
a 9B model's other per-token work.

It also predicts that the head's share should be **larger at low depth**, where it is amortised over
fewer accepted tokens. `a14dh0d1` measures the same delta at depth 1 to test that.

## Depth 1 (`a14dh0d1`): the prediction was backwards, and the correction closes the loop

I predicted the head's share of the step would be **larger** at depth 1, on the reasoning that it is
amortised over fewer accepted tokens. It is smaller:

| | head ON | head OFF | head worth | head removes |
| --- | ---: | ---: | ---: | --- |
| depth 1 | 93.09 tok/s (19.43 ms) | 82.96 tok/s (22.12 ms) | +12.2% | 2.69 ms (12.1% of step) |
| depth 3 | 110.68 tok/s (24.97 ms) | 81.24 tok/s (34.62 ms) | +36.2% | 9.65 ms (27.9% of step) |

The reasoning was simply wrong. The draft head runs **once per drafted token**, so depth `d` pays
`d` passes through it. The share therefore grows with depth. Per pass:

```
depth 1:  2.69 ms / 1 pass = 2.69 ms per draft pass
depth 3:  9.65 ms / 3 pass = 3.22 ms per draft pass
```

**And that closes the loop with the depth ladder.** The step-cost growth measured independently from
the slope of seven rate measurements is **+2.87 ms per depth**. The head's per-pass cost measured by
toggling a flag at two depths is **2.7-3.2 ms**. Two quantities obtained by completely different
means agree.

So the draft lm_head is not merely the largest term - it is essentially **the entire mechanism by
which depth costs anything**. Acceptance saturates near three tokens while each additional depth
buys one more ~3 ms pass through a 248,320-row projection. That is the depth curve, explained end to
end:

- gains: accepted tokens per step, saturating (+0.809, +0.568, +0.387, +0.254, +0.142, +0.028)
- costs: one draft-head pass per depth, ~2.9 ms each

Peak at depth 3 is where those cross, and nothing about that is coincidental.

### Consequence

Cheapening this head improves **every** depth and improves deeper ones most - it would also move the
optimum depth rightward, since the cost side of the crossing gets shallower. That makes the seven
queued head-tuning arms the only remaining work in this lane that acts on the term governing both
the peak's height and its location.
