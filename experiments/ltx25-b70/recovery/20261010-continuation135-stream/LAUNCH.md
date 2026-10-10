# Packet 135 future qualification

Coordinator only. Preparation executed no model launch or live request.
Packet: `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-135`.
Manifest: `4356482eae2f1d7ac95b17e6483379ceed0cc90ed488d46765803451980402c3`.
Inner plan: `7750e7b54c885f99a73ab87b17013fc0a850a1af942f0c00422adbae596258c4`.
[Build receipt](../../data/resume-20261008/continuation135-build.json).

After reviewing the native qualification prerequisites and providing the current
health receipt, the recommended candidate is:

```bash
env -u LTX_DISPLAY_REPLICA_TRANSIENT_GIB \
LTX_TEXT_RESIDENCY=split36 LTX_CONE_GRAPH_MEMORY=text-shift \
LTX_AUDIO_RESIDENCY=legacy LTX_CONE_CAPTURE_RESERVE=parent \
LTX_DISPLAY_ALLOCATOR_RELEASE=off LTX_AUX_RESIDENCY=legacy \
LTX_DISPLAY_WORKER=serial LTX_MAINTENANCE_MODE=idle \
LTX_GC_INTERVAL_SECONDS=60 LTX_SNAPSHOT_DIGEST_CACHE=1 \
LTX_STORAGE_SCAN_MODE=background LTX_RUN_WRITE_ALLOWANCE_GIB=16 \
experiments/ltx25-b70/recovery/20261010-continuation135-stream/launch-135.sh \
145 frame 1 cone 1 1 fingerprint - eager-display 0 full xpu:3 HEALTH_RECEIPT
```

Leave `LTX_DISPLAY_REPLICA_TRANSIENT_GIB` unset. The launcher uses the pinned
`/home/steve/.venvs/ltx25-baseline/bin/python -B`. It refuses existing runs and
latches; it never retries. The client is `stream/start-client-135.sh` with
`LTX_STREAM_WORKDIR` default `/home/steve/ltx-stream/s135-live01`; its expectations
must explicitly select split36, text-shift, parent reserve and native display3.

Off form: select `LTX_TEXT_RESIDENCY=legacy`; all packet132 modes and their
scopes remain. Keep text-shift off for legacy. This is a launch option, not
permission to run either form during CPU preparation.

Every inherited physical-memory and output-byte gate remains mandatory.
169-frame split36 stays outside packet 135’s scope.

This storage repair follows parent 133b without changing arithmetic or native
qualification requirements. See the [design](../../notes/2026-10-10-continuation135-stream-design.md).
The launcher and its check-only path were never executed during preparation.
