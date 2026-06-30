# 2026-06-30 - GQA8 Middle-Ubatch Balance Screen

Goal: find a single Gemma 4 26B A4B Q8 runtime setting that improves
long-context prompt processing while preserving the validated short-context
decode rate. This followed the promoted
`GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8` service/prefill win.

## Policy

This screen uses two separate gates:

- long-context service gate: fixed deterministic long prompts, one cold request
  per prompt, exact JSON validation, `cached_tokens=0`;
- short-decode guard: fixed realistic cold suite, `cached_tokens=0`, no
  prompt/KV/history reuse, primary metric median generated tokens 1-100 after
  TTFT.

No LocalMaxxing submission is implied. A setting can only replace the short
record if it beats the current fixed-gate record:
`123.67689864739785 tok/s`.

## Long-Context Screen

Command:

```bash
GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8 \
STAMP=20260630Tfattn-gqa8-midubatch-A \
LONG_CONTEXT_CASE_IDS='lc-12288-early lc-16384-late lc-22000-middle' \
LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS=24000 \
LANE_SPECS='0:1280:1280:ub1280-gqa8 1:1536:1536:ub1536-gqa8 2:1792:1792:ub1792-gqa8 3:1920:1920:ub1920-gqa8' \
CANARY_REPEATS=2 MAX_TOKENS=96 BASE_PORT=18610 \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh
```

Artifact:
`data/gemma4-long-context-service-gate-20260630Tfattn-gqa8-midubatch-A.json`

All lanes passed exact long-context validation and had `cached_tokens=0`.

| UB | Median prefill tok/s | 30400-token prefill tok/s | Median decode tok/s | Readout |
| ---: | ---: | ---: | ---: | --- |
| 1280 | 1006.41 | 920.49 | 122.35 | best decode balance in this screen |
| 1536 | 1025.05 | 930.79 | 121.93 | modest prefill gain, slight decode loss |
| 1792 | 1058.04 | 965.02 | 119.46 | strong prefill, clear decode drop |
| 1920 | 1055.84 | 957.53 | 119.14 | no better than UB1792 |

Compared with the broad GQA8 service gate:

- UB1024 broad: median prefill `969.77`, median decode `125.36`;
- UB2048 broad: median prefill `1039.60`, median decode `119.08`;
- UB2304 broad: median prefill `1075.98`, median decode `117.00`.

The middle values fill the tradeoff curve but do not create a free lunch.

## Short-Decode Guard

Command:

```bash
GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8 \
STAMP=20260630Tfattn-gqa8-midubatch-shortguard-A \
LANE_SPECS='0:1280:1280:ub1280-gqa8 1:1536:1536:ub1536-gqa8 2:1792:1792:ub1792-gqa8 3:1920:1920:ub1920-gqa8' \
CANARY_REPEATS=32 MAX_TOKENS=512 BASE_PORT=18620 \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-short-decode-guard.sh
```

Artifact:
`data/gemma4-short-decode-guard-20260630Tfattn-gqa8-midubatch-shortguard-A.json`

All lanes passed the fixed realistic gate, canary, and `cached_tokens=0`.

| UB | Median tok/s 1-100 after TTFT | p10 | Full 512-token tok/s | Decision |
| ---: | ---: | ---: | ---: | --- |
| 1280 | 118.73 | 108.53 | 113.43 | best middle compromise, but below record |
| 1536 | 115.16 | 105.46 | 111.89 | reject |
| 1792 | 117.13 | 108.14 | 112.10 | reject |
| 1920 | 112.38 | 105.06 | 111.21 | reject |

## Decision

Do not promote a middle ubatch as the default short+long recipe.

`UBATCH_SIZE=1280` is the most balanced middle setting, giving about `+3.8%`
long-prefill median over UB1024, but it does not preserve the short decode
record (`118.73` vs `123.68` tok/s). For strict "do not lower decode at all",
keep the short record recipe unchanged.

Recommended split:

- short-decode headline / no-regression lane: keep the current UB1024 record
  recipe;
- balanced long-prefill service lane: UB2048 with GQA8;
- pure long-prefill service lane: UB2304 with GQA8.
