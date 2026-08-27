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
