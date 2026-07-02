# 2026-07-02 Post-Cleanup Baseline and SWA Left-Bound Service Confirmation

Status: valid post-cleanup diagnostics and service/prefill confirmation. No LocalMaxxing submission; this does not beat the short-decode headline record.

## Purpose

After consolidating the workspace back to a single active `main` checkout, re-establish today's Gemma 4 26B Q8 runtime state and verify the prompt-processing service recipe without using warmed/cache/history acceleration.

Quality and validity constraints were unchanged:

- target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft for MTP lanes: Q4_0 MTP draft, target-verified accepted tokens;
- fixed realistic suite for short decode, each prompt once, `cached_tokens=0`;
- fixed long-context JSON retrieval suite for service lanes, exact validation and `cached_tokens=0`;
- one B70 per lane, four lanes in parallel.

Aggregate evidence: `data/gemma4-postclean-baseline-swalb-service-confirm-20260702.json`.

## Exact Record Recipe Baseline

Command shape: four lanes of `run-vdr2-short-decode-guard.sh` with `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`, `CTX_SIZE=32768`, `FLASH_ATTN=on`, `GGML_SYCL_ENABLE_VMM=1`, full512 output.

All four lanes passed the fixed realistic gate, canary, and `cached_tokens=0`.

| GPU | median tok/s 1-100 | p10 | mean | full512 | TTFT ms | label |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0 | `111.392523` | `103.911368` | `114.486012` | `108.843225` | `178.288` | `gemma4-q8-gpu0-shortguard-baseline-a-ctx32768-o512-20260702Tbaseline-020014Z` |
| 1 | `118.583248` | `105.002838` | `117.300942` | `109.140109` | `178.515` | `gemma4-q8-gpu1-shortguard-baseline-b-ctx32768-o512-20260702Tbaseline-020014Z` |
| 2 | `111.248304` | `108.250400` | `114.851767` | `109.895999` | `179.111` | `gemma4-q8-gpu2-shortguard-baseline-c-ctx32768-o512-20260702Tbaseline-020014Z` |
| 3 | `116.706674` | `104.743728` | `117.176029` | `110.867467` | `179.914` | `gemma4-q8-gpu3-shortguard-baseline-d-ctx32768-o512-20260702Tbaseline-020014Z` |

Average lane median: `114.482687` tok/s. Range: `111.248304` - `118.583248`. The historical `124.977` row remains valid, but did not reproduce in this window; this is normal MTP variance and not a regression by itself.

## No-Spec Calibration

Command shape: four lanes of `run-vdr2-nospec-calibration.sh`, full512 output. This disables speculative decoding and cache/history acceleration so target-side changes have a low-variance comparator.

All four lanes passed the fixed realistic gate, canary, and `cached_tokens=0`.

| GPU | median tok/s 1-100 | p10 | mean | full512 | TTFT ms | label |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0 | `76.895850` | `76.856111` | `76.885424` | `75.468541` | `179.402` | `gemma4-q8-gpu0-nospec-calib-postclean-full512-20260702Tnospec-020259Z` |
| 1 | `76.768259` | `76.661949` | `76.749911` | `75.348965` | `179.746` | `gemma4-q8-gpu1-nospec-calib-postclean-full512-20260702Tnospec-020259Z` |
| 2 | `76.911699` | `76.833032` | `76.892432` | `75.513208` | `180.223` | `gemma4-q8-gpu2-nospec-calib-postclean-full512-20260702Tnospec-020259Z` |
| 3 | `76.639535` | `76.597772` | `76.647297` | `75.291258` | `179.263` | `gemma4-q8-gpu3-nospec-calib-postclean-full512-20260702Tnospec-020259Z` |

Average lane median: `76.803836` tok/s; range only `76.639535` - `76.911699` (`0.35%` spread). Use this as today's reliable target-side comparator.

## SWA Left-Bound Long-Context Service A/B

Recipe under test:

```bash
BATCH_SIZE=2048
UBATCH_SIZE=1024
LLAMA_PREFILL_UBATCH_SIZE=2048
GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8
LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND=1
LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_MIN_Q=2048
```

Cases: `lc-12288-early`, `lc-16384-late`, `lc-22000-middle`; `MAX_TOKENS=96`; exact JSON validation.

All lanes passed canary, exact long-context gate, prompt uniqueness, and `cached_tokens=0`.

Combined control prefill average: `1050.425206` tok/s. Combined SWA-left-bound prefill average: `1123.192732` tok/s. Delta: **`6.927%`**.

Combined control decode average: `119.488908` tok/s. Combined SWA-left-bound decode average: `119.922298` tok/s. Delta: `0.363%`.

| Round | Variant | GPU | prefill median | decode median | TTFT s | label |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 20260702Tswalb-long-ab1-020810Z | control | 0 | `1054.433478` | `119.523328` | `21.557` | `gemma4-q8-gpu0-longctx-control-phase2048-20260702Tswalb-long-ab1-020810Z` |
| 20260702Tswalb-long-ab1-020810Z | swalb | 1 | `1111.177300` | `119.680755` | `20.456` | `gemma4-q8-gpu1-longctx-swalb-phase2048-20260702Tswalb-long-ab1-020810Z` |
| 20260702Tswalb-long-ab1-020810Z | control | 2 | `1056.863163` | `119.440414` | `21.507` | `gemma4-q8-gpu2-longctx-control-phase2048-20260702Tswalb-long-ab1-020810Z` |
| 20260702Tswalb-long-ab1-020810Z | swalb | 3 | `1125.460894` | `119.891445` | `20.196` | `gemma4-q8-gpu3-longctx-swalb-phase2048-20260702Tswalb-long-ab1-020810Z` |
| 20260702Tswalb-long-xover1-021034Z | swalb | 0 | `1127.203036` | `120.108293` | `20.165` | `gemma4-q8-gpu0-longctx-swalb-phase2048-20260702Tswalb-long-xover1-021034Z` |
| 20260702Tswalb-long-xover1-021034Z | control | 1 | `1038.236503` | `119.258496` | `21.893` | `gemma4-q8-gpu1-longctx-control-phase2048-20260702Tswalb-long-xover1-021034Z` |
| 20260702Tswalb-long-xover1-021034Z | swalb | 2 | `1128.929697` | `120.008701` | `20.134` | `gemma4-q8-gpu2-longctx-swalb-phase2048-20260702Tswalb-long-xover1-021034Z` |
| 20260702Tswalb-long-xover1-021034Z | control | 3 | `1052.167680` | `119.733393` | `21.603` | `gemma4-q8-gpu3-longctx-control-phase2048-20260702Tswalb-long-xover1-021034Z` |

## Short-Decode Guard For Service Flag

The same SWA-left-bound `MIN_Q=2048` service flag was checked against the fixed realistic short suite with full512 output. All lanes passed canary, realistic gate, and `cached_tokens=0`.

Combined short metric control average: `117.884328` tok/s. Combined SWA-left-bound average: `118.146979` tok/s. Delta: `0.223%`.

Combined full512 control average: `109.851555` tok/s. Combined SWA-left-bound average: `111.129019` tok/s. Delta: `1.163%`.

This is inside normal MTP variance and does **not** justify a short-record claim. It is sufficient to say the service/prefill flag did not show a short-decode regression in this confirmation window.

| Round | Variant | GPU | median tok/s 1-100 | p10 | full512 | label |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 20260702Tswalb-shortguard-ab1-021304Z | control | 0 | `117.199911` | `107.987127` | `111.680971` | `gemma4-q8-gpu0-shortguard-control-swalb2048-20260702Tswalb-shortguard-ab1-021304Z` |
| 20260702Tswalb-shortguard-ab1-021304Z | swalb | 1 | `120.235944` | `105.550050` | `113.598810` | `gemma4-q8-gpu1-shortguard-swalb-swalb2048-20260702Tswalb-shortguard-ab1-021304Z` |
| 20260702Tswalb-shortguard-ab1-021304Z | control | 2 | `115.759720` | `101.767819` | `109.242569` | `gemma4-q8-gpu2-shortguard-control-swalb2048-20260702Tswalb-shortguard-ab1-021304Z` |
| 20260702Tswalb-shortguard-ab1-021304Z | swalb | 3 | `116.611809` | `107.775936` | `109.533116` | `gemma4-q8-gpu3-shortguard-swalb-swalb2048-20260702Tswalb-shortguard-ab1-021304Z` |
| 20260702Tswalb-shortguard-xover1-021535Z | swalb | 0 | `120.077513` | `105.854372` | `112.071886` | `gemma4-q8-gpu0-shortguard-swalb-swalb2048-20260702Tswalb-shortguard-xover1-021535Z` |
| 20260702Tswalb-shortguard-xover1-021535Z | control | 1 | `121.853333` | `100.408256` | `107.735223` | `gemma4-q8-gpu1-shortguard-control-swalb2048-20260702Tswalb-shortguard-xover1-021535Z` |
| 20260702Tswalb-shortguard-xover1-021535Z | swalb | 2 | `115.662649` | `105.189146` | `109.312263` | `gemma4-q8-gpu2-shortguard-swalb-swalb2048-20260702Tswalb-shortguard-xover1-021535Z` |
| 20260702Tswalb-shortguard-xover1-021535Z | control | 3 | `116.724347` | `107.334406` | `110.747458` | `gemma4-q8-gpu3-shortguard-control-swalb2048-20260702Tswalb-shortguard-xover1-021535Z` |

## Decision

- Keep the short-decode headline recipe unchanged: `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`, no service-only claims.
- Treat `LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND=1` with `MIN_Q=2048`, `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`, and phase-prefill `2048/1024` as the current validated long-context service/prefill recipe.
- Do not submit this as a LocalMaxxing short-decode record. It is a service/prompt-processing improvement.
- For new target-side code changes, use the no-spec calibration lane first; today's spread was tight enough to detect sub-1% target-side movement.
