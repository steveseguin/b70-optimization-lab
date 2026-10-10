# Packet 125 — future coordinator launch only

Packet `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-125`.
Final manifest and inner plan SHA256 are recorded below after sealing and in the
[build receipt](../../data/resume-20261008/continuation125-build.json).
Nothing in this file was executed during CPU preparation. The coordinator owns
all health receipts, server/client operations, name admission and live work.

The first candidate keeps145 frames, legacy auxiliary placement, dg0, cone,
B overlap1/A prep1, sampler-a display on xpu:3, read-ahead0, full snapshots and
serial completion. It changes the inherited ten-second maintenance threshold
to60 seconds. It neither moves cache cleanup into active sampling nor removes it.
A full collection/cache cleanup still occurs about once per eleven chunks.

From this directory, with the coordinator's fresh health receipt:

```bash
LTX_GC_INTERVAL_SECONDS=60 LTX_AUX_RESIDENCY=legacy LTX_DISPLAY_WORKER=serial \
LTX_RUN_WRITE_ALLOWANCE_GIB=16 \
./launch-125.sh 145 frame 0 cone 1 1 fingerprint - sampler-a 0 full xpu:3 "$RECEIPT"
```

Corresponding client from `experiments/ltx25-b70/stream/`:

```bash
LTX_GC_INTERVAL_SECONDS=60 LTX_AUX_RESIDENCY=legacy LTX_DISPLAY_WORKER=serial \
LTX_RUN_WRITE_ALLOWANCE_GIB=16 \
./start-client-125.sh 145 0 cone 1 1 fingerprint none sampler-a 0 full xpu:3
```

`LTX_STREAM_WORKDIR` defaults to `/home/steve/ltx-stream/s125-live01`.
The launchers use `/home/steve/.venvs/ltx25-baseline/bin/python -B` and OMP/MKL2.
For the parent scheduling control set `LTX_GC_INTERVAL_SECONDS=10` on both,
using a fresh client directory chosen by the coordinator. No automatic fallback
or retry is provided. The60 run name ends `-gc60`; the10 run keeps the parent
form within packet125's new namespace.

Forecast at legacy145: median5.45–5.75 s per6.0 s of new video
(0.908–0.958 s/s); target **5.55 s /0.925 s/s**. A simple amortized model leaves
about5.58 s /0.930 s/s with minute maintenance retained. Adverse5.75–6.10 s.
These are predictions, not measured125 speeds, and fresh-text costs remain.

Require three-chain exact identity and the saved145 reference, every
cone==display byte check and each preview hash. Observe multiple60-second
maintenance windows, bind events to prompt IDs and report GC/cache durations,
commit-to-serve delay, period within matching text classes, all-chunk mean/p90,
FIFO completion and host RSS/card memory trends. Keep maintenance chunks in the
results. Longer allocation retention can fail the unchanged memory floors;
CPU preparation establishes neither a memory plateau nor native output parity.
A speed verdict needs two fresh qualified opportunities selected by the
coordinator; this is no instruction for this CPU task to operate either server.
