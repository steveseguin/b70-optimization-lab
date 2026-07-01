# 2026-07-01 - Phase-Prefill Per-Lane Ladder

Status: valid service/prefill diagnostics. No LocalMaxxing submission.

## Purpose

After adding durable `prefill_ubatch_size` identity capture, the long-context
service wrapper was extended so one four-GPU run can compare different
`LLAMA_PREFILL_UBATCH_SIZE` values directly.

Harness change:

- `repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh`
  accepts `LANE_SPECS` as either the original
  `GPU:BATCH:UBATCH:TAG` or the new
  `GPU:BATCH:UBATCH:TAG:PREFILL_UBATCH_SIZE`;
- when the fifth field is present, only that lane exports
  `LLAMA_PREFILL_UBATCH_SIZE`;
- aggregate `rows` and `group_summaries` now include
  `prefill_ubatch_size`, so phase-prefill comparisons do not collapse into the
  same `batch/ubatch` bucket.

This is a harness/reproducibility improvement and does not change runtime
behavior for old four-field lane specs.

## Shared Identity

- target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- draft: Q4_0 MTP draft, target verified
- runtime: llama.cpp Gemma record stack at `c926ad098`
- hardware: one B70 per lane
- context: `CTX_SIZE=32768`, `FLASH_ATTN=on`, `GGML_SYCL_ENABLE_VMM=1`
- service attention selector: `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`
- decode ubatch: `UBATCH_SIZE=1024` on all phase-prefill lanes
- suite: fixed deterministic long-context suite, cases
  `lc-12288-early`, `lc-16384-late`, `lc-22000-middle`
- validity: exact JSON validation, `cached_tokens=0`, prompts unique, canary
  pass

## Ladder: 1792 / 2048 / 2304 / 2560

Command:

```bash
cd /home/steve/qwen36-results-main
STAMP=20260701T023759Z-phaseprefill-ladder \
GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8 \
LONG_CONTEXT_CASE_IDS='lc-12288-early lc-16384-late lc-22000-middle' \
LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS=24000 \
CANARY_REPEATS=2 \
MAX_TOKENS=96 \
READINESS_TIMEOUT_S=900 \
BASE_PORT=18630 \
LANE_SPECS='0:1792:1024:phase1792-ub1024:1792 1:2048:1024:phase2048-ub1024:2048 2:2304:1024:phase2304-ub1024:2304 3:2560:1024:phase2560-ub1024:2560' \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh
```

Aggregate:

- `data/gemma4-long-context-service-gate-20260701T023759Z-phaseprefill-ladder.json`

All lanes passed validation, canary, and `cached_tokens=0`.

| Phase prefill | Median prefill tok/s | Median decode tok/s | Readout |
| ---: | ---: | ---: | --- |
| 1792 | `1056.1084` | `119.3112` | looked balanced in this one-lane screen |
| 2048 | `1042.0264` | `119.0503` | known balanced default, weak lane in this run |
| 2304 | **`1078.9997`** | `116.9092` | best pure prefill, decode drops |
| 2560 | `1071.8658` | `116.3453` | pure prefill only, decode drops more |

## Crossover: 1792 vs 2048

Because the ladder suggested 1792 might be better balanced than 2048, a
two-lane crossover compared 1792 and 2048 on different GPUs.

Command:

```bash
cd /home/steve/qwen36-results-main
STAMP=20260701T024013Z-phaseprefill-1792-xover \
GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8 \
LONG_CONTEXT_CASE_IDS='lc-12288-early lc-16384-late lc-22000-middle' \
LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS=24000 \
CANARY_REPEATS=2 \
MAX_TOKENS=96 \
READINESS_TIMEOUT_S=900 \
BASE_PORT=18640 \
LANE_SPECS='0:2048:1024:phase2048-xa:2048 1:1792:1024:phase1792-xa:1792 2:1792:1024:phase1792-xb:1792 3:2048:1024:phase2048-xb:2048' \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh
```

Aggregate:

- `data/gemma4-long-context-service-gate-20260701T024013Z-phaseprefill-1792-xover.json`

All lanes passed validation, canary, and `cached_tokens=0`.

| Phase prefill | Lanes | Median prefill avg | Median decode avg | Decision |
| ---: | ---: | ---: | ---: | --- |
| 1792 | 2 | `1047.0015` | `119.3035` | no advantage |
| 2048 | 2 | **`1052.6123`** | **`119.7308`** | remains balanced default |

The 1792 hint in the ladder was GPU/run noise. Do not switch the balanced
phase-prefill service recipe from 2048 to 1792.

## Decision

- Keep `BATCH_SIZE=2048`, `UBATCH_SIZE=1024`,
  `LLAMA_PREFILL_UBATCH_SIZE=2048` as the balanced phase-prefill service
  candidate.
- `2304` and `2560` are valid pure-prefill diagnostics, but their long-context
  decode drop makes them unsuitable for the "do not lower decode" service
  profile without a separate deployment reason.
- No short-decode LocalMaxxing submission: this is a long-context service
  lane, not a fresh short-decode record.
