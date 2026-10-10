# Packet 123 launch reference — coordinator only

Text for later coordinator-selected windows. Nothing here was launched, queued,
or run with `--check-only` during CPU preparation. The coordinator owns health
admission, the existing live server and all lifecycle/collision decisions.
Never lower a floor or retry a failed arm automatically.

Packet: `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-123`.
Manifest `db5ea277d381c8a77c1bae94cc4e25b1e22035a084a7e3a33b7d10e5d68b340d`
is pinned in the server wrapper and client packet table, and recorded in the
[build receipt](../../data/resume-20261008/continuation123-build.json).

Commands below are relative to `experiments/ltx25-b70/`.
Both wrappers retain 122 positional grammar and use
`/home/steve/.venvs/ltx25-baseline/bin/python -B`. New environment option:
`LTX_AUX_RESIDENCY=legacy|xpu2`, default `legacy`. Set it identically for server
and client. `xpu2` moves the native upsampler and audio VAE/vocoder to card2;
its run basename gains `-auxxpu2`. All recommended arms use dg0, read-ahead 0,
full snapshots and display xpu:3. The client defaults `LTX_STREAM_WORKDIR` to
`/home/steve/ltx-stream/s123-live01`; preparation never writes there.

1. **145-frame control with atomic previews, legacy residency.** Predicted
   repeat band 5.45–6.10 s per 6.0 s new video =0.908–1.017 s/s. Recorded 121 control
   margins 0/1/2/3: 1.270/ 1.828/ 9.706/ 1.850 GiB above 8/8/2/9 floors.

```bash
LTX_AUX_RESIDENCY=legacy recovery/20261010-continuation123-stream/launch-123.sh 145 frame 0 cone 1 1 fingerprint - sampler-a 0 full xpu:3 /absolute/coordinator-health-receipt.json
LTX_AUX_RESIDENCY=legacy stream/start-client-123.sh 145 0 cone 1 1 fingerprint none sampler-a 0 full xpu:3
```

2. **145 frames, auxiliary residency.** Require three-chain qualification and
   byte equality to the frozen 121 eager hashes, then every live anchor/display
   check. Predicted 5.45–6.20 s =0.908–1.033 s/s; margins 2.198/ 1.828/ 6.439/ 2.189 GiB
   including 2 GiB new workspace allowance on 2. Measure actual savings and
   retained allocations before the third arm. Use a fresh coordinator-chosen
   work directory and resolve existing 123 output-name collisions under the
   normal procedure. These wrappers do not archive or overwrite evidence.

```bash
LTX_AUX_RESIDENCY=xpu2 recovery/20261010-continuation123-stream/launch-123.sh 145 frame 0 cone 1 1 fingerprint - sampler-a 0 full xpu:3 /absolute/coordinator-health-receipt.json
LTX_AUX_RESIDENCY=xpu2 LTX_STREAM_WORKDIR=/home/steve/ltx-stream/s123-aux145-live01 stream/start-client-123.sh 145 0 cone 1 1 fingerprint none sampler-a 0 full xpu:3
```

3. **169 frames, auxiliary residency, conditional on the 145 evidence.**
   Predicted 5.95–6.65 s per 7.0 s new video =0.850–0.950 s/s (central 6.2 s/ 0.886 s/s).
   Margins 1.620–1.930/ 1.574–1.711/ 6.439/ 0.825–1.557 GiB. The low card 3 margin is
   only 0.075 GiB beyond the screening requirement. Actual memory, geometry and
   exact-output gates can refuse this forecast. Use a new work directory.

```bash
LTX_AUX_RESIDENCY=xpu2 recovery/20261010-continuation123-stream/launch-123.sh 169 frame 0 cone 1 1 fingerprint - sampler-a 0 full xpu:3 /absolute/coordinator-health-receipt.json
LTX_AUX_RESIDENCY=xpu2 LTX_STREAM_WORKDIR=/home/steve/ltx-stream/s123-aux169-live01 stream/start-client-123.sh 169 0 cone 1 1 fingerprint none sampler-a 0 full xpu:3
```

169 display is forecast 2.72–3.30 s; a separate 3 s display target remains unproved.
The inherited 3 s successor-wait deadline is unchanged. Auxiliary+display replica
is refused because its combined workspace estimate does not fit. 145 dg1 replica
is also refused. There is no recommended graph or replica fallback command.

Collect all nine qualification chunks, exact geometry and cross-packet 145
hashes; per-chunk cone/display checks, physical-free readings and auxiliary
workspace receipts; at least 100 interior periods, preview failures/status
snapshots and display durations. CPU tests establish source/control behavior;
full-model exactness, actual headroom and speed await these coordinator runs.
[Design and limitations](../../notes/2026-10-10-continuation123-stream-design.md).
