# Packet 132 future qualification — coordinator only

These are text for review. None was executed during preparation.
Packet: `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-132`.
Parent131 manifest: `e25d8d623741fed31fccfd049a323e9bf853302a21aaff472c48eda40fb1ed6f`.
Manifest: `67ec59a5b0c5131d0b129e4c0b9187386c29c0395ac225dc28422516684991ad`.
Inner plan: `fbb1d04b2cc87c61353bdf275565d14d6429c3fc45429995d4610fc817761e8f`.
Exact CPU counts are in the
[build receipt](../../data/resume-20261008/continuation132-build.json).

Recommended first qualification uses the unchanged 5 GiB capture reserve:

```bash
LTX_AUDIO_RESIDENCY=xpu2 LTX_CONE_CAPTURE_RESERVE=parent \
LTX_CONE_GRAPH_MEMORY=replica-release LTX_DISPLAY_ALLOCATOR_RELEASE=off \
LTX_MAINTENANCE_MODE=idle LTX_GC_INTERVAL_SECONDS=60 \
LTX_SNAPSHOT_DIGEST_CACHE=1 LTX_STORAGE_SCAN_MODE=background \
LTX_AUX_RESIDENCY=legacy LTX_DISPLAY_WORKER=serial \
LTX_DISPLAY_REPLICA_TRANSIENT_GIB=5.640625 LTX_RUN_WRITE_ALLOWANCE_GIB=16 \
experiments/ltx25-b70/recovery/20261010-continuation132-stream/launch-132.sh \
  145 frame 1 cone 1 1 fingerprint - eager-display 0 full xpu:2 "$HEALTH_RECEIPT"
```

Matching client:

```bash
LTX_STREAM_WORKDIR=/home/steve/ltx-stream/s132-live01 \
LTX_AUDIO_RESIDENCY=xpu2 LTX_CONE_CAPTURE_RESERVE=parent \
LTX_CONE_GRAPH_MEMORY=replica-release LTX_DISPLAY_ALLOCATOR_RELEASE=off \
LTX_MAINTENANCE_MODE=idle LTX_GC_INTERVAL_SECONDS=60 \
LTX_SNAPSHOT_DIGEST_CACHE=1 LTX_STORAGE_SCAN_MODE=background \
LTX_AUX_RESIDENCY=legacy LTX_DISPLAY_WORKER=serial \
LTX_DISPLAY_REPLICA_TRANSIENT_GIB=5.640625 LTX_RUN_WRITE_ALLOWANCE_GIB=16 \
experiments/ltx25-b70/stream/start-client-132.sh \
  145 1 cone 1 1 fingerprint none eager-display 0 full xpu:2
```

Both wrappers use `/home/steve/.venvs/ltx25-baseline/bin/python -B`.
The client defaults to `s132-live01`. It checks both new options, the sealed
manifest, **inner** `plan_sha256`, status, receipts, decode records, verdict,
and audio/reference memory and waveform evidence. Run suffix is `-audioxpu2`
after packet131's `-cmreplica-release` suffix.

Projected first-capture physical free is 16,189,906,932 B if the checkpoint
residency savings become free. Against 15,837,691,904 B required, the margin
is **352,215,028 B = 0.328025807 GiB**, after the unchanged 0.75 GiB band.
No physical savings were measured here. The temporary native card3 audio
reference can itself refuse its workspace guard before this boundary.

The cadence forecast is **5.25–5.35 seconds per six seconds of new video
(0.875–0.892 s/s), plus the unmeasured isolated audio placement cost**.
This is conditional on native qualification, sustained memory fit and the
unchanged reference/byte gates; it is not a measured speed claim.

Off forms set audio legacy and reserve parent, retaining131 behavior with
132 packet identities. `scaled-476` is recognized but refuses before device
work because the121 receipts do not establish a145-frame peak bound. Its
hypothetical combined margin is0.568025806GiB; it is not recommended.
No floor/screen override, automatic fallback, retry or latch removal exists.

For an isolated timing comparison, the same145 serial eager-display2 setup
also admits dg0/cone-memory-off with GC10, digest0 and parent maintenance.
Compare `LTX_AUDIO_RESIDENCY=legacy` against `xpu2`, holding every other option
fixed; then measure the admitted dg1 audio arm. Record at least two fresh
servers per arm only under a future authorized campaign. No run is started
or queued by these instructions. Keep qualification reference-copy/decode/
unload timing separate from steady-state audio timing and parity period.

See [contract](CONTRACT.md), [design](../../notes/2026-10-10-continuation132-stream-design.md)
and [memory arithmetic](../../notes/2026-10-10-continuation132-memory-evidence.md).
