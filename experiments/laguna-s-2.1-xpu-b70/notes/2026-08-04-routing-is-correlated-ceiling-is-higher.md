# Routing is correlated: the 32K ceiling is ~147 tok/s, not 68.9

Date: 2026-08-04 America/Toronto

Status: **inference from measurement. Supersedes the "physically impossible"
verdict on >150 tok/s at 32K in the two companion notes.**

## The correction

Every decode ceiling published in this campaign's 2026-08-03/04 notes rests on a
single number: how many **distinct** experts a 12-row decode step touches. That
number was estimated at **97 of 256** by treating the twelve speculative rows as
routing independently and uniformly. It was never measured.

The machine's own timing contradicts it.

## Derivation

The 1,024 and 32,640 q12 rows are both M=12 on the identical optimized path.
The only difference between their steps is KV bytes, which follows exactly from
the layer geometry: 12 full-attention layers over the full context plus 36
sliding layers capped at the 512-token window.

```
1K  step  23.83 ms   KV 0.075 GB
32K step  26.52 ms   KV 1.610 GB
delta      2.69 ms      1.535 GB   ->  571 GB/s marginal
```

Back-solving the 1K step against that marginal rate:

| assumed expert-gather bandwidth | bytes/step | experts/layer | 32K ceiling |
| :--- | ---: | ---: | ---: |
| same as KV (571 GB/s) | 13.5 | **27.2** | **147.0** |
| 30% slower than KV | 9.5 | 10.9 | 201.2 |
| uniform-routing assumption | 32.3 | 97.3 | 68.9 |

Scattered expert gather is not plausibly *faster* than contiguous KV streaming,
so **27 experts per layer is an upper bound**. The slower the true gather, the
fewer experts the timing implies.

## Why the old number was incoherent

At 97 experts the step reads 32.3 GB in 26.52 ms, an average of 1.22 TB/s --
while the marginal read on the KV delta measures 571 GB/s. One memory system
cannot stream its marginal bytes at less than half its average rate. That
inconsistency was visible in the data before this analysis and was not chased.

At 27 experts the step reads 13.5 GB and the average and marginal rates
reconcile.

## Consequences

- The 32K ceiling is approximately **147 tok/s**, not 68.9. The >150 target sits
  essentially at it rather than at twice it, and should no longer be described
  as physically impossible.
- Measured 39.589 is therefore about **27% of achievable**, not 57%. Long-context
  headroom is roughly **3.7x**, not 1.7x.
- Nothing about the measurements changes. 39.589, 152.3, 13.31 and the prefill
  figures all stand. What changes is how much of the gap is recoverable.

## Standing, and what this does not overturn

Unaffected by this correction, because each is directly measured rather than
modelled:

- Speculation is not overhead. M=12 supplies enough rows to stream; M=1 does
  not. Disabling speculation measures 0.34x at 32K, not the 3x once projected.
- The configuration is a local optimum welded across verifier width, draft
  depth, expert parallelism, graph capture and attention metadata. Six attempts
  to vary one axis were each rejected by a contract guarding another.
- Prefill exceeds 1000 tok/s at every context measured.

## What would settle it properly

This is inference from two points, not a direct count. Six instrumented runs
failed to obtain the count itself: graph replay executes no Python so the fast
path cannot be observed, device-side `topk`/`unique` exhausts XPU memory, and the
eager path deadlocks or cancels on TP4. The remaining routes are device-side
counters inside the MoE kernel, or an eager arm with `max_model_len` reduced far
enough that activations fit at low utilisation.

Anyone planning kernel work should get that count first. It is the difference
between chasing 1.7x and chasing 3.7x, and this note argues strongly for the
latter.

## Boundaries

No new device run was required for this analysis; it uses figures already
recorded in the companion notes. No quantisation changed, no caching or
speculation setting was used to inflate any number, and the protected
`125.4619731637751 tok/s` conventional short-decode record is untouched.
