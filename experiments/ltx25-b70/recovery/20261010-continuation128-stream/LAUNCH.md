# Packet 128 future launch reference — coordinator only

Text only: the coordinator owns the live server and supplies a fresh health
receipt. No command here was executed by the CPU author.

Parent127 manifest `c2564507a9bb88a948bc726d079d8b5a981b3834ad54801be47d0d0c81dc359e`.
Packet `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-128`.
Manifest `bd6471f7e10d2ec3219879a281820056178556a3388f50fb7c2c7896199f5ead`.
Inner plan `d0f849d2f9b59bf8a28ae5c9f5186ee68914d372796c4d63e2ca5bd5c492f3d5`.
Both wrappers use `/home/steve/.venvs/ltx25-baseline/bin/python -B`.

Recommended first launch:

```sh
LTX_MAINTENANCE_MODE=idle LTX_GC_INTERVAL_SECONDS=10 \
LTX_SNAPSHOT_DIGEST_CACHE=1 LTX_STORAGE_SCAN_MODE=background \
LTX_AUX_RESIDENCY=legacy LTX_DISPLAY_WORKER=serial LTX_RUN_WRITE_ALLOWANCE_GIB=16 \
experiments/ltx25-b70/recovery/20261010-continuation128-stream/launch-128.sh \
  145 frame 0 cone 1 1 fingerprint - sampler-a 0 full xpu:3 "$HEALTH_RECEIPT"
```

Matching client after unchanged qualification succeeds:

```sh
LTX_MAINTENANCE_MODE=idle LTX_GC_INTERVAL_SECONDS=10 \
LTX_SNAPSHOT_DIGEST_CACHE=1 LTX_STORAGE_SCAN_MODE=background \
LTX_AUX_RESIDENCY=legacy LTX_DISPLAY_WORKER=serial LTX_RUN_WRITE_ALLOWANCE_GIB=16 \
LTX_STREAM_WORKDIR=/home/steve/ltx-stream/s128-live01 \
experiments/ltx25-b70/stream/start-client-128.sh \
  145 0 cone 1 1 fingerprint none sampler-a 0 full xpu:3
```

Workdir defaults to the shown path. Client expectations must match mode, GC,
cache, storage, residency and every geometry/schedule option. Plan pins use the
inner plan_sha256, never the file hash. Matched control: change only maintenance
mode to `parent` in both wrappers. GC60 remains supported but idle gives no
additional deferral when it first becomes due at the hard bound.

Forecast at 145: 5.50–5.75 seconds per six seconds of new video; center
5.60 seconds / 0.933 s/s. The saved-timeline counterfactual of 5.567 / 0.928
is not a measurement. Reused-text chunks may approach 5.57 seconds; fresh text
every fourth chunk remains slower. Equal pooled parities and guaranteed native
routes under 50 ms are not established.

169 is currently blocked: the coordinator's 127 qualification refused its
xpu:2 memory floor (CURRENT, 09:15 UTC). Packet 128 does not change that guard.
Recover headroom and qualify first; do not lower the reserve. Conditional
settings: parallel display2/eager-display, legacy auxiliaries, 6.5 GiB replica
transient reserve, cache0, GC10, background storage. The combined forecast of
6.20–6.65 seconds per seven seconds of video (0.886–0.950 s/s) remains unmeasured.

Retain native byte/reference/three-chain/hash gates, precompute/cone/display
equality, storage and memory floors, faults/latches, and a long-run memory
plateau across forced cleanup. Compare fixed full windows on two fresh qualified
servers, retaining slow/maintenance/fresh-text samples. Report modulo-four
classes, source parity, cleanup age/reason, commit→served,text/prep,whole period
and decode/preview queue depths. CPU preparation makes no live claim.
