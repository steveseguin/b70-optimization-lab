# Qwen3.6 XPU Tiny D2H Token Copy Isolation

Date: 2026-06-12

Purpose: isolate the c1 async-output token-id copy shape after vLLM timing
showed `async_copy_ready_event.synchronize()` taking about `3.8 ms` per token.
The copied payload in the live c1 path is only an `int32` token tensor, so this
bench checks whether the raw XPU-to-host copy can plausibly explain that wait.

Artifacts:

- `scripts/bench-xpu-d2h-token-copy.py`
- `data/qwen36-xpu-d2h-token-copy-20260612by.json`
- `data/qwen36-xpu-d2h-token-copy-xpu3-20260612by.json`

Runtime:

- Python: `/home/steve/.venvs/vllm-xpu/bin/python`
- Torch: `2.11.0+xpu`
- Current service left running on `127.0.0.1:18080`
- Main run: `xpu:0`, shapes `1x1`, `1x8`, `1x32`, `48x1`,
  warmup `200`, iterations `3000`
- Cross-check: `xpu:3`, shapes `1x1`, `48x1`, warmup `100`,
  iterations `1000`

Key medians, pinned host destination:

| Device | Shape | `.to("cpu")` | NB copy+event | NB p99 | side-stream NB | blocking copy+sync |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `xpu:0` | `1x1` | `0.009047 ms` | `0.010019 ms` | `0.016331 ms` | `0.016391 ms` | `0.033042 ms` |
| `xpu:0` | `1x8` | `0.009628 ms` | `0.010530 ms` | `0.017353 ms` | `0.016641 ms` | `0.033493 ms` |
| `xpu:0` | `1x32` | `0.013244 ms` | `0.014227 ms` | `0.021300 ms` | `0.020248 ms` | `0.037199 ms` |
| `xpu:0` | `48x1` | `0.020538 ms` | `0.011431 ms` | `0.018799 ms` | `0.017854 ms` | `0.036878 ms` |
| `xpu:3` | `1x1` | `0.008886 ms` | `0.010299 ms` | `0.016627 ms` | `0.016140 ms` | `0.033202 ms` |
| `xpu:3` | `48x1` | `0.020618 ms` | `0.011722 ms` | `0.020649 ms` | `0.017302 ms` | `0.043286 ms` |

Baselines:

- Empty event median: about `0.003 ms`.
- Empty `torch.xpu.synchronize(device)` median: about `0.025 ms`.
- Plain CPU destinations were similar to pinned destinations for these tiny
  shapes.

Interpretation:

- The isolated tiny token copy is not the `~3.8 ms` async-output wait. For the
  exact `1x1` shape, the nonblocking copy plus event wait median is about
  `0.010 ms` and p99 about `0.016-0.017 ms`, or roughly `200-380x` smaller
  than the live vLLM event wait.
- Reusing the CPU buffer or avoiding `.tolist()` can no longer be considered a
  likely multi-millisecond win. Prior vLLM diagnostics already showed list
  conversion around `0.010 ms`; this isolated run confirms the raw copy/event
  path is also microsecond-scale.
- The live `async_copy_ready_event.synchronize()` wait is probably exposing
  upstream queue dependencies: model-forward tail work, sampler/logits work,
  graph/event ordering, rank synchronization, or worker-result handoff.

Next target:

Add a device/worker timeline around sampler output, D2H copy submission,
event record, worker response enqueue, and EngineCore future completion. The
copy itself is not worth optimizing until a device timeline proves otherwise.
