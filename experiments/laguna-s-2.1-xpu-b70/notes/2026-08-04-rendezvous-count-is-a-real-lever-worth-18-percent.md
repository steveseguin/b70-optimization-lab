# Halving the four-rank rendezvous count is worth ~18% of the decode step

Date: 2026-08-04 America/Toronto

Status: **measured on a deliberately inexact diagnostic arm. Approximate, and
the arm's throughput is not a rate Laguna can achieve. It is the first
structural change this session that moved step time by more than a few
percent.**

## Why this experiment

Four structural quantities have now been varied independently:

| varied | change | step-time effect |
| :--- | :--- | ---: |
| collective **bytes** (expert parallelism off) | -95% | -4.6% |
| draft depth | 11 -> 7 | -0.6% |
| **graph breaks** (inline attention) | 145 -> 97 | **-2.4%** |
| **rendezvous count** (this note) | 96 -> 48 gathers | **-18.3%** |

Every earlier arm held the rendezvous count at 97. This one changes only that.

## The instrument

`VLLM_XPU_LAGUNA_GATHER_SKIP_MOD=2` performs only every second all-gather. The
output buffer keeps its prior contents, so **the model's arithmetic is wrong
and its tokens are meaningless**. Boundary count, graph topology, segment kinds
and every kernel are untouched, so the delta isolates the rendezvous.

The 96 gathers are, per `laguna_m8_collectives.py`: **48 attention O
projections, 1 layer-0 dense MLP down projection, and 47 MoE final combines** --
two per layer, plus one embedding all-reduce for 97 boundaries.

## The confound, and how it was handled

Garbage activations make the drafter and target agree trivially, so acceptance
went to ~100%: **10.667 tokens per step against the control's 3.765.** Since
`tok/s = tokens_per_step / step_time`, the raw tok/s figures (up to +1005%) say
nothing about speed. Emission also became bursty -- ten tokens at once, then a
gap -- which corrupts the percentile-interval metric the campaign scores on.

Step time recomputed from **mean inter-token latency**, which is robust to
burstiness:

| case | tok/step | step ms, control | step ms, mod2 | delta |
| :--- | ---: | ---: | ---: | ---: |
| 256 sentinel | 3.765 -> 10.667 | 32.97 | 26.92 | **-18.3%** |
| 32,640 | 1.058 -> 10.667 | 37.33 | 34.71 | **-7.0%** |
| 8,192 | 1.347 -> 10.667 | 145.27 | 926.28 | unusable |

The 8,192 row is not used: its generation dynamics under garbage activations
make both metrics meaningless.

## Reading it

**-18.3% at short context for a 2x rendezvous reduction**, against the
standalone `bench_laguna_collective_scaling.py` prediction of -23.7% for the
same 96 -> 48 change. Two independent instruments agreeing to within six points
is the strongest structural signal the campaign has produced.

It is also the *only* lever that has moved step time by more than a few
percent, which retires a family of hypotheses: the cost is not the bytes moved,
not the number of graph segments, and not the drafter. It is **how many times
per step four ranks must meet**, each meeting bounded by the slowest arrival.

## What the honest version costs

The rendezvous cannot simply be deferred: two per layer is the standard
tensor-parallel cost, and the next layer's column-parallel matmul needs the
complete hidden vector. The principled way to remove exactly 48 of the 96 is
**replicated attention with expert parallelism only** -- each rank holds all
attention weights and 1/4 of the experts, so the attention O projection needs
no collective at all.

| quantity | value |
| :--- | ---: |
| attention parameters | 2.114 B |
| attention weights, BF16 | 3.94 GiB |
| per rank today, TP4-sharded | 0.98 GiB |
| per rank if replicated | 3.94 GiB |
| **extra per rank** | **+2.95 GiB** |

Experts dominate the footprint, so replicating attention is affordable in
principle at util 0.80. It requires changing the parallel identity, which every
contract on this path pins to TP4/EP4.

## What it does not deliver

At -18%, short-context decode goes from 131.5 to about 161 tok/s. **It does not
reach 250 on its own**, and it does nothing for the 32,640 target, which is
gated by 1.058 tokens per step rather than by step time.

## Boundaries

qdepth depth 11, width 12, TP4, util 0.80, EP4, warm server, cold prefix cache,
matched control `20260804-depthwarm-d11`. The candidate arm is **inexact by
construction**: it computes the wrong answer on purpose to price a structural
quantity, its retrieval checks fail, and its throughput must never be quoted as
an achieved rate. No quantisation change. The protected
`125.4619731637751 tok/s` conventional short-decode record is untouched.
