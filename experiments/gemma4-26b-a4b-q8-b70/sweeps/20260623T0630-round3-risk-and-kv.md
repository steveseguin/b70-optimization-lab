# 20260623T0630 Round 3 Runtime Risk / KV Sweep

## Goal

Test the next bounded set after scheduler knobs were flat:

- `POLL=100`;
- `FLASH_ATTN=off`;
- q8 KV side lane;
- risky `GGML_SYCL_DISABLE_OPT=0` lane, guarded by the same 32-repeat chat
  canary because upstream reports Gemma 4/B70 nonsense output when optimized
  SYCL paths are enabled.

All lanes kept UD-Q8_K_XL weights and `REASONING=off`.

## Results

| Label | GPU | Change | Canary | p512/o512 tok/s after TTFT | Wall tok/s | Decision |
| --- | ---: | --- | --- | ---: | ---: | --- |
| `gemma4-q8-gpu0-poll100-20260623T0630` | 0 | `POLL=100` | 128/128 | `26.0269` | `24.5861` | no steady-decode win |
| `gemma4-q8-gpu1-faoff-20260623T0630` | 1 | `FLASH_ATTN=off` | 128/128 | `26.6036` | `23.6954` | small after-TTFT smoke win; repeat if optimized-SYCL fails |
| `gemma4-q8-gpu2-q8kv-20260623T0630` | 2 | `CACHE_TYPE_K=q8_0`, `CACHE_TYPE_V=q8_0` | 128/128 | `24.4285` | `22.8939` | slower; keep only for 32K memory headroom tests |
| `gemma4-q8-gpu3-syclopt0-20260623T0630` | 3 | `GGML_SYCL_DISABLE_OPT=0` | 128/128 | `40.7221` | `36.2933` | major speed smoke win; requires 96-repeat promotion because this flag is known risky |

## Decision

The new candidate is `GGML_SYCL_DISABLE_OPT=0`. It breaks the previous local
best by about `+56%` (`26.10 -> 40.72 tok/s`) while passing the 32-repeat smoke,
but it cannot be promoted from a smoke due the known upstream corruption report.
A promotion-depth run started as
`gemma4-q8-gpu3-syclopt0-deep-20260623T0645` with `CANARY_REPEATS=96` and
explicit f16-KV identity.

If optimized SYCL passes the deep gate, submit that as the first Gemma Q8
LocalMaxxing result. If it fails, keep `FLASH_ATTN=off` as the smaller valid
candidate and deep-repeat that instead.

## Artifacts

- `data/gemma4-q8-gpu0-poll100-20260623T0630/summary.json`
- `data/gemma4-q8-gpu1-faoff-20260623T0630/summary.json`
- `data/gemma4-q8-gpu2-q8kv-20260623T0630/summary.json`
- `data/gemma4-q8-gpu3-syclopt0-20260623T0630/summary.json`
