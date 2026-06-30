# Gemma 4 26B Q8 B70: DV512/GQA8 `nbatch_fa=128` Retune

Date: 2026-06-30

Status: negative / noise for the current long-prefill lane. Preserve the patch
and result, but keep the existing FP16 tile config
`GGML_SYCL_FATTN_TILE_CONFIG_CASE(576, 512, 16, 256, 2, 64, 64)`.

## Question

The validated service/prefill win for Gemma full-attention `DV=512` / GQA8
uses the default-off selector patch `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`. That
lands the hot near-32K prompt path on the FP16 tile config:

```cpp
GGML_SYCL_FATTN_TILE_CONFIG_CASE(576, 512, 16, 256, 2, 64, 64)
```

Node profiling showed the top prompt-processing nodes are full-attention
`FLASH_ATTN_EXT:__fattn__` layers, so test whether increasing the K/V token
chunk for that exact tile from `nbatch_fa=64` to `128` improves long-context
prefill without changing quantization, prompt cache behavior, or decode recipe.

Patch artifacts:

- `patches/gemma4-26b-a4b-q8-b70/20260630-sycl-fattn-dv512-gqa8-nbatchfa128-negative.patch`
- `patches/gemma4-26b-a4b-q8-b70/20260630-sycl-fattn-dv512-gqa8-nbatchfa128-negative.diffstat`

## Build

Built in `/home/steve/src/llama.cpp-gemma-record-repro-c926`:

```bash
source /opt/intel/oneapi/setvars.sh >/tmp/oneapi-setvars-gemma-nbatchfa128.log 2>&1 \
  || source /opt/intel/oneapi/setvars.sh --force >/tmp/oneapi-setvars-gemma-nbatchfa128.log 2>&1
cmake --build build-sycl-b70-aot-bmg-g31-q8reorder-vdr2 --target llama-server -j 8
```

The build completed. Non-fatal noise matched prior AOT builds: npm UI
`EBADENGINE`, IGC spill warnings, and a "Stack call has been detected" warning.

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

Command:

```bash
cd /home/steve/qwen36-results-main
GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8 \
LONG_CONTEXT_CASE_IDS='lc-22000-middle' \
LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS=24000 \
CANARY_REPEATS=1 \
MAX_TOKENS=96 \
READINESS_TIMEOUT_S=900 \
BASE_PORT=18530 \
STAMP=20260630Tfattn-gqa8-nbatchfa128-A \
LANE_SPECS='0:2048:2048:ub2048-gqa8-nbatchfa128-a 1:2048:2048:ub2048-gqa8-nbatchfa128-b 2:2048:2048:ub2048-gqa8-nbatchfa128-c 3:2048:2048:ub2048-gqa8-nbatchfa128-d' \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh
```

## Result

All lanes passed exact validation, canary, `cached_tokens=0`, and produced the
same output hash:

```text
a2c9ffd867b906c1f59e57e7b647e91bae0909b04f7f8de3883c6fae77dfdf72
```

| Lane | GPU | Prefill tok/s | Decode tok/s | TTFT s | Valid |
| --- | ---: | ---: | ---: | ---: | --- |
| `ub2048-gqa8-nbatchfa128-a` | 0 | `953.3767` | `113.3384` | `31.8867` | yes |
| `ub2048-gqa8-nbatchfa128-b` | 1 | `944.6846` | `112.6329` | `32.1801` | yes |
| `ub2048-gqa8-nbatchfa128-c` | 2 | `955.1166` | `113.2424` | `31.8286` | yes |
| `ub2048-gqa8-nbatchfa128-d` | 3 | `952.9311` | `113.2075` | `31.9016` | yes |

Aggregate:

- mean prefill: `951.5273 tok/s`
- per-lane prefill: `[953.3767, 944.6846, 955.1166, 952.9311]`
- mean decode after TTFT: `113.1053 tok/s`

Same-case controls around this run:

- forced-`ncols1` paired controls, implicit `ncols1=2`:
  `953.0630` and `950.5813 tok/s`
- KV-scan threshold control: `955.2365 tok/s`

Aggregate summary:

- `data/gemma4-long-context-service-gate-20260630Tfattn-gqa8-nbatchfa128-A.json`

Raw per-lane output folders and driver logs are also tracked:

- `data/gemma4-q8-gpu0-longctx-ub2048-gqa8-nbatchfa128-a-ctx32768-o96-20260630Tfattn-gqa8-nbatchfa128-A/`
- `data/gemma4-q8-gpu1-longctx-ub2048-gqa8-nbatchfa128-b-ctx32768-o96-20260630Tfattn-gqa8-nbatchfa128-A/`
- `data/gemma4-q8-gpu2-longctx-ub2048-gqa8-nbatchfa128-c-ctx32768-o96-20260630Tfattn-gqa8-nbatchfa128-A/`
- `data/gemma4-q8-gpu3-longctx-ub2048-gqa8-nbatchfa128-d-ctx32768-o96-20260630Tfattn-gqa8-nbatchfa128-A/`
- matching `.driver.log` files beside those folders.

## Decision

Reject the retune:

- the four-lane mean `951.5273 tok/s` is within noise of the recent controls;
- one lane fell to `944.6846 tok/s`, so there is no evidence of a robust
  prefill improvement;
- decode did not improve materially;
- the result is valid but does not beat the existing service recipe.

Keep the current tile config:

```cpp
GGML_SYCL_FATTN_TILE_CONFIG_CASE(576, 512, 16, 256, 2, 64, 64)
```

No LocalMaxxing submission: this is a service/prefill diagnostic, not a
fresh-response short-decode headline result.
