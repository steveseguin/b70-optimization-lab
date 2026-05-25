# 2026-05-25 TurboQuant Active-Context Boundary

Goal: test whether TurboQuant plus XPU CPU KV offload can turn the session-cache
lane into true active-context overflow, with the long-term target of multiple
active `196608` token sessions.

Short result: not yet. TurboQuant improves the number of GPU KV blocks, and CPU
KV offload can park/reload sessions, but the current vLLM/XPU attention path
still requires the active request's KV blocks to fit in live GPU KV memory.

## Baseline Reminder

The production lane remains the normal FP16-family KV endpoint:

- context: `32768`
- concurrency: `1`
- host: `0.0.0.0:8000`
- warmed short-prompt decode: about `84-95 tok/s` depending on warm state and
  benchmark shape
- quality status: current production recommendation

TurboQuant and CPU KV offload are research lanes only.

## 100K TurboQuant 4-Bit NC + C4 Offload

Temporary server:

```bash
vllm serve "$MODEL" \
  --served-model-name minimax-tq-4bit-nc \
  --host 127.0.0.1 \
  --port 18080 \
  --trust-remote-code \
  --dtype float16 \
  --tensor-parallel-size 4 \
  --distributed-executor-backend mp \
  --max-model-len 100000 \
  --max-num-batched-tokens 512 \
  --max-num-seqs 4 \
  --gpu-memory-utilization 0.95 \
  --block-size 256 \
  --no-enable-prefix-caching \
  --no-scheduler-reserve-full-isl \
  --kv-offloading-size 32 \
  --compilation-config '{"use_inductor_graph_partition":true,"compile_sizes":[1],"cudagraph_mode":"PIECEWISE"}' \
  --kv-cache-dtype turboquant_4bit_nc
```

Log:

`/mnt/fast-ai/bench-results/minimax-m27-b70-turboquant-20260525/server-turboquant_4bit_nc-ctx100000-c4-kvoffload32-20260525T130225Z.log`

Startup facts:

- `max_model_len=100000`
- GPU KV cache size: `84654` tokens
- vLLM maximum concurrency for `100000` tokens per request: `0.85x`
- CPU KV offload budget: `8.0 GiB` per worker from `--kv-offloading-size 32`
- compile again exposed Intel `ocloc` / IGC error `245`, then fallback compile
  completed

The server started and accepted requests, but active requests were still bounded
by live GPU KV blocks.

## Tokenization Ladder

The strict-word prompt length was measured through `/tokenize`:

| Prompt lines | Prompt tokens |
| ---: | ---: |
| `2700` | `81074` |
| `2750` | `82574` |
| `2800` | `84074` |
| `2810` | `84374` |
| `2815` | `84524` |
| `2819` | `84644` |
| `2820` | `84674` |
| `2850` | `85574` |
| `3000` | `90074` |

## Active Boundary Results

Working near-limit request:

`/mnt/fast-ai/bench-results/minimax-m27-b70-turboquant-20260525/strict-word-tq4-near-active-limit-lines2800-ctx100000-20260525T131655Z.json`

- prompt tokens: `84074`
- output tokens: `4`
- elapsed: `12.128 s`
- TTFT: `8.592 s`
- expected word: `blue`
- observed word: `blue`
- result: passed

Working cached/reloaded near-limit request:

`/mnt/fast-ai/bench-results/minimax-m27-b70-turboquant-20260525/strict-word-tq4-active-limit-lines2810-ctx100000-20260525T132604Z.json`

- prompt tokens: `84374`
- output tokens: `4`
- elapsed: `1.296 s`
- TTFT: `0.933 s`
- expected word: `blue`
- observed word: `blue`
- result: passed

The short elapsed time on the `2810`-line request is likely from the external
prefix/session cache after prior near-identical requests. It should not be read
as cold prefill performance.

Failed or hung shapes:

- `2819` lines / `84644` prompt tokens timed out after `300 s`.
- `2850` lines / `85574` prompt tokens timed out waiting for first text.
- `3000` lines / `90074` prompt tokens hung until the client was killed after
  several minutes.

Interpretation: the active boundary is just below the reported `84654` GPU KV
tokens because block granularity and decode space matter. With block size `256`,
`84654` tokens is `330.7` blocks. A prompt that consumes all available blocks
leaves no room for decode. This matches the earlier FP16-family finding: the
connector can park/reload KV, but active attention still needs live GPU blocks.

## 196K C1 High-Utilization Probe

The next test asked whether reducing concurrency and pushing
`gpu_memory_utilization` could make a single full `196608` active context work.

Failed startup attempts:

- `gpu_memory_utilization=0.99` failed because desired reserved memory exceeded
  free startup memory.
- `gpu_memory_utilization=0.965` failed on `xpu:0` for the same reason.

Working startup:

```bash
vllm serve "$MODEL" \
  --served-model-name minimax-tq-4bit-nc-c1-196k \
  --host 127.0.0.1 \
  --port 18080 \
  --trust-remote-code \
  --dtype float16 \
  --tensor-parallel-size 4 \
  --distributed-executor-backend mp \
  --max-model-len 196608 \
  --max-num-batched-tokens 512 \
  --max-num-seqs 1 \
  --gpu-memory-utilization 0.959 \
  --block-size 256 \
  --no-enable-prefix-caching \
  --no-scheduler-reserve-full-isl \
  --kv-offloading-size 32 \
  --compilation-config '{"use_inductor_graph_partition":true,"compile_sizes":[1],"cudagraph_mode":"PIECEWISE"}' \
  --kv-cache-dtype turboquant_4bit_nc
```

Log:

`/mnt/fast-ai/bench-results/minimax-m27-b70-turboquant-20260525/server-turboquant_4bit_nc-ctx196608-c1-bt512-util0959-20260525T140637Z.log`

Startup facts:

- available KV cache memory: `1.82 GiB`
- GPU KV cache size: `98304` tokens
- vLLM maximum concurrency for `196608` tokens per request: `0.50x`
- graph capture memory: `0.50 GiB`
- CPU KV offload budget: `8.0 GiB` per worker
- compile again exposed Intel `ocloc` / IGC error `245`, then fallback compile
  continued

Working request:

`/mnt/fast-ai/bench-results/minimax-m27-b70-turboquant-20260525/strict-word-tq4-c1-lines2800-ctx196608-bt512-util0959-20260525T141427Z.json`

- prompt tokens: `84074`
- output tokens: `4`
- elapsed: `117.534 s`
- TTFT: `114.342 s`
- expected word: `blue`
- observed word: `blue`
- result: passed, but much too slow for an interactive long-context lane

Near-limit failure:

`/mnt/fast-ai/bench-results/minimax-m27-b70-turboquant-20260525/strict-word-tq4-c1-lines3260-ctx196608-bt512-util0959-20260525T141707Z.json`

- prompt lines: `3260`
- expected prompt size: about `97800` tokens by the prompt ladder
- elapsed before failure response: `326.475 s`
- streamed text chunks: `0`
- usage: `null`
- observed word: empty
- result: failed

The engine log showed the request at the active limit:

```text
num_computed_tokens=[97792]
num_scheduled_tokens=82
kv_cache_usage=1.0
TimeoutError: RPC call to sample_tokens timed out.
```

This is a stronger failure than a client timeout: the engine hit full KV usage
and died at the transition into sampling.

## Restore Gotcha After Engine Death

After the 196K near-limit fatal error, the API server exited but three orphaned
worker processes kept running:

```text
VLLM::Worker_TP0
VLLM::Worker_TP1
VLLM::Worker_TP3
```

The next production restore failed because those workers still held almost all
XPU memory:

```text
ValueError: Free memory on device xpu:0 (0.24/31.89 GiB) on startup is less
than desired GPU memory utilization (0.95, 30.3 GiB).
```

Recovery:

```bash
ps -ef | rg 'vllm|EngineCore|Worker_TP|multiprocessing.resource_tracker'
kill -9 <orphan_worker_pids> <orphan_resource_tracker_pid>
rm -f /dev/shm/psm_* /dev/shm/sem.mp-*
xpu-smi stats -d 0
```

After killing the orphan workers, `xpu-smi` showed the cards back near idle
memory (`26-125 MiB` used), and the normal `32768` endpoint restored
successfully.

## What This Means For 4 x 196K

The best active GPU KV capacity seen in this lane was `98304` tokens with
`turboquant_4bit_nc`, c1, `gpu_memory_utilization=0.959`.

Lay math:

- one full MiniMax context is `196608` tokens
- the best live active KV capacity observed is about `98304` tokens
- one full context is therefore about `2x` too large
- four full contexts are `786432` tokens
- four full contexts are about `8x` the best live active KV capacity observed

Using the measured `1.82 GiB` live KV memory for `98304` TurboQuant tokens:

- one `196608` token active context would need roughly `3.64 GiB` of live KV
  per worker
- four active `196608` token contexts would need roughly `14.6 GiB` of live KV
  per worker
- this system currently has roughly `1.8 GiB` available for live KV per worker
  in the tested high-utilization TurboQuant lane

Host RAM can store parked KV, but today it does not make the attention kernel
attend directly over CPU-resident KV. To make `4 x 196K` production-viable, the
next implementation has to be one of:

1. CPU-paged or CPU-streamed attention that can read offloaded KV during active
   attention.
2. A hybrid attention path that keeps recent/local blocks on GPU and streams
   older blocks from CPU without changing model semantics.
3. A quality-proven KV compression format with enough compression to fit the
   active contexts in GPU memory.
4. More available GPU KV memory per rank.

Scheduler admission patches and larger `--kv-offloading-size` values are not
enough by themselves.

## Simple CPU Offload Note

The newer `SimpleCPUOffloadConnector` path is not a shortcut for active
overflow on this XPU stack. Code inspection shows it is still CUDA-oriented
(`torch.cuda.Stream`, CUDA event handling, and `cudaHostRegister`-style pinning)
and it still moves blocks back into GPU block slots for active execution.

It may be useful upstream in the future, but the current practical XPU path is
the native offload connector with the local XPU worker prototype.

## Current Recommendation

Do not promote TurboQuant or CPU KV offload as a replacement for the production
`32768` endpoint.

Use these labels:

- `production`: FP16-family KV, `32768`, c1, normal vLLM endpoint
- `experimental-session-cache`: CPU KV offload for parked/reloaded sessions
  whose individual active context fits in GPU KV
- `experimental-compressed-kv`: TurboQuant capacity probes
- `blocked-rd`: true active overflow past GPU KV capacity

## Next Engineering Step

Stop testing larger scheduler limits until the runtime can execute active
attention over non-GPU-resident KV. The next useful work item is a small design
prototype for CPU-paged attention:

- trace the exact XPU attention backend entry points that consume block tables
- add instrumentation to show which layer/block ids are required at each
  prefill/decode step
- prototype a synchronous "load block range just before attention" path for a
  tiny context over GPU capacity
- only after that returns exact strict-word canaries, optimize with XPU streams
  and range coalescing

This is a real kernel/runtime project, not just a launch-flag change.
