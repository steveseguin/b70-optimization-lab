# Packet119 launch reference — coordinator only, text not executed in this task

This CPU task did not operate a server, port, unit or device. The coordinator
owns the live118b server and any future controlled transition. Existing fault,
health, latch, storage, name-collision and owner rules remain. No automatic retry,
restart or restore is added. [Design](../../notes/2026-10-10-continuation119-stream-design.md).

Packet: `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-119`.
Manifest: **d4b99d333f8193fc74041290b3cc3ebc7309b73836323997d14271a9aa246890** (also pinned in launch-119.sh and the client).
Parent118b: `248e762de49d21b02a4f95d3791dbd9da7504b731f1a88cb5a930a78448db1f1`.

Both wrappers call `/home/steve/.venvs/ltx25-baseline/bin/python -B`.
`bin/python3` is not the fingerprinted executable. Both set OMP_NUM_THREADS=4
and MKL_NUM_THREADS=4. Do not execute either wrapper just to test parsing.

## Recommended first arm (fresh health receipt required)

From the repository root, future command only:

```bash
experiments/ltx25-b70/recovery/20261010-continuation119-stream/launch-119.sh 121 frame 1 cone 1 1 fingerprint 1.0 eager-display 1 full "$FRESH_HEALTH_RECEIPT"
```

This keeps graph cone decoding, restores eager display interleaving and moves
verified anchor reading ahead. Full snapshots remain enabled. Prediction:
4.95–5.17 seconds, central5.04, for a121-frame5.041667-second chunk; unmeasured.
A continuation contributes120new frames/5.0seconds; report that stricter pace too.

Future matching client, in its own new work directory:

```bash
experiments/ltx25-b70/stream/start-client-119.sh 121 1 cone 1 1 fingerprint 1.0 eager-display 1 full
```

The default work directory is `/home/steve/ltx-stream/s119-live01`; it was not
created or written by this task. `LTX_STREAM_WORKDIR` may select another new
location. Client qualification and the per-chunk byte gates remain mandatory.

## Controls and alternatives

Launcher arguments, in order:
`frames anchor dg ad bo pa sm cap display read-ahead snapshot receipt [mode]`.
Mode is `launch` (default) or the inherited `--check-only`; neither was executed
here. Unknown modes reject before operational commands. Cap `-` explicitly
unsets the inherited cap; a cap requires dg1. All three new options are assigned
explicitly, so ambient values cannot silently enable them.

- New-options-off dg0 comparison: `121 frame 0 cone 1 1 fingerprint - sampler-a 0 full`.
- Isolate eager display: `121 frame 1 cone 1 1 fingerprint 1.0 eager-display 0 full`.
- Delayed display trial: `121 frame 1 cone 1 1 fingerprint 1.0 sampler-b 0 full`.
  Watch next-cone FIFO wait; a faster B-prep bucket is not a win by itself.
- Owner-only barrier trial: replace `full` with `a-xpu3-sync` after the owner
  selects the documented loss of xpu:0/1/2 completion barriers at two A sites.
  This is never implied by enabling fingerprint mode or read-ahead.

Append the receipt argument to each arm. No arm here is an unattended campaign
or authority to interrupt the coordinator. The inherited latches remain shared:
decoder-graph116, anchor-decode117/118, precompute117/118 and snapshot118.

## Validation and recorded limits

See [build receipt](../../data/resume-20261008/continuation119-build.json) for the
exact final CPU counts, commands, source hashes, manifest and recursive closure.
No bytecode directories are allowed in the packet. Runtime components under this directory are copied into the packet; changing
them later requires a separately sealed successor, never an edit of119's sealed
files. The build receipt separately binds the auxiliary launchers, docs and tests.

The coordinator's later qualification must pass all nine chunks and use the
selected options. After streaming, the CPU file audit can check interior chunks:

```bash
OMP_NUM_THREADS=4 /home/steve/.venvs/ltx25-baseline/bin/python -B experiments/ltx25-b70/recovery/20261010-continuation119-stream/stream_schedule_gate.py --run "$COMPLETED_119_RUN" --first 10 --last 109 --control-run "$MATCHED_CONTROL_RUN"
```

This reads saved files and prints a report; it never contacts the model server.
The same-scene, same-seed comparison must use a chain from the same sequence0
state. Require unchanged image, waveform and anchor hashes, cone equality,
correct decoder signatures, actual read-ahead hits, matching display release
proof where selected, correct barrier scopes and no latch/fault/floor violation.
Report actual period and memory margins. CPU tests establish none of XPU speed,
allocator headroom, whole-model parity or sustained stability.
