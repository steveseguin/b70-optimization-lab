# 2026-05-25 Stage A GPU-Resident Split-Attention Attempt

Goal: test the safest first vLLM runtime step toward CPU-paged attention:
force a request that already fits in GPU KV to split old/new attention and
merge partial results, with all KV still GPU-resident.

Short result: failed exactness. The standalone split-attention math is correct,
but naively forcing vLLM's existing cascade path for arbitrary single-sequence
decode on XPU FA2 is not equivalent to the normal attention path.

## Patch Tested

Patch artifact:

`patches/vllm-xpu-gpu-split-attn-stagea-failed-20260525.patch`

The patch added a disabled-by-default environment gate:

```bash
VLLM_XPU_GPU_SPLIT_ATTN=1
```

When enabled, the metadata builder forced `common_prefix_len` for
single-sequence XPU decode so the existing `cascade_attention()` path would
split the GPU-resident KV into a prefix and suffix, then merge with
`merge_attn_states()`.

The patch also changed the cascade call to pass `q_descale` only when
`self.supports_quant_query_input` is true. This mirrors the normal
non-cascade path.

## Baseline

Normal production-style server, no split env var:

```bash
VLLM_MAX_MODEL_LEN=32768 /home/steve/bin/minimax-vllm-serve
```

Canary:

```bash
session_cache_canary.py \
  --prompt-mode checklist \
  --prompt-lines 160 \
  --max-tokens 64 \
  --passes 1 \
  --concurrency 1 \
  --labels A
```

Result file:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/gpu-split-stagea-baseline-checklist-20260525T150019Z.json`

Result:

- prompt tokens: `3714`
- completion tokens: `64`
- elapsed: `3.425 s`
- TTFT: `2.725 s`
- output tok/s after TTFT: `91.44`
- hash: `5afda1f4fa37f3d3`
- text starts with: `The checklist should be written...`

## First Split Attempt

Temporary split server:

```bash
VLLM_XPU_GPU_SPLIT_ATTN=1 \
VLLM_MAX_MODEL_LEN=32768 \
/home/steve/bin/minimax-vllm-serve
```

Log:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/serve-32768-c1-gpu-split-stagea-20260525T150050Z.log`

Result:

- The first response only streamed `The`.
- The worker crashed and the server shut down.
- Error:

```text
NotImplementedError: FA2 does not support q_descale
```

The error came from the XPU FA2 flash-attention wrapper during the prefix
`cascade_attention()` call. The normal non-cascade path already avoids
`q_descale` unless quantized query input is supported, so the patch was updated
to do the same for cascade.

## Second Split Attempt After Q-Descale Fix

Temporary split server:

```bash
VLLM_XPU_GPU_SPLIT_ATTN=1 \
VLLM_MAX_MODEL_LEN=32768 \
/home/steve/bin/minimax-vllm-serve
```

Log:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/serve-32768-c1-gpu-split-stagea-qdescale-20260525T150424Z.log`

The log confirms the experimental path fired:

```text
VLLM_XPU_GPU_SPLIT_ATTN enabled: using GPU-resident cascade split for single-sequence XPU decode.
```

Result file:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/gpu-split-stagea-qdescale-checklist-20260525T150608Z.json`

Result:

- prompt tokens: `3714`
- completion tokens: `64`
- elapsed: `7.520 s`
- TTFT: `2.704 s`
- output tok/s after TTFT: `13.29`
- hash: `2fb45f78a286e529`
- text starts with: `Output the checklist only.\n</think>exact_kv...`
- baseline hash match: false
- baseline first-word match: false

Interpretation: the q-descale fix removes the hard crash, but the forced
cascade split is not semantically equivalent on this stack and is much slower.
Do not use this path for quality-preserving context overflow.

## Current Interpretation

The standalone math probe passed, so log-sum-exp merging itself is not the
problem. The failed vLLM shortcut is likely one or more of:

- XPU FA2 cascade metadata is not equivalent to arbitrary per-sequence decode
  splitting.
- The suffix block-table slice and causal alignment do not match the normal
  full block-table call.
- AOT scheduler metadata generated for cascade has assumptions that do not hold
  for this forced split.
- The existing cascade path is intended for shared-prefix batching, not a
  general paged-attention staging mechanism.

## Next Step

Do not keep pushing this cascade shortcut.

The next prototype should build an explicit experimental attention path:

1. Start in eager/no-graph if needed.
2. For a GPU-resident sequence that fits, call XPU FlashAttention over explicit
   prefix/suffix block tables and return LSE.
3. Compare logits/token output against the normal path.
4. Only after exactness passes, replace the prefix GPU block table with a
   staged scratch block table loaded from CPU KV.

This remains the most plausible no-quality-loss route to full active context,
but Stage A showed that the existing cascade machinery cannot simply be reused
as a drop-in split-attention implementation.

## Restore

After the failed split tests, the stable server was restored without
`VLLM_XPU_GPU_SPLIT_ATTN`:

```bash
VLLM_MAX_MODEL_LEN=32768 /home/steve/bin/minimax-vllm-serve
```

`/v1/models` again reported:

```json
{"max_model_len": 32768}
```
