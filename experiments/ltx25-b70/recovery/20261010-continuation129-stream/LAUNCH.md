# Packet 129 future launch — coordinator only

Text only. The CPU author has not launched or contacted any live server.

Packet: `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-129`.
Parent: sealed 128 (`bd6471f7e10d2ec3219879a281820056178556a3388f50fb7c2c7896199f5ead`).
Manifest: `42e6a7452e11873f33c78a953105754605121f2a96dfca1954b1d55966a4886c`.
Inner plan: `466039fc05fa45169c4e7c054c824b375da4e0a4d4ecbe3f374c6679dbd06536`.

The first arm retains 127's 145-frame production geometry and 128's proposed
idle-maintenance lever. Use a fresh coordinator-provided health receipt:

```sh
LTX_MAINTENANCE_MODE=idle LTX_GC_INTERVAL_SECONDS=60 \
LTX_SNAPSHOT_DIGEST_CACHE=1 LTX_STORAGE_SCAN_MODE=background \
LTX_AUX_RESIDENCY=legacy LTX_DISPLAY_WORKER=serial LTX_RUN_WRITE_ALLOWANCE_GIB=16 \
experiments/ltx25-b70/recovery/20261010-continuation129-stream/launch-129.sh \
  145 frame 0 cone 1 1 fingerprint - sampler-a 0 full xpu:3 "$HEALTH_RECEIPT"
```

After unchanged qualification succeeds, match all client expectations:

```sh
LTX_MAINTENANCE_MODE=idle LTX_GC_INTERVAL_SECONDS=60 \
LTX_SNAPSHOT_DIGEST_CACHE=1 LTX_STORAGE_SCAN_MODE=background \
LTX_AUX_RESIDENCY=legacy LTX_DISPLAY_WORKER=serial LTX_RUN_WRITE_ALLOWANCE_GIB=16 \
LTX_STREAM_WORKDIR=/home/steve/ltx-stream/s129-live01 \
experiments/ltx25-b70/stream/start-client-129.sh \
  145 0 cone 1 1 fingerprint none sampler-a 0 full xpu:3
```

Both wrappers call `/home/steve/.venvs/ltx25-baseline/bin/python -B`.
The workdir defaults to `/home/steve/ltx-stream/s129-live01`.
Client requires packet129, the sealed manifest, the inner plan hash, atomic
publication capability and matching maintenance/storage/cache/geometry options.
No client retries, server restarts or weaker byte/memory guards were added.

169 remains blocked by 127's display2 memory refusal; this packet does not
change that reserve. Publication prevents incomplete-file visibility; no model
speed gain is claimed. Idle maintenance's native speed and memory qualification
also remain open. Coordinator retains control of the live process.

GC60 keeps 127's production interval. Packet 128's unchanged 60-second hard
age bound means idle mode gives no additional deferral when GC60 first becomes
due; this recommendation makes no claim that combining the options adds speed.
