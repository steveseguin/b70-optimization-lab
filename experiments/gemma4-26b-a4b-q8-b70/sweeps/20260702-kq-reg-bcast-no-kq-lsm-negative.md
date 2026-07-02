# Gemma 4 26B Q8: KQ Register/Broadcast No-KQ-LSM Follow-Up

Date: 2026-07-02

## Summary

This experiment tested whether the promoted global FlashAttention KQ
register/broadcast path still paid an avoidable local-memory allocation cost
for the KQ scratch buffer. The candidate added a second default-off flag:

```bash
GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST=1
GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST_NO_KQ_LSM=1
```

The first flag is the validated KQ register/broadcast service micro-win. The
second flag changed only that path by eliding the unused KQ local-memory region
inside the tile kernel. The hypothesis was that reducing declared local memory
could improve occupancy or scheduling for the hot Gemma global GQA shape.

Result: **no win / noise**. The patch built and passed validation, but the
balanced four-wave A/B + crossover measured `-0.034%` mean prefill delta and
`+0.067%` median prefill delta, with mixed wave/GPU behavior. The active source
was reverted to the promoted KQ register/broadcast path without the no-KQ-LSM
variant.

## Source Artifacts

Patch snapshots:

- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-kq-reg-bcast-no-kq-lsm-preedit-source.patch`
- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-kq-reg-bcast-no-kq-lsm-preedit-source.diffstat`
- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-kq-reg-bcast-no-kq-lsm-preedit-fattn-tile.patch`
- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-kq-reg-bcast-no-kq-lsm-source.patch`
- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-kq-reg-bcast-no-kq-lsm-source.diffstat`
- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-kq-reg-bcast-no-kq-lsm-fattn-tile.patch`

Build result:

- build target: `build-sycl-b70-aot-bmg-g31-q8reorder-vdr2/bin/llama-server`
- candidate build succeeded
- candidate `libggml-sycl.so.0.15.2` hash:
  `093a56b238058634d20fa580d97f56b578c8c42757b075dae3e67c57a5495daa`
- compile/link cost increased because the extra template variant forced another
  slow BMG device-image compile; this cost alone does not reject the idea, but
  it matters for future iteration speed.

## Validation

Smoke:

- summary: `data/gemma4-long-context-service-gate-20260702Tkqregbcast-nokqlsm-smoke1.json`
- run dir:
  `data/gemma4-q8-gpu0-longctx-kqregbcast-nokqlsm-ctx32768-o96-20260702Tkqregbcast-nokqlsm-smoke1/`
- exact JSON validation: pass
- `cached_tokens=0`
- approximate prefill: `1231.100954879233 tok/s`
- decode: `127.68507408335661 tok/s`
- TTFT: `13.16951297596097 s`

Full A/B + crossover:

- comparison:
  `data/gemma4-global-fattn-kq-reg-bcast-no-kq-lsm-comparison-20260702.json`
- 48/48 rows valid
- exact JSON validation passed on every row
- `cached_tokens=0` on every row

Aggregates:

- control mean prefill: `1124.0265437291819 tok/s`
- candidate mean prefill: `1123.6487109309744 tok/s`
- mean prefill delta: `-0.03361422382018864%`
- median prefill delta: `+0.06689916698370268%`
- mean decode delta: `+0.047999861759251417%`
- mean TTFT delta: `+0.0499296007400174%`

By GPU prefill deltas:

- GPU0: `-0.12997566407713101%`
- GPU1: `-0.03669722501467021%`
- GPU2: `-0.1166671033770772%`
- GPU3: `+0.14957634074890258%`

By case prefill deltas:

- `lc-12288-early`: `-0.006132169324268855%`
- `lc-16384-late`: `+0.002822793870915774%`
- `lc-22000-middle`: `-0.10616855431548888%`

By wave prefill deltas:

- wave A: `-0.8676423856124105%`
- wave B: `+0.9034118784108314%`
- wave C: `-0.8993071978477984%`
- wave D: `+0.7451270305410818%`

The wave alternation is a strong sign that this candidate is inside normal
measurement noise rather than a real structural improvement.

## Decision

Decision: **closed negative / no-win noise**.

Do not promote `GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST_NO_KQ_LSM`. The source
was reverted to keep only the promoted `GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST`
path and rebuilt successfully. The reverted active `libggml-sycl.so.0.15.2`
hash returned to the promoted DKQ576 KQ register/broadcast build:
`61c364b690ea6f852ad71c77abd65605c33de967dc9186c19d322c28e4ea8864`.
Reopen only if a future compiler/kernel layout change makes declared local
memory size visibly affect occupancy for this tile.

This is a service/prefill diagnostic result only. It is not a LocalMaxxing
headline decode result.
