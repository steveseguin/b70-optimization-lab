# Packet 121 launch reference — text only

Coordinator action only, after the coordinator's ordinary independent admission.
No launch, `--check-only`, GPU operation, port/unit operation, process signal or
write under an existing run or `/home/steve/ltx-stream` was made by this CPU task.

Packet: `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-121`.
Manifest: **8f1d4e3b5b8ca79f79a43b9a6f0acec252e58fdde72b92ffb5ea0743f71444dd**.
Parent120: `9af9330b7b9f08ad5c3b88d38b5c3f66186fab583d3b810afad7f0d61c5c328e`.

The safer first arm at145 is **dg0 with display on xpu:3**. It isolates chunk
length on118b's better measured schedule. dg1 cap1.0 plus the xpu:2 replica is
an optional later experiment: mandatory xpu:3 qualification references may retain
enough memory to refuse the larger shape. No automatic fallback is provided.

Future command from repository root (not executed):

```bash
experiments/ltx25-b70/recovery/20261010-continuation121-stream/launch-121.sh 145 frame 0 cone 1 1 fingerprint - sampler-a 0 full xpu:3 "$FRESH_HEALTH_RECEIPT"
```

Matching future client (not executed):

```bash
experiments/ltx25-b70/stream/start-client-121.sh 145 0 cone 1 1 fingerprint none sampler-a 0 full xpu:3
```

`LTX_STREAM_WORKDIR` defaults to `/home/steve/ltx-stream/s121-live01`; this task
has not created it. Both wrappers call the fingerprinted `bin/python -B`, with
OMP_NUM_THREADS=4 and MKL_NUM_THREADS=4. Syntax checking uses `bash -n` only.

Server grammar remains `frames anchor dg ad bo pa sm cap display read-ahead
snapshot display-device receipt [mode]`. Client omits anchor (fixed frame),
receipt and mode. Server cap`-` unsets ambient cap; client cap`none` expects none.
The inherited optional mode parser remains; neither launch nor preflight was
executed. Run/unit/names use121. Existing shared fault/lever latches, collisions,
storage and health requirements are retained without retries or restarts.

Admitted frame lengths49/97/121/145. **169 is refused** pending better measured
sampler memory evidence. Optional xpu:2 display accepts121/145 only, frame/cone/
eager-display, with the enlarged allowance and all nine full-image comparisons.
For an explicitly selected later145 replica arm, server arguments are
`145 frame 1 cone 1 1 fingerprint 1.0 eager-display 0 full xpu:2 "$FRESH_HEALTH_RECEIPT"`;
client arguments are `145 1 cone 1 1 fingerprint 1.0 eager-display 0 full xpu:2`.

Predicted first-arm period5.55–6.10s (central5.75):0.919–1.010s per nominal video
second, or0.925–1.017 per new anchored second. This is a hypothesis, not a speed
claim. After qualification, measure at least100 interior chunks after the first10,
then repeat on a separately admitted fresh run before a speed verdict. Require
exact bytes, measured geometry, unmodified floors, all-card peak/free evidence,
no hidden snapshot or FIFO cost, and owner seam/audio review. No GPU action or
continued experiment is authorized by this preparation document.
