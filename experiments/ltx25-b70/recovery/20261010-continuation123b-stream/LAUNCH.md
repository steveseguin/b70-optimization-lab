# Packet 123b launch reference — coordinator only

Text for later coordinator-selected windows. Nothing here was launched, queued,
or run with `--check-only` during CPU preparation. The coordinator owns health
admission, the existing live server and all lifecycle/collision decisions.
Never lower a floor or retry a failed arm automatically.

Packet: `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-123b`.
Manifest `5bdc0956f69259a99ca82849280e73b8bd2a80e28ff421ce5d61122e8a74d433`
is pinned in the server wrapper and client packet table, and recorded in the
[build receipt](../../data/resume-20261008/continuation123b-build.json).

Commands below are relative to `experiments/ltx25-b70/`.
Both wrappers retain 123 positional grammar and use
`/home/steve/.venvs/ltx25-baseline/bin/python -B`. Inherited environment option:
`LTX_AUX_RESIDENCY=legacy|xpu2`, default `legacy`. Set it identically for server
and client. `xpu2` moves the native upsampler and audio VAE/vocoder to card2;
its run basename gains `-auxxpu2`. All recommended arms use dg0, read-ahead 0,
full snapshots and display xpu:3. The client defaults `LTX_STREAM_WORKDIR` to
`/home/steve/ltx-stream/s123b-live01`; preparation never writes there.

1. **145-frame control with atomic previews, legacy residency.** Predicted
   repeat band 5.45–6.10 s per 6.0 s new video =0.908–1.017 s/s. Recorded 121 control
   margins 0/1/2/3: 1.270/ 1.828/ 9.706/ 1.850 GiB above 8/8/2/9 floors.

```bash
LTX_AUX_RESIDENCY=legacy recovery/20261010-continuation123b-stream/launch-123b.sh 145 frame 0 cone 1 1 fingerprint - sampler-a 0 full xpu:3 /absolute/coordinator-health-receipt.json
LTX_AUX_RESIDENCY=legacy stream/start-client-123b.sh 145 0 cone 1 1 fingerprint none sampler-a 0 full xpu:3
```

2. **145 frames, auxiliary residency.** Require three-chain qualification and
   byte equality to the frozen 121 eager hashes, then every live anchor/display
   check. Predicted 5.45–6.20 s =0.908–1.033 s/s; margins 2.198/ 1.828/ 6.439/ 2.189 GiB
   including 2 GiB new workspace allowance on 2. Measure actual savings and
   retained allocations before the third arm. Use a fresh coordinator-chosen
   work directory and resolve existing 123b output-name collisions under the
   normal procedure. These wrappers do not archive or overwrite evidence.

```bash
LTX_AUX_RESIDENCY=xpu2 recovery/20261010-continuation123b-stream/launch-123b.sh 145 frame 0 cone 1 1 fingerprint - sampler-a 0 full xpu:3 /absolute/coordinator-health-receipt.json
LTX_AUX_RESIDENCY=xpu2 LTX_STREAM_WORKDIR=/home/steve/ltx-stream/s123b-aux145-live01 stream/start-client-123b.sh 145 0 cone 1 1 fingerprint none sampler-a 0 full xpu:3
```

3. **169 frames, auxiliary residency, conditional on the 145 evidence.**
   Predicted 5.95–6.65 s per 7.0 s new video =0.850–0.950 s/s (central 6.2 s/ 0.886 s/s).
   Margins 1.620–1.930/ 1.574–1.711/ 6.439/ 0.825–1.557 GiB. The low card 3 margin is
   only 0.075 GiB beyond the screening requirement. Actual memory, geometry and
   exact-output gates can refuse this forecast. Use a new work directory.

```bash
LTX_AUX_RESIDENCY=xpu2 recovery/20261010-continuation123b-stream/launch-123b.sh 169 frame 0 cone 1 1 fingerprint - sampler-a 0 full xpu:3 /absolute/coordinator-health-receipt.json
LTX_AUX_RESIDENCY=xpu2 LTX_STREAM_WORKDIR=/home/steve/ltx-stream/s123b-aux169-live01 stream/start-client-123b.sh 169 0 cone 1 1 fingerprint none sampler-a 0 full xpu:3
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
[Design and limitations](../../notes/2026-10-10-continuation123b-storage.md).

## 123b grammar change

The positional arguments are unchanged; only the filenames and optional
allowance environment variable change:

```text
[LTX_RUN_WRITE_ALLOWANCE_GIB=N] [LTX_AUX_RESIDENCY=legacy|xpu2] launch-123b.sh <frames> <anchor> <dg> <ad full|cone> <bo> <pa> <sm walk|fingerprint> <pool cap GB|-> <display sampler-a|sampler-b|eager-display> <read-ahead 0|1> <snapshot full|a-xpu3-sync> <display-device xpu:3|xpu:2> <receipt> [--check-only]
[LTX_RUN_WRITE_ALLOWANCE_GIB=N] [LTX_AUX_RESIDENCY=legacy|xpu2] stream/start-client-123b.sh <frames> <dg> <ad> <bo> <pa> <sm> <cap|none> <display> <read-ahead> <snapshots> <display-device> [client args]
```

N is an integer GiB from 1 through 64; omitting it means 3. Set it identically
for server and client. The wrapper supplies `--expect-run-write-allowance-gib N`.
The server unit is `ltx123b-stream-server-20261010`. These are future coordinator
commands only: no launch, preflight, unit or port operation was executed here.
See [storage contract](CONTRACT.md#packet-123b-storage-contract).
