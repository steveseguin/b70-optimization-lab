# Phase 2 XPU KV Block Copy Probe

Date: 2026-05-24

Probe:

```bash
/home/steve/.venvs/vllm-xpu/bin/python \
  experiments/minimax_xpu_kv_offload/probes/xpu_kv_block_copy_probe.py \
  --mode slice \
  --transfer-blocks 64 256 1024 \
  --output experiments/minimax_xpu_kv_offload/xpu_kv_block_copy_probe_20260524-slice.json
```

The normal `32768` MiniMax server was left running. The probe used modest
working-set sizes so it would not disturb the production endpoint.

## What The Probe Models

The probe models the core CPU KV offload movement:

- GPU/XPU KV pages as `int8` rows.
- Pinned CPU backing pages.
- `block_size_factor=2`, so one CPU row holds two GPU-sized logical blocks.
- Odd logical offset `1`, so the test exercises sub-block placement rather
  than only aligned CPU block boundaries.
- GPU -> CPU store and CPU -> GPU load.
- Exact byte comparison after round trip.

## Results

Loop mode:

- Correct.
- About `2.1-2.4 GB/s`.
- Too slow for a real worker except as a simplest correctness fallback.

Indexed scatter mode:

- Not usable as written.
- `cpu_view[indices].copy_(...)` writes into a temporary rather than the CPU
  backing tensor.
- `index_copy_` rejects cross-device source/destination on this XPU build.

Slice mode:

- Correct.
- Uses a logical CPU view:

```python
cpu_view = cpu_tensor.view(num_cpu_blocks * block_size_factor, page_size)
```

- Then copies contiguous logical ranges directly between XPU and pinned CPU
  slices.

Measured event rates:

| Transfer blocks | Bytes one-way per timed region | Store GPU->CPU | Load CPU->GPU | Correct |
| ---: | ---: | ---: | ---: | --- |
| 64 | 16 MiB | 17.33 GB/s | 23.59 GB/s | yes |
| 256 | 64 MiB | 27.94 GB/s | 27.77 GB/s | yes |
| 1024 | 256 MiB | 28.45 GB/s | 28.59 GB/s | yes |

Raw artifacts:

- `xpu_kv_block_copy_probe_20260524.json`: loop-mode correctness baseline.
- `xpu_kv_block_copy_probe_20260524-indexed-fail.json`: failed indexed
  scatter attempt.
- `xpu_kv_block_copy_probe_20260524-slice.json`: correct high-throughput
  slice result.

## Decision

An XPU CPU KV worker looks feasible for contiguous logical block ranges using
plain PyTorch pinned-memory slice copies on `torch.xpu.Stream`.

The first worker prototype should not try to port vLLM's CUDA
`swap_blocks_batch` path directly. It should start with:

- contiguous logical range detection
- fast slice copies for contiguous ranges
- loop fallback for fragmented ranges
- later replacement of fragmented copies with a custom XPU batch-copy kernel

This gives a practical path to a correct c1 long-context prototype before
optimizing for heavily fragmented concurrent workloads.

## Next Step

Create an experimental XPU handler design for:

`vllm/v1/kv_offload/cpu/xpu_worker.py`

Initial worker behavior:

- Flatten canonical KV tensors to `(num_gpu_blocks, page_size_bytes)`.
- Allocate pinned CPU tensors with
  `(num_cpu_blocks, page_size_bytes * block_size_factor)`.
- In transfer planning, coalesce consecutive logical block IDs into ranges.
- Use slice copies for coalesced ranges.
- Fall back to the proven loop path for non-contiguous or partial groups.
- Keep timing and byte counters so LocalMaxxing-style notes can report CPU KV
  transfer pressure.
