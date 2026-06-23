# 20260623T0715 Optimized SYCL Follow-Ups

## Goal

After `GGML_SYCL_DISABLE_OPT=0` produced the first major speed win, test
promotion-depth variants and MTP. Optimized SYCL is known-risky for Gemma 4 on
B70 from upstream reports, so promotion requires `96` chat canary repeats.

## Validated No-Spec Results

| Label | Change | Canary | p512/o512 tok/s after TTFT | Wall tok/s | Decision |
| --- | --- | --- | ---: | ---: | --- |
| `gemma4-q8-gpu3-syclopt0-deep-20260623T0645` | `GGML_SYCL_DISABLE_OPT=0`, `FLASH_ATTN=on`, `POLL=50` | 384/384 | `40.2412` | `36.5812` | first validated speed win |
| `gemma4-q8-gpu1-syclopt0-poll100-deep-20260623T0715` | `GGML_SYCL_DISABLE_OPT=0`, `FLASH_ATTN=on`, `POLL=100` | 384/384 | `40.6941` | `37.1094` | better wall/TTFT alternative |
| `gemma4-q8-gpu0-syclopt0-faoff-deep-20260623T0715` | `GGML_SYCL_DISABLE_OPT=0`, `FLASH_ATTN=off`, `POLL=50` | 384/384 | `41.8058` | `36.4375` | **current promoted after-TTFT decode best** |

`FLASH_ATTN=off` wins the target metric (single-session decode after TTFT), but
it has worse TTFT and wall throughput than the `POLL=100` alternative. Keep
both in mind if future work optimizes endpoint latency rather than steady
decode.

## Other Optimized-SYCL Smokes

| Label | Change | Canary | p512/o512 tok/s after TTFT | Decision |
| --- | --- | --- | ---: | --- |
| `gemma4-q8-gpu0-syclopt0-faoff-20260623T0700` | `FLASH_ATTN=off` | 128/128 | `41.8697` | deep-validated above |
| `gemma4-q8-gpu1-syclopt0-poll100-20260623T0700` | `POLL=100` | 128/128 | `40.7555` | deep-validated above |
| `gemma4-q8-gpu2-syclopt0-ub128-20260623T0700` | `UBATCH_SIZE=128` | 128/128 | `40.6866` | no win |
| `gemma4-q8-gpu1-syclopt0-poll25-20260623T0730` | `POLL=25` | 128/128 | `40.6533` | no win |
| `gemma4-q8-gpu2-syclopt0-disablegraph-20260623T0730` | `GGML_SYCL_DISABLE_GRAPH=1` | 128/128 | `40.5944` | no win |
| `gemma4-q8-gpu3-syclopt0-disablednn-20260623T0730` | `GGML_SYCL_DISABLE_DNN=1` | 128/128 | `40.5963` | no win |

## MTP Smokes

MTP draft downloaded:

```text
/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/mtp-gemma-4-26B-A4B-it.gguf
size: 461,766,816 bytes
```

First MTP smokes used the validated optimized-SYCL base with `POLL=100`,
`FLASH_ATTN=on`, f16 KV, and `REASONING=off`:

| Label | `--spec-draft-n-max` | Canary | p512/o512 tok/s after TTFT | Decision |
| --- | ---: | --- | ---: | --- |
| `gemma4-q8-gpu1-syclopt0-mtp2-20260623T0745` | 2 | 128/128 | `39.8290` | slower than no-spec |
| `gemma4-q8-gpu2-syclopt0-mtp4-20260623T0745` | 4 | 128/128 | `35.7714` | slower |
| `gemma4-q8-gpu3-syclopt0-mtp8-20260623T0745` | 8 | 128/128 | `17.6895` | much slower |

Decision: do not pursue MTP blindly on this llama.cpp/SYCL setup. It loads and
passes canaries, but draft verification overhead exceeds accepted-token benefit
for this prompt shape. Revisit only with acceptance counters or a different
prompt family known to benefit from MTP.

## LocalMaxxing

The promoted `syclopt0 + FLASH_ATTN=off` result is queued for submission at
`data/localmaxxing-gemma4-26b-a4b-q8-b70-syclopt0-faoff-20260623.queue.json`.
