# Packet126 future launch

Prepared instructions only. The CPU preparation task did not execute a launcher,
client wrapper, live preflight, unit command or GPU operation. The coordinator
owns the running LTX session and decides when to use this packet.

Parent: sealed125. Packet:
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-126`.
Manifest and inner plan identities are recorded in
`../../data/resume-20261008/continuation126-build.json` and pinned in the launcher
and client. The client pin is the inner `plan_sha256`, never the plan file hash.

The explicit `background` arm bundles the helper-thread storage accounting
with a full typed binary plan comparison on every integrity check. The plan is
canonically verified at load; any changed binary serialization falls back to
the original canonical hash validation. `request` preserves both parent paths.

## First matched arm

Keep145 frames, legacy auxiliaries, serial display on xpu:3, sampler-a schedule,
full fingerprint snapshots, cone anchor, overlap/prep enabled, no decoder graph,
and the inherited ten-second maintenance cadence. This isolates126 from125's
separate sixty-second maintenance option. Use the same run allowance on both
sides of the comparison.

Coordinator command, text only (replace the receipt with a fresh authorized
health receipt; no receipt is produced by this CPU work):

```bash
LTX_STORAGE_SCAN_MODE=background LTX_GC_INTERVAL_SECONDS=10 \
LTX_AUX_RESIDENCY=legacy LTX_DISPLAY_WORKER=serial \
LTX_RUN_WRITE_ALLOWANCE_GIB=16 \
bash experiments/ltx25-b70/recovery/20261010-continuation126-stream/launch-126.sh \
  145 frame 0 cone 1 1 fingerprint - sampler-a 0 full xpu:3 /path/to/health-receipt.json
```

Matching client, text only:

```bash
LTX_STORAGE_SCAN_MODE=background LTX_GC_INTERVAL_SECONDS=10 \
LTX_AUX_RESIDENCY=legacy LTX_DISPLAY_WORKER=serial \
LTX_RUN_WRITE_ALLOWANCE_GIB=16 \
bash experiments/ltx25-b70/stream/start-client-126.sh \
  145 0 cone 1 1 fingerprint none sampler-a 0 full xpu:3
```

The client's work directory defaults to `/home/steve/ltx-stream/s126-live01`;
`LTX_STREAM_WORKDIR` can select a new directory. This task did not create or
write that directory. The wrappers call the baseline virtual environment's
`bin/python -B` and preserve existing HTTP routes.

Forecast: **5.55–5.75 s/chunk**, or **0.925–0.958 s/s** for six seconds of new
video. Target: **5.61–5.64 s**, **0.935–0.940 s/s**. These ranges are predictions;
the matched-window evidence does not justify guaranteeing a recovered0.15 s.
Measure both parities, fresh-text events and every recorded timing bucket.

## Controls and gates

`LTX_STORAGE_SCAN_MODE=request` preserves parent accounting and integrity-check
paths; use it for the matched control on a separately authorized fresh session.
Keep `LTX_GC_INTERVAL_SECONDS=10` for both arms before considering60 separately.
Do not reuse occupied run names. Qualification, reference-byte proof, memory
checks, fault handling and fail-closed storage checks remain mandatory.
A stale or failed accounting sample, insufficient256 MiB pending allowance,
or a completion-epoch timeout refuses new work rather than skipping a check.
Do not infer a speed win from CPU suites or a single server.
