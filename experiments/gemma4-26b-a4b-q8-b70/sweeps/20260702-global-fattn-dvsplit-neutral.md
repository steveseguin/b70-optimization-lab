# Gemma 4 26B Q8 Global FlashAttention DV-Split Neutral

Date: 2026-07-02

## Question

The long-context service node profile showed full/global FlashAttention layers
dominating TTFT. The hot global shape was:

```text
Q=[512,2,16,1], K/V=[512,256,2,1], mask=[256,2,1,1]
```

The existing tile path handles this as `DKQ=512`, `DV=512`, GQA8, with
`GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`. The cheap vec-dispatch experiment was
negative, so this experiment tested whether splitting only the value dimension
into two `DV=256` tile launches would improve occupancy enough to beat the
extra softmax/KQ work.

## Patch

Default-off source patch:

- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-global-fattn-dvsplit-source.patch`
- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-global-fattn-dvsplit-source.diffstat`

Pre-edit source snapshot:

- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-global-fattn-dvsplit-preedit-source.patch`
- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-global-fattn-dvsplit-preedit-source.diffstat`

The tested gate was `GGML_SYCL_FATTN_GLOBAL_GQA8_DVSPLIT=2`. The patch:

- added sliced destination support to `launch_fattn` / `flash_attn_combine_results`;
- added a guarded hot-shape branch that launches two `DV=256` tile kernels into
  the original `DV=512` output row;
- preserved the normal path when the env var is unset.

The candidate built successfully with the oneAPI environment sourced:

```bash
source /opt/intel/oneapi/setvars.sh --force
ninja -C /home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2 llama-server
```

## Validation

Single-case smoke:

- `data/gemma4-long-context-service-gate-20260702Tglobaldvsplit-smoke1.json`
- case `lc-12288-early`
- exact JSON pass, canary pass, `cached_tokens=0`
- approximate prefill `1223.744 tok/s`, decode `127.476 tok/s`

Four-GPU same-window A/B plus crossover:

- Wave A control:
  `data/gemma4-long-context-service-gate-20260702Tglobaldvsplit-waveA-control.json`
- Wave A candidate:
  `data/gemma4-long-context-service-gate-20260702Tglobaldvsplit-waveA-candidate.json`
- Wave B control:
  `data/gemma4-long-context-service-gate-20260702Tglobaldvsplit-waveB-control.json`
- Wave B candidate:
  `data/gemma4-long-context-service-gate-20260702Tglobaldvsplit-waveB-candidate.json`
- Combined comparison:
  `data/gemma4-global-fattn-dvsplit-comparison-20260702.json`

Run identity:

- model: Gemma 4 26B A4B instruct `UD-Q8_K_XL` target/verifier
- llama.cpp source baseline: `c926ad098` record stack
- one replica per B70 GPU, GPUs 0-3
- `FLASH_ATTN=on`, `CTX_SIZE=32768`, `GGML_SYCL_ENABLE_VMM=1`
- `BATCH_SIZE=2048`, `UBATCH_SIZE=1024`, `LLAMA_PREFILL_UBATCH_SIZE=2048`
- `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`
- `LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND=1`
- `LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_MIN_Q=2048`
- cases: `lc-12288-early`, `lc-16384-late`, `lc-22000-middle`
- `MAX_TOKENS=96`, `CANARY_REPEATS=2`
- every comparison row had exact JSON validation pass and `cached_tokens=0`

## Result

The candidate was valid but effectively flat:

| scope | approximate prefill delta |
| --- | ---: |
| wave A mean | `-0.917%` |
| wave B mean | `+0.908%` |
| combined mean | `-0.009%` |
| combined median | `-0.036%` |

Per-case combined deltas were also flat:

| case | delta |
| --- | ---: |
| `lc-12288-early` | `-0.063%` |
| `lc-16384-late` | `-0.005%` |
| `lc-22000-middle` | `+0.049%` |

Decision: **neutral / no win / do not promote**.

## Interpretation

The occupancy gain from halving `DV` is cancelled by recomputing KQ/softmax and
launching two kernels. This closes the straightforward "split value dimension"
branch for the profiled global GQA8 shape.

Do not leave this patch active. Future service work should target a true
one-pass global-tile improvement: better intra-kernel parallelism, better
GQA/KV reuse, or a mask/bound optimization that avoids work instead of
duplicating it.
