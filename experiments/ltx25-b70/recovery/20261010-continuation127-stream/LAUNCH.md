# Packet 127 future launch reference — coordinator only

No command below was executed by the CPU author. The coordinator supplies a
fresh health receipt, owns the live server, and chooses the operating window.
Do not run another live action alongside their work. No restart or retry loop.

Parent 126 manifest `fe5ce9e09b7e8c86ac659c20430f85b3c83cb35bf5e8476f740610da82b60aa4`.
Packet `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-127`.
Manifest `c2564507a9bb88a948bc726d079d8b5a981b3834ad54801be47d0d0c81dc359e`.
Inner plan `554c80518ab28dbdecd502bb942d28850e70bbd24a75b4521be0c5c9d2abcc01`.
The checked wrapper uses `/home/steve/.venvs/ltx25-baseline/bin/python -B`.

First recommended launch (text only):

```sh
LTX_SNAPSHOT_DIGEST_CACHE=1 LTX_STORAGE_SCAN_MODE=background \
LTX_GC_INTERVAL_SECONDS=60 LTX_AUX_RESIDENCY=legacy \
LTX_DISPLAY_WORKER=serial LTX_RUN_WRITE_ALLOWANCE_GIB=16 \
experiments/ltx25-b70/recovery/20261010-continuation127-stream/launch-127.sh \
  145 frame 0 cone 1 1 fingerprint - sampler-a 0 full xpu:3 "$HEALTH_RECEIPT"
```

After unchanged qualification succeeds, the matching client command is:

```sh
LTX_SNAPSHOT_DIGEST_CACHE=1 LTX_STORAGE_SCAN_MODE=background \
LTX_GC_INTERVAL_SECONDS=60 LTX_AUX_RESIDENCY=legacy \
LTX_DISPLAY_WORKER=serial LTX_RUN_WRITE_ALLOWANCE_GIB=16 \
LTX_STREAM_WORKDIR=/home/steve/ltx-stream/s127-live01 \
experiments/ltx25-b70/stream/start-client-127.sh \
  145 0 cone 1 1 fingerprint none sampler-a 0 full xpu:3
```

`LTX_STREAM_WORKDIR` defaults to the path shown. The client expects strict
integer `snapshot_digest_cache=1`, background accounting, GC 60, legacy
auxiliaries and all listed geometry/schedule options. Missing or mismatched
candidate expectations refuse. Client plan pins are the **inner** `plan_sha256`,
not the plan file hash, covered by the all-pins test.

For a matched new-lever control use `LTX_SNAPSHOT_DIGEST_CACHE=0` on both
wrappers while holding every other option fixed. Default 0 executes parent 126
route-digest code; default GC 10/request accounting also preserve their parent
forms. Do not combine controls from different parities, text classes or windows.
A source sequence divisible by 4 encodes fresh text in this saved schedule.
Keep maintenance and fresh-text samples in aggregate speed/tail reports.

Forecast: 5.45–5.70 seconds per 6.0 seconds new video (0.908–0.950s/s), central
5.55 seconds (0.925s/s). This is not a measured result. The direct mechanism
check is cumulative signature-cache hit/miss/fallback counters, followed by
per-snapshot state timings. Every tensor-fact inspection must still execute.

Native gate: full eager/graph/repeat captures and saved 145 reference bytes,
precomputed/native conditioning, cone/full/display and preview hashes,
unchanged memory floors, no faults/latches, storage freshness/refusal,
long-run memory plateau, two fresh qualified servers and matched fixed windows.
Report modulo 4 text classes, source parity and maintenance-overlap timing.

169 with 124 parallel display 2 remains a separate inherited arm: cache 0,
GC 10, background accounting, legacy auxiliaries, eager-display, parallel
worker and 6.5GiB replica reserve. It has no 169 measurement with this combination.
145 decoder graph relocation/capture is not newly admitted by packet 127.
