# Qwen3.8-27B Q4_K_M TP2 exact F16 cache: qualified c64 result

The `ffn_down` exact-weight cache is a qualified **aggregate-only**
optimization. On two local Intel Arc Pro B70 cards, the fixed c64 public
profile improved from a matched control center of `160.981046 tok/s` to a
two-run candidate center of **`168.138940 tok/s`**: **+4.45%**. This is 1.66%
above the prior `165.387286 tok/s` public c64 row.

| arm | aggregate tok/s | complete token identity |
| --- | ---: | ---: |
| candidate-off pilot | 161.095587 | oracle source |
| candidate-off replay | 160.866504 | 64/64 |
| exact-cache candidate 1 | 168.344562 | 64/64 |
| exact-cache candidate 2 | 167.933317 | 64/64 |

All four runs used Qwen3.8-27B Q4_K_M, TP2 `1,1`, MTP0, 64 pinned
simultaneous slots, 32,768 total context, batch 2048, ubatch 256, F16 KV,
128 generated token IDs per request, and prompt caching disabled. The two
candidate runs differed by only 0.245%. Cached-token counts were zero, no
cross-base output collision occurred, all shutdowns were clean, and kernel
error evidence was empty.

## What changed

The default-off source patch caches the exact F16 bytes produced by the
incumbent Q4_K dequantizer for `ffn_down` weights, per device. Batched GEMM
then reuses those bytes instead of dequantizing the same weights on every
step. It does not introduce a new quantizer or approximate arithmetic.

Enable it with:

```bash
export GGML_SYCL_Q4K_F16_CACHE_FILTER=ffn_down
```

The tradeoff is approximately 6.5 GiB of additional device memory per B70.
The cache is useful when decode reaches the batched GEMM path. It did not
improve one-user MMVQ decode: the cold 12-prompt suite was 12/12 exact but
measured `50.316504 tok/s` versus a `50.632425 tok/s` replay control. There is
therefore no single-user speed claim.

## Deterministic cohort gate

Earlier c64 replay failures were caused by timing-dependent batch admission:
one HTTP request could begin GPU work before the other 63 were visible. The
default-off validation patch now waits until an explicit number of new
inference tasks is queued. Internal `NEXT_RESPONSE` work is excluded.

For these runs:

```bash
export LLAMA_SERVER_QUEUE_SETTLE_MS=1000
export LLAMA_SERVER_QUEUE_SETTLE_TARGET=64
```

The 1000 ms value is a fail-safe ceiling, not a fixed sleep: admission
releases when 64 inference tasks are present. Measured launch spans were
0.524–1.117 ms. The pilot's complete token IDs were frozen before replay or
candidate runs; the control replay and both candidates matched them 64/64.

Two earlier public-profile attempts are retained only as audit history. R6
used a fixed client-visible 1000 ms delay, measured a 159.15 tok/s control, and
stopped before any candidate. R7 guessed a 50 ms window, but one request
launched 861 ms before the rest; it failed the preregistered 20 ms cohort gate
and its speed was discarded. Neither attempt contributes to the promoted rate.

## Reproduction assets

- [Preregistration](../data/2026-08-30-qwen38-q4km-tp2-public-profile-cache-c64-r8-prereg.json)
- [Result summary](../data/2026-08-30-qwen38-q4km-tp2-public-profile-cache-c64-r8-results.json)
- [Exact cache patch](../patches/llama-qwen38-q4k-f16-exact-weight-cache-candidate-20260830.patch)
- [Fixed cohort admission patch](../patches/llama-server-fixed-inference-cohort-admission-20260830.patch)
- [Strict runner](../scripts/run-20260830-qwen38-q4km-tp2-wdc-http-quality-arm-r1.sh)

The patches are layered on this lab's accepted Qwen3.8 llama.cpp SYCL stack;
apply the packet's existing prerequisite patch stack first. Binary, model,
source-diff, oracle, and result hashes are recorded in the result summary.
Do not reuse `168.138940` for another concurrency, context, card count, quant,
or MTP depth.
