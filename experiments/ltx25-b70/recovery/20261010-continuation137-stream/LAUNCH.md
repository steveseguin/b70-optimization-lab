# Packet 137 launch (owner action, not executed during preparation)

Candidate: `LTX_F32_SCAN=bulk`; control: `LTX_F32_SCAN=parent` (default).
Use the same approved fresh health receipt and all production settings for both.
Both server and client wrappers use `/home/steve/.venvs/ltx25-baseline/bin/python`.
Do not use the virtual environment `bin/python3` launcher alias.

```bash
env -u LTX_DISPLAY_REPLICA_TRANSIENT_GIB \
  LTX_F32_SCAN=bulk LTX_TEXT_RESIDENCY=split36 LTX_CONE_GRAPH_MEMORY=text-shift \
  LTX_AUDIO_RESIDENCY=legacy LTX_CONE_CAPTURE_RESERVE=parent \
  LTX_DISPLAY_ALLOCATOR_RELEASE=off LTX_AUX_RESIDENCY=legacy LTX_DISPLAY_WORKER=serial \
  LTX_GC_INTERVAL_SECONDS=10 LTX_STORAGE_SCAN_MODE=background LTX_SNAPSHOT_DIGEST_CACHE=1 \
  LTX_MAINTENANCE_MODE=idle LTX_RUN_WRITE_ALLOWANCE_GIB=16 \
  experiments/ltx25-b70/recovery/20261010-continuation137-stream/launch-137.sh \
  145 frame 1 cone 1 1 fingerprint - eager-display 0 full xpu:3 \
  /absolute/path/to/fresh-health-receipt.json
```

The launcher retains the parent admission and name-collision refusals, and uses
an exclusive packet137 run name, adding `-f32bulk` only for bulk. No launch,
check-only, endpoint inspection, systemd operation or GPU access is authorized
by the CPU preparation task. The command above is text only.

Client: `experiments/ltx25-b70/stream/start-client-137.sh` with
`LTX_EXPECT_F32_SCAN=bulk`; the control expectation is `parent` (default).
`LTX_STREAM_WORKDIR` defaults to `/home/steve/ltx-stream/s137-live01`.
Use matching production expectations (text only):

```bash
env -u LTX_DISPLAY_REPLICA_TRANSIENT_GIB \
  LTX_EXPECT_F32_SCAN=bulk LTX_TEXT_RESIDENCY=split36 LTX_CONE_GRAPH_MEMORY=text-shift \
  LTX_AUDIO_RESIDENCY=legacy LTX_CONE_CAPTURE_RESERVE=parent \
  LTX_DISPLAY_ALLOCATOR_RELEASE=off LTX_AUX_RESIDENCY=legacy LTX_DISPLAY_WORKER=serial \
  LTX_GC_INTERVAL_SECONDS=10 LTX_STORAGE_SCAN_MODE=background LTX_SNAPSHOT_DIGEST_CACHE=1 \
  LTX_MAINTENANCE_MODE=idle LTX_RUN_WRITE_ALLOWANCE_GIB=16 \
  experiments/ltx25-b70/stream/start-client-137.sh \
  145 1 cone 1 1 fingerprint none eager-display 0 full xpu:3
```

The inner-plan identity is
`61e39067e333d6c392b6a76fbe8b6a962878ed95dc577fb684e10a2af05321a5`.
Sealed manifest:
`18c80d25c2ba4992d8c6dff24779737a056a325389a84486d24da674ef7e463e`.
See the build receipt for exact test counts.

CPU tests use `nice -n 19 env OMP_NUM_THREADS=2` and
`bin/python -B run_tests_137.py`, with device/network/signal guards and dedicated
scratch. The complete client suites and sealed import inventory are mandatory.
