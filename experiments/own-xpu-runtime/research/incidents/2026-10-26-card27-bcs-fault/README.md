# Card 27 copy-engine page fault, 2026-10-26 08:50:29 EDT (boot 2cba7160)

## What happened

- **08:50:29.** `xe 0000:27:00.0` logged a GPU page fault on the copy engine (bcs):
  - `Fault response: Unsuccessful -ENOENT`, address 0x0000d556aa2a0000, FaultLevel 4;
  - `Engine reset: engine_class=bcs, guc_id=6`.
  - Card 27 is the spare lab card, not one of the service's cards (23/47).
- **08:50:33.** The live `sc117-lan` service (engine 1d72818cfe8c) saw the new fault line and stopped itself, by design.
  It stopped cooperatively: both ranks reported "cooperative rank stop" and the unit exited with status 1.
  See `incident.json`, `monitor.json` and `sc117-lan-journal.txt`.

## Likely cause

A lab microbenchmark (`bench_quant`, dense-decode agent) requested 209 KB of local memory for one bench-only kernel
variant and aborted twice with `UR_RESULT_ERROR_OUT_OF_RESOURCES`, exiting with work still in flight. The fault lines
appeared on the second abort.

That second the bench held the card-27 lock. The prefill agent's engine wrote its first output 0.8 s later. The
journal has one-second resolution, so this is very likely rather than certain. No engine change under test was
involved.

## Response (owner rule of 2026-10-03)

1. All lab device work stopped.
2. Evidence saved: kernel and service journals, `incident.json`, `monitor.json`.
3. After a 5-minute gap since the stop (08:55:43 UTC 12:55:43), one bounded health probe ran:
   `experiments/ltx25-b70/scripts/check-four-card-health.py`. It passed on all four cards with no fault lines
   during the probe. See `health-probe-receipt.json`.
4. The service was started once on the same engine 1d72818cfe8c.

## Lesson

A standalone microbenchmark that aborts with work in flight can page-fault the card's copy engine. Check
work-group and local-memory limits before launch, wait for the queue before any exit path, and keep failing variants
out of device runs.

## Service status: down, waiting on the owner

The service refuses to start while the boot's kernel fault list differs from the reviewed baseline,
`gsq-rco-iq3s/operating/host-before-stop.json`. The current list is the baseline's 14 lines, unchanged as a prefix,
plus exactly the two card-27 lines above (`observe-after-probe.json`). Re-recording the baseline was blocked as a
safety-guard change, so it is the owner's call, as on 2026-10-25.

To restore the service:
1. Check that `observe.py` still shows only these two new lines.
2. Re-record the baseline:
   `cp research/incidents/2026-10-26-card27-bcs-fault/observe-after-probe.json gsq-rco-iq3s/operating/host-before-stop.json`
   (or a fresh `observe.py` snapshot), from `experiments/own-xpu-runtime`.
3. Start the service once on the last served engine: `bash engine/tools/service-cycle.sh 1d72818cfe8c restore`.

All lab GPU work is halted until then. `engine/src` is unchanged, so the 1d72818cfe8c receipt still matches.
