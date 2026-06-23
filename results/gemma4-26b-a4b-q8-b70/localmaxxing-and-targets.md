# Gemma 4 26B A4B LocalMaxxing Targets

Research snapshot: 2026-06-23.

This page separates public leaderboard context from this lane's promoted result
rules. The goal is a valid Q8 / INT8-or-better result on Intel Arc Pro B70, not
a speed-only lower-precision entry.

## Public Target Context

Current public pages are useful as a speed target, but not as direct
quality-equivalent comparisons:

| Page | Current public top context | Why it is not directly comparable |
| --- | ---: | --- |
| `google/gemma-4-26B-A4B-it` | about `87.3 tok/s` | Rows include mixed engines, hardware, and quantization such as MXFP4/Q4. |
| `unsloth/gemma-4-26B-A4B-it-GGUF` | about `94.3 tok/s` | GGUF page, but public top rows are still mixed precision/hardware. |
| `Jackrong/Gemopus-4-26B-A4B-it-GGUF` | about `94.5 tok/s` | Fine-tune, useful idea source only; not the same checkpoint. |

Interpretation for this lane:

- A single-B70 Q8 result near or above `90 tok/s` would already be interesting.
- A lower number can still be worth keeping if it is the first validated Q8 B70
  baseline.
- Do not compare a Q8/INT8 result against MXFP4/Q4 entries as if the quality
  lane were identical.

Current local Q8 baseline:

- `20260623T052850Z`, llama.cpp SYCL on one B70, UD-Q8_K_XL, f16 KV, 8K context;
- chat canary 128/128 pass;
- p512/o512 chat decode `26.10 tok/s` after TTFT, `24.24 tok/s` wall;
- status: keep as a control and **do not submit** as a record unless a
  baseline-only reference entry is explicitly desired. It is far below the
  public Gemma 4 family context and should be improved first.

Current promoted local Q8 best:

- `gemma4-q8-gpu2-syclopt0-faoff-parallel1-cache0-deep-20260623T0915`,
  llama.cpp SYCL on one B70,
  UD-Q8_K_XL, f16 KV, 8K context;
- `GGML_SYCL_DISABLE_OPT=0`, `FLASH_ATTN=off`, `POLL=50`,
  `--parallel 1 --cache-ram 0`, `REASONING=off`;
- chat canary **384/384** pass;
- benchmark requested `max_tokens=512`, but actual completions averaged
  `146.4` tokens because the model stopped naturally;
- p512/o512 chat decode `42.15 tok/s` after TTFT, `36.41 tok/s` wall;
- status: submitted to LocalMaxxing and approved as
  `cmqq9nqbh010gqo01a9jnzl6r`;
- queue: `data/localmaxxing-gemma4-26b-a4b-q8-b70-syclopt0-faoff-parallel1-cache0-20260623.queue.json`;
- prior approved result: `41.81 tok/s`, LocalMaxxing ID
  `cmqq8phxt0103qo01afcgyjq8`.

Current sustained-decode Q8 best:

- `gemma4-q8-gpu0-currentbest-longprompt-deep-20260623T0945`,
  llama.cpp SYCL on one B70, same runtime identity as the promoted
  `parallel1-cache0` record;
- `BENCH_PROMPT_MODE=long`, which is a short instruction designed to prevent
  early stopping, not a true 512-token prompt fill;
- actual LocalMaxxing packet shape: `75` prompt tokens and `512` output tokens;
- chat canary **384/384** pass;
- decode `42.72 tok/s` after TTFT, `41.35 tok/s` wall;
- status: submitted to LocalMaxxing and approved as
  `cmqqa6zbx010xqo01cdtfn8e0`; this is a separate sustained-decode shape, not a
  direct replacement for the natural-stop/default-prompt row;
- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-long512-20260623.queue.json`.

Current draft-MTP sustained-decode Q8 best:

- `gemma4-q8-gpu3-mtp-n3-aot-bmg-long-deep-20260623T0345`,
  llama.cpp SYCL on one B70,
  UD-Q8_K_XL main GGUF plus `mtp-gemma-4-26B-A4B-it.gguf` draft GGUF;
- `--spec-type draft-mtp --spec-draft-n-max 3`, draft KV `f16/f16`,
  AOT BMG build (`GGML_SYCL_DEVICE_ARCH=bmg-g31`),
  `GGML_SYCL_DISABLE_OPT=0`, `FLASH_ATTN=off`, `POLL=50`,
  `--parallel 1 --cache-ram 0`, `REASONING=off`;
- actual LocalMaxxing packet shape: `75` prompt tokens and `512` output tokens;
- chat canary **384/384** pass;
- decode `47.92 tok/s` after TTFT, `46.18 tok/s` wall;
- status: submitted to LocalMaxxing and approved as
  `cmqqcje2r014fqo01e8rrgwwr`;
- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-mtp-n3-aot-bmg-long512-20260623.queue.json`.

Previous draft-MTP approved result:

- `gemma4-q8-gpu1-mtp-n3-long-deep-20260623T0328`, `46.36 tok/s` after TTFT,
  approved as `cmqqbyv5w013vqo019pmp161f`;
- `gemma4-q8-gpu0-mtp-n3-repeat-long-deep-20260623T0337`, `47.63 tok/s` after
  TTFT, approved as `cmqqc99m2014cqo01s5t61bs6`;
- `gemma4-q8-gpu1-mtp-n4-long-deep-20260623T1140`, `44.50 tok/s` after TTFT,
  approved as `cmqqblfw30132qo01jbi1svnu`.

## Submission Packet

LocalMaxxing requires at minimum:

- `hfId`;
- `hardware`;
- `engineName`;
- `quantization`;
- `tokSOut`;
- at least one secondary metric: `tokSPrefill`, `tokSTotal`, `ttftMs`, or
  `peakVramGb`.

Useful optional fields for this repo's records:

- `modelRevision`;
- `engineVersion`;
- `backend`;
- `promptTokens`;
- `outputTokens`;
- `contextLength`;
- `batchSize`;
- `engineFlags`;
- `notes`.

The API supports a dry-run endpoint before writing a real benchmark. The local
helper reads the key from `LMX_API_KEY` or
`/home/steve/.config/localmaxxing/api_key`; never put that key in a payload,
note, shell history snippet, or commit.

## Gemma 4 Payload Shape

For the primary GGUF lane:

```text
hfId: unsloth/gemma-4-26B-A4B-it-GGUF
modelRevision: 3bb10d594514ef4edb7f3a65d41a7e4eb8c5767a
engineName: llama.cpp
backend: sycl/xpu
quantization: UD-Q8_K_XL
hardware.hwClass: DISCRETE_GPU
hardware.gpuName: Intel Arc Pro B70
hardware.vramGb: 32
hardware.gpuCount: 1 for a single-replica record, 4 only for aggregate service records
```

Engine flags should include the command snippet and the relevant values from
the server log:

- llama.cpp commit;
- `CTX_SIZE`;
- `BATCH_SIZE`;
- `UBATCH_SIZE`;
- `CACHE_TYPE_K` / `CACHE_TYPE_V`;
- `GGML_SYCL_DISABLE_OPT`;
- `GGML_SYCL_DISABLE_GRAPH`;
- `GGML_SYCL_DISABLE_DNN`;
- `ONEAPI_DEVICE_SELECTOR`;
- `-fa` state;
- benchmark prompt mode and actual prompt/output token counts;
- MTP/spec flags if enabled.

## Do Not Submit If

- any chat canary fails;
- only raw `/v1/completions` was tested;
- `usage.completion_tokens` is missing and output token count was guessed;
- the result is Q6/Q4/MXFP4/NVFP4 but labeled as the Q8 lane;
- a speed win comes from a config family with unresolved nondeterministic
  failures;
- the model file, runtime commit, or launch identity is incomplete.

## Source Links

- LocalMaxxing API docs: <https://www.localmaxxing.com/en/api-docs>
- Google model page:
  <https://www.localmaxxing.com/en/models/google/gemma-4-26B-A4B-it>
- Unsloth GGUF model page:
  <https://localmaxxing.com/en/models/unsloth/gemma-4-26B-A4B-it-GGUF>
- LocalMaxxing CLI:
  <https://github.com/LottoLottoLotto/localmaxxing-cli>
