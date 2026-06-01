# 2026-06-01 Decode Improvement Pass

Goal: look for quality-preserving REAP decode improvements after the
`89.49922316987691 output tok/s` pidfd result.

## Tooling Changes

- Added `scripts/profile-decode.sh` for short p512/n256 timing runs with:
  - `VLLM_XPU_DECODE_TIMING=1`
  - `VLLM_XPU_DECODE_TIMING_RANK=0`
  - `VLLM_XPU_DECODE_TIMING_SKIP_FIRST=16`
  - `VLLM_XPU_DECODE_TIMING_SYNC=0`
- Added `scripts/summarize-timing.py` to extract timing summary rows from logs.
- Extended the REAP benchmark wrapper to preserve more MiniMax/vLLM override
  variables after sourcing the promoted non-REAP env.
- Extended the shared MiniMax benchmark log header to print those extra knobs.

## Important Cache Finding

Do not instrument active source files in the promoted cache root unless the cache
root has already been copied aside. A temporary timing instrumentation pass
caused vLLM to recompile and overwrite the AOT artifact in:

`/mnt/fast-ai/vllm-cache-exp/minimax-m27-reap-autoround-no-logits-ws-20260531`

After that recompile, the same conservative no-logits-WS path direct-loads but
runs around `85.6-85.9 output tok/s` instead of the archived `89.5 output tok/s`.
The runtime source hashes in the old and new logs are identical, so the
regression appears to be an AOT/cache artifact rather than an intentional source
change.

The archived best remains valid:

- log:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260531T232017Z.log`
- output throughput: `89.49922316987691 tok/s`
- LocalMaxxing ID: `cmpuesbma00r5mq01yk0zdcjx`

## Baseline After Cache Rebuild

Conservative no-logits-WS path, same settings as the archived best:

- `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T010610Z.log`
- output throughput: `85.76 tok/s`
- AOT direct-loaded after rebuild.

This is not promoted. It is a warning that cache state is now part of the
performance artifact.

## Screens Run

All runs used greedy p512/n1536 unless noted.

- `VLLM_MINIMAX_M2_ATTN_DELAY_ALLREDUCE=1`
  - cache: `/mnt/fast-ai/vllm-cache-exp/minimax-m27-reap-attndelay-20260601`
  - warm log:
    `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T011515Z.log`
  - output throughput: about `85.7 tok/s`
  - decision: reject, no improvement

- `VLLM_MINIMAX_MOE_DELAY_ALLREDUCE=1`
  - cache: `/mnt/fast-ai/vllm-cache-exp/minimax-m27-reap-moedelay-20260601`
  - warm log:
    `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T012115Z.log`
  - output throughput: about `85.4 tok/s`
  - decision: reject

- `MAX_BATCHED_TOKENS=1024`
  - cache:
    `/mnt/fast-ai/vllm-cache-exp/minimax-m27-reap-mbt1024-retest-20260601`
  - warm log:
    `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T012815Z.log`
  - output throughput: about `80.3 tok/s`
  - decision: reject

- `VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS_WS=1`
  - cache:
    `/mnt/fast-ai/vllm-cache-exp/minimax-m27-reap-logitsws-retest-20260601`
  - warm log:
    `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T013429Z.log`
  - output throughput: about `87.3 tok/s`
  - decision: faster than the rebuilt conservative cache, still below archived
    best

- `VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS_WS=1`
  plus `VLLM_XPU_LLM_SCALER_MOE_MINIMAX_SKIP_REDUNDANT_CONTIGUOUS=1`
  - cache:
    `/mnt/fast-ai/vllm-cache-exp/minimax-m27-reap-logitsws-skipcontig-20260601`
  - warm log:
    `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T014032Z.log`
  - output throughput: about `87.0 tok/s`
  - decision: reject

- `VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS_WS=1`
  plus `VLLM_XPU_LLM_SCALER_MOE_CACHE_MINIMAX_LOGITS_OP=1`
  - cache:
    `/mnt/fast-ai/vllm-cache-exp/minimax-m27-reap-logitsws-cacheop-20260601`
  - warm log:
    `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T014704Z.log`
  - output throughput: about `87.3 tok/s`
  - quality smoke failed during engine startup with:
    `'MiniMaxText01RMSNormTP' object has no attribute '_minimax_clean_weight_xpu'`
  - decision: reject for promotion until the cache/AOT mismatch is resolved

## Interpretation

The easy math-equivalent scheduling knobs did not produce a meaningful speedup.
The only positive direction remains the E=192 MiniMax logits WS path, but it is
still below the archived best and has cache/quality-gate fragility.

Next real work should be source-level:

- make the E=192 logits WS path compile cleanly from a fresh cache and pass the
  quality smoke
- copy/cache-freeze any record-class AOT root before instrumentation
- add a cache fingerprint to benchmark notes: source hashes, cache root, AOT
  file sizes, and AOT mtimes
- profile kernel-level work inside the logits WS path rather than doing more
  high-level env sweeps
