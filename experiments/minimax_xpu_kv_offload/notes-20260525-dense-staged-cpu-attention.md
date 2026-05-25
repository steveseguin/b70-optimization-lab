# 2026-05-25 Dense-Scratch CPU-Staged Attention Probe

Goal: find a realistic route from today's CPU KV session cache to true active
context overflow through system RAM.

Short result: the current vLLM CPU KV offload path still cannot make one active
request exceed live GPU KV capacity by itself. However, a new standalone probe
shows that CPU-staged dense scratch attention can match normal paged attention
output on XPU. This is now the best implementation direction.

## Existing Boundary

The current XPU CPU KV offload worker can move KV blocks between B70 VRAM and
host RAM. It works as a session cache:

- park or reload repeated prefixes through CPU RAM;
- c2/c4/c8 session-cache experiments can reuse prompts after reload;
- CPU-to-GPU transfer rates are in the `~12-16 GB/s` range in prior vLLM runs.

It does not yet provide true active overflow. XPU FlashAttention still expects
the active request's attention window to be resident in GPU-addressable KV
storage before attention runs.

## Paged Scratch Is Not Safe Enough

Added diagnostic probe:

`probes/xpu_cpu_staged_attention_probe.py`

This uses paged XPU scratch KV:

1. keep a normal paged reference KV cache on XPU;
2. copy older prefix KV blocks to CPU;
3. copy CPU chunks back into a smaller paged XPU scratch cache;
4. run paged FlashAttention over each chunk;
5. merge chunk outputs with `merge_attn_states()`.

Findings:

- A tiny `2048` token synthetic case can pass on output when the old prefix is
  staged as one chunk:
  - `max_output_abs_error = 0.0015106201171875`
  - `max_lse_abs_error = 0.6931471824645996`
- Larger or multi-chunk paged scratch cases fail output equivalence:
  - `4096` tokens, one `2048`-token CPU prefix chunk:
    `max_output_abs_error = 0.07269287109375`
  - `8192` tokens, one `4096`-token CPU prefix chunk:
    `max_output_abs_error = 0.037506103515625`

The root issue is not the CPU copy. Exact CPU->XPU round trips preserved FP16
KV values. The issue is that XPU paged FlashAttention output can match while
its returned LSE changes depending on whether the same KV is in the original
paged cache or a scratch paged cache. Exact chunk merging depends on reliable
relative LSE values, so paged scratch is not safe enough for no-quality-loss
active overflow.

## Dense Scratch Is Promising

Added positive probe:

`probes/xpu_cpu_dense_staged_attention_probe.py`

This avoids paged scratch LSE entirely:

1. use normal paged attention output as the reference;
2. reshape the full paged KV to dense and confirm dense full attention matches
   paged full attention output;
3. copy the older prefix KV to CPU RAM;
4. stage CPU prefix chunks into dense XPU scratch tensors;
5. stage the GPU-resident suffix into dense XPU scratch tensors too;
6. run dense FlashAttention on every chunk with `return_softmax_lse=True`;
7. merge dense chunk outputs/LSE values.

MiniMax-shaped synthetic result:

```bash
PYTHONPATH=/home/steve/src/vllm \
/home/steve/.venvs/vllm-xpu/bin/python \
  experiments/minimax_xpu_kv_offload/probes/xpu_cpu_dense_staged_attention_probe.py \
  --blocks 128 \
  --prefix-blocks 64 \
  --stage-tokens 8192 \
  --heads 8 \
  --head-size 128 \
  --warmup-calls 2 \
  --output /mnt/fast-ai/bench-results/minimax-m27-b70-serve/xpu-cpu-dense-staged-attn-synth-32768-h8-20260525.json
```

Shape:

- block size: `256`
- total synthetic sequence: `32768` tokens
- CPU-staged prefix: `16384` tokens
- GPU suffix: `16384` tokens
- dense scratch chunk: `8192` tokens
- KV heads: `8`
- head size: `128`
- dtype: `float16`

Result:

- `ok = true`
- paged full output vs dense full output:
  `3.0517578125e-05`
- dense staged output vs paged full output:
  `3.0517578125e-05`
- dense staged output vs dense full output:
  `1.52587890625e-05`
- dense staged LSE vs dense full LSE:
  `9.5367431640625e-07`
- CPU-staged synthetic prefix KV bytes:
  `67108864` bytes
- total staged bytes in the probe:
  `134217728` bytes

Timing caveat: this probe is for correctness. The reported attention timing is
not production throughput because first-use XPU kernel behavior still creates
large one-off timing spikes. The copy timing for CPU chunks was in the same
rough range as earlier offload work, about `11-12 GB/s` for the CPU chunks in
this run.

## Why Dense Scratch Matters

Normal paged attention is still the production path. For active RAM overflow,
though, exact chunked merge needs trustworthy LSE values. On this stack:

- paged FlashAttention output is good;
- paged FlashAttention LSE is not reliable enough for arbitrary scratch merges;
- dense FlashAttention output and LSE are reliable enough in the standalone
  probe.

So the next prototype should not try to merge paged scratch chunks. It should
use dense scratch chunks for both CPU-resident old KV and GPU-resident suffix
KV, then merge the dense attention states.

## Proposed vLLM Prototype

Add a disabled-by-default branch such as:

```bash
VLLM_XPU_CPU_DENSE_STAGED_ATTN=1
```

Start with c1 decode-only and contexts that already fit in GPU KV.

Attention backend:

- target `/home/steve/src/vllm/vllm/v1/attention/backends/flash_attn.py`;
- only enable for XPU, FP16-family KV, one active decode query, no ALiBi, no
  sliding window;
- gather each logical KV chunk into dense XPU scratch tensors;
- run dense `flash_attn_varlen_func(..., return_softmax_lse=True)`;
- merge chunks with `merge_attn_states()`;
- compare output tokens against the normal paged path.

Scheduler/runtime:

- first stage: do not change scheduler capacity; prove dense staged attention
  under the normal 32K limit;
- second stage: deliberately store older chunks in the existing CPU KV
  offload worker and stage them into dense scratch;
- third stage: separate logical KV length from live physical GPU KV blocks so
  one active request can exceed the resident GPU KV budget.

Initial ladder:

1. `32768`, c1, dense staged attention with all KV still GPU-resident.
2. `32768`, c1, older prefix copied through CPU and staged back into dense
   scratch.
3. `36K-40K`, c1, first true active overflow.
4. `49152`, c1.
5. `65536`, c1.
6. `98304`, c1.
7. `131072`, c1.
8. `196608`, c1.
9. only then c2/c4 long-context concurrency.

## Memory Estimate Reminder

Model config on this checkpoint:

- layers: `62`
- attention heads: `48`
- KV heads: `8`
- hidden size: `3072`
- head size: `128`
- max position embeddings: `196608`

Earlier vLLM startup math estimated one full `196608` FP16-family KV context at
about `11.62 GiB` per tensor-parallel worker, or about `46.5 GiB` total across
TP4. Four full active sessions would be roughly `186 GiB` of KV before engine,
OS, scratch, allocator, and staging overhead. That is feasible only on higher
RAM systems, not the minimum `16 GB` community target.

## Current Recommendation

Production remains the normal `32768` c1 endpoint.

For R&D, stop pursuing paged scratch merging for active overflow. The next
serious path is dense scratch staging:

- it preserves output in standalone XPU tests;
- it avoids unreliable paged LSE;
- it can use the existing CPU KV movement work;
- it will be slower, but it is the first path that looks compatible with the
  no-quality-loss requirement.
