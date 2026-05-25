# 2026-05-25 C4/C8 Session-Cache Ladder

Goal: push CPU KV session caching beyond c2 while keeping the production
endpoint unchanged. This is still session caching, not true active-context
overflow. Each request must still fit in the live GPU KV budget when it is
actively being processed.

## Launch Shapes

Stable production remains:

```bash
VLLM_MAX_MODEL_LEN=32768 /home/steve/bin/minimax-vllm-serve
```

c4 experimental session cache, using the updated launcher:

```bash
VLLM_MAX_MODEL_LEN=32768 \
VLLM_MAX_NUM_SEQS=4 \
VLLM_KV_OFFLOADING_SIZE=32 \
VLLM_NO_SCHEDULER_RESERVE_FULL_ISL=1 \
/home/steve/bin/minimax-vllm-serve
```

c8 experimental session cache, using the updated launcher:

```bash
VLLM_MAX_MODEL_LEN=32768 \
VLLM_MAX_NUM_SEQS=8 \
VLLM_KV_OFFLOADING_SIZE=64 \
VLLM_NO_SCHEDULER_RESERVE_FULL_ISL=1 \
/home/steve/bin/minimax-vllm-serve
```

The base launcher originally included `--max-num-seqs 1`, so these tests logged
a duplicate key warning when a larger value was appended. The later CLI value
was the one used by the server. After these tests,
`/home/steve/bin/minimax-vllm-serve` and the tracked repro launcher
`repro/minimax-m27-b70-110tps-ubuntu24-20260523/scripts/06-serve-openai-compatible.sh`
were updated to support:

- `VLLM_MAX_NUM_SEQS`
- `VLLM_MAX_NUM_BATCHED_TOKENS`
- `VLLM_KV_OFFLOADING_SIZE`
- `VLLM_NO_SCHEDULER_RESERVE_FULL_ISL=1`

Future c4/c8 launches can use those environment variables instead of duplicate
CLI overrides.

Tracked helper:

```bash
experiments/minimax_xpu_kv_offload/scripts/serve_session_cache.sh c4
experiments/minimax_xpu_kv_offload/scripts/serve_session_cache.sh c8
```

## Startup Facts

| Shape | CPU offload budget | Live GPU KV tokens | Max concurrency for 32K | Startup note |
| --- | ---: | ---: | ---: | --- |
| c4 | `8.0 GiB` per TP worker, `32 GiB` total | `34304` | `1.05x` | Cached compile, normal startup |
| c8 | `16.0 GiB` per TP worker, `64 GiB` total | `22784` | `0.70x` | `315.97 s` engine init, `234.78 s` compile |

Important: increasing the offload/session-cache budget reduces live GPU KV
headroom. c8 can park more sessions in RAM, but its live GPU budget is much
smaller than c4.

## C4 Fact-Word Result

Result:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/session-cache-c4-fact-900lines-20260525T163841Z.json`

Shape:

- `prompt-mode=fact-word`
- `prompt-lines=900`
- `concurrency=4`
- `passes=2`
- prompt tokens per session: `22540`
- total first-pass prompt tokens: `90160`

Outcome:

| Pass | Requests | TTFT range | Max elapsed | Expected words |
| --- | ---: | ---: | ---: | --- |
| 1 | `4` | `16.452-63.980 s` | `63.987 s` | all matched |
| 2 | `4` | `0.390-1.211 s` | `1.216 s` | all matched |

Interpretation: c4 session caching is mechanically useful. Four long sessions
around `22.5K` prompt tokens each can be parked and reloaded with sub-1.3 s
second-pass TTFT in this constrained retrieval canary.

Transfer examples from the c4 log:

- GPU to CPU chunks were usually about `3.3-3.8 GB` in `0.28-0.33 s`.
- CPU to GPU reload examples included `20.48 GB` in `1.436 s` and `6.83 GB`
  in `0.517 s`.
- Effective transfer rates were roughly `11-14 GB/s`.
- External prefix cache hit rate reached about `49.6-49.8%`.

## C8 Fact-Word Passing Results

### 500 Lines

Result:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/session-cache-c8-fact-500lines-20260525T164810Z.json`

Shape:

- `prompt-lines=500`
- `concurrency=8`
- prompt tokens per session: `12540-12541`
- total first-pass prompt tokens: `100321`

Outcome:

| Pass | Requests | TTFT range | Max elapsed | Expected words |
| --- | ---: | ---: | ---: | --- |
| 1 | `8` | `13.553-73.397 s` | `76.852 s` | all matched |
| 2 | `8` | `0.552-3.709 s` | `3.716 s` | all matched |

### 700 Lines

Result:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/session-cache-c8-fact-700lines-20260525T171200Z.json`

Shape:

- `prompt-lines=700`
- `concurrency=8`
- prompt tokens per session: `17540-17541`
- total first-pass prompt tokens: `140321`

Outcome:

| Pass | Requests | TTFT range | Max elapsed | Expected words |
| --- | ---: | ---: | ---: | --- |
| 1 | `8` | `11.852-59.221 s` | `59.229 s` | all matched |
| 2 | `8` | `0.415-3.247 s` | `3.254 s` | all matched |

Interpretation: c8 can reliably park and reload eight sessions at about
`17.5K` prompt tokens each, or about `140K` combined prompt tokens, with the
fact-word quality canary passing on both passes.

The c8 700-line second pass moved `35.37 GB` CPU-to-GPU in `2.469 s`, about
`14.3 GB/s`, and the external prefix cache hit rate reached about `49.0%`.

## C8 Stalls Near The Upper Bound

Three higher-pressure c8 attempts were intentionally aborted after the scheduler
stalled:

| Shape | Prompt tokens per session | Approx total prompt tokens | Completed before stall | Observed stall |
| --- | ---: | ---: | ---: | --- |
| 750 lines | `18790-18791` | `150321` | `6 / 8` | `2` waiting/deferred at `100%` GPU KV |
| 800 lines | `20040` | `160320` | `5 / 8` | `3` waiting/deferred at about `99%` GPU KV |
| 850 lines | `21290` | `170320` | `4 / 8` | `4` waiting/deferred at `100%` GPU KV |
| 900 lines | `22540` | `180320` | `0 / 8` | `8` waiting, mostly capacity/deferred |

These failures did not crash the server. Killing the canary client cleared the
queue. They look like scheduler/admission or KV-freeing stalls under c8 pressure,
not model quality failures.

## Practical Boundary Found Today

Current safe experimental recommendation:

- c1 `32768` remains the production endpoint.
- c2 near-32K session caching is the strongest quality-gated experiment for
  two parked sessions.
- c4 at about `22.5K` tokens per session appears mechanically useful and passed
  the fact-word canary.
- c8 is promising at about `17.5K` tokens per session, `140K` total prompt
  tokens, but stalls above that on this stack.

This does not yet provide four or eight active `196608`-token sessions. To get
there, we still need one of:

1. true CPU-paged/staged attention for a single active sequence beyond live GPU
   KV;
2. quality-gated KV compression that keeps more active KV resident;
3. scheduler fixes so offloaded sessions do not deadlock/defer at high c8
   pressure.

## Next Work

1. Reproduce the c8 750-line stall with debug logging and determine whether
   blocks are not released, not admitted, or waiting for offload transfer state.
2. Try c8 with smaller `max_num_batched_tokens` or different scheduler settings
   to see whether the stall boundary moves.
3. Keep using `fact-word` as the quick canary, then add a longer semantic
   quality gate before calling c4/c8 production-equivalent.
