# 2026-05-25 Session-Cache Operations

Goal: make the CPU KV session-cache lane usable as an alternate operating mode,
not just a benchmark experiment.

## Mental Model

The OpenAI-compatible endpoint is still stateless from the client's point of
view. A "session" is the prompt/history the client sends.

For chat clients, that means:

1. The client keeps the conversation history.
2. Every request sends the full relevant history again.
3. vLLM tokenizes the request and hashes the repeated prefix blocks.
4. The session-cache path can store those prefix KV blocks in CPU RAM.
5. When the same conversation continues, vLLM reloads matching prefix blocks
   instead of recomputing the whole prompt.

There is no separate session ID in vLLM that keeps a chat alive by itself. The
stable identity is the exact token prefix. If an old message, system prompt,
chat template, whitespace, or tool transcript changes, the prefix match can be
lost after that point.

## Recommended Profiles

| Profile | Purpose | Notes |
| --- | --- | --- |
| `c1` | production default | `32768` context, `max_num_seqs=1`, no CPU KV offload |
| `c2` | two large parked sessions | best quality-gated session-cache lane for near-32K sessions |
| `c4` | practical multi-session target | four sessions around `22.5K` prompt tokens passed fact-word reload in the ladder, but live ops smoke still has blockers |
| `c8` | many smaller sessions | eight `17.5K` sessions passed, but larger contexts stalled |

Use `c2` first when correctness matters. Use `c4` as the next operational
target, not as the production default yet. It has the best practical shape on
paper, but the live switching smoke below found scheduler/device-loss blockers
that need debugging before it should be exposed to users.

## Switching Profiles

Added:

```bash
experiments/minimax_xpu_kv_offload/scripts/switch_session_cache_profile.sh
experiments/minimax_xpu_kv_offload/scripts/session_cache_status.sh
```

Start the experimental c4 target profile:

```bash
cd /home/steve/llm-optimizations
experiments/minimax_xpu_kv_offload/scripts/switch_session_cache_profile.sh c4
```

Start the safer c2 profile:

```bash
cd /home/steve/llm-optimizations
experiments/minimax_xpu_kv_offload/scripts/switch_session_cache_profile.sh c2
```

Return to production:

```bash
cd /home/steve/llm-optimizations
experiments/minimax_xpu_kv_offload/scripts/switch_session_cache_profile.sh c1
```

Check what is running:

```bash
cd /home/steve/llm-optimizations
experiments/minimax_xpu_kv_offload/scripts/session_cache_status.sh
```

The switcher:

- stops existing MiniMax vLLM processes;
- starts the selected profile detached;
- writes a timestamped log under
  `/mnt/fast-ai/bench-results/minimax-m27-b70-serve/`;
- waits for `/v1/models`;
- writes
  `/mnt/fast-ai/bench-results/minimax-m27-b70-serve/current-session-cache-profile.json`.

## How To Juggle Clients

Use one endpoint, not one endpoint per user:

```text
http://<server-lan-ip>:8000/v1
```

Recommended client policy for `c4`:

- allow up to four active generations at once;
- queue additional users/agents outside vLLM if more than four are active;
- keep each conversation's full history in the client/application;
- resend that history on every turn;
- keep the system prompt and chat formatting stable;
- avoid editing old transcript text if you want prefix reuse;
- cap individual active contexts below the known stable profile boundary.

For c4 today, use roughly:

- high-confidence correctness canary: four sessions around `22.5K` prompt
  tokens in the controlled ladder, but not yet in live service switching;
- sustained decode comfort zone: four sessions around `9.2K` prompt tokens;
- larger sustained `n128` decode at `16K+` still needs scheduler work.

Operationally, put the queue outside vLLM. Treat `max_num_seqs` as the number
of active generations the server may try to run at once, not the number of
human conversations the product can remember. A chat application can keep many
conversation transcripts on disk or in a database, but only let two or four of
them actively generate at a time.

## What The User Experiences

First request for a long session:

- slower TTFT because the prompt is prefilling and KV is being stored.

Later request for the same conversation prefix:

- much faster TTFT if the prefix blocks are found and reloaded from CPU RAM.

Several sessions can be parked:

- vLLM can evict less-active prefix KV to CPU RAM;
- when a parked session returns, the cache reload crosses PCIe at roughly
  `11-16 GB/s` in our measurements.

## What This Does Not Do

This does not make one active context larger than live GPU KV capacity. A single
active request still needs its active attention window to fit. True `196608`
active context needs the dense-scratch CPU-staged attention work documented in:

`notes-20260525-dense-staged-cpu-attention.md`

## Why Not `--gpu-memory-utilization 0.999`?

The current production lane uses `--gpu-memory-utilization 0.95`. That is a
guardrail, not wasted memory.

vLLM's reported KV budget is only one part of the memory story. The remaining
space absorbs:

- graph-capture memory;
- block tables and scheduler metadata;
- Level Zero / oneAPI driver scratch;
- temporary tensors during prefill and decode;
- allocator fragmentation;
- occasional display/runtime overhead if the GPUs are not fully headless.

Pushing from `0.95` toward `0.999` may show a larger theoretical KV cache, but
it also removes the buffer that keeps graph capture, CPU-to-GPU KV reloads, and
driver workspaces from colliding. The live c4 smoke below stalled with only
`88.0%` GPU KV cache usage reported, so the failure boundary is not simply
"wait until the metric says 100%".

Higher values can be tested in small increments, but each increment needs the
same checks:

1. c1 starts cleanly and answers a smoke request.
2. c2 strict/fact-word canaries still match baseline.
3. c4 does not stall waiting/deferred requests after a second-pass reload.
4. No `UR_RESULT_ERROR_DEVICE_LOST` appears in the worker logs.

## Live C4 Operations Smoke

After starting c4:

```bash
ts=$(date -u +%Y%m%dT%H%M%SZ)
experiments/minimax_xpu_kv_offload/scripts/session_cache_canary.py \
  --prompt-mode fact-word \
  --prompt-lines 400 \
  --max-tokens 4 \
  --passes 2 \
  --concurrency 4 \
  --labels A,B,C,D \
  --stop-newline \
  --output-json "/mnt/fast-ai/bench-results/minimax-m27-b70-serve/session-cache-c4-ops-smoke-${ts}.json"
```

2026-05-25 result:

- c4 started and reported `34304` GPU KV tokens with `8.0 GiB` CPU KV budget
  per TP worker.
- The first pass of this `400`-line fact-word smoke produced the expected
  A/B/C/D words.
- The second pass stalled with `Running: 0 reqs`, `Waiting: 4 reqs`,
  `Deferred: 3 reqs`, `GPU KV cache usage: 88.0%`, and external prefix cache
  hit rate `42.6%`.
- The log reported CPU-to-GPU KV movement of `7606370304` bytes in
  `0.496500628 s`, roughly `15.3 GB/s`, before the stall.

Rerunning the earlier controlled `900`-line c4 fact-word canary after a fresh
c4 restart did not reproduce the earlier clean pass. The first three labels
completed correctly, then worker TP0 failed while copying the vLLM block table
to GPU:

```text
RuntimeError: level_zero backend failed with error: 20 (UR_RESULT_ERROR_DEVICE_LOST)
```

Relevant stack:

```text
gpu_model_runner.py:_prepare_inputs
block_table.py:commit_block_table
vllm/v1/utils.py:copy_to_gpu
```

Interpretation:

- The profile switch/status tooling works.
- c1 recovered after the failure and answered a smoke request.
- c4 should remain an experimental profile until the stalled second-pass reload
  and Level Zero device-loss path are understood.
- c2 remains the safer RAM-backed profile for correctness work.

Next c4 debugging ideas:

1. Repeat c4 with `VLLM_MAX_NUM_BATCHED_TOKENS=256`.
2. Repeat c4 with a lower `VLLM_KV_OFFLOADING_SIZE`, such as `24`, to see
   whether extra CPU KV budget is costing too much live headroom.
3. Test staggered second-pass requests instead of four simultaneous reloads.
4. Add a small watchdog script that fails fast when requests remain
   waiting/deferred with zero running requests.
5. Capture the block-table copy size near the `copy_to_gpu` device-loss path.

## Live C2 Operations Smoke

After the c4 failure, the switcher was used to start c2:

```bash
cd /home/steve/llm-optimizations
experiments/minimax_xpu_kv_offload/scripts/switch_session_cache_profile.sh c2
```

Log:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/serve-session-cache-c2-20260525T223257Z.log`

Result:

- `/v1/models` reported `max_model_len=32768`.
- c2 reported `34304` GPU KV tokens.
- The ops smoke used two concurrent fact-word sessions.
- Each prompt was `22540` tokens.
- Both labels matched the expected word and exact output hash across passes.
- Second-pass reload TTFT was `0.320 s` for A and `0.570 s` for B.
- vLLM reported external prefix cache hit rate `50.0%`.
- CPU-to-GPU KV movement was `11442061312` bytes in `0.705925844 s`, about
  `16.2 GB/s`.

Smoke command:

```bash
ts=$(date -u +%Y%m%dT%H%M%SZ)
experiments/minimax_xpu_kv_offload/scripts/session_cache_canary.py \
  --prompt-mode fact-word \
  --prompt-lines 900 \
  --max-tokens 4 \
  --passes 2 \
  --concurrency 2 \
  --labels A,B \
  --stop-newline \
  --output-json "/mnt/fast-ai/bench-results/minimax-m27-b70-serve/session-cache-c2-ops-fact-900lines-${ts}.json"
```

Result file:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/session-cache-c2-ops-fact-900lines-20260525T223527Z.json`

Interpretation: c2 is the current known-good operational session-cache profile
for juggling two long conversations. It does not create one larger active
context, but it does show that two `22.5K`-token sessions can be parked/reloaded
with sub-second second-pass TTFT and exact canary output.

After the smoke, the switcher restored c1:

```bash
experiments/minimax_xpu_kv_offload/scripts/switch_session_cache_profile.sh c1
```

Restored c1 log:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/serve-session-cache-c1-20260525T223617Z.log`

Final state:

- profile state file says `c1`;
- `/v1/models` reports `max_model_len=32768`;
- a small completion smoke returned normally.
