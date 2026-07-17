# TP4 M=2 finite event-chain closure

Date: 2026-07-17

## Outcome

The default-off direct oneCCL event chain is exact, but it fails the reusable
graph performance gate and is closed before service integration. Two strict
40-epoch eager runs save `5.601488` and `5.697565 ms/cycle`, including a
`100 us` per-rank arrival skew. Once both paths are captured at fixed
addresses, the saving collapses to only **`0.109546 ms/cycle`**:

- ordinary captured XCCL plus native M=2 MHC: `4.265725 ms`;
- direct event-chain graph: `4.156179 ms`;
- required saving: `0.50 ms/cycle`.

All 87 reduced BF16 `[2,4096]` tensors and all four outputs from all 85 MHC
consumers remain bitwise exact. The graph itself is reusable and exact; the
failure is performance, not correctness.

## What was implemented

The isolated oneCCL commit `9636514` adds a default-off TP4/BF16/SUM/count-8192
bridge. It retains oneCCL-owned communicator/stream identity after an ordinary
XCCL warmup, accepts a producer `sycl::event`, submits the unchanged Arc LL
ring on the supplied PyTorch queue, and returns the ring event. It also keeps
the earlier repair that threads producer dependencies into the ring.

The isolated XPU-kernel commit `a609e1f` adds the fixed M=2 operation
`tp4_oneccl_allreduce_mhc_post_pre_m2_out`. It submits a producer barrier,
calls the bridge, and launches the native M=2 MHC consumer dependent on the
ring event. Reduced storage is persistent and distinct from the producer. The
gate places a separate one-BF16 completion witness after every consumer.

The exact binaries are:

- oneCCL SHA-256
  `5783f343dfffa441ff5bf10c083739b0c014934991324c7567efdf9408861e93`;
- XPU extension SHA-256
  `5df3e93f08896f9cf7bb7024174f1cc3e1174786cd0cc2dcf4fcd5c271449309`.

## Why the eager result was misleading

The direct hook bypasses 85 Python/c10d collective submissions, so it produces
a large and real eager-only improvement. Production decode, however, already
uses reusable command-graph replay. Capturing the ordinary comparator removes
the same host submission cost. The direct chain therefore changes very little
device work and retains only a `0.109546 ms` advantage.

This is exactly why the fixed-address graph gate exists. Promoting from eager
timing would have claimed roughly 5.6 ms that the production path had already
eliminated.

## Decision

Do not run the 70-replay or full-model service gates and do not add this
candidate to a micro-win portfolio: its graph-replay floor is below the
`0.50 ms/cycle` admission threshold. Preserve the source commits, runtime,
gate script, and raw results. Future TP4 work must remove collective/device
work or fuse producer/consumer arithmetic; merely bypassing framework
submission is closed.

Raw evidence:

- `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/tp4-m2-event-chain-eager-gate-20260717T0625Z`;
- `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/tp4-m2-event-chain-eager-skew100us-20260717T0641Z`;
- `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/tp4-m2-event-chain-graph-probe-20260717T0647Z`.
