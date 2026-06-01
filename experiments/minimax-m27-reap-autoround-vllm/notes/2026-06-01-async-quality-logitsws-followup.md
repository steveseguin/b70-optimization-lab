# 2026-06-01 Async Quality and Logits-WS Follow-up

Goal: respond to the `82.7078` endpoint result being worse than the archived
REAP throughput by separating throughput-only caches from quality-valid caches.

## New Harness

Added `scripts/async-quality-smoke.py`, a small async-engine quality smoke that
uses the same `build_async_engine_client_from_engine_args` path as the direct
async benchmarks. This catches cases where `vllm bench throughput` reports good
token rates but generated text is corrupt.

The sync `LLM(...)` quality harness is still useful, but it can fail before the
first prompt when a stale AOT graph expects MiniMax q/k clean-weight module
attributes. The async harness lets us test the actual fast async path directly.

## Findings

Preserved fast `f728d2c0cf` cache:

- Decode control:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T134739Z.log`
- Result: `118.61 total tok/s`, `88.96 output tok/s`
- Async quality:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-f728-fast-20260601T135246Z.json`
- Result: fail, all generated tokens are id `0`

Conclusion: the preserved fast cache is not quality-valid for the async/server
path even though it still measures near the old record in throughput-only runs.

Existing logits-WS fast cache (`4258951ecd`):

- Async quality:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-logitsws-425895-20260601T135551Z.json`
- Result: fail, all generated tokens are id `0`

Conclusion: reject the old `~87.3 output tok/s` logits-WS result unless/until
the same settings can pass a quality smoke.

Fresh logits-WS, restore off, attention-delay on:

- Cache root:
  `/mnt/fast-ai/vllm-cache-exp/minimax-m27-reap-logitsws-qualitysafe-20260601T1358`
- Async quality:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-logitsws-qualitysafe-20260601T135722Z.json`
- Quality result: pass, no NUL/control output
- Decode:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T140120Z.log`
- Decode result: `108.34 total tok/s`, `81.26 output tok/s`

Fresh logits-WS, restore off, attention-delay off:

- Cache root:
  `/mnt/fast-ai/vllm-cache-exp/minimax-m27-reap-logitsws-restore0-attndelay0-20260601T1403`
- Async quality:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-logitsws-restore0-attndelay0-20260601T140312Z.json`
- Quality result: pass, no NUL/control output
- Decode:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T140720Z.log`
- Decode result: `107.86 total tok/s`, `80.89 output tok/s`

Conclusion: quality-safe logits-WS is currently slower than the OpenAI qk-helper
serve lane, so do not promote it.

## Current Best Quality-Preserving State

The best current quality-preserving OpenAI endpoint result remains qk-helper
with restore-weight disabled:

- Baseline qk-helper:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/openai-endpoint-qkhelper1-graph-p512n1536-r2-20260601T051723Z.json`,
  `82.6854 output tok/s`
- Optional stream cadence screen:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/openai-endpoint-qkhelper1-streamint8-graph-p512n1536-r2-20260601T053846Z.json`,
  corrected `82.7078 output tok/s`

`82.7078` is not an improvement over the archived throughput-only record; it is
only the best small endpoint-cadence screen so far.

## Next Work

- Do not optimize against throughput-only caches unless the async quality smoke
  passes.
- The main quality/speed gap is still the restore-weight/QK-norm path: restore
  enabled or stale restore-weight AOT can be fast, but it produces NaN/NUL
  output on async/server quality.
- Next source-level target should be a restore-weight-safe q/k RMSNorm path that
  avoids changing the hot graph shape enough to lose AOT performance.
- After any source change, require: async quality pass, OpenAI quality pass,
  warmed p512/n1536 benchmark, and cache/AOT fingerprint in notes.
