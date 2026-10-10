# Packet 133b future qualification

Coordinator only. Preparation executed no model launch or live request.
Packet: `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-133b`.
Manifest: `ed908a9031a937801d17264edacfe0807bea543badc412a32eb6118daa214fd3`.
Inner plan: `b67b1a8fe9b3457666190267a3ff020cd3708371d89de60952d1e0f60dafab7b`.
[Build receipt](../../data/resume-20261008/continuation133b-build.json).

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
experiments/ltx25-b70/recovery/20261010-continuation133b-stream/launch-133b.sh \
145 frame 1 cone 1 1 fingerprint - eager-display 0 full xpu:3 HEALTH_RECEIPT
```

Leave `LTX_DISPLAY_REPLICA_TRANSIENT_GIB` unset. The launcher uses the pinned
`/home/steve/.venvs/ltx25-baseline/bin/python -B`. It refuses existing runs and
latches; it never retries. The client is `stream/start-client-133b.sh` with
`LTX_STREAM_WORKDIR` default `/home/steve/ltx-stream/s133b-live01`; its expectations
must explicitly select split36, text-shift, parent reserve and native display3.

Off form: select `LTX_TEXT_RESIDENCY=legacy`; all packet132 modes and their
scopes remain. Keep text-shift off for legacy. This is a launch option, not
permission to run either form during CPU preparation.

The candidate transfers5.076040GiB of weights from3 to2; owned graph buffers add
an estimated1.078491GiB transfer. Those logical bytes are not a physical-free
measurement. Every native physical-memory and byte gate still decides admission.
See the [design](../../notes/2026-10-10-continuation133-stream-design.md) for
memory scenarios and the conditional timing forecast.169 remains outside this option.

This packaging rebuild follows parent 133 without changing its arithmetic or
qualification requirements. See [rebuild](../../notes/2026-10-10-continuation133b-rebuild.md).
The launcher and its `--check-only` path were never executed during preparation.
