# 2026-05-25 Phase 3: XPU CPU KV Worker Live Server Notes

Goal: move beyond primitive copy probes and run vLLM's CPU KV offload path on
Intel Arc Pro B70/XPU with MiniMax M2.7.

Stable baseline preserved:

- Production recipe remains `32768` context, TP4, FP16-family KV, no CPU KV
  offload.
- Expected warm decode remains about `84-85 tok/s`.
- This phase did not replace `/home/steve/bin/minimax-vllm-serve` defaults.

## Prototype Patch

Patch artifact:

`patches/xpu-cpu-kv-worker-prototype-20260525.patch`

Main changes:

- Added `vllm/v1/kv_offload/cpu/xpu_worker.py`.
- Routed `CPUOffloadingSpec` to the XPU worker when
  `current_platform.is_xpu()`.
- Added a max-context admission patch that counts CPU KV offload bytes only
  for the startup preflight check, without inflating GPU KV allocation.
- Added an offload scheduler patch so a request can fence pending store jobs
  before issuing a later load job.
- Added optional `VLLM_KV_OFFLOAD_SYNC_LOADS=1` mode to test synchronous
  CPU-to-XPU loads, avoiding the async remote-KV wake path.

Important implementation detail:

- Contiguous logical block ranges use slice copies.
- Fragmented ranges fall back to a per-block loop for correctness.
- The earlier probe showed slice copies around `28 GB/s`; loop copies were
  only about `2.1-2.4 GB/s`.

## Launch Shape

Successful startup command shape:

```bash
VLLM_MAX_MODEL_LEN=49152 /home/steve/bin/minimax-vllm-serve \
  --kv-offloading-size 16 \
  --no-scheduler-reserve-full-isl
```

The `--no-scheduler-reserve-full-isl` flag is required for this experiment.
Without it, a long request can remain queued for `capacity` because the
scheduler tries to reserve the full input sequence in GPU KV before starting.

The same launch with `VLLM_KV_OFFLOAD_SYNC_LOADS=1` also starts and runs the
transfer path, but still does not complete generation.

Observed startup facts at `49152`, c1:

- `/v1/models` reports `max_model_len=49152`.
- GPU KV cache size: about `33792` tokens.
- CPU KV admission budget: `4.0 GiB` per worker from
  `--kv-offloading-size 16` and TP4.
- Cross-layer GPU KV tensor shape: `(132, 62, 2, 256, 2, 128)`.

## What Worked

Short prompt on the compiled 49K experimental server completed:

- Prompt: 12 tokens
- Output: 64 tokens
- Wall time: `0.903 s`
- Output rate: `70.88 tok/s`
- Total rate: `84.17 tok/s`

This is lower than the stable 32K warm decode lane, but confirms the server
can start and run short requests with the XPU KV offload connector present.

The long prompt transfer path also works mechanically:

- 1500 repeated lines tokenize to about `34500` tokens.
- The request crossed the GPU-only KV budget and triggered CPU spill/reload.
- Observed CPU-to-XPU KV load: `8.321499136 GB` total across four workers.
- Measured CPU-to-XPU transfer time from vLLM metrics: `0.508610908 s`.
- Effective aggregate transfer rate: about `16.4 GB/s` for that live path.
- GPU-to-CPU store traffic for the same experiment: `8.45152256 GB` in
  `0.779795848 s`, about `10.8 GB/s`.

These numbers prove the XPU worker can move multi-GB KV payloads through vLLM
without immediate data-path crashes.

## Current Blocker

Long prompt generation is not complete yet.

Async load mode:

- The 34.5K-token prompt stores KV blocks and completes CPU-to-XPU load jobs.
- The worker reports load completion and the scheduler sees
  `finished_recving`.
- The request remains stuck in `WAITING_FOR_REMOTE_KVS` / `deferred`.
- This appears to be a vLLM scheduler wake-up/bookkeeping issue for this
  local CPU KV offload use case.

Sync load mode:

- `VLLM_KV_OFFLOAD_SYNC_LOADS=1` avoids the async wait-state crash by waiting
  for CPU-to-XPU load before forward execution.
- The load completes and no `finished_recving` signal is emitted for running
  requests.
- The request then parks at `capacity` with GPU KV usage reported as `0%`.
- This points to another scheduler/accounting issue after spill reload, not a
  raw copy failure.

Representative logs:

- Async assertion-clearing run:
  `/mnt/fast-ai/bench-results/minimax-m27-b70-serve/serve-49152-c1-kvoffload16-xpuworker-schedulerflush-20260525T002025Z.log`
- Async completion-trace run:
  `/mnt/fast-ai/bench-results/minimax-m27-b70-serve/serve-49152-c1-kvoffload16-xpuworker-tracecompletion-20260525T002630Z.log`
- Sync-load run:
  `/mnt/fast-ai/bench-results/minimax-m27-b70-serve/serve-49152-c1-kvoffload16-xpuworker-syncloads2-20260525T003427Z.log`

## Next Engineering Step

The next useful patch is not another transfer kernel. The copy path has now
proven enough to focus on scheduler state.

Investigate:

- How `WAITING_FOR_REMOTE_KVS` requests are re-promoted when no other model
  execution is active.
- Whether local CPU KV offload should use the async remote-KV path at all.
- Why sync mode parks at `capacity` after a completed spill reload even though
  reported GPU KV usage is `0%`.
- Whether the scheduler should explicitly cache/promote loaded blocks for this
  local connector, instead of depending on the remote KV transfer lifecycle.

Do not promote the CPU KV offload lane until a long prompt above GPU-only KV
capacity returns a valid completion.
