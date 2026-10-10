# Packet 124 — coordinator reference, not executed

Packet: `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-124`.
Manifest SHA256: `897442d035728c35a923840046c51c1bd43cad5097e4807c59e6d786699926a5`.
Inner plan SHA256: `71fc6e9bb1e9f38f2edf3e77f6cd71b36805586cdbe88ac891fbd1838572da68`.
Seal and validation are recorded in the
[build receipt](../../data/resume-20261008/continuation124-build.json).
`launch-124.sh` uses the baseline venv's **bin/python -B**; no launcher, check-only,
health probe, unit or live endpoint was operated during preparation.

The coordinator owns fresh health evidence, idle-card admission, archiving any
previous packet124 names, and every server/client operation. Use one arm per
explicit comparison; never run these lines together or retry a failed launch.
Keep all byte/memory gates. A refusal is evidence, not permission to lower a floor.

## Order and forecasts

All arms use frame/cone, dg0, B overlap1, A prep1, fingerprint snapshots with
full barriers, read-ahead0, sampler20/28. Margins are GiB above card0/1/2/3 floors.

| Order | Arm | Period / s per video s | Margins0/1/2/3 |
|---|---|---|---|
| 1 | 145, legacy auxiliaries, replica2, serial placement control | 5.50–6.10 / 0.917–1.017 | 1.270 /1.828 /3.070 /1.850 |
| 2 | 145, same, parallel completion with early audio | 5.50–6.10 / 0.917–1.017 | 1.270 /1.828 /3.070 /1.850 |
| 3 | 169, same parallel path, 6.5 GiB replica reserve | **6.20–6.65 /0.886–0.950**, central6.30/0.900 | **1.340 /1.798 /2.210 /1.809** |
| Optional diagnostic | 169, same replica placement, serial worker | 6.65–7.15 /0.950–1.021 | 1.340 /1.798 /2.210 /1.809 |

These are projections. The adverse169 parallel range is6.65–7.20/0.950–1.029.
Require <6.685 s to beat the current0.955 line, <6.573 to beat the older0.939 line.
145 qualifies the placement against saved same-length bytes, then the reorder;
169 must qualify all three chains including parallel repeat. Measure two fresh
qualified servers before a speed verdict, at coordinator-selected opportunities.
Measure display and sink completion within the chunk period, full snapshot
latency, FIFO depth and per-phase physical free; do not count buffered playback
as proof of production rate. Auxiliaries→1 is refused by static margin; deferred
same-card display misses the sink latency constraint. Neither is a launch arm.

## Command grammar

Supply the coordinator's fresh receipt as the last required argument. These are
future command examples only. Set matching server/client environment options.
The allowance16 matches tonight's coordinator choice; packet default remains3.

145 placement control:

```bash
LTX_AUX_RESIDENCY=legacy LTX_DISPLAY_WORKER=serial LTX_RUN_WRITE_ALLOWANCE_GIB=16 \
  ./launch-124.sh 145 frame 0 cone 1 1 fingerprint - eager-display 0 full xpu:2 "$RECEIPT"
```

145 reordered candidate (after control qualification):

```bash
LTX_AUX_RESIDENCY=legacy LTX_DISPLAY_WORKER=parallel LTX_RUN_WRITE_ALLOWANCE_GIB=16 \
  ./launch-124.sh 145 frame 0 cone 1 1 fingerprint - eager-display 0 full xpu:2 "$RECEIPT"
```

169 candidate (after145 qualifies):

```bash
LTX_AUX_RESIDENCY=legacy LTX_DISPLAY_WORKER=parallel \
LTX_DISPLAY_REPLICA_TRANSIENT_GIB=6.5 LTX_RUN_WRITE_ALLOWANCE_GIB=16 \
  ./launch-124.sh 169 frame 0 cone 1 1 fingerprint - eager-display 0 full xpu:2 "$RECEIPT"
```

The optional169 serial diagnostic uses the same command with
`LTX_DISPLAY_WORKER=serial`. No change to seed, precision, model or output shapes.
The replica budget may only increase from its length floor, with maximum8 GiB.
For145 omit it to keep5.640625 GiB;169 already defaults6.5 GiB.

Corresponding client, from the lane's `stream/` directory:

```bash
LTX_AUX_RESIDENCY=legacy LTX_DISPLAY_WORKER=parallel \
LTX_DISPLAY_REPLICA_TRANSIENT_GIB=6.5 LTX_RUN_WRITE_ALLOWANCE_GIB=16 \
  ./start-client-124.sh 169 0 cone 1 1 fingerprint none eager-display 0 full xpu:2
```

For145 substitute145 and omit the169 reserve; match serial/parallel to the server.
`LTX_STREAM_WORKDIR` defaults `/home/steve/ltx-stream/s124-live01`; the coordinator
selects fresh work directories for subsequent arms, for example
`s124-f145-parallel` and `s124-f169-parallel`. This task creates none of them.
Client expectation includes inner plan SHA, manifest/module pins, residency,
worker, reserve and disk allowance. The plan's byte hash is not a client plan pin.

## Disabled forms

`LTX_DISPLAY_WORKER=serial` retains the123b decode order and completion policy.
With `LTX_DISPLAY_DEVICE=xpu:3` the display replica is absent. The existing145/169
`LTX_AUX_RESIDENCY=xpu2`, serial worker, display3 path remains admissible;
169 legacy plus display3 remains refused. Auxiliaries and display cannot both
occupy2, and145/169 dg1 replicas remain refused. No automatic mode fallback.

After any failure the coordinator handles the saved latch and live state. This
packet does not launch, stop, restart, reset or restore a service automatically.
