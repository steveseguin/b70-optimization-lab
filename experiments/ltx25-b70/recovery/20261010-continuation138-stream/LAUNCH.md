# Packet 138 launch (owner action, not executed during preparation)

Candidate: `LTX_TEXT_PREFETCH=scheduled`; control: `LTX_TEXT_PREFETCH=off` (default).
Keep `LTX_F32_SCAN=bulk` in both matching production arms.
Use the same approved fresh health receipt and all production settings for both.
Both server and client wrappers use `/home/steve/.venvs/ltx25-baseline/bin/python`.
Do not use the virtual environment `bin/python3` launcher alias.

```bash
env -u LTX_DISPLAY_REPLICA_TRANSIENT_GIB \
  LTX_TEXT_PREFETCH=scheduled LTX_F32_SCAN=bulk LTX_TEXT_RESIDENCY=split36 LTX_CONE_GRAPH_MEMORY=text-shift \
  LTX_AUDIO_RESIDENCY=legacy LTX_CONE_CAPTURE_RESERVE=parent \
  LTX_DISPLAY_ALLOCATOR_RELEASE=off LTX_AUX_RESIDENCY=legacy LTX_DISPLAY_WORKER=serial \
  LTX_GC_INTERVAL_SECONDS=10 LTX_STORAGE_SCAN_MODE=background LTX_SNAPSHOT_DIGEST_CACHE=1 \
  LTX_MAINTENANCE_MODE=idle LTX_RUN_WRITE_ALLOWANCE_GIB=16 \
  experiments/ltx25-b70/recovery/20261010-continuation138-stream/launch-138.sh \
  145 frame 1 cone 1 1 fingerprint - eager-display 0 full xpu:3 \
  /absolute/path/to/fresh-health-receipt.json
```

The launcher retains the parent admission and name-collision refusals, and uses
an exclusive packet 138 run name, with a distinct suffix for scheduled prefetch. No launch,
check-only, endpoint inspection, systemd operation or GPU access is authorized
by the CPU preparation task. The command above is text only.

Client: `experiments/ltx25-b70/stream/start-client-138.sh` with
`LTX_EXPECT_TEXT_PREFETCH=scheduled` and `LTX_EXPECT_F32_SCAN=bulk`.
The control expectation is `LTX_EXPECT_TEXT_PREFETCH=off`.
`LTX_STREAM_WORKDIR` defaults to `/home/steve/ltx-stream/s138-live01`.
`LTX_CLIENT_PACING_LOG=precise` is the wrapper default; `legacy` retains 137 logs.
Only the pinned ten-scene/four-chunk schedule publishes its position and hash;
altered schedules omit the optional pair and use fresh encoding.
Use matching production expectations (text only):

```bash
env -u LTX_DISPLAY_REPLICA_TRANSIENT_GIB \
  LTX_EXPECT_TEXT_PREFETCH=scheduled LTX_EXPECT_F32_SCAN=bulk LTX_TEXT_RESIDENCY=split36 LTX_CONE_GRAPH_MEMORY=text-shift \
  LTX_AUDIO_RESIDENCY=legacy LTX_CONE_CAPTURE_RESERVE=parent \
  LTX_DISPLAY_ALLOCATOR_RELEASE=off LTX_AUX_RESIDENCY=legacy LTX_DISPLAY_WORKER=serial \
  LTX_GC_INTERVAL_SECONDS=10 LTX_STORAGE_SCAN_MODE=background LTX_SNAPSHOT_DIGEST_CACHE=1 \
  LTX_MAINTENANCE_MODE=idle LTX_RUN_WRITE_ALLOWANCE_GIB=16 \
  experiments/ltx25-b70/stream/start-client-138.sh \
  145 1 cone 1 1 fingerprint none eager-display 0 full xpu:3
```

Packet: `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-138`.
Manifest: `85781225aad084faf676268cbe693df5649aa77cad76373306243a688fb23fc5`.
Inner plan: `38ba6ca1e54d34acd0e27a438c6978436cbd5ecbb268946587c9e13f7f3cab2a`.
The [build receipt](../../data/resume-20261008/continuation138-build.json) records
validation and source hashes.

CPU tests use `nice -n 19 env OMP_NUM_THREADS=2` and
`bin/python -B run_tests_138.py`, with device/network/signal guards and dedicated
scratch. The complete client suites and sealed import inventory are mandatory.
