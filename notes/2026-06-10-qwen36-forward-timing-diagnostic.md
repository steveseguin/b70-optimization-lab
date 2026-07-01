# Qwen3.6 Quark INT8 TP4 Forward Timing Diagnostic

Date: 2026-06-10

Model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`

Accepted runtime restored after diagnostic:

- backend: `127.0.0.1:18080`
- frontdoor: `127.0.0.1:8000`
- tmux: `qwen36-tp4-noprefix-32k`
- log: `/tmp/qwen36-quark-int8-tp4-accepted-32k-noprefix-restored8.log`
- 32K context, TP4, BF16 runtime, Quark W8A8 INT8, PIECEWISE graph, custom collectives, no prefix cache

## Diagnostic Setup

The timing run used the same accepted runtime shape, but temporarily enabled synchronized decode timing:

```bash
export VLLM_XPU_DECODE_TIMING=1
export VLLM_XPU_DECODE_TIMING_SYNC=1
export VLLM_XPU_DECODE_TIMING_SKIP_FIRST=16
export VLLM_XPU_DECODE_TIMING_PRINT_EVERY=64
```

Benchmark command:

```bash
/home/steve/.venvs/vllm-xpu/bin/python scripts/measure-openai-endpoint-metrics.py \
  --base-url http://127.0.0.1:18080 \
  --out data/qwen36-quark-int8-tp4-noprefix-timing-sync-p512n128-20260610.json \
  --prompt-tokens 512 \
  --output-tokens 128 \
  --repeats 1 \
  --warmup-output-tokens 32 \
  --mode stream \
  --skip-vram
```

Patch artifact: `patches/vllm-qwen36-runner-forward-timing-boundaries-20260610.patch`

## Result

Because synchronized timing is invasive, this is a diagnostic run rather than a speed gate.

Artifact: `data/qwen36-quark-int8-tp4-noprefix-timing-sync-p512n128-20260610.json`

- corrected after-first output throughput: `88.23790492161743 tok/s`
- e2e output throughput: `82.56160400555225 tok/s`
- TTFT: `111.06672999449074 ms`

Steady decode timing at count 128:

| Region | Rank 0 | Rank 1 | Rank 2 | Rank 3 |
| --- | ---: | ---: | ---: | ---: |
| `gpu_model_runner.model_forward` | `8.554916 ms` | `8.778085 ms` | `8.784457 ms` | `8.823571 ms` |
| `gpu_model_runner.compute_logits` | `0.765448 ms` | `0.772721 ms` | `0.774965 ms` | `0.763403 ms` |
| `gpu_model_runner.sampler` | `0.152396 ms` | `0.148569 ms` | `0.149651 ms` | `0.148338 ms` |
| `gpu_model_runner.bookkeeping_sync` | `0.069861 ms` | `0.068589 ms` | `0.067958 ms` | `0.067146 ms` |

Additional observed buckets:

- `gpu_model_runner.async_output_tolist` rank 0 at count 128: `0.085300 ms`
- `all_reduce:(512, 2048):torch.bfloat16` during the p512 pass: about `0.212-0.223 ms`

## Interpretation

The compiled forward graph is the dominant steady-state cost. Logits, sampler, bookkeeping, and output conversion are all sub-millisecond in this diagnostic. That explains why the local-argmax and fast-output-list variants did not move the accepted speed gate.

Next work should target forward graph internals: GDN/linear-attention kernels, MoE execution/workspace behavior, and collective boundary/copy behavior. More sampler/output micro-optimizations are unlikely to produce meaningful speedup until `model_forward` drops.
