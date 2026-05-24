# Phase 1 XPU Primitive Probe

Date: 2026-05-24

Probe:

```bash
/home/steve/.venvs/vllm-xpu/bin/python \
  experiments/minimax_xpu_kv_offload/probes/xpu_stream_copy_probe.py \
  --sizes-mib 1 4 16 64 \
  --output experiments/minimax_xpu_kv_offload/xpu_stream_copy_probe_20260524.json
```

The normal `32768` MiniMax server was left running during this probe. This
kept the test conservative: it checked API availability and small pinned-copy
behavior without requiring large free VRAM.

## Result

Pass.

Runtime:

- PyTorch: `2.11.0+xpu`
- Device: `Intel(R) Arc(TM) Pro B70 Graphics`
- XPU device count: `4`

Available primitives:

- `torch.xpu.Stream`: yes
- `torch.xpu.stream(...)` context: yes
- `torch.xpu.Event`: yes
- `torch.xpu.current_stream()`: yes
- `torch.xpu.synchronize()`: yes
- pinned CPU allocation: yes

Pinned CPU round-trip copies passed for:

| Size | H2D event GB/s | D2H event GB/s | Correct |
| --- | ---: | ---: | --- |
| 1 MiB | 10.39 | 2.00 | yes |
| 4 MiB | 26.39 | 27.98 | yes |
| 16 MiB | 25.88 | 28.50 | yes |
| 64 MiB | 27.47 | 25.08 | yes |

The small 1 MiB case is dominated by fixed overhead. The 4-64 MiB cases show
roughly `25-28 GB/s`, which is in the range expected for high-end PCIe host
transfer paths and is promising for a CPU KV offload experiment.

Raw result:

`xpu_stream_copy_probe_20260524.json`

## Decision

The current PyTorch XPU runtime has enough basic stream/event/pinned-copy
surface to justify an XPU CPU KV worker prototype.

Do not port by deleting the CUDA-only guard and hoping the CUDA worker works.
The existing worker uses CUDA symbols directly. The next step should be an XPU
parallel implementation that mirrors the transfer handler structure while
using `torch.xpu` streams/events and pinned CPU tensors.

## Next Step

Create a narrow design/prototype for:

`vllm/v1/kv_offload/cpu/xpu_worker.py`

Initial prototype goal:

- allocate CPU KV pages with pinned CPU tensors
- flatten GPU KV cache tensors in the same shape as the CUDA worker
- copy selected block rows GPU -> CPU and CPU -> GPU
- run outside full vLLM first if possible
- then wire through `CPUOffloadingSpec` only after the transfer primitive is
  verified
