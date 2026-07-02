# Gemma 4 26B Q8 Global FlashAttention KQ Register Broadcast DKQ576 Extension

Date: 2026-07-02

## Question

The first KQ register/broadcast patch proved a small but repeatable
long-context service win for the hot global FlashAttention GQA8 tile path, but
the initial dispatch was limited to `DKQ=512`, `DV=512`. The service node
profile showed the dominant Gemma global-attention service shape is actually
`DKQ=576`, `DV=512`, `ncols=16`:

```text
Q=[512,2,16,1], K/V=[512,256,2,1], mask=[256,2,1,1]
```

This follow-up tests whether the same default-off register/broadcast path is
valid and useful for `DKQ=576`.

## Patch

Default-off source extension:

- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-kq-reg-bcast-dkq576-source.patch`
- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-kq-reg-bcast-dkq576-source.diffstat`
- focused file patch:
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-kq-reg-bcast-dkq576-fattn-tile.patch`

Pre-edit source snapshot:

- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-kq-reg-bcast-dkq576-preedit-source.patch`
- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-kq-reg-bcast-dkq576-preedit-source.diffstat`
- focused pre-edit patch:
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-kq-reg-bcast-dkq576-preedit-fattn-tile.patch`

The tested gate remains:

```bash
GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST=1
```

The functional change extends the dispatch condition from `DKQ == 512` to
`DKQ == 512 || DKQ == 576`. The normal path remains unchanged unless the env
var is enabled and the exact hot shape matches.

The candidate built successfully:

```bash
source /opt/intel/oneapi/setvars.sh --force
ninja -C /home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2 llama-server
```

`libggml-sycl.so.0.15.2` after build:

```text
61c364b690ea6f852ad71c77abd65605c33de967dc9186c19d322c28e4ea8864
```

## Validation

Single-case smoke:

- `data/gemma4-long-context-service-gate-20260702Tkqregbcast-dkq576-smoke1.json`
- case `lc-12288-early`
- exact JSON pass, canary pass, `cached_tokens=0`
- approximate prefill `1231.683 tok/s`, decode `127.828 tok/s`

Balanced four-wave service A/B:

- Wave A:
  - control:
    `data/gemma4-long-context-service-gate-20260702Tkqregbcast-dkq576-waveA-control.json`
  - candidate:
    `data/gemma4-long-context-service-gate-20260702Tkqregbcast-dkq576-waveA-candidate.json`
- Wave B:
  - control:
    `data/gemma4-long-context-service-gate-20260702Tkqregbcast-dkq576-waveB-control.json`
  - candidate:
    `data/gemma4-long-context-service-gate-20260702Tkqregbcast-dkq576-waveB-candidate.json`
- Wave C:
  - control:
    `data/gemma4-long-context-service-gate-20260702Tkqregbcast-dkq576-waveC-control.json`
  - candidate:
    `data/gemma4-long-context-service-gate-20260702Tkqregbcast-dkq576-waveC-candidate.json`
- Wave D:
  - control:
    `data/gemma4-long-context-service-gate-20260702Tkqregbcast-dkq576-waveD-control.json`
  - candidate:
    `data/gemma4-long-context-service-gate-20260702Tkqregbcast-dkq576-waveD-candidate.json`
- Combined comparison:
  `data/gemma4-global-fattn-kq-reg-bcast-dkq576-comparison-20260702.json`

Run identity:

- model: Gemma 4 26B A4B instruct `UD-Q8_K_XL` target/verifier
- llama.cpp source baseline: `c926ad098` record stack plus the default-off KQ
  register/broadcast source patch extended to `DKQ=576`
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

Short-decode guard with the candidate flag enabled:

- `data/gemma4-short-decode-guard-20260702Tkqregbcast-dkq576-shortguard.json`
- four lanes passed the fixed realistic gate, canaries, and `cached_tokens=0`
- `MAX_TOKENS=256`, `CANARY_REPEATS=8`; this is a regression guard, not a
  headline record attempt
- lane medians for generated tokens 1-100 after TTFT:
  - UB1024: `117.801`, `114.569 tok/s`
  - UB2048: `118.541`, `117.336 tok/s`

Full512 short-decode follow-up, after the service win:

- `data/gemma4-kqregbcast-short-full512-ab-20260702T112211Z-kqregbcast-short-full512-ab.json`
- all eight lanes passed the fixed realistic gate, canaries, and
  `cached_tokens=0`;
- isolated variable: control `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`, candidate
  adds `GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST=1`;
- control medians: `117.584`, `124.161`, `115.228`, `116.737 tok/s`;
- candidate medians: `116.760`, `117.590`, `124.444`, `115.657 tok/s`;
- paired prompt median ratio 95% CI:
  `-2.666% / -0.040% / +3.119%`, decision `no_win`.

This confirms the KQ flag remains service/prefill-only; it should not be added
to the short-decode headline recipe or submitted to LocalMaxxing. See
`20260702-kq-reg-bcast-short-full512-no-win.md`.

## Result

Balanced A/B/C/D comparison:

| metric | control mean | candidate mean | delta |
| --- | ---: | ---: | ---: |
| approximate prefill tok/s | `1117.634` | `1125.702` | `+0.722%` |
| approximate prefill tok/s, median delta | | | `+0.813%` |
| after-TTFT decode tok/s | `119.941` | `120.295` | `+0.296%` |
| TTFT seconds | `21.164` | `21.002` | `-0.765%` |

Per-wave prefill was mixed because the same-window direction is dominated by
GPU placement, which is why the test used crossover waves:

| wave | prefill delta | decode delta |
| --- | ---: | ---: |
| A | `-0.142%` | `-0.148%` |
| B | `+1.618%` | `+0.630%` |
| C | `-0.125%` | `-0.058%` |
| D | `+1.552%` | `+0.761%` |

Same-GPU prefill deltas were positive on every GPU:

| GPU | prefill delta | decode delta |
| --- | ---: | ---: |
| 0 | `+0.648%` | `+0.342%` |
| 1 | `+0.878%` | `-0.042%` |
| 2 | `+0.574%` | `+0.354%` |
| 3 | `+0.791%` | `+0.527%` |

Per-case prefill deltas were also positive:

| case | prefill delta | decode delta |
| --- | ---: | ---: |
| `lc-12288-early` | `+0.567%` | `+0.120%` |
| `lc-16384-late` | `+0.753%` | `+0.315%` |
| `lc-22000-middle` | `+0.872%` | `+0.472%` |

Decision: **service-prefill win, default-off.** Promote the DKQ576 extension
as part of the optional `GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST=1` service
flag. This is not a LocalMaxxing headline decode result and should not be
submitted as one. The full512 short-decode A/B did not promote the flag for the
short headline; keep the current short-record recipe separate.

## Reproduction

The combined comparison can be regenerated with:

```bash
cd /home/steve/llm-optimizations
scripts/compare-gemma-long-context-service-ab.py \
  --kind gemma4_global_fattn_gqa8_kq_reg_bcast_dkq576_ab_comparison \
  --decision service-prefill-win-default-off \
  --candidate-env GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST=1 \
  --candidate-env GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8 \
  --notes 'Extension of the default-off KQ register/broadcast path from DKQ512 to DKQ576; service/prefill diagnostic, not LocalMaxxing headline.' \
  --control waveA=data/gemma4-long-context-service-gate-20260702Tkqregbcast-dkq576-waveA-control.json \
  --candidate waveA=data/gemma4-long-context-service-gate-20260702Tkqregbcast-dkq576-waveA-candidate.json \
  --control waveB=data/gemma4-long-context-service-gate-20260702Tkqregbcast-dkq576-waveB-control.json \
  --candidate waveB=data/gemma4-long-context-service-gate-20260702Tkqregbcast-dkq576-waveB-candidate.json \
  --control waveC=data/gemma4-long-context-service-gate-20260702Tkqregbcast-dkq576-waveC-control.json \
  --candidate waveC=data/gemma4-long-context-service-gate-20260702Tkqregbcast-dkq576-waveC-candidate.json \
  --control waveD=data/gemma4-long-context-service-gate-20260702Tkqregbcast-dkq576-waveD-control.json \
  --candidate waveD=data/gemma4-long-context-service-gate-20260702Tkqregbcast-dkq576-waveD-candidate.json \
  --output data/gemma4-global-fattn-kq-reg-bcast-dkq576-comparison-20260702.json
```

For a fresh service confirmation, use the promoted wrapper:

```bash
cd /home/steve/llm-optimizations
STAMP=YYYYMMDD-kqregbcast-service-confirm \
REPLICATES=2 \
RUN_SHORT_GUARD=1 \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-kqregbcast-service-confirm.sh
```

## Interpretation

The DKQ576 extension matters because it reaches the dominant profiled global
FlashAttention service shape. The effect is still a micro-win, but it is
positive after same-GPU balancing and across all long-context cases. Keep it as
an optional service/prefill flag, and continue to protect the short decode
record with a short-suite guard before changing any promoted service recipe.
