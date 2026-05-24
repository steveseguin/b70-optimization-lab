# MiniMax XPU CPU KV Offload Research Lane

Date started: 2026-05-24

This folder tracks the experimental path toward serving MiniMax M2.7 on Intel
Arc Pro B70 with context beyond the current high-performance `32768` token
endpoint by spilling KV cache to host RAM.

The stable production lane remains:

- Model: `Lasimeri/MiniMax-M2.7-int4-AutoRound`
- Engine: vLLM/XPU TP4
- Context: `32768`
- KV dtype: `auto` / FP16-family
- Endpoint: OpenAI-compatible vLLM on `0.0.0.0:8000`
- Warm endpoint decode: about `84-85 tok/s`

Do not replace that lane with this work until correctness, stability, and
quality are proven.

## Why This Matters

MiniMax advertises `196608` max position embeddings. The current B70 endpoint
serves a reliable `32768` tokens because the FP16-family KV cache must fit in
GPU memory. CPU KV offload would let the server keep less-active KV blocks in
system RAM and page them back as needed.

Useful targets:

| Target | Purpose |
| --- | --- |
| `32768`, c1 | Current fast baseline; must remain easy to restore. |
| `65536`, c1 | First large-context milestone. |
| `131072`, c1 | Prove CPU KV offload is genuinely useful. |
| `196608`, c1 | Full MiniMax advertised context. |
| `196608`, c2-c4 | Long-context concurrency research, likely slow but valuable. |

Expected performance with CPU KV offload is much lower than full-VRAM decode.
That is acceptable for this lane if it enables otherwise impossible sessions
and does not degrade model quality.

## Quality Rules

This lane may experiment with memory movement, cache layout, TurboQuant, and
runtime scheduling. It must not silently lower answer quality.

Promotion requires:

- Same model weights unless explicitly labeled otherwise.
- No expert dropping.
- No speculative decoding unless separately labeled and quality-gated.
- Exact-token canaries for deterministic low-level changes.
- Semantic/arithmetic/sixpack checks before promoting any server recipe.
- Endpoint metrics should record prompt tokens, output tokens, TTFT, output
  tok/s, total tok/s, context length, concurrency, and peak VRAM when possible.

FP8 KV, TurboQuant, or other compressed KV modes must be labeled as compressed
KV experiments and compared against the FP16-family baseline.

## 2026-05-24 Experiment Summary

All experiments were temporary. The normal `32768` server was restored.

### Attempt 1: CPU Weight Offload

Command shape:

```bash
VLLM_MAX_MODEL_LEN=196608 /home/steve/bin/minimax-vllm-serve \
  --max-num-seqs 4 \
  --cpu-offload-gb 16
```

Result:

```text
AssertionError: CPU tensor must be pinned
```

This is model-weight offload, not KV offload. It failed during model load in
vLLM's UVA offloader before any useful long-context test could run.

Log:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/serve-196k-c4-cpuoffload16-20260524T215219Z.log`

### Attempt 2: No CPU Offload

Command shape:

```bash
VLLM_MAX_MODEL_LEN=196608 /home/steve/bin/minimax-vllm-serve \
  --max-num-seqs 4
```

Result:

```text
To serve at least one request with max seq len 196608,
11.62 GiB KV cache is needed, larger than available KV cache memory 1.56 GiB.
Based on the available memory, the estimated maximum model length is 26368.
```

Log:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/serve-196k-c4-nooffload-20260524T215257Z.log`

### Attempt 3: Native CPU KV Offload Flag

Command shape:

```bash
VLLM_MAX_MODEL_LEN=196608 /home/steve/bin/minimax-vllm-serve \
  --max-num-seqs 4 \
  --kv-offloading-size 64
```

Result:

vLLM accepted the flag but the KV preflight check still counted only GPU KV
capacity and rejected the run before the offload connector could initialize.

Log:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/serve-196k-c4-kvoffload64-20260524T221520Z.log`

### Attempt 4: Temporary Admission-Check Patch

A local patch added the per-worker CPU KV budget to the preflight capacity
calculation. This got past the prior GPU-only KV check.

The next blocker:

```text
Exception: CPU Offloading is currently only supported on CUDA-alike GPUs
```

The native CPU KV offload path then tried to initialize
`OffloadingConnector` / `CPUOffloadingSpec`, but rejected XPU explicitly.

Log:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/serve-196k-c4-kvoffload64-admissionpatch-20260524T223029Z.log`

Patch sketch:

`patches/kv-offload-admission-check-xpu-experiment-20260524.patch`

## Current Root Cause

vLLM's native CPU KV offload implementation is CUDA-oriented. The XPU run gets
past the scheduler-side configuration only after an admission-check patch, then
fails in the worker-side offload handler because the CPU KV path uses CUDA
concepts:

- `torch.cuda.Stream`
- `torch.cuda.current_stream`
- CUDA events
- `cudaHostRegister`
- CUDA-style async copy handling

The guard is in:

`vllm/v1/kv_offload/cpu/spec.py`

The CUDA-specific worker code is in:

`vllm/v1/kv_offload/cpu/gpu_worker.py`

## Candidate Work Plan

1. Keep `32768` FP16-family KV endpoint as the stable fallback.
2. Create an XPU implementation parallel to the CUDA CPU KV worker rather than
   weakening CUDA assumptions in place.
3. Replace CUDA streams/events with XPU stream/event equivalents if available
   in the installed PyTorch XPU stack.
4. Replace `cudaHostRegister` with a Level Zero / SYCL / PyTorch XPU pinned
   host-memory path. `torch.empty(..., pin_memory=True)` and `.pin_memory()`
   already work locally in `torch 2.11.0+xpu`.
5. Start with small context over GPU capacity, not full `196608`:
   `49152` or `65536`, c1.
6. Measure decode with long prompt plus small output first, then short prompt
   plus long output, then concurrency.
7. Only after c1 works, test c2/c4.

## TurboQuant Interaction

TurboQuant remains interesting because it reduces KV footprint and therefore
reduces both RAM capacity pressure and PCIe transfer volume.

Current TurboQuant status:

- `turboquant_k8v4` starts and reports `60416` KV tokens at `32768` context.
- First completion fails with a workspace-lock assertion in
  `turboquant_attn.py`.
- It is not production-ready, but it may become the most useful companion to
  CPU KV offload once the XPU workspace bug is fixed.

Relevant repro:

`scripts/repro-minimax-turboquant-xpu-workspace-bug.sh`

## Open Questions

- Does PyTorch XPU expose enough stream/event behavior to mirror the CUDA CPU
  KV worker cleanly?
- Can Level Zero host allocation or SYCL USM host memory replace
  `cudaHostRegister` for pinned CPU KV pages?
- Will XPU FlashAttention accept blocks that were copied back from host without
  hidden synchronization stalls?
- What is the lowest useful context above 32K once offload works?
- Is TurboQuant k8v4 quality-equivalent enough for long-context practical use,
  assuming the workspace allocation bug is fixed?
- How much decode throughput is lost per offloaded KV block ratio on PCIe4?

## Stable Restore Command

If an experiment leaves the server down, restore the stable endpoint with:

```bash
pkill -f 'vllm serve' || true
VLLM_MAX_MODEL_LEN=32768 /home/steve/bin/minimax-vllm-serve
```

Expected `/v1/models`:

```json
{
  "id": "/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround",
  "max_model_len": 32768
}
```
