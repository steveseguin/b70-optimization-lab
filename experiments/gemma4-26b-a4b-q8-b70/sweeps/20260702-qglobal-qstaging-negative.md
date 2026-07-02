# 2026-07-02 Q-global FlashAttention Staging Screen

Status: **negative / reverted**

Purpose: test a bounded service/prefill micro-optimization suggested by the
FlashAttention audit. The idea was to avoid staging Q into local memory for the
hot Gemma GQA8 DV512 KQ register-broadcast tile, and instead reload Q directly
from global memory inside the KQ loop. This was expected to be low-upside and
moderate-risk, but bounded because it sat behind a new default-off env var.

## Patch Artifacts

- Pre-edit source snapshot:
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-qstaging-preedit-source.patch`
- Q-global source snapshot:
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-qstaging-qglobal-source.patch`
- Q-global source diff hash: `e3568baa166f578fbd763e4afb023cf240fd1b9842ebb63a4f0e6bcb819effb5`
- Q-global binary hash:
  `3dd31a163e27a813783010e2225342b8391aadfb9c03e34a75c110a3867be849`
  for `build-sycl-b70-aot-bmg-g31-q8reorder-vdr2/bin/libggml-sycl.so.0.15.2`

The patch added `GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST_QGLOBAL=1` and left
the existing record path as the default.

## Validation Commands

Candidate:

```bash
cd /home/steve/llm-optimizations
GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8 \
LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND=1 \
LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_MIN_Q=2048 \
GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST=1 \
GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST_QGLOBAL=1 \
STAMP=20260702Tqglobal-smoke1 \
BASE_PORT=19320 \
MAX_TOKENS=96 \
CANARY_REPEATS=1 \
READINESS_TIMEOUT_S=900 \
LONG_CONTEXT_CASE_IDS='lc-12288-early' \
LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS=24000 \
LANE_SPECS='0:2048:1024:qglobal-smoke-gpu0:2048' \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh
```

Control, same rebuilt binary and same case with Q-global disabled:

```bash
cd /home/steve/llm-optimizations
GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8 \
LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND=1 \
LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_MIN_Q=2048 \
GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST=1 \
STAMP=20260702Tqglobal-control1 \
BASE_PORT=19321 \
MAX_TOKENS=96 \
CANARY_REPEATS=1 \
READINESS_TIMEOUT_S=900 \
LONG_CONTEXT_CASE_IDS='lc-12288-early' \
LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS=24000 \
LANE_SPECS='0:2048:1024:qglobal-control-gpu0:2048' \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh
```

## Results

Both runs passed the deterministic long-context row and chat canaries. Both had
`cached_tokens=0`.

| Run | Prefill tok/s | Decode tok/s after TTFT | TTFT |
| --- | ---: | ---: | ---: |
| Control, Q-global off | `1232.947927865592` | `128.22633277138354` | `13.149784864042886` |
| Candidate, Q-global on | `1188.7215805967094` | `123.4378078992772` | `13.639022176968865` |

Delta: prefill `-3.59%`, decode `-3.73%`, TTFT `+3.72%`.

## Decision

Do not continue this lane. Reloading Q from global memory loses more than the
saved shared-memory staging buys, at least for the hot B70 Gemma service shape.
The source patch was reverted after recording the result, and the baseline
binary should be rebuilt before further optimization work.
