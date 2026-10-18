# Packet128 — fresh bundle7 attribution prepared on CPU

The coordinator has one proposed lane-B load for a fresh budget of the bundle7
engine. It runs all twelve registered prompts once, 64 tokens each, and checks
every emitted token against `iq3-p49-split32-v1`. No device job, service, live
queue, host setting, reset or privileged operation ran in this preparation.

The [new packet](../experiments/own-xpu-runtime/stage2/packet128-attribution/README.md)
copies frozen packet124b. All arithmetic objects, selection, 24/24 placement,
80,128-row draft prefix, head split and BF16 KV are unchanged. The engine entry
adds packet77-style event observation for every layer on both ranks, all generated
tokens, the draft, head partitions, transfers and snapshot/restore work. Event
records are buffered until reset. Native receipts retain draft waits; additional
host records separate the hidden-input and suffix-result waits.

The analysis checks overhead first against the supplied 58.0–58.3 tok/s bundle7
range. Below 90% of 58.3 it withholds lever rankings. The different response length
is disclosed; this is a distortion screen, not a matched overhead measurement.
It reports per-class milliseconds separately by rank and hit/miss, queue gaps,
and named waits. Critical-path limits and the 20% class-reduction / >=0.5% gain
scenario are labeled as optimistic projections, not measured savings. Transfers,
rollback and gaps remain visible even when recoverability is unknown.

CPU verification passed:

- GNU host and Intel device-target compilation; only the engine entry rebuilt,
  all inherited numerical objects hash-checked. No device binary executed.
- Parent, control and two fresh instrumented miniature runs: 24 tokens, 96 layer
  fixtures, draft proposals and final state match. A one-load control / instrumented
  / control test also matches across resets. Miniature choices are defaults;
  production-only layouts are covered separately by full-size startup checks.
- Both ranks' real production-shape selection consumers and memory admission.
- The real Python worker produces both native launch arguments under hard exec
  interception. Those arguments then pass the real native parser with the CPU
  payload/backend fixture; nice19 and temporary paths are explicitly substituted
  only in that CPU fixture. The saved original launch arguments retain nice0.
- Six analysis tests, four worker/wrapper tests and four inherited drain tests.
  The old cooldown race fails as the negative control; the new local clamp passes.
- [Final check](../experiments/own-xpu-runtime/stage2/packet128-attribution/evidence/final-check.json):
  parent bytes unchanged, source/selection seals pass, one temporary lane-B queue
  plan passes. Generated build files total 127,628,611 bytes, below 250 MB; root
  remained above 25 GB. CPU children used less than 1 GiB reported peak RSS.

The pinned v4 screen normally insists on writing into its own frozen tree.
`screen128.py` changes only that output-location check, putting all new receipts
inside packet128. A CPU test enforces the exact one-line source difference.
The worker preserves its fault supervision, lane ownership, mask and graceful
drain; a local subclass applies packet124b's nonnegative cooldown sleep fix.
The shared screen, every existing packet and ops file, and live queues are untouched.

Prepared job:
[proposed-p128-attr-B.txt](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p128-attr-B.txt).
It is one load, with a 3,600-second watchdog against the 10–15 minute estimate,
and no automatic retry. The first suite request supplies the incident64 check.
The coordinator runs it, then the README's CPU analysis command writes
[BUDGET.md](../experiments/own-xpu-runtime/stage2/packet128-attribution/BUDGET.md).
That file is explicitly pending until real receipts exist. No speed claim or
quality promotion was made.

[CPU closeout](../experiments/own-xpu-runtime/stage2/packet128-attribution/CPU-PREPARATION-CLOSEOUT.md)
records preparation refusals and review findings;
[retention](../experiments/own-xpu-runtime/stage2/packet128-attribution/RETENTION.md)
explains ignored builds, reproducible hashes and the required 4 MiB rope table.
