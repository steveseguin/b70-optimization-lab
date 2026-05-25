# 2026-05-25 CPU-Paged Attention Design

Goal: identify the next real step toward one active MiniMax M2.7 request whose
context is larger than live B70 GPU KV capacity, ideally scaling later toward
`196608` tokens and then multi-session long context.

Short result: the next step is not a larger `--kv-offloading-size` value. The
current CPU KV path can park and reload sessions, but XPU FlashAttention still
expects the active request's KV blocks to be in GPU memory. True active
overflow needs a CPU-paged or CPU-streamed attention path.

## Current Production Boundary

The production endpoint should stay on the normal FP16-family KV recipe:

- `max_model_len=32768`
- `max_num_seqs=1`
- OpenAI-compatible vLLM on `0.0.0.0:8000`
- warm short-prompt decode: about `84-95 tok/s`
- quality status: current recommended lane

All work below is R&D until exactness, stability, and semantic quality are
proven.

## Why Session Offload Is Not Enough

The XPU CPU KV worker can move KV blocks between GPU memory and pinned host
RAM. That has already enabled useful session-cache behavior:

- c2 reload works for two near-32K sessions.
- CPU-to-GPU reload bandwidth is about `14-15 GB/s`.
- Strict-word c2 canaries match the GPU-only baseline.

But a single active request still needs enough live GPU KV blocks for its
current full attention window. Once the prompt approaches the live GPU KV block
budget, generation parks or times out. The TurboQuant 4-bit NC lane lifted the
observed live active boundary to about `98304` tokens, but it still failed well
below one full `196608` MiniMax context.

For FP16-family KV, vLLM's old startup estimate said one `196608` request needs
about `11.62 GiB` of KV per tensor-parallel worker, or about `46.5 GiB` total
across TP4. Four full active sessions would be roughly `186 GiB` of KV before
OS, engine, allocator, and staging overheads. That is a useful high-end target,
but it is not a 16 GB system-RAM feature.

## XPU Attention Call Path

XPU platform routing:

`/home/steve/src/vllm/vllm/platforms/xpu.py`

- Sets `VLLM_KV_CACHE_LAYOUT` to `NHD`.
- Routes `turboquant_*` KV dtypes to `TurboQuantAttentionBackend`.
- Routes normal FP16-family KV to `FlashAttentionBackend`.

Normal FP16-family attention:

`/home/steve/src/vllm/vllm/v1/attention/backends/flash_attn.py`

- `FlashAttentionImpl.forward()` receives:
  - `query`, `key`, `value`
  - `kv_cache`
  - `FlashAttentionMetadata`
  - `output`
- It unbinds `kv_cache` into `key_cache` and `value_cache`.
- It calls `flash_attn_varlen_func(...)` with:
  - `k=key_cache`
  - `v=value_cache`
  - `block_table=attn_metadata.block_table`
  - `seqused_k=attn_metadata.seq_lens`
  - `scheduler_metadata=attn_metadata.scheduler_metadata`

KV connector timing:

`/home/steve/src/vllm/vllm/v1/worker/kv_connector_model_runner_mixin.py`

- `kv_connector.start_load_kv(get_forward_context())` runs before model
  forward.
- The existing connector is therefore built around loading blocks before
  attention runs.
- For true active overflow, loading all required old blocks before forward is
  exactly what cannot fit. The staging hook has to be closer to the attention
  call itself.

## Existing vLLM Pattern To Reuse

There are two useful precedents already in vLLM.

First, XPU FlashAttention has cascade attention:

`/home/steve/src/vllm/vllm/v1/attention/backends/flash_attn.py`

- `cascade_attention()` computes a shared prefix and a suffix separately.
- Both calls request `return_softmax_lse=True`.
- It merges the partial outputs with:
  `vllm/v1/attention/ops/merge_attn_states.py`

Second, the ROCm AITER backend has a closer chunked-context pattern:

`/home/steve/src/vllm/vllm/v1/attention/backends/rocm_aiter_fa.py`

- `extend_forward()` gathers prior KV chunks into a workspace.
- It runs attention over each gathered chunk.
- It merges the chunk outputs and LSE values with `merge_attn_states()`.

That is not CPU overflow, but it proves vLLM already has an accepted shape for
"attention over chunks, then exact softmax merge."

## Proposed Exact Prototype

Prototype a disabled-by-default XPU FP16-family path behind an environment
variable such as:

```bash
VLLM_XPU_CPU_PAGED_ATTN=1
```

Start decode-only and single-request. Do not start with full prefill or c4.

For one attention layer:

1. Keep recent/current KV in the normal GPU KV cache.
2. Keep older logical KV blocks in CPU offload storage.
3. Allocate a small GPU staging KV workspace, for example enough for
   `4096-8192` tokens per layer/rank.
4. For each old CPU-resident chunk:
   - copy that chunk into the staging workspace
   - build a temporary block table that points at staging blocks
   - call `flash_attn_varlen_func(..., causal=False,
     return_softmax_lse=True)`
   - merge its output/LSE into the running attention state
5. Run normal attention for the live GPU-resident suffix/current region.
6. Merge the suffix output/LSE with the old-context merged state.

The math is exact if every chunk uses the same scale, softcap, position
semantics, and values, and if outputs are merged with log-sum-exp weights. It
will be slower because old KV must cross PCIe, but it should not change model
semantics.

## Prototype Ladder

### Stage A: Standalone Math Probe

Add and run:

`probes/split_attention_merge_probe.py`

It compares full attention against chunked attention plus LSE merge. This does
not touch vLLM or GPU memory.

Pass condition:

- merged output and LSE match full attention within a tight float tolerance.

### Stage B: GPU-Resident Split Equivalence

Inside vLLM, force a request that already fits in GPU KV to split into two or
more chunks, but keep all chunks GPU-resident.

Pass condition:

- strict-word canary matches normal GPU-only output hash.
- semantic/fact-word checks match.
- no decode-rate regression when the env var is disabled.

This proves the staged attention path is semantically correct before CPU RAM
enters the picture.

### Stage C: CPU-Staged Split Equivalence

Still use a context that fits in GPU KV, but deliberately store older chunks in
CPU KV and stage them back through the scratch workspace during attention.

Pass condition:

- exact canaries match the GPU-only path.
- transfer counters match expected chunk sizes.
- no hangs when CPU chunks are reloaded repeatedly.

### Stage D: Small Active Overflow

Allow logical KV length to exceed live GPU KV length by a small amount, for
example `36K-40K` on the FP16-family lane. Old blocks live in CPU storage and
are streamed through staging workspace.

Pass condition:

- one request returns where today's scheduler-only offload parks.
- strict-word and fact-word canaries pass.
- failure handling leaves no orphan workers or stale shared-memory allocations.

### Stage E: Scale Context

Only after Stage D works:

- `49152`, c1
- `65536`, c1
- `98304`, c1
- `131072`, c1
- `196608`, c1
- c2/c4 only after c1 is reliable

For each rung, record TTFT, output tok/s, PCIe transfer volume, peak VRAM, CPU
RAM used, and exact/semantic quality gates.

## Required vLLM Changes

Scheduler/block manager:

- Separate logical KV ownership from live physical GPU KV residency.
- Do not require every historical logical block to consume a live GPU block.
- Keep enough live GPU blocks for current writes, suffix attention, and staging.

KV connector/offload manager:

- Expose a query/load API for layer/block ranges needed by attention.
- Return CPU-resident blocks in logical sequence order.
- Coalesce contiguous block ranges before copy.
- Keep the existing session-cache path working.

Attention metadata:

- Mark which block ranges are CPU-resident versus GPU-resident.
- Provide enough data to build temporary staging block tables.
- Keep the normal block table path unchanged when the env var is disabled.

Attention backend:

- Add an XPU-only experimental branch near `FlashAttentionImpl.forward()`.
- Use `return_softmax_lse=True` for chunk calls.
- Use `merge_attn_states()` for exact merge.
- Start with ALiBi disabled and sliding window disabled, matching MiniMax.
- Keep TurboQuant out of the first prototype; use FP16-family KV first.

Prefill:

- Decode-only is the simplest first target, but full prompt support requires
  chunked prefill.
- For a prefill chunk, old staged chunks are non-causal because they are before
  the current query chunk.
- The current query chunk/suffix remains causal and can use the normal GPU KV
  path.

## Main Risks

- `flash_attn_varlen_func` expects GPU tensors and GPU block tables. CPU pages
  must be copied into GPU staging first.
- Scheduler allocation can still reject requests unless logical and physical
  KV accounting are separated.
- The first implementation will be PCIe-bound. This is expected.
- Long prefill may be far slower than 32K production serving.
- Intel `ocloc` / IGC error `245` has appeared during compile fallback and may
  reappear with new graph shapes.
- Full `196608` c4 likely needs more than `186 GiB` of host KV capacity plus
  overhead, so it needs a high-RAM machine even if the code works.

## Near-Term Recommendation

Keep the production endpoint unchanged. For R&D, implement the CPU-paged
attention ladder in order:

1. standalone split-attention merge probe
2. GPU-resident split equivalence in vLLM
3. CPU-staged split equivalence under the live GPU limit
4. small active overflow
5. scale toward full `196608`

This is the first path found that could plausibly deliver full active context
with no intentional quality loss.
