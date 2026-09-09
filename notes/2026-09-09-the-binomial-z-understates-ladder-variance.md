# A replicate says the binomial z understates ladder variance

Found by auditing this campaign's own committed claims against a replicate arm,
after the replicate turned out to exist by accident.

## The measurement

`g1` and `g2` are the same configuration run twice — `g2` was queued as a
slot-pinning test and `--pin-slots` is inert on vLLM, so the two arms differ in
nothing that reaches the server. Both are 20 passes of 64 concurrent requests on
the same fragile suite.

They give 691 and 617 divergent of 1280. Treating requests as independent
Bernoulli draws, that is

```
53.98% vs 48.20%   z = 2.93
```

for two configurations that are identical. So **z ≈ 2.9 is what this measurement
returns when there is nothing to find.**

## Why

A ladder pass issues 64 requests into one batch. They share a batch composition,
a set of decode steps and each other's presence, and the campaign has established
that composition is exactly what the divergence depends on. Requests inside a
pass are therefore strongly correlated, and the effective sample size is nearer
the number of passes than the number of requests — 20, not 1280. The binomial
standard error, computed on 1280, is too small by roughly the square root of the
per-pass cluster size.

## What it costs

Any single-rung comparison with a z near 3 is not an effect. The audit found one
of this campaign's own numbers in that position:

| comparison | rates | z | verdict |
| --- | --- | ---: | --- |
| `f3` c16 against c20, single rung | 1.04% vs 9.17% | 2.87 | **below the floor** |
| `f3` c8+c12+c16 against c20+c24+c32, pooled | 0.93% vs 8.33% | 5.11 | clears it |

The published claim — that c16 is the speculation ceiling — rests on the pooled
form, which is what
`2026-09-09-qwen35-4b-speculation-ceiling-is-c16.json` states: 2 of 216 below the
step against 38 of 456 above, where the lower rate predicts about 4.2. That
survives. The single-rung version of the same claim would not have.

Other committed comparisons were checked and clear the floor or are nulls:
`f1` against `f4` at z = 5.46, the graph-capture and determinism-pad arms at
z = 0.00 and z = 0.06, the two-populations result on zero observed against 22
expected, and the TP2 outlier on throughput, which reproduces to a tenth of a
percent.

## The asymmetry that makes existing nulls safe

Understated variance inflates z. It therefore makes a **null harder** to declare
and a **positive easier**, so every null on this lane is conservative and none is
put at risk by this. That includes the 9B lane's `p = 1.00` for the row-wise
all-reduce and serialised norm pair and its `p = 0.88` for the vocabulary
projection chunking: if anything those are stronger than stated.

Only positive findings near the threshold are affected.

## What to do

- Quote the **empirical replicate floor**, not a nominal p, when calling an
  effect on a ladder. On this suite and rung it is z ≈ 2.9.
- Prefer **pooled multi-rung** comparisons to single-rung ones; the pooling is
  what moved the c16 claim from 2.87 to 5.11.
- Run a **same-config replicate** in any campaign that will compare arms. This one
  existed only because an arm turned out to be a no-op, and it caught both this
  and a wrong cross-model claim. It is cheap relative to what it protects.
- Throughput is not affected: `g1` and `g2` reproduce to 0.1%, about twenty times
  tighter than the identity measure. A table carrying both invites reading them
  at the same confidence, and they do not deserve it.
