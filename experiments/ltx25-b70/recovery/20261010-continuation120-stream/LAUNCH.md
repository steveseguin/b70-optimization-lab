# Packet 120 launch reference — future coordinator action only

Nothing here was launched or rehearsed. No port, unit, device, host setting or
existing run was operated by the CPU task. The coordinator owns any transition.
All inherited health, fault, storage, collision and latch requirements remain.
No automatic retry, restart or service restoration is added.

Packet: `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-120`.
Manifest: **9af9330b7b9f08ad5c3b88d38b5c3f66186fab583d3b810afad7f0d61c5c328e**.
Parent119: `d4b99d333f8193fc74041290b3cc3ebc7309b73836323997d14271a9aa246890`.

Both launch wrappers call `/home/steve/.venvs/ltx25-baseline/bin/python -B`,
with OMP_NUM_THREADS=4 and MKL_NUM_THREADS=4. Do not execute them to test parsing.

## Recommended first comparison

Future command, repository root, after the coordinator's normal admission:

```bash
experiments/ltx25-b70/recovery/20261010-continuation120-stream/launch-120.sh 121 frame 1 cone 1 1 fingerprint 1.0 eager-display 0 full xpu:2 "$FRESH_HEALTH_RECEIPT"
```

Future matching client:

```bash
experiments/ltx25-b70/stream/start-client-120.sh 121 1 cone 1 1 fingerprint 1.0 eager-display 0 full xpu:2
```

`LTX_STREAM_WORKDIR` defaults to `/home/steve/ltx-stream/s120-live01`. It was
not created or written by this task. The new device option is off by default;
these explicit commands select its mandatory qualification, not a qualified
production mode. Read-ahead is off and all snapshots remain full.

Predicted period at 121 frames: 5.10–5.40 seconds, central 5.22, conditional on
cross-card equality and improved xpu:3 memory margin. Conservative adverse range:
5.35–5.70 seconds. These are estimates, not measured speeds. The chunk duration
is 5.041667 seconds, but a continuation adds 5.0 seconds of new frames.

## Controls

Server argument order:
`frames anchor dg ad bo pa sm cap display read-ahead snapshot display-device receipt [mode]`.
Client omits anchor (fixed frame), receipt and mode; use `none` for its no-cap
expectation. Server `cap=-` unsets an ambient cap. Device xpu:2 is accepted only for 121/frame/cone/eager-display. Device xpu:3
preserves119's choices; all options are explicitly assigned by the wrappers.
The inherited mode parser supports `launch` and `--check-only`; **neither was
executed in this task**.

- Match119 live settings: `121 frame 1 cone 1 1 fingerprint 1.0 eager-display 1 full xpu:3`.
- Isolate replica, read-ahead off: same as first command but `xpu:3`.
- Preserve118b dg0 reference: `121 frame 0 cone 1 1 fingerprint - sampler-a 0 full xpu:3`.

Append a fresh receipt to each server argument list. Any refuse/latch stays for
coordinator review; there is no scripted fallback. The replica latch is
`display-replica-120-refused.json`, alongside every inherited latch.

## Qualification and review

All nine full-frame cross-card comparisons and the unchanged latent/image/audio/
anchor chain checks must pass. Live display-last-frame/cone-anchor equality stays
mandatory. Record physical free/allocator peaks on every card, replica resident
bytes, xpu:3 dual-walk frequency and decode FIFO wait. The 4 GiB transient reserve
is a conservative assumption, not a measured peak guarantee. Qualification's
reference decode may leave xpu:3 allocations reserved, so moving display may not
recover the expected margin.

Compare complete matched scenes/seeds/chains, 100 interior chunks after the first
ten and fresh-run repeats for a speed verdict. Inspect the saved receipts with
`stream_schedule_gate.py`; no endpoint is needed for that file audit. Require
unchanged output hashes and no failure, floor violation or fallback. Keep all
safety checks, including near-floor dual walks. [Design](../../notes/2026-10-10-continuation120-stream-design.md)
and [build receipt](../../data/resume-20261008/continuation120-build.json) contain
limits and the exact CPU results. CPU checks prove no XPU speed or exactness.
