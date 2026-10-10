# Packet 122 launch reference — coordinator only

This is text for a later coordinator-owned window. Neither wrapper nor its
`--check-only` mode was executed during CPU preparation. The coordinator owns
the live server, health admission, collision handling and all server lifecycle
choices. No action is queued. Keep inherited fault/latch and quality gates.

Packet: `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-122`.
Manifest SHA256: `8b576c863ec5896fe356e5a264728ddafe368ef2fe90608c9b5bc164687cb7fa`.
Also recorded in the [build receipt](../../data/resume-20261008/continuation122-build.json).
The sealed manifest is also pinned in `launch-122.sh` and `start-client-122.sh`.

First: the requested **145-frame dg1, cap 1.0, eager display on xpu:2** diagnostic.
The graph cap is a decimal-GB post-capture decision, not a hard pool-size bound.
The default replica transient allowance is 5.640625 GiB. The census warns that
retained xpu:3 reservations may refuse this arm; do not reduce a floor to fit it.

```bash
recovery/20261010-continuation122-stream/launch-122.sh 145 frame 1 cone 1 1 fingerprint 1.0 eager-display 0 full xpu:2 /absolute/coordinator-health-receipt.json
stream/start-client-122.sh 145 1 cone 1 1 fingerprint 1.0 eager-display 0 full xpu:2
```

Optional, explicitly larger xpu:2 reserve (application admission only): prefix
**both** commands with `LTX_DISPLAY_REPLICA_TRANSIENT_GIB=6`. This reserves
6 GiB plus the 2 GiB floor before each replica decode. It cannot fix xpu:3
pressure. The accepted range at 145 is 5.640625 through 8 GiB, whole bytes only;
setting a smaller reserve or setting it for display on xpu:3 is refused. Leave
the variable unset for the default census. The client requires the same explicit
expectation and refuses missing/different evidence.

Second, in a separate coordinator-selected window: the matched **145-frame dg0,
display on xpu:3** control, with `LTX_DISPLAY_REPLICA_TRANSIENT_GIB` unset.
Existing names or run directories refuse reuse; this document authorizes no
archival, deletion, automatic fallback or retry.

```bash
recovery/20261010-continuation122-stream/launch-122.sh 145 frame 0 cone 1 1 fingerprint - sampler-a 0 full xpu:3 /absolute/coordinator-health-receipt.json
stream/start-client-122.sh 145 0 cone 1 1 fingerprint none sampler-a 0 full xpu:3
```

169-frame commands are deliberately absent: both arms remain disabled. See the
[analysis](../../notes/2026-10-10-continuation121-results-145.md) for predicted
period ranges, all-card margins and what evidence would reopen 169.

Both wrappers call `/home/steve/.venvs/ltx25-baseline/bin/python -B`; the server
uses OMP/MKL 4. The client defaults `LTX_STREAM_WORKDIR` to
`/home/steve/ltx-stream/s122-live01`, which CPU preparation never creates or writes.
Use a new coordinator-chosen work directory for a second arm. Verify all nine
qualification chunks, measured geometry, cross-card full-image bytes when
selected, live cone equality, memory floors and the selected reserve. Collect
at least 100 interior periods without treating a fit as a measurement. Retain
all snapshots and the read-ahead-off/full-snapshot setting for the comparison.

Known inherited limit: the coordinator's later CURRENT entry records a preview
file changing during the client's guarded read at packet121 chunk154. Packet122
does not change preview publication/read behavior or add a retry; this remains
a separate follow-up. Do not treat CPU qualification as a streaming soak result.
