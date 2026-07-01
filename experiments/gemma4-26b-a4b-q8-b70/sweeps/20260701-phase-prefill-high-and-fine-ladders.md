# 2026-07-01 - Phase-Prefill High/Fine Ladders

Status: valid service/prefill diagnostics; closed negative for changing the
balanced service default. No LocalMaxxing submission.

## Purpose

After the phase-prefill per-lane ladder kept
`BATCH_SIZE=2048`, `UBATCH_SIZE=1024`, and
`LLAMA_PREFILL_UBATCH_SIZE=2048` as the balanced service profile, test whether
larger or slightly larger prefill chunks can improve long-context prompt
processing without lowering long-context decode.

This is a service/prefill lane, not a short-decode headline lane. The current
fresh-response short-decode record remains `123.67689864739785 tok/s`.

## Shared Identity

- target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- draft: Q4_0 MTP draft, target verified
- runtime: llama.cpp Gemma record stack at `c926ad098`
- hardware: one B70 per lane
- context: `CTX_SIZE=32768`, `FLASH_ATTN=on`, `GGML_SYCL_ENABLE_VMM=1`
- service attention selector: `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`
- decode ubatch: `UBATCH_SIZE=1024` for every lane
- suite: fixed deterministic long-context suite, cases
  `lc-12288-early`, `lc-16384-late`, `lc-22000-middle`
- validity: exact JSON validation, `cached_tokens=0`, prompts unique, canary
  pass

## High Ladder: 2048 / 2304 / 2816 / 3072

Command:

```bash
cd /home/steve/qwen36-results-main
STAMP=20260701T031836Z-phaseprefill-high1 \
GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8 \
LONG_CONTEXT_CASE_IDS='lc-12288-early lc-16384-late lc-22000-middle' \
LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS=24000 \
CANARY_REPEATS=2 \
MAX_TOKENS=96 \
READINESS_TIMEOUT_S=900 \
BASE_PORT=18660 \
LANE_SPECS='0:2048:1024:phase2048-high1:2048 1:2304:1024:phase2304-high1:2304 2:2816:1024:phase2816-high1:2816 3:3072:1024:phase3072-high1:3072' \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh
```

Aggregate:

- `data/gemma4-long-context-service-gate-20260701T031836Z-phaseprefill-high1.json`

All lanes passed validation, canary, and `cached_tokens=0`.

| Phase prefill | Median prefill tok/s | Median decode tok/s | Decision |
| ---: | ---: | ---: | --- |
| 2048 | `1055.4653` | **`119.8684`** | balanced default still strongest |
| 2304 | `1059.1151` | `116.7015` | tiny prefill gain, clear decode loss |
| 2816 | **`1067.3839`** | `114.8402` | best in-run pure prefill, decode loss too large |
| 3072 | `1051.4601` | `114.1090` | regresses both vs 2816 |

## Fine Ladder: 2048 / 2112 / 2176 / 2240

Command:

```bash
cd /home/steve/qwen36-results-main
STAMP=20260701T032044Z-phaseprefill-fine1 \
GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8 \
LONG_CONTEXT_CASE_IDS='lc-12288-early lc-16384-late lc-22000-middle' \
LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS=24000 \
CANARY_REPEATS=2 \
MAX_TOKENS=96 \
READINESS_TIMEOUT_S=900 \
BASE_PORT=18670 \
LANE_SPECS='0:2048:1024:phase2048-fine1:2048 1:2112:1024:phase2112-fine1:2112 2:2176:1024:phase2176-fine1:2176 3:2240:1024:phase2240-fine1:2240' \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh
```

Aggregate:

- `data/gemma4-long-context-service-gate-20260701T032044Z-phaseprefill-fine1.json`

All lanes passed validation, canary, and `cached_tokens=0`.

| Phase prefill | Median prefill tok/s | Median decode tok/s | Decision |
| ---: | ---: | ---: | --- |
| 2048 | `1054.8361` | **`119.9451`** | balanced default still strongest |
| 2112 | `1041.6486` | `116.2161` | regresses both |
| 2176 | `1055.9590` | `117.0618` | negligible prefill gain, decode loss |
| 2240 | `1056.7940` | `116.8961` | negligible prefill gain, decode loss |

## Decision

Keep the balanced phase-prefill service profile at:

```bash
BATCH_SIZE=2048
UBATCH_SIZE=1024
LLAMA_PREFILL_UBATCH_SIZE=2048
GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8
```

The larger-prefill sweeps are valid but not useful for the no-decode-regression
service target:

- high values above `2304` do not beat the older best pure-prefill evidence and
  lower long-context decode;
- fine values `2112/2176/2240` do not find a free prefill improvement near
  `2048`;
- no short-decode guard is warranted because every non-2048 candidate already
  loses long-context decode.

Future prompt-processing work should move away from ubatch sweeps and into a
source/kernel change, especially SWA-specific FlashAttention tile/mask handling
or a more detailed attention timing split.
