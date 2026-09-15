# Exact 2-way column parallelism is retired: break-even at best

September15, 2026. Offline, exclusive GPUs, no server. This was the largest
remaining measured lever for the sampler. It does not pay, and the measurement
below is why — established before building it, not after.

## The idea

Only one of four B70s computes at any instant during sampling: blocks 0-20 run on
XPU0, then 21-47 on XPU1, strictly serially. Giving each device half the output
columns of every projection would let both work at once.

## Exactness, at the token counts LTX really runs

An earlier probe tested every layer at 64 and 256 tokens and reported the audio
feed-forward as non-exact. That was an artifact: **the audio stream runs at 26
tokens**, a shape it never sees at 256. Re-tested at the real counts — video
64/256, audio 26, text context 128/256 — across all 13 real projection shapes:

| Split | Cases | Bitwise exact |
| --- | ---: | ---: |
| 2-way | 20 | **19** |
| 4-way | 20 | 9 |

The single 2-way failure is `a2v to_q` (2048x4096) at 256 tokens, a 16 MiB layer
that could simply stay unsplit. **But 4-way is only 9/20, which rules out any
3- or 4-GPU lossless variant** — the idle encoder and VAE cards cannot be
recruited without losing exactness.

## The economics

| Configuration | Time | vs production |
| --- | ---: | ---: |
| Production serial (one graph, 48 full blocks) | 104.34 ms | 1.00x |
| **Ideal split, zero communication** | **67.82 ms** | **1.54x** |
| 4 gathers per block | 79.40 ms | 1.31x |
| 8 gathers per block | 91.69 ms | 1.14x |
| 12 gathers per block | 103.98 ms | **1.00x** |
| 16 gathers per block | 116.27 ms | **0.90x** |

Two facts set the ceiling. Halving a block's weights takes a 48-block chain from
104.3 to only 67.8 ms, not 52 — small projections do not halve, as a separate
probe showed (`ff.net.0.proj` splits 1.98x but `attn.to_q` only 1.26x). And the
two devices genuinely do run concurrently (factor 1.999), so 1.54x is the honest
ceiling, not 2x.

## Why the gathers cannot be avoided

The standard trick is Megatron's column-then-row pairing, which needs **one**
cross-device all-reduce instead of two gathers. It is unavailable here: an
all-reduce is a *sum* across devices, and summing partial products in a different
order changes the floating-point result. That fails the four-tensor oracle.

Without it, every point that reduces over the feature dimension needs the whole
vector:

- every RMSNorm normalises across all 4096 (or 2048) features;
- every attention output projection needs all heads concatenated first.

That is about **16 gather points per block**: six attentions times two, plus two
feed-forwards times two. A gather also cannot live inside a per-device graph, so
each one additionally splits the captured chain into another segment to replay.

At 16 gathers per block the result is **0.90x — slower than what is running
today**. Even a hypothetical 8 would return 1.14x on the block chain, which is
about 0.2 s on the clip, for a full column-wise re-shard of a 42 GB model plus
its own exactness re-qualification.

## Decision

**Retired.** A non-exact variant using row-parallel all-reduce would be
substantially faster; it is excluded by the losslessness requirement, not by the
measurement. Recorded so it is not re-proposed.

Evidence: [`data/column-parallel-verdict-01.json`](../data/column-parallel-verdict-01.json),
[`data/nsplit-exactness-real-shapes-01.json`](../data/nsplit-exactness-real-shapes-01.json),
probes `probe-column-parallel-economics.py` and `probe-nsplit-exactness-real-shapes.py`.
