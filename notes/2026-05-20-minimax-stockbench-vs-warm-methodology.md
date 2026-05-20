# MiniMax stock-bench versus warm-engine methodology

Date: 2026-05-20

## Question

The restored WS path passed quality and produced `87.964466` output tok/s in a
strict stock-bench repeat, while the warm in-process harness produced
`92.535653` output tok/s with synthetic token prompts. The goal was to explain
that gap without changing model math or weakening quality gates.

## Checks

### Stock `vllm bench throughput`, sync engine

- Path: `vllm bench throughput`, no `--async-engine`
- Prompt source: vLLM random dataset, text prompt
- Output detokenization: enabled
- Result JSON:
  `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/stockbench-sync-20260520T125706Z/vllm-minimax-m27-autoround-tp4-p512n1536-20260520T125706Z.json`
- Elapsed: `17.462174` s
- Total throughput: `117.282076` tok/s
- Output throughput: `87.961557` tok/s

This matches the strict source-rebuild recovery result.

### Stock `vllm bench throughput`, sync engine, no output detokenization

- Path: `vllm bench throughput`, no `--async-engine`
- Prompt source: vLLM random dataset, text prompt
- Output detokenization: disabled with `--disable-detokenize`
- Result JSON:
  `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/stockbench-sync-nodetok-20260520T130107Z/vllm-minimax-m27-autoround-tp4-p512n1536-20260520T130107Z.json`
- Elapsed: `17.329653` s
- Total throughput: `118.178937` tok/s
- Output throughput: `88.633054` tok/s

Disabling output detokenization recovers only about `0.67` output tok/s, so
detokenization is not the main gap.

### Warm in-process harness, vLLM random text prompt

- Path: `scripts/run-vllm-minimax-warm-throughput.py`
- Prompt source: `vllm_random_text`
- Output detokenization: enabled
- Result JSON:
  `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/warm-vllm-random-text-retry-20260520T130948Z/minimax-ws-warm-vllm-random-text-p512n1536.json`
- Mean output throughput: `92.374916` tok/s
- Mean total throughput: `123.166555` tok/s
- Output min/max: `92.320204` / `92.406456` tok/s
- Output standard deviation: `0.039938` tok/s

This uses the same vLLM random text prompt source as stock-bench, but keeps the
engine alive and performs one warmup generation before measuring.

### Warm in-process harness, synthetic token prompt

- Path: `scripts/run-vllm-minimax-warm-throughput.py`
- Prompt source: `synthetic_tokens`
- Output detokenization: enabled
- Result JSON:
  `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/warm-throughput-20260520T124510Z/minimax-ws-source-rebuild-warm-throughput-p512n1536.json`
- Mean output throughput: `92.535653` tok/s
- Mean total throughput: `123.380870` tok/s
- Output standard deviation: `0.012139` tok/s

The text prompt and token prompt warm results differ by only `0.160737`
output tok/s. Input tokenization is therefore not the main stock-bench gap.

## Graph Capture Note

The first `vllm_random_text` warm attempt failed during XPU graph capture with:

```text
The sycl_ext_oneapi_work_group_scratch_memory feature is not yet available for use with the SYCL Graph extension.
```

There were stale user-owned `/dev/shm/psm_*` and `/dev/shm/sem.mp-*` objects
from prior multiprocessing runs. No vLLM workers were still alive. Removing
those stale entries and retrying with the explicit stock compilation config
allowed the run to complete.

## Conclusion

The promoted public stock-bench result (`89.314195` output tok/s) and the latest
strict stock-bench recovery (`87.964466` output tok/s) are conservative cold
first-generation measurements. A warmed engine on the same WS path and the same
vLLM random text prompt shape reaches about `92.37` output tok/s without any
model math change or quality relaxation.

For public LocalMaxxing-style comparisons, keep the stock-bench number unless
the methodology is clearly labeled. For engineering optimization, use the warm
text-prompt harness to avoid chasing first-request/process overhead as if it
were decode kernel time.
