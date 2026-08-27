# Qwen3.8 Flash-Next TP4 MTP0 1,536-token-cap preregistration

Date: 2026-08-27

## Purpose

Add one context-depth classification without modifying or replacing the
attempt-19 512-token research baseline. This arm tests the same exact
production source and runtime at a configured maximum of 1,536 tokens, then
exercises approximately 1K active context.

## Frozen identity

- Official FP8 child artifact at
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`.
- vLLM `658965050f259999e635b52a850004a3771cd644`.
- XPU kernels `2f829747503c77d4814834dffd0840fb1dd9f75a`.
- Runtime stage
  `/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70`.
- TP4 + EP4, eager, graph off, MTP0, text-only, automatic KV precision,
  prefix caching off, diagnostics absent.
- Selective UVA placement and 12.25-GiB allowance unchanged.
- `max_num_batched_tokens=64`, 192-MiB KV allocation, and `BLHNC` unchanged.
- Only `max_model_len` changes from 512 to 1,536.

Attempt 19 already reported capacity for 1,536 cache tokens under the same
192-MiB allocation. The new launcher entry point wraps the existing launcher;
the original path still defaults to 512, and both modes fail closed on every
source, runtime, model, host, and cache identity gate.

## Ordered run

1. Require the healthy API, all four exact 12.22-GiB offload receipts, and at
   least 1,536 cache tokens in the server log.
2. Run the short exact battery plus 16 repeats and a 1K needle with thinking
   disabled and unique request IDs.
3. If the context/quality gate is usable, run the fixed realistic suite and
   three unique exact-1K, 256-output-token, concurrency-one samples.
4. Stop through the launcher's bounded process-group cleanup and retain all
   logs, requests, responses, hashes, token counts, and cache-zero values.

## Interpretation and stop rules

Any identity mismatch, capacity below 1,536, missing offload receipt, unhealthy
server, nonzero cached-token value, failed 1K needle, repeat divergence, or
realistic-quality failure blocks promotion. A bounded failure still classifies
the matrix cell and must be preserved; it does not lower or overwrite the 512
result. Do not enable MTP or graph, increase cache, change binaries, or alter
the selective placement within this arm.

## Pre-request suite seal

The independent launcher audit completed after model loading began but before
the API became healthy or any model request was sent. It found the launcher
identity unchanged except for the intended length/campaign selector and noted
that the realistic suite path needed an explicit seal. The fixed suite is:

- `repro/gemma4-26b-a4b-q8-b70/realistic-suite-v1.json`, SHA-256
  `cdf65eae1b63d39fdca0ae320a91535c3108a6c0bb60c337bf7a060d83f3990c`;
- 12 prompts with IDs from `incident-retrospective` through `decision-memo`;
- harness `scripts/bench-openai-realistic-suite.py`, SHA-256
  `911fcd172cb3b4d2a319e34cc6ba6ca41ee7c352fcd269e93008371e45cc4fb2`;
- chat mode, 512 maximum output tokens, 100 metric tokens, seed 20260609,
  returned token IDs, thinking disabled, and no natural-EOS requirement.

The short/needle harness is
`scripts/qwen38-text-quality-suite.py` at SHA-256
`67e65fc342393e5ae6903a332c929b3a2693e1f943c8a819b8447284fe835f6d`.
The later exact-depth timing harness is
`scripts/bench-openai-concurrency.py` at SHA-256
`0703d8f0564cab625183a02f010d238c8456d2e9e6aac04f4b8e11f81c8d6ae0`.

## Result

The arm completed as a valid research context screen. The server reported the
configured 1,536-token maximum, 3,949 cache tokens, and 2.57× maximum
concurrency at that request length. All four ranks retained the exact
12.22-GiB selective placement and 31.27-GiB model footprint.

The valid quality invocation reproduced the known 5/7 short strict result,
but improved the repeat evidence to 16/16 one hash and passed the exact needle
at 987 actual prompt tokens. All 24 quality requests were cache-zero. The first
quality invocation is retained as an invalid harness-environment attempt: it
used system Python, sent only the short requests, then stopped before the
needle or JSON write because the tokenizer dependency was absent. The server
remained healthy and the valid rerun used a new request prefix.

The sealed 12-prompt realistic suite passed its formal validity gate: unique
cold prompts, zero cached tokens, 512 returned token IDs per row, and known
length finish reasons. Its conventional 99-interval median was
`4.449168445 tok/s`; full-output after-first-text median was `4.569059754
tok/s`, and median TTFT was `3944.517 ms`. The suite retains free-form outputs
but does not itself grade their semantic quality.

Three unique exact-1,024-prompt-token, 256-output-token samples measured
`5.153794241`, `5.133587561`, and `5.051270051 tok/s` after first text, for a
median of `5.133587561 tok/s`. Median TTFT was `29.043115 s`. That harness did
not retain cached-token detail, so no cache-zero claim is made for those three
rows; prompt salts were unique and prefix caching remained disabled.

All four workers logged shutdown completion. At the five-second shutdown
limit the manager force-ended the remaining engine process, whose executor
still listed three workers; the API handler then repeated the known
post-manager-stop message and the resource tracker reported one cleanup item.
No process remained. Shutdown is therefore classified as controlled with an
API-observability caveat. The compact receipt is
`data/20260827-tp4-mtp0-1536-context-screen.json`.

The 1K context and repeat gates pass, but the inherited substantive `30`/`14`
short-quality miss remains. This cell is `lab-screened`, research-only, and not
promotion-eligible. It does not alter the attempt-19 512 result.
