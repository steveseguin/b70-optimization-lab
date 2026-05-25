# 2026-05-25 Phase 5: C2 Session-Swap Smoke

Goal: test the useful part of CPU KV offload after the active-context limit
finding: exact-quality session swapping for contexts that individually fit in
GPU KV, but collectively exceed the live GPU KV cache.

This is not `196608` active-context overflow. It is a practical RAM-backed
session-cache test.

## Launch Shape

Temporary server:

```bash
VLLM_MAX_MODEL_LEN=32768 /home/steve/bin/minimax-vllm-serve \
  --kv-offloading-size 16 \
  --max-num-seqs 2 \
  --no-scheduler-reserve-full-isl
```

Log:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/serve-32768-c2-kvoffload16-session-swap-smoke-20260525T012013Z.log`

Startup facts:

- `max_model_len=32768`
- `max_num_seqs=2`
- GPU KV cache size: `26112` tokens
- Maximum concurrency for `32768` tokens per request: `0.80x`
- CPU KV admission budget: `4.0 GiB` per worker from
  `--kv-offloading-size 16` and TP4
- First c2 startup had a new compile cost: `234.06 s` total torch compile.

The lower GPU KV cache size versus the c1 server is expected because c2 graph
capture and runtime buffers consume more memory.

## Test Shape

Two concurrent completion requests:

- Session A: `14000` prompt tokens, `8` output tokens
- Session B: `14000` prompt tokens, `8` output tokens
- Combined prompt tokens: `28000`, above the `26112` GPU KV budget
- Each individual session: well below the GPU KV budget

The prompts were intentionally distinct:

```text
Session A line 0000: CPU KV offload session swapping validation text with a unique marker.
Session B line 0000: CPU KV offload session swapping validation text with a unique marker.
```

## First Pass Result

Both requests completed:

| Session | Prompt tokens | Output tokens | Wall time |
| --- | ---: | ---: | ---: |
| A | `14000` | `8` | `14.83 s` |
| B | `14000` | `8` | `25.22 s` |

vLLM reported GPU-to-CPU KV stores:

| Direction | Bytes | Time | Effective rate |
| --- | ---: | ---: | ---: |
| GPU -> CPU | `3965714432` | `0.35821499999999995 s` | about `11.1 GB/s` |
| GPU -> CPU | `325058560` | `0.030804488 s` | about `10.6 GB/s` |

Total stored during this smoke: about `4.29 GB`.

## Second Pass Result

The same two prompts were submitted concurrently again. Both returned quickly:

| Session | Prompt tokens | Output tokens | Wall time |
| --- | ---: | ---: | ---: |
| A | `14000` | `8` | `0.474 s` |
| B | `14000` | `8` | `0.846 s` |

vLLM then reported CPU-to-GPU KV loads:

| Direction | Bytes | Time | Effective rate |
| --- | ---: | ---: | ---: |
| CPU -> GPU | `7021264896` | `0.46733606399999994 s` | about `15.0 GB/s` |

The log also reported:

```text
External prefix cache hit rate: 49.4%
```

Interpretation: CPU KV offload is usable as an exact session cache for prompts
that fit individually. It can store KV from one pass and reload it for a later
matching prompt. This is the first practical RAM-backed behavior observed in
this lane.

## Caveats

- This does not prove multi-turn chat session management yet; it proves
  repeated-prompt external KV reuse through the vLLM offload connector.
- It does not allow a single active request to exceed the GPU KV block budget.
- The first c2 launch compiled new shapes and took several minutes. Future c2
  launches should be faster once the compile cache is warm.
- The first pass is prefill-heavy, so wall-time output tok/s is not comparable
  to the normal 32K decode benchmark.
- The second pass is cache-hit-heavy, so its sub-second wall time is not a
  normal generation benchmark either.

## Next Steps

1. Build deterministic canaries comparing GPU-only output against offload
   reload output for the same prompt.
2. Test c2 with longer outputs after the second-pass reload, to measure decode
   rate after CPU KV has been restored.
3. Try c4 with smaller individual contexts.
4. Measure transfer size per stored token and estimate practical session-cache
   RAM requirements.
5. Keep this separate from active-context overflow work.

## Restore

The normal server was restored after this experiment with:

```bash
VLLM_MAX_MODEL_LEN=32768 /home/steve/bin/minimax-vllm-serve
```
