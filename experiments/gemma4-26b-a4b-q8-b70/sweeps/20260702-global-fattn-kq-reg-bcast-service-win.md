# Gemma 4 26B Q8 Global FlashAttention KQ Register Broadcast Service Win

Date: 2026-07-02

## Question

The long-context service node profile showed the full/global FlashAttention
layers dominating TTFT. The hot global GQA8 shape is the same lane tested by the
DV-split negative:

```text
Q=[512,2,16,1], K/V=[512,256,2,1], mask=[256,2,1,1]
```

The previous DV-split patch was neutral because it duplicated KQ/softmax work.
This experiment instead kept a single tile pass and removed local-memory KQ
handoff for the hot `DKQ=512`, `DV=512`, `ncols1=2`, `ncols2=8`, `nbatch_fa=64`
shape. Softmax values are retained in a tiny per-lane register array and read by
the V@KQ phase with subgroup lane selection.

## Patch

Default-off source patch:

- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-kq-reg-bcast-source.patch`
- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-kq-reg-bcast-source.diffstat`

Pre-edit source snapshot:

- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-kq-reg-bcast-preedit-source.patch`
- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-kq-reg-bcast-preedit-source.diffstat`

The tested gate is `GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST=1`.

The patch:

- adds the env gate above;
- adds a `kq_reg_bcast` template parameter to the FlashAttention tile path;
- stores KQ softmax values in per-lane registers for the hot global GQA8 shape;
- uses `sycl::select_from_group` during V@KQ instead of reading KQ from local
  memory;
- preserves the normal path unless the env var is enabled and the exact hot
  shape matches.

The candidate built successfully:

```bash
source /opt/intel/oneapi/setvars.sh --force
ninja -C /home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2 llama-server
```

## Validation

Single-case smoke:

- `data/gemma4-long-context-service-gate-20260702Tkqregbcast-smoke1.json`
- case `lc-12288-early`
- exact JSON pass, canary pass, `cached_tokens=0`
- approximate prefill `1232.353 tok/s`, decode `127.738 tok/s`

Balanced four-wave service A/B:

- Wave A control:
  `data/gemma4-long-context-service-gate-20260702Tkqregbcast-waveA-control.json`
- Wave A candidate:
  `data/gemma4-long-context-service-gate-20260702Tkqregbcast-waveA-candidate.json`
- Wave B control:
  `data/gemma4-long-context-service-gate-20260702Tkqregbcast-waveB-control.json`
- Wave B candidate:
  `data/gemma4-long-context-service-gate-20260702Tkqregbcast-waveB-candidate.json`
- Wave C control:
  `data/gemma4-long-context-service-gate-20260702Tkqregbcast-waveC-control.json`
- Wave C candidate:
  `data/gemma4-long-context-service-gate-20260702Tkqregbcast-waveC-candidate.json`
- Wave D control:
  `data/gemma4-long-context-service-gate-20260702Tkqregbcast-waveD-control.json`
- Wave D candidate:
  `data/gemma4-long-context-service-gate-20260702Tkqregbcast-waveD-candidate.json`
- Combined comparison:
  `data/gemma4-global-fattn-kq-reg-bcast-comparison-20260702.json`

Run identity:

- model: Gemma 4 26B A4B instruct `UD-Q8_K_XL` target/verifier
- llama.cpp source baseline: `c926ad098` record stack plus the default-off KQ
  register/broadcast source patch
- one replica per B70 GPU, GPUs 0-3
- `FLASH_ATTN=on`, `CTX_SIZE=32768`, `GGML_SYCL_ENABLE_VMM=1`
- `BATCH_SIZE=2048`, `UBATCH_SIZE=1024`, `LLAMA_PREFILL_UBATCH_SIZE=2048`
- `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`
- `LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND=1`
- `LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_MIN_Q=2048`
- candidate only: `GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST=1`
- cases: `lc-12288-early`, `lc-16384-late`, `lc-22000-middle`
- `MAX_TOKENS=96`, `CANARY_REPEATS=2`
- all 48 comparison rows had exact JSON validation pass and `cached_tokens=0`

Short-decode guard smoke with the candidate flag enabled:

- `data/gemma4-short-decode-guard-20260702Tkqregbcast-shortguard-smoke.json`
- four lanes passed realistic gate, canaries, and `cached_tokens=0`
- this was a `MAX_TOKENS=256`, `CANARY_REPEATS=8` smoke only; it is not a
  headline record attempt

## Result

Balanced A/B/C/D comparison:

| metric | control mean | candidate mean | delta |
| --- | ---: | ---: | ---: |
| approximate prefill tok/s | `1116.664` | `1124.810` | `+0.730%` |
| after-TTFT decode tok/s | `119.771` | `120.288` | `+0.431%` |
| TTFT seconds | `21.173` | `21.007` | `-0.782%` |

Same-GPU prefill deltas were positive on every GPU:

| GPU | prefill delta | decode delta |
| --- | ---: | ---: |
| 0 | `+0.617%` | `+0.385%` |
| 1 | `+0.924%` | `+0.298%` |
| 2 | `+0.560%` | `+0.339%` |
| 3 | `+0.820%` | `+0.704%` |

Per-case prefill deltas were also positive and grow with context length:

| case | prefill delta | decode delta |
| --- | ---: | ---: |
| `lc-12288-early` | `+0.553%` | `+0.209%` |
| `lc-16384-late` | `+0.747%` | `+0.468%` |
| `lc-22000-middle` | `+0.920%` | `+0.643%` |

Decision: **service-prefill win, default-off, promote as an optional service
flag after keeping the source patch available.** This is not a LocalMaxxing
headline decode record and should not be submitted as one.

## Reproduction

Use:

```bash
cd /home/steve/llm-optimizations
STAMP=YYYYMMDD-kqregbcast-service-confirm \
REPLICATES=2 \
RUN_SHORT_GUARD=1 \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-kqregbcast-service-confirm.sh
```

The wrapper emits a comparison JSON via:

```bash
scripts/compare-gemma-long-context-service-ab.py
```

## Interpretation

This closes the "one-pass KQ handoff" branch as a small but real win for the
profiled global GQA8 long-context service shape. The size is below the level
worth claiming as a broad record improvement, but it is consistent after
same-GPU balancing and does not require lowering quality or using cached
continuations.

Next service-prefill work should stay structural: reduce global-tile memory
traffic or skip provably out-of-window work without touching the short-decode
record path. Future changes must continue to run the short-decode guard because
past prompt-processing wins sometimes regressed the record lane.
