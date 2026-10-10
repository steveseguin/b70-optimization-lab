# Packet 131 future qualification — coordinator only

These commands are text for review. They were not executed during preparation.
Packet: `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-131`.
Parent130 manifest: `14aa145e6ad814eb600ceca75286742a08898ae5bb704d270dfada69420980ed`.
Packet manifest: `e25d8d623741fed31fccfd049a323e9bf853302a21aaff472c48eda40fb1ed6f`.
Inner plan: `526f832c76c1ef8eb66a3fea1673bc6ffbd0a0dadb9b7e76ea450504a0da7514`.
Exact CPU counts are in the
[build receipt](../../data/resume-20261008/continuation131-build.json).

Recommended guarded qualification, with the coordinator's fresh health receipt:

```bash
LTX_CONE_GRAPH_MEMORY=replica-release LTX_DISPLAY_ALLOCATOR_RELEASE=off \
LTX_MAINTENANCE_MODE=idle LTX_GC_INTERVAL_SECONDS=60 \
LTX_SNAPSHOT_DIGEST_CACHE=1 LTX_STORAGE_SCAN_MODE=background \
LTX_AUX_RESIDENCY=legacy LTX_DISPLAY_WORKER=serial \
LTX_DISPLAY_REPLICA_TRANSIENT_GIB=5.640625 LTX_RUN_WRITE_ALLOWANCE_GIB=16 \
experiments/ltx25-b70/recovery/20261010-continuation131-stream/launch-131.sh \
  145 frame 1 cone 1 1 fingerprint - eager-display 0 full xpu:2 "$HEALTH_RECEIPT"
```

Matching client:

```bash
LTX_STREAM_WORKDIR=/home/steve/ltx-stream/s131-live01 \
LTX_CONE_GRAPH_MEMORY=replica-release LTX_DISPLAY_ALLOCATOR_RELEASE=off \
LTX_MAINTENANCE_MODE=idle LTX_GC_INTERVAL_SECONDS=60 \
LTX_SNAPSHOT_DIGEST_CACHE=1 LTX_STORAGE_SCAN_MODE=background \
LTX_AUX_RESIDENCY=legacy LTX_DISPLAY_WORKER=serial \
LTX_DISPLAY_REPLICA_TRANSIENT_GIB=5.640625 LTX_RUN_WRITE_ALLOWANCE_GIB=16 \
experiments/ltx25-b70/stream/start-client-131.sh \
  145 1 cone 1 1 fingerprint none eager-display 0 full xpu:2
```

Both wrappers call pinned bin/python with `-B`. The client defaults to the
folder above and requires the selected mode, all options, sealed manifest,
inner plan and matching admission evidence. Run suffix is `-cmreplica-release`.

The unchanged production-shaped off form uses `LTX_CONE_GRAPH_MEMORY=off`,
dg0, sampler-a and xpu:3 with GC60/digest1/idle, serial display and legacy
auxiliaries. Existing130 options retain their old scopes and behavior.
There is no automatic fallback, retry, latch removal or server operation here.

The new first capture requires14.75GiB free; later cones9.75GiB. The145 estimate
is4.505890GiB growth. Packet124's clean streaming boundary would leave1.046902GiB
above the9GiB floor after that estimate, but its qualification tail would miss
the screening target by3.345680GiB. The stricter5GiB reserve needs3.839790GiB
released at that saved tail. No reclaim was measured during CPU preparation.

Conditional target: **5.25–5.35 seconds per6 seconds of new video,
0.875–0.892 s/s**. It transfers the121 graph gain; actual release overhead,
card2 text/display contention, full native equality and sustained memory fit
remain open. Keep the129 production line until coordinator qualification.

Do not lower the reserve or skip reference checks to force admission. Preserve
all latches for the coordinator's review. No snapshot scheduling option is
recommended with this launch; keep `full`.
See [inventory](../../notes/2026-10-10-xpu3-residency-145.md),
[snapshot audit](../../notes/2026-10-10-continuation131-snapshot-schedule.md), and
[design](../../notes/2026-10-10-continuation131-stream-design.md).
