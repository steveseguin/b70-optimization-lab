# Benchmarks

## Initial Shapes

Use small shapes while the loader is unstable:

| Label | Prompt | Output | Context | Purpose |
| --- | ---: | ---: | ---: | --- |
| `p64n16-smoke` | 64 | 16 | 2048 | prove construction, load, and decode |
| `p512n128-early` | 512 | 128 | 2048 | compare early decode with historical AutoRound baselines |
| `p512n1536-main` | 512 | 1536 | 2048 | eventual MiniMax-style decode record shape |
| `p4096n512-prefill` | 4096 | 512 | 8192 | later prefill/decode balance |

## Comparability Rules

- Output tok/s is `output_tokens / elapsed_time` for `vllm bench throughput`
  single-prompt runs.
- Total tok/s comes from vLLM's reported `tokens_per_second`.
- Always record prompt length, output length, context length, batch size, TP,
  dtype, KV dtype, block size, prefix caching, compilation config, and XPU env.
- Warm/cold runs are separate datapoints.
- A failed run with a new error is still useful and should be entered in
  `../results/experiment-ledger.md`.

## First Wrapper

```bash
INPUT_LEN=64 OUTPUT_LEN=16 MAX_MODEL_LEN=2048 RUN_TIMEOUT=30m \
  ../scripts/bench-vllm-deepseek-v4-flash-autoround-xpu.sh
```
