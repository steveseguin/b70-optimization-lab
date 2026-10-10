# Packet 130 future launch — coordinator only

These are text instructions. Preparation did not execute this wrapper, a
check-only mode, a client against the live service, or any unit operation.

Packet: `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-130`.
Parent: sealed129, manifest
`42e6a7452e11873f33c78a953105754605121f2a96dfca1954b1d55966a4886c`.
Packet manifest: `14aa145e6ad814eb600ceca75286742a08898ae5bb704d270dfada69420980ed`.
INNER plan: `0d24d0ff5446de8445d9774dd20057aaa284e34c2bedba0baba186b3b8af82ba`.
Validation is recorded in the [build receipt](../../data/resume-20261008/continuation130-build.json).

Recommended 169 qualification (fresh coordinator health receipt supplied last):

```bash
LTX_DISPLAY_ALLOCATOR_RELEASE=before-admission \
LTX_MAINTENANCE_MODE=idle LTX_GC_INTERVAL_SECONDS=10 \
LTX_SNAPSHOT_DIGEST_CACHE=0 LTX_STORAGE_SCAN_MODE=background \
LTX_AUX_RESIDENCY=legacy LTX_DISPLAY_WORKER=parallel \
LTX_DISPLAY_REPLICA_TRANSIENT_GIB=6.5 LTX_RUN_WRITE_ALLOWANCE_GIB=16 \
experiments/ltx25-b70/recovery/20261010-continuation130-stream/launch-130.sh \
  169 frame 0 cone 1 1 fingerprint - eager-display 0 full xpu:2 "$HEALTH_RECEIPT"
```

The wrapper calls `/home/steve/.venvs/ltx25-baseline/bin/python -B`.
GC60 and digest1 remain scoped to145; neither is admitted here. The new run name
ends in `-arbefore-admission`. Off form removes the new option or sets it to
`off` and otherwise preserves129. No automatic fallback or restart is added.

Matching client (all existing qualification, artifact and completion checks):

```bash
LTX_STREAM_WORKDIR=/home/steve/ltx-stream/s130-live01 \
LTX_DISPLAY_ALLOCATOR_RELEASE=before-admission \
LTX_MAINTENANCE_MODE=idle LTX_GC_INTERVAL_SECONDS=10 \
LTX_SNAPSHOT_DIGEST_CACHE=0 LTX_STORAGE_SCAN_MODE=background \
LTX_AUX_RESIDENCY=legacy LTX_DISPLAY_WORKER=parallel \
LTX_DISPLAY_REPLICA_TRANSIENT_GIB=6.5 LTX_RUN_WRITE_ALLOWANCE_GIB=16 \
experiments/ltx25-b70/stream/start-client-130.sh \
  169 0 cone 1 1 fingerprint none eager-display 0 full xpu:2
```

The client workdir defaults to `/home/steve/ltx-stream/s130-live01`; its wrapper
also calls the pinned bin/python with `-B`. It expects release mode, all other
selected server options, sealed manifest, INNER plan, atomic publication and
unchanged quality gates. Existing latches must be handled by the coordinator's
established evidence/review process; preparation does not remove them.

The latest saved169 qualification margins above8/8/2/9 GiB floors are
1.231304 / 1.772644 / 5.884018 / 1.554504 GiB. The xpu:2 number precedes the
6.5 GiB transient charge, so its effective margin is **−0.615982 GiB**.
A conditional1.5 GiB physical release changes that to **0.884018 GiB**,
0.134018 above the mandatory0.75 screen. Other-card margins are held unchanged
for planning: no credit is taken for their possible allocator releases.
This is a recomputed scenario, not measured130 admission. The actual release
must recover at least1.365982 GiB at that saved state, and each later admission
must independently pass. Reserved-unused cannot substitute for that check.

Forecast inherited from124: **6.20–6.65 seconds per seven seconds of new video
(0.886–0.950 s/s; center6.30/0.900)**, plus unmeasured cache-release cost.
Text/card contention or global allocator synchronization may instead give
6.65–7.20 seconds (0.950–1.029 s/s). No130 speed has been measured.

The coordinator must close full nine-decode equality, three-chain/fresh-text
qualification, retained reservation plateau, all-card floors and two fresh
qualified-server speed evidence before adopting the option. A failed admission
is a refusal, never permission to lower6.5 GiB. The inventory and ranked
alternatives are in [the residency note](../../notes/2026-10-10-xpu2-residency-169.md).
