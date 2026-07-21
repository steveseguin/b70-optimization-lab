# K160 EAGLE five-epoch XPU-1 long-haul

Date: 2026-07-21

Status: **RUNNING DETACHED; first checkpoint and full DEV gate verified**.

## Numbers first

- Run directory:
  `/media/steve/CorsairExternal/llm-optimization-artifacts/deepseek-v4-eagle-signal-20260719T210100Z/training/single-card-longhaul-20260721T133541Z`.
- Detached supervisor PID: **1963836**. Current single Python worker PID:
  **1963843**.
- XPU verification: XPU-smi DeviceID **1**, worker `xpu:0` inside the mask,
  only `/dev/dri/renderD131` open, PCI `0000:27:00.0`, no DDP/process group,
  no rank/CCL/preload environment. Cards 2 and 3 remained occupied by their
  separate telemetry kernels.
- First checkpoint: global step **76,977**, continuation step 3,000,
  **615,816** cumulative anchors, epoch **0.6243268233**, atomic checkpoint
  size 1.1 GiB.
- First complete disjoint-DEV gate over **49,142** anchors:
  P1-P7 conditional acceptance = **55.9481%, 51.6040%, 58.2957%, 65.4697%,
  67.2761%, 67.0876%, 66.9804%**; mean conditional P2-P7 = **62.7856%**;
  overall = **18.3410%**; checkpoint-interval mean loss = **2.914232**.
  `go_signal=false`.
- Full DEV took **383.887 seconds**. Training then resumed on the same worker;
  the post-eval check observed global step 77,051 and only renderD131.
- Durable DEV metrics:
  `/media/steve/CorsairExternal/llm-optimization-artifacts/deepseek-v4-eagle-signal-20260719T210100Z/training/single-card-longhaul-20260721T133541Z/metrics.jsonl`.
- Clean STOP sentinel:
  `/media/steve/CorsairExternal/llm-optimization-artifacts/deepseek-v4-eagle-signal-20260719T210100Z/training/single-card-longhaul-20260721T133541Z/STOP`.
- Launcher implementation commit: `2cabed9a7c11b89643adb1da82693be076ed0b1a`;
  proven-environment correction: `3e5ecb1993d62d84aead14f95ab00af11f9edfc1`.

## Plan and immutable scope

- Device: physical B70 1 only, PCI `0000:27:00.0`, render node
  `/dev/dri/renderD131`; `ZE_AFFINITY_MASK=1` exposes it as trainer `xpu:0`.
- No DDP, torchrun, process group, oneCCL variables, or `LD_PRELOAD`.
- Eager BF16 autocast with FP32 parameters and AdamW state, recursive
  non-reentrant activation checkpointing, and a 60-second synchronized
  optimizer-step watchdog.
- Warm start:
  `/media/steve/CorsairExternal/llm-optimization-artifacts/deepseek-v4-eagle-signal-20260719T210100Z/training/single-card-signal-20260720T181607Z/train-bf16-b8-ga1/head-best-mean-p2-p7.pt`.
- Starting state: global step 73,977, 591,816 anchors, 0.599995 epoch.
- The old checkpoint lacks a serialized data cursor. The long-haul worker
  deterministically reconstructs the seed-160719 shard/anchor order and
  advances it by 591,816 anchors without materializing model inputs before the
  first update, so the continuation does not replay the earlier corpus prefix.
- Continuation: 542,503 updates at eight anchors/update, ending at global step
  616,480, 4,931,840 cumulative anchors, exactly 5.0 epochs of the 986,368
  eligible-anchor corpus.
- LR: continuation-local 3% linear warmup to `2e-4`, cosine decay to `2e-5`
  over the remaining 542,503 steps; AdamW `(0.9, 0.95)`, weight decay 0.05,
  global gradient clip 1.0.
- Checkpoint: every 3,000 continuation steps. Each atomic checkpoint contains
  model, optimizer, global/run step, exact shuffled shard/anchor cursor, RNG,
  LR schedule identity, cumulative anchors, and data/model identities.
- DEV: complete disjoint 49,142-anchor DEV evaluation at every checkpoint,
  batch 64, with a 120-second watchdog on each evaluation batch. The frozen
  held-out `quality/` packs are out of scope and must not be accessed.
- Recovery: run-local and host-global XPU-1 locks ensure at most one long-haul
  supervisor and one Python worker, the supervisor restarts a failed worker,
  and the worker selects the newest intact checkpoint. The full training/LR/
  cadence contract must match exactly on resume. If a
  crash occurs after checkpoint persistence but before its DEV row, restart
  completes that missing evaluation before training resumes.
- Clean stop: create the run-local `STOP` sentinel. The worker checks between
  optimizer steps and before further training; a sentinel arriving during an
  interval causes an atomic checkpoint and full DEV evaluation after the
  current step, then clean exit.

## Monitoring contract

The stable interfaces are:

- `metrics.jsonl`: one durable JSON row per checkpoint with `step`, `anchors`,
  `epoch`, `P1`, `mean_cond_P2_P7`, `overall`, `loss`, P1-P7 conditionals,
  paths, timing, LR, and the GO flag;
- `training-metrics.jsonl`: append-only per-attempt optimizer-step telemetry;
- `latest-checkpoint.json`: atomic pointer metadata for the newest checkpoint;
- `STOP`: operator-created clean-stop sentinel;
- `supervisor.pid` and `trainer.pid`: detached supervisor and current worker;
- `supervisor.log`, `worker.log`, and `events.jsonl`: restart/runtime evidence.

The first shared-host interval took about 14.4 minutes of training per 3,000
updates, plus 6.4 minutes for full DEV and checkpoint I/O: approximately 21
minutes per published `metrics.jsonl` row. At that observed cadence, the full
remaining plan is roughly 2.5-3 days. Claude should use the live row cadence,
not the earlier solo-card throughput projection.

Read the latest compact gate with:

```bash
tail -n 1 /media/steve/CorsairExternal/llm-optimization-artifacts/deepseek-v4-eagle-signal-20260719T210100Z/training/single-card-longhaul-20260721T133541Z/metrics.jsonl \
  | jq '{step, anchors, epoch, P1, mean_cond_P2_P7, overall, loss, go_signal}'
```

Request a clean stop with:

```bash
touch /media/steve/CorsairExternal/llm-optimization-artifacts/deepseek-v4-eagle-signal-20260719T210100Z/training/single-card-longhaul-20260721T133541Z/STOP
```

After the supervisor has exited, resume from the newest intact checkpoint with:

```bash
rm -f /media/steve/CorsairExternal/llm-optimization-artifacts/deepseek-v4-eagle-signal-20260719T210100Z/training/single-card-longhaul-20260721T133541Z/STOP
cd /home/steve/llm-optimizations
RUN_DIR=/media/steve/CorsairExternal/llm-optimization-artifacts/deepseek-v4-eagle-signal-20260719T210100Z/training/single-card-longhaul-20260721T133541Z \
  experiments/deepseek-v4-flash-reap-xpu-b70/scripts/launch-k160-eagle-longhaul-xpu1.sh
```

Claude should apply these later decisions only to the DEV `metrics.jsonl`:

- **GO:** `mean_cond_P2_P7 > 0.75` and `overall > 0.40`.
- **Kill:** `mean_cond_P2_P7` has no improvement greater than 0.005 for at
  least two consecutive epochs while remaining below 0.72.

No LocalMaxxing action is part of this run.

## Initial launch correction

The first detached attempt at `2026-07-21T13:35:41Z` failed closed before XPU
allocation: sourcing standalone oneAPI compiler/MKL/DNNL environment fragments
made PyTorch report zero visible XPUs. The supervisor was stopped after two
failed discovery attempts; no optimizer step or checkpoint occurred. The
known-good signal-run environment did not source those fragments. A direct
probe with its exact scrubbed environment, `ZE_AFFINITY_MASK=1`, and
`ONEAPI_DEVICE_SELECTOR=level_zero:*` reported `torch.xpu.is_available=true`,
`device_count=1`, and Intel Arc Pro B70. The launcher now uses that exact
direct-venv environment.
