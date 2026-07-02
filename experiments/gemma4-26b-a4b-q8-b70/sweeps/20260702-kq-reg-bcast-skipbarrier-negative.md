# Gemma 4 26B Q8: KQ Register/Broadcast Pre-Softmax Barrier Skip

Date: 2026-07-02

## Summary

This experiment tested whether the promoted global FlashAttention KQ
register/broadcast path still paid an avoidable local-memory barrier before
softmax. The candidate added a second default-off flag:

```bash
GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST=1
GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST_SKIP_PRESOFTMAX_BARRIER=1
```

The hypothesis was that, in the KQ register/broadcast specialization, the
`np == 1` pre-softmax `item_ct1.barrier(local_space)` may no longer be needed
because KQ values are retained in lane-local registers and later read via
subgroup selection instead of the old shared KQ scratch handoff.

Result: **no win / noise**. The patch built and passed validation, but the
balanced four-wave A/B + crossover measured only `+0.031%` mean prefill delta
and `+0.169%` median prefill delta, with wave signs alternating negative and
positive. The active source was reverted to the promoted KQ register/broadcast
path without the barrier-skip variant.

## Source Artifacts

Patch snapshots:

- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-kq-reg-bcast-skipbarrier-preedit-source.patch`
- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-kq-reg-bcast-skipbarrier-preedit-source.diffstat`
- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-kq-reg-bcast-skipbarrier-source.patch`
- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-kq-reg-bcast-skipbarrier-source.diffstat`
- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-kq-reg-bcast-skipbarrier-fattn-tile.patch`

Build result:

- build target: `build-sycl-b70-aot-bmg-g31-q8reorder-vdr2/bin/llama-server`
- candidate build succeeded
- candidate `libggml-sycl.so.0.15.2` hash:
  `ee9e1dd1927c345937c97b5c8c38fbff0f292129a702e40968e8efb9aff75b3d`
- reverted/promoted `libggml-sycl.so.0.15.2` hash:
  `61c364b690ea6f852ad71c77abd65605c33de967dc9186c19d322c28e4ea8864`

## Validation

Smoke:

- summary:
  `data/gemma4-long-context-service-gate-20260702Tkqregbcast-skipbarrier-smoke1.json`
- run dir:
  `data/gemma4-q8-gpu0-longctx-kqregbcast-skipbarrier-ctx32768-o96-20260702Tkqregbcast-skipbarrier-smoke1/`
- exact JSON validation: pass
- `cached_tokens=0`
- approximate prefill: `1230.80762350552 tok/s`
- decode: `127.56864411940751 tok/s`
- TTFT: `13.172651591012254 s`

Full A/B + crossover:

- comparison:
  `data/gemma4-global-fattn-kq-reg-bcast-skipbarrier-comparison-20260702Tkqregbcast-skipbarrier-ab1.json`
- 48/48 rows valid
- exact JSON validation passed on every row
- `cached_tokens=0` on every row

Aggregates:

- control mean prefill: `1123.3297415742663 tok/s`
- candidate mean prefill: `1123.681833590059 tok/s`
- mean prefill delta: `+0.03134360310794726%`
- median prefill delta: `+0.16937123171023583%`
- mean decode delta: `-0.004589486184392033%`
- mean TTFT delta: `-0.02373824369216182%`

By GPU prefill deltas:

- GPU0: `+0.024476938387829605%`
- GPU1: `+0.1231857794770308%`
- GPU2: `-0.03739521277895674%`
- GPU3: `+0.016426569232219634%`

By wave prefill deltas:

- wave A: `-0.858216823712632%`
- wave B: `+0.7669254360244127%`
- wave C: `-0.670889016819165%`
- wave D: `+0.9015255036537662%`

The wave alternation shows the apparent aggregate gain is normal run variance,
not a structural improvement.

## Decision

Decision: **closed negative / no-win noise**.

Do not promote
`GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST_SKIP_PRESOFTMAX_BARRIER`. The source
was reverted to keep only the promoted
`GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST` path and rebuilt successfully.
Reopen only if a future KQ register/broadcast design removes more shared-memory
state or a profiler shows this exact barrier as a measurable stall.

This is a service/prefill diagnostic result only. It is not a LocalMaxxing
headline decode result.
