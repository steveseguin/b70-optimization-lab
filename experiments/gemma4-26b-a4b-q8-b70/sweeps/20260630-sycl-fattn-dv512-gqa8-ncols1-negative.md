# Gemma 4 26B Q8 B70: DV512/GQA8 `ncols1` Forced Tile Width

Date: 2026-06-30

Status: negative for the current long-prefill lane. Preserve as a diagnostic
patch, but keep the existing implicit `ncols1=2` selector that is reached by
the validated `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8` service/prefill patch.

## Question

After the Gemma full-attention `DV=512` / GQA8 patch showed a large prefill win
by forcing `ncols2=8`, test whether the remaining `ncols1` selector should also
be forced for this shape.

The source patch is layered on top of
`20260630-sycl-fattn-dv512-gqa8-ncols2.patch` and adds a default-off diagnostic
knob:

```bash
GGML_SYCL_FATTN_DV512_GQA8_NCOLS1=1
GGML_SYCL_FATTN_DV512_GQA8_NCOLS1=4
```

Unset behavior remains the current GQA8 path, which selects `ncols1=2`.

Patch artifacts:

- `patches/gemma4-26b-a4b-q8-b70/20260630-sycl-fattn-dv512-gqa8-ncols1-negative.patch`
- `patches/gemma4-26b-a4b-q8-b70/20260630-sycl-fattn-dv512-gqa8-ncols1-negative.diffstat`

## Validation

Four-lane cold long-context diagnostic, one request per lane:

- model: Gemma 4 26B A4B it `UD-Q8_K_XL` target/verifier
- runtime: llama.cpp `c926ad098` plus local Gemma/B70 patches
- hardware: one B70 per lane
- context: `CTX_SIZE=32768`, `FLASH_ATTN=on`
- lane shape: `BATCH_SIZE=2048`, `UBATCH_SIZE=2048`
- suite case: `lc-22000-middle`
- actual prompt tokens: `30400`
- generation: `MAX_TOKENS=96`
- required validity: exact JSON retrieval pass, canary pass, `cached_tokens=0`
- common env: `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`

Command shape:

```bash
cd /home/steve/qwen36-results-main
COMMON_ENV=(
  LONG_CONTEXT_CASE_IDS='lc-22000-middle'
  LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS=24000
  CANARY_REPEATS=1
  MAX_TOKENS=96
  READINESS_TIMEOUT_S=900
  GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8
)

env "${COMMON_ENV[@]}" BASE_PORT=18530 \
  STAMP=20260630Tfattn-gqa8-ncols1-controlA \
  LANE_SPECS='0:2048:2048:ub2048-gqa8-controlA' \
  repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh

env "${COMMON_ENV[@]}" GGML_SYCL_FATTN_DV512_GQA8_NCOLS1=1 BASE_PORT=18531 \
  STAMP=20260630Tfattn-gqa8-ncols1-oneA \
  LANE_SPECS='1:2048:2048:ub2048-gqa8-ncols1' \
  repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh

env "${COMMON_ENV[@]}" GGML_SYCL_FATTN_DV512_GQA8_NCOLS1=4 BASE_PORT=18532 \
  STAMP=20260630Tfattn-gqa8-ncols1-fourA \
  LANE_SPECS='2:2048:2048:ub2048-gqa8-ncols4' \
  repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh

env "${COMMON_ENV[@]}" BASE_PORT=18533 \
  STAMP=20260630Tfattn-gqa8-ncols1-controlB \
  LANE_SPECS='3:2048:2048:ub2048-gqa8-controlB' \
  repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh
```

The actual run launched the four lanes concurrently.

## Result

| Lane | GPU | `ncols1` | Prefill tok/s | Decode tok/s | TTFT s | Valid |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `20260630Tfattn-gqa8-ncols1-controlA` | 0 | default `2` | `953.0630` | `113.5131` | `31.8972` | yes |
| `20260630Tfattn-gqa8-ncols1-controlB` | 3 | default `2` | `950.5813` | `112.9802` | `31.9804` | yes |
| `20260630Tfattn-gqa8-ncols1-oneA` | 1 | forced `1` | `821.6392` | `101.8506` | `36.9992` | yes |
| `20260630Tfattn-gqa8-ncols1-fourA` | 2 | forced `4` | `856.8965` | `109.3550` | `35.4769` | yes |

All lanes produced the same output hash:

```text
a2c9ffd867b906c1f59e57e7b647e91bae0909b04f7f8de3883c6fae77dfdf72
```

Aggregate summaries:

- `data/gemma4-long-context-service-gate-20260630Tfattn-gqa8-ncols1-controlA.json`
- `data/gemma4-long-context-service-gate-20260630Tfattn-gqa8-ncols1-controlB.json`
- `data/gemma4-long-context-service-gate-20260630Tfattn-gqa8-ncols1-oneA.json`
- `data/gemma4-long-context-service-gate-20260630Tfattn-gqa8-ncols1-fourA.json`

Raw per-lane output folders and driver logs are also tracked because they are
small and include the exact server stdout, model response, and canary payloads:

- `data/gemma4-q8-gpu0-longctx-ub2048-gqa8-controlA-ctx32768-o96-20260630Tfattn-gqa8-ncols1-controlA/`
- `data/gemma4-q8-gpu1-longctx-ub2048-gqa8-ncols1-ctx32768-o96-20260630Tfattn-gqa8-ncols1-oneA/`
- `data/gemma4-q8-gpu2-longctx-ub2048-gqa8-ncols4-ctx32768-o96-20260630Tfattn-gqa8-ncols1-fourA/`
- `data/gemma4-q8-gpu3-longctx-ub2048-gqa8-controlB-ctx32768-o96-20260630Tfattn-gqa8-ncols1-controlB/`
- matching `.driver.log` files beside those folders.

## Decision

Reject both forced `ncols1` variants:

- forced `ncols1=1` regressed prefill by about `13.7%` versus the paired
  control mean;
- forced `ncols1=4` regressed prefill by about `10.0%` versus the paired
  control mean;
- decode also moved lower in both forced lanes.

Keep `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8` as the useful service/prefill patch,
but do not force `GGML_SYCL_FATTN_DV512_GQA8_NCOLS1`. The current selector's
implicit `ncols1=2` is locally best for this Gemma long-prefill shape.

No LocalMaxxing submission: this is a service/prefill diagnostic, not a
fresh-response short-decode headline result.
