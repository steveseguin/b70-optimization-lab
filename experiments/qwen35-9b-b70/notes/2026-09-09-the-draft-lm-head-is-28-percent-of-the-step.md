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
