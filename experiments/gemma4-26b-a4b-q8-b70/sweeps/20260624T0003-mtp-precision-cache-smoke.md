# 2026-06-24 00:03 - Gemma 4 26B Q8 MTP precision/cache smoke

Goal: check whether higher-precision MTP draft weights or lower-precision draft
KV cache improve the current fresh-response single-session record.

Current valid record for comparison:

- `gemma4-q8-gpu0-mtp-n7-c926-fastargmax-cpucleanup-vmm0-ub512-poll100-full-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-20260623T222838Z`
- canary: 384/384
- fresh-response headline: `92.397 tok/s after TTFT` for the first measured
  request (`cached_tokens=0`); supporting repeat mean `92.767 tok/s`
- target: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- draft: `mtp-gemma-4-26B-A4B-it.gguf`
- key settings: `MTP_N_MAX=7`, `MTP_N_MIN=2`, `MTP_P_MIN=0.12`,
  draft cache `f16/f16`, `--ctx-checkpoints 0`, `VMM=0`, `ubatch=512`,
  poll `100`, fast draft argmax enabled, no draft backend sampling.

Common smoke settings:

- source: `/home/steve/src/llama.cpp-latest-gemma`
- server: `build-sycl-b70-aot-bmg-g31/bin/llama-server`
- target model: `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- validation: 8 canary repeats / 32 rows
- throughput: one fresh filled-long 512-token decode, `cached_tokens=0`

| Label | Variant | Canary | Fresh tok/s after TTFT | Wall tok/s | Outcome |
| --- | --- | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-mtp-n7-f16mtp-f16kv-smoke2-20260624T0003Z` | F16 MTP draft, f16/f16 draft KV | 32/32 | 87.35 | 75.37 | valid but slower |
| `gemma4-q8-gpu1-mtp-n7-bf16mtp-f16kv-smoke2-20260624T0003Z` | BF16 MTP draft, f16/f16 draft KV | 32/32 | 88.62 | 76.15 | valid but slower |
| `gemma4-q8-gpu2-mtp-n7-q8mtp-draftkvq8-smoke2-20260624T0003Z` | Q8 MTP draft, q8_0/q8_0 draft KV | 32/32 | 41.14 | 38.25 | severe speed regression |
| `gemma4-q8-gpu3-mtp-n7-q8mtp-draftkvq4-smoke2-20260624T0003Z` | Q8 MTP draft, q4_0/q4_0 draft KV | 32/32 | 41.33 | 38.45 | severe speed regression |

There were earlier `20260623T2354Z` attempts with the same labels but without
`smoke2`; those are build/startup failures caused by a transient missing
`libggml-sycl.so.0.15.2` after an interrupted rebuild. Do not count them as
model benchmark results.

Interpretation:

- Higher-precision MTP draft weights did not improve acceptance/quality enough
  to beat the Q8 MTP draft path. They remain valid but are below the current
  record by about 4-6%.
- Draft KV quantization (`q8_0` or `q4_0`) is a dead end for this path on B70:
  it roughly halves decode throughput while preserving the simple canaries.
- Keep the current record stack: Q8 target + Q8 MTP draft, f16/f16 draft KV,
  fast argmax, no backend sampling, `MTP_N_MAX=7`, `n_min=2`, `p_min=0.12`.

Next action:

- Do not promote any precision/cache variant.
- Continue with code-level MTP throughput work. The >150 tok/s goal requires a
  structural improvement to speculative throughput, not a draft precision/KV
  knob.
