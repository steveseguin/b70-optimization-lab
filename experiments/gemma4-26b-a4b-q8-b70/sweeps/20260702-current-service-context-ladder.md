# Gemma 4 26B Q8: Current Service Context Ladder

Date: 2026-07-02

Status: valid service/prompt-processing baseline. This is not a short-decode
LocalMaxxing headline result.

## Purpose

After the global FlashAttention micro-lanes closed mostly negative or tiny
positive, capture a clean four-GPU cold long-context ladder for the current
validated service recipe. This gives future prompt-processing work a reliable
baseline across context lengths instead of comparing against scattered one-case
service screens.

## Recipe

Current service stack:

```bash
GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8
LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND=1
LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_MIN_Q=2048
GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST=1
BATCH_SIZE=2048
UBATCH_SIZE=1024
LLAMA_PREFILL_UBATCH_SIZE=2048
CTX_SIZE=32768
FLASH_ATTN=on
GGML_SYCL_ENABLE_VMM=1
```

Command:

```bash
cd /home/steve/llm-optimizations
GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8 \
LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND=1 \
LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_MIN_Q=2048 \
GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST=1 \
STAMP=20260702Tservice-ladder-current-rep4 \
BASE_PORT=19220 \
MAX_TOKENS=128 \
CANARY_REPEATS=4 \
READINESS_TIMEOUT_S=900 \
LONG_CONTEXT_CASE_IDS='lc-00512-early lc-02048-middle lc-04096-late lc-08192-middle lc-12288-early lc-16384-late lc-22000-middle lc-24000-late' \
LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS=24000 \
LANE_SPECS='0:2048:1024:svc-current-gpu0:2048 1:2048:1024:svc-current-gpu1:2048 2:2048:1024:svc-current-gpu2:2048 3:2048:1024:svc-current-gpu3:2048' \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh
```

Source / binary identity after the run:

- active source diff hash:
  `7220e022ae836b2a885f6e1ba5d73422f1ddd9c74e0c3e4582a0d7066fa295e3`
- active `libggml-sycl.so.0.15.2` hash:
  `61c364b690ea6f852ad71c77abd65605c33de967dc9186c19d322c28e4ea8864`

## Evidence

- Aggregate:
  `data/gemma4-long-context-service-gate-20260702Tservice-ladder-current-rep4.json`
- Per-lane run directories:
  - `data/gemma4-q8-gpu0-longctx-svc-current-gpu0-ctx32768-o128-20260702Tservice-ladder-current-rep4/`
  - `data/gemma4-q8-gpu1-longctx-svc-current-gpu1-ctx32768-o128-20260702Tservice-ladder-current-rep4/`
  - `data/gemma4-q8-gpu2-longctx-svc-current-gpu2-ctx32768-o128-20260702Tservice-ladder-current-rep4/`
  - `data/gemma4-q8-gpu3-longctx-svc-current-gpu3-ctx32768-o128-20260702Tservice-ladder-current-rep4/`

## Validity

All four lanes passed:

- fixed deterministic long-context suite;
- each prompt once as a cold request;
- `cached_tokens=0` for every row;
- exact JSON retrieval validation for every row;
- chat canary pass, 16 rows per GPU;
- UD-Q8_K_XL target/verifier unchanged; Q4_0 MTP draft unchanged.

This is a service/prefill baseline only. It should not be submitted or advertised
as fresh short-response LocalMaxxing throughput.

## Aggregate Result

Across four B70 lanes with the same recipe:

| Metric | Value |
| --- | ---: |
| exact long-context rows | 32/32 pass |
| cached-token rows | 32/32 at `cached_tokens=0` |
| canary rows | 64/64 pass |
| average lane median prefill | `1192.965 tok/s` |
| average lane median long-context decode | `131.786 tok/s` |

Per-lane medians:

| GPU | Median prefill tok/s | Median decode tok/s |
| --- | ---: | ---: |
| GPU0 | `1198.394` | `132.089` |
| GPU1 | `1180.003` | `131.318` |
| GPU2 | `1198.371` | `131.893` |
| GPU3 | `1195.090` | `131.843` |

## Context-Length Curve

Representative GPU0 row-level data:

| Case | Actual prompt tokens | Prefill tok/s | Decode tok/s | TTFT s |
| --- | ---: | ---: | ---: | ---: |
| `lc-00512-early` | 741 | `856.663` | `162.069` | `0.865` |
| `lc-02048-middle` | 2806 | `1406.307` | `145.149` | `1.995` |
| `lc-04096-late` | 5643 | `1478.602` | `141.429` | `3.816` |
| `lc-08192-middle` | 10976 | `1337.027` | `136.172` | `8.209` |
| `lc-12288-early` | 16213 | `1263.127` | `128.006` | `12.836` |
| `lc-16384-late` | 22730 | `1133.660` | `120.817` | `20.050` |
| `lc-22000-middle` | 30400 | `1032.119` | `114.438` | `29.454` |
| `lc-24000-late` | 32571 | `1004.976` | `115.180` | `32.410` |

The other GPUs followed the same curve. At the longest validated prompt
(`32571` actual tokens), prefill stayed about `991-1006 tok/s` and decode stayed
about `114-115 tok/s`.

## Interpretation

The validated service stack is strong and stable across the whole 512-to-24K
target-token ladder. The main remaining service decline is expected: prefill
falls from the mid-1400s near 4K actual prompt tokens to about `1000 tok/s` near
32K, and long-context decode falls from about `160 tok/s` on tiny prompts to
about `115 tok/s` near 32K.

Subagent/source audit found only one bounded unclosed service micro-lane:
bypass the large `Q_tmp` / Q local-memory staging for the hot global GQA8 tile
on top of `GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST=1`. Expected benefit is
small (`0%` to `+1%`) and risk is nontrivial because Q would be reloaded/scaled
inside the KQ loop. Treat it as optional service research, not a likely
short-decode record path.

Short-decode record work should not be driven by this ladder. The current
short-decode frontier remains a deeper exact verifier LM-head/backend redesign,
not another FlashAttention service micro-knob.
