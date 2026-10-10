# Prepared packet 134 command — coordinator only

This command has not been run. It requires the coordinator's fresh health receipt and launch authority. The conservative 169 graph census fails; only the graph-off arm is prepared. Forecast 6.5–6.95 seconds per 7 seconds of video (0.929–0.993 s/s; central 6.65/0.95), not a measured improvement over133b at 145.

```bash
LTX_CHUNK_ARM=split36-169 LTX_TEXT_RESIDENCY=split36 LTX_CONE_GRAPH_MEMORY=off LTX_AUDIO_RESIDENCY=legacy LTX_CONE_CAPTURE_RESERVE=parent LTX_DISPLAY_ALLOCATOR_RELEASE=off LTX_AUX_RESIDENCY=legacy LTX_DISPLAY_WORKER=serial LTX_MAINTENANCE_MODE=idle LTX_GC_INTERVAL_SECONDS=60 LTX_SNAPSHOT_DIGEST_CACHE=1 LTX_STORAGE_SCAN_MODE=background LTX_RUN_WRITE_ALLOWANCE_GIB=16 experiments/ltx25-b70/recovery/20261010-continuation134-stream/launch-134.sh 169 frame 0 cone 1 1 fingerprint - eager-display 0 full xpu:3 /absolute/path/to/fresh-health-receipt.json
```

Matching client, after native qualification:

```bash
LTX_CHUNK_ARM=split36-169 LTX_TEXT_RESIDENCY=split36 LTX_CONE_GRAPH_MEMORY=off LTX_MAINTENANCE_MODE=idle LTX_GC_INTERVAL_SECONDS=60 LTX_SNAPSHOT_DIGEST_CACHE=1 LTX_STORAGE_SCAN_MODE=background LTX_RUN_WRITE_ALLOWANCE_GIB=16 experiments/ltx25-b70/stream/start-client-134.sh 169 0 cone 1 1 fingerprint none eager-display 0 full xpu:3
```

The client defaults to `/home/steve/ltx-stream/s134-live01`; override with `LTX_STREAM_WORKDIR` for a new authorized session. Both launchers use `/home/steve/.venvs/ltx25-baseline/bin/python -B`, OMP2 and no restart policy. No launcher was executed during CPU preparation.

Off form: `LTX_CHUNK_ARM=off` with the existing 133b at 145 configuration (`LTX_TEXT_RESIDENCY=split36 LTX_CONE_GRAPH_MEMORY=text-shift`, frames 145, dg1). No inherited numerical identity is changed. The launcher pins manifest `a46fb116f2ce97948c694db870db5a939096814986222fcd0b732e8c025a653c`. See CONTRACT.md and the packet 134 design note for limits.
