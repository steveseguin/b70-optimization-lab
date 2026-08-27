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
