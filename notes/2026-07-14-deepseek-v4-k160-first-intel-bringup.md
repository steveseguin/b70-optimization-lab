# DeepSeek V4 Flash K160 first Intel TP4 bring-up

Date: **2026-07-14**

## Outcome

The frozen public K160 checkpoint now loads and generates correctly on four
Arc Pro B70 cards through the pinned native vLLM/XPU path. It does not pass the
performance investment gate.

The successful construction identity is TP4 plus explicit expert parallelism,
`allgather_reducescatter`, FP8 KV, 2K context, 95% device-memory utilization,
graph off, and no speculation. vLLM reported 40 of 160 experts per rank,
`XPUExpertsMxFp4`, about 24.95 GiB of model memory per rank, 2.11 GiB of KV
cache, and 5,925 cache tokens. The deterministic arithmetic canary returned
`1073` for `37 * 29`.

The warm diagnostic 128-token row reached only `2.616225 tok/s` after TTFT;
the preceding row reached `1.323304 tok/s` while remaining decode kernels were
being compiled. This is graph-off diagnostic evidence, not a quality or
production promotion. It is approximately 19 times below the 50 tok/s gate
that must be approached before speculation work begins.

## Why earlier attempts failed

- The original 8K/90% launch loaded all weights but reported `-1.28 GiB`
  available for KV blocks. Weight fit alone was not enough.
- Raising utilization to 98% failed before loading because only 29.09 of 30.3
  GiB was free while vLLM requested 29.69 GiB.
- The working point is 2K/95%. Context is deliberately small because the user
  prioritizes the smartest model that fits, not long context.
- The first promotion retry exposed two verifier bugs, not artifact faults:
  safetensors encoded `metadata.total_size` as a JSON string, and GNU `find`
  did not descend through the `current-k160` symlink. Both checks now normalize
  their inputs.

## Graph blocker

The supported non-eager XPU-graph attempt reached sparse-decode capture and
then failed consistently in
`vllm/models/deepseek_v4/xpu/xpu_sparse_decode_fp8.py`. The code computes
`int(combined_lens.max().item())` during graph capture. `.item()` forces a host
wait, and Level Zero raises:

```text
RuntimeError: wait method cannot be used for an event associated with a command graph.
```

This is the first high-value runtime fix. The dynamic maximum must be removed
from capture, bounded statically, or computed through a graph-safe device path.
Only after capture succeeds is it worth measuring graph replay and deciding
whether deeper MXFP4/EP kernel work can plausibly close the gap. Speculation is
still out of scope.

## Iteration improvements

The archive and hot copy were both fully SHA-256 verified. Repeated hot starts
now retain structural, tensor-map, and exact byte-count checks while skipping
the redundant 96 GiB hash read by default; `VERIFY_MANIFEST=1` restores it.
The first decode created a persistent 44 MiB compiler cache under
`/mnt/fast-ai/vllm-cache-exp`, and the launcher reuses it.

Structured summary:
[`../data/deepseek-v4-k160-tp4-bringup-20260714.json`](../data/deepseek-v4-k160-tp4-bringup-20260714.json).
